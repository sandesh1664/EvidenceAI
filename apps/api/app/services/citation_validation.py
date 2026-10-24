"""Fail closed: claim text must be a relevant, exact quotation of admitted context."""

from app.schemas.ask import AnswerClaim, Citation, GroundedOutput
from app.services.rag_context import UNSAFE, relevant, terms


class CitationError(Exception):
    pass


def validate_answer(output, context, question, settings, *, relevance_verified=False):
    try:
        generated = GroundedOutput.model_validate(output)
    except ValueError:
        raise CitationError("Malformed answer") from None
    if len(generated.claims) > settings.rag_max_claims:
        raise CitationError("Too many claims")
    if generated.outcome == "insufficient_evidence":
        return [], []
    mapping = {item.citation_id: item for item in context}
    claims, citations, by_id = [], [], {}
    for index, claim in enumerate(generated.claims, 1):
        text = claim.text.strip()
        # A Gemini relevance review replaces literal question-word containment,
        # never the exact source/quote checks below. Other providers remain strict.
        semantic_review = settings.llm_provider == "gemini" and relevance_verified is True
        numeric_qualifiers = {w for w in terms(question) if w.isdigit()}
        if (UNSAFE.search(text) or len(text) < 8 or not numeric_qualifiers <= terms(text)
                or not semantic_review and not relevant(text, question)):
            raise CitationError("Unsupported claim")
        claim_id = f"A{index}"
        references = []
        for support in claim.supports:
            source = mapping.get(support.citation_id)
            quote = support.quote.strip()
            if source is None or quote != text or quote not in source.text:
                raise CitationError("Invalid or unsupported citation")
            if support.citation_id not in references:
                references.append(support.citation_id)
            if support.citation_id not in by_id:
                start = source.char_start + source.text.index(quote)
                citation = Citation(
                    citation_id=support.citation_id,
                    document_id=source.document_id,
                    chunk_id=source.chunk_id,
                    filename=source.filename,
                    page_number=source.page_number,
                    section=source.section,
                    source_ref=source.source_ref,
                    supporting_excerpt=quote,
                    char_start=start,
                    char_end=start + len(quote),
                    claim_ids=[claim_id],
                )
                by_id[support.citation_id] = citation
                citations.append(citation)
            else:
                citation = by_id[support.citation_id]
                if citation.supporting_excerpt != quote:
                    # One citation identifies one admitted chunk; support multiple claims
                    # by returning the whole bounded context and its source span.
                    citation.supporting_excerpt = source.text
                    citation.char_start = source.char_start
                    citation.char_end = source.char_start + len(source.text)
                if claim_id not in citation.claim_ids:
                    citation.claim_ids.append(claim_id)
        claims.append(
            AnswerClaim(claim_id=claim_id, text=text, citation_ids=references)
        )
    return claims, citations
