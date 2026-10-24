"""Pure offline contracts for server-owned source spans and quote-ID selection."""
from dataclasses import FrozenInstanceError
import json

import pytest
from pydantic import ValidationError

from app.services.gemini_providers import (
    MAX_QUOTE_CANDIDATES,
    QUOTE_SPAN_MAX,
    QUOTE_SPAN_OVERLAP,
    exact_quote_candidates,
    selection_request,
    source_spans,
)
from app.services.llm_providers import LLMError
from app.services.rag_context import token_upper_bound


def budget_used(encoded, instructions, schema):
    return (token_upper_bound(encoded) + token_upper_bound(instructions)
            + token_upper_bound(json.dumps(schema.model_json_schema())) + 256)


def evidence_sources(count=6, units=160):
    return [
        {'citation_id': f'C{source + 1}', 'text': ' '.join(
            f'Source {source} passage {unit} describes solar panels and renewable electricity.'
            for unit in range(units)
        ) + f' Final source {source} tail marker must remain available.'}
        for source in range(count)
    ]


def test_pdf_spans_keep_exact_offsets_line_breaks_and_hyphenation():
    text = '  \n' + '\n\n'.join(
        f'Page {page} technical excerpt: panels con-\nvert sunlight into renewable electricity. '
        'The extracted line spacing and original wording remain unchanged.'
        for page in range(25)
    )
    spans = source_spans(text)
    candidates = exact_quote_candidates([{'citation_id': 'C1', 'text': text}])
    assert len(spans) > 1 and len(candidates) == len(spans)
    assert spans[0][0] == text.index('Page 0')
    assert spans[-1][1] == len(text)
    assert all(8 <= end - start <= QUOTE_SPAN_MAX for start, end in spans)
    assert all(candidate.text == text[candidate.start:candidate.end] for candidate in candidates)
    assert all(candidate.citation_id == 'C1' for candidate in candidates)
    assert any('con-\nvert sunlight' in candidate.text for candidate in candidates)
    assert all('convert sunlight' not in candidate.text for candidate in candidates)


def test_long_unbroken_units_overlap_without_losing_the_tail():
    tail = 'Unique final tail marker for bounded span coverage'
    text = ' '.join(f'word{index:04d}' for index in range(1300)) + ' ' + tail
    spans = source_spans(text)
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    assert len(spans) > 10
    assert all(8 <= end - start <= QUOTE_SPAN_MAX for start, end in spans)
    assert all(0 < previous_end - start <= QUOTE_SPAN_OVERLAP
               for (_, previous_end), (start, _) in zip(spans, spans[1:]))
    assert text[spans[-1][0]:spans[-1][1]].endswith(tail)
    covered = {index for start, end in spans for index in range(start, end)}
    assert all(index in covered for index, character in enumerate(text) if not character.isspace())


def test_long_word_is_split_into_bounded_exact_spans():
    text = 'x' * 1205
    spans = source_spans(text)
    assert spans[0] == (0, 600)
    assert spans[-1][1] == len(text)
    assert all(8 <= end - start <= QUOTE_SPAN_MAX for start, end in spans)
    assert all(text[start:end] == 'x' * (end - start) for start, end in spans)


def test_candidate_cap_preserves_every_source_and_late_source_tail():
    evidence = evidence_sources()
    assert sum(len(source_spans(item['text'])) for item in evidence) > MAX_QUOTE_CANDIDATES
    candidates = exact_quote_candidates(evidence)
    assert len(candidates) == MAX_QUOTE_CANDIDATES
    expected = {item['citation_id'] for item in evidence}
    assert {candidate.citation_id for candidate in candidates[:len(evidence)]} == expected
    assert {candidate.citation_id for candidate in candidates} == expected
    assert any(candidate.citation_id == 'C6'
               and 'Final source 5 tail marker' in candidate.text for candidate in candidates)
    original = {item['citation_id']: item['text'] for item in evidence}
    assert all(candidate.text == original[candidate.citation_id][candidate.start:candidate.end]
               for candidate in candidates)


