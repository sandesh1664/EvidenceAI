"""Bounded, non-authoritative history; never a replacement for fresh source retrieval."""

import re

from app.services.rag_context import UNSAFE, encode, terms

FOLLOW_UP = re.compile(
    r"\b(it|its|they|their|them|this|that|those|these)\b", re.IGNORECASE
)


def bounded_history(messages, settings):
    result = []
    for message in reversed(
        messages[-settings.conversation_history_messages :]
        if settings.conversation_history_messages
        else []
    ):
        # Assistant answers are deliberately excluded from prompts and retrieval. User
        # questions alone are sufficient to provide conservative reference context.
        if (
            message.role != "user"
            or message.generation_status != "completed"
            or UNSAFE.search(message.content)
        ):
            continue
        trial = [{"role": "user", "content": message.content}] + result
        if len(encode(trial).encode()) > settings.conversation_history_token_budget:
            break
        result = trial
    return result


def retrieval_question(question, history):
    if not FOLLOW_UP.search(question) or not history:
        return question
    # Keep the complete latest question. Older context is expendable. No generated
    # answer or saved citation is ever used as fresh evidence or a source filter.
    augmented = question
    for item in reversed(history):
        candidate = augmented + "\nPrevious question: " + item["content"]
        if len(candidate) > 2000 or len(candidate.encode()) > 6000:
            break
        augmented = candidate
    return augmented


def history_terms(question, history):
    if not FOLLOW_UP.search(question):
        return set()
    # Prefer the most recent explicit subject so a longer old question cannot
    # outweigh a newer topic. Skip intervening referential follow-ups.
    for item in reversed(history):
        if not FOLLOW_UP.search(item["content"]):
            return terms(item["content"])
    return set()


def evidence_question(question, history):
    """Pronouns provide references, not literal source qualifiers, when history exists."""
    return FOLLOW_UP.sub(" ", question) if history else question
