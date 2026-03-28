"""Blocks and document types excluded from automated scoring / explainability aggregates."""

from invision_api.models.enums import DocumentType, SectionKey

# Demographics and social-status certificate must not influence scoring dimensions.
BLOCK_KEYS_EXCLUDED_FROM_SCORING: frozenset[str] = frozenset(
    {
        SectionKey.social_status_cert.value,
        SectionKey.personal.value,  # contains gender, nationality, etc.
    }
)

DOCUMENT_TYPES_EXCLUDED_FROM_SCORING: frozenset[str] = frozenset(
    {
        DocumentType.certificate_of_social_status.value,
    }
)


def should_exclude_block_for_scoring(block_key: str) -> bool:
    return block_key in BLOCK_KEYS_EXCLUDED_FROM_SCORING


def should_exclude_document_for_scoring(document_type: str) -> bool:
    return document_type in DOCUMENT_TYPES_EXCLUDED_FROM_SCORING


def filter_context_for_scoring(context: dict) -> dict:
    """Remove excluded keys from an arbitrary context dict (shallow)."""
    out = dict(context)
    for k in ("gender", "nationality", "certificate_of_social_status", "social_status"):
        out.pop(k, None)
    return out