def test_too_many_eligible_sources_cannot_be_silently_dropped():
    evidence = [{'citation_id': f'C{index}', 'text': f'Unique source {index} has enough text.'}
                for index in range(MAX_QUOTE_CANDIDATES + 1)]
    with pytest.raises(LLMError) as caught:
        exact_quote_candidates(evidence)
    assert caught.value.code == 'budget'


def test_budget_trims_candidates_but_preserves_every_source_and_request_context():
    evidence = evidence_sources()
    data = {'question': 'How is renewable electricity produced?', 'evidence': evidence,
            'research_mode': 'comparison', 'source_groups': {'C1': 'document-one', 'C6': 'document-six'},
            'conversation_history': [{'role': 'user', 'content': 'Compare the selected documents.'}]}
    instructions, budget = 'Select only server-owned quote IDs.', 12000
    payload, encoded, schema, mapping = selection_request(data, instructions, 4, budget)
    assert budget_used(encoded, instructions, schema) <= budget
    assert len(evidence) <= len(mapping) < len(exact_quote_candidates(evidence))
    assert {candidate.citation_id for candidate in mapping.values()} == {
        item['citation_id'] for item in evidence}
    assert 'evidence' not in payload
    assert payload['question'] == data['question']
    assert payload['source_groups'] == data['source_groups']
    assert payload['conversation_history'] == data['conversation_history']
    assert json.loads(encoded) == payload
    assert {item['quote_id'] for item in payload['quote_candidates']} == set(mapping)
    with pytest.raises(TypeError):
        mapping['Q1'] = mapping['Q1']
    with pytest.raises(FrozenInstanceError):
        mapping['Q1'].text = 'A changed quotation'


def test_impossible_budget_fails_instead_of_dropping_sources():
    with pytest.raises(LLMError) as caught:
        selection_request({'question': 'A question', 'evidence': evidence_sources(count=3, units=2)},
                          'Select source IDs.', 4, 1)
    assert caught.value.code == 'budget'


def test_dynamic_schema_admits_only_server_ids_and_at_most_four_selections():
    _, _, schema, mapping = selection_request(
        {'question': 'A question', 'evidence': evidence_sources(count=6, units=2)},
        'Select source IDs.', 4, 12000)
    field = schema.model_json_schema()['properties']['selection_ids']
    assert field['maxItems'] == 4
    assert set(field['items']['enum']) == set(mapping)
    selected = list(mapping)[:4]
    result = schema.model_validate({'outcome': 'answered', 'selection_ids': selected})
    grounded = result.grounded_output(mapping)
    assert [claim.text for claim in grounded.claims] == [mapping[key].text for key in selected]
    assert [claim.supports[0].citation_id for claim in grounded.claims] == [
        mapping[key].citation_id for key in selected]
    for value in (
        {'outcome': 'answered', 'selection_ids': list(mapping)[:5]},
        {'outcome': 'answered', 'selection_ids': ['Q1', 'Q1']},
        {'outcome': 'answered', 'selection_ids': ['Q999']},
        {'outcome': 'answered', 'selection_ids': []},
        {'outcome': 'insufficient_evidence', 'selection_ids': ['Q1']},
        {'outcome': 'answered', 'selection_ids': ['Q1'], 'quote': 'Unapproved text'},
    ):
        with pytest.raises(ValidationError):
            schema.model_validate(value)
    assert schema.model_validate({'outcome': 'insufficient_evidence', 'selection_ids': []}).selection_ids == []


@pytest.mark.parametrize('text', ['', 'short', '1234567', ' \n\t '])
def test_zero_candidates_return_locally_without_a_provider_schema(text):
    assert source_spans(text) == []
    assert selection_request({'question': 'A question', 'evidence': [
        {'citation_id': 'C1', 'text': text}]}, 'Select source IDs.', 4, 12000) is None


@pytest.mark.parametrize('maximum', [0, 7])
def test_invalid_selection_limit_is_rejected(maximum):
    with pytest.raises(LLMError) as caught:
        selection_request({'question': 'A question', 'evidence': evidence_sources(count=1, units=1)},
                          'Select source IDs.', maximum, 12000)
    assert caught.value.code == 'configuration'
