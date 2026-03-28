"""Unified helpers for section payloads (non-scoring demographics stay out of aggregates elsewhere)."""

from typing import Any

from pydantic import BaseModel

from invision_api.models.enums import SectionKey
from invision_api.services import section_payloads


def parse_section(section_key: SectionKey, payload: dict[str, Any]) -> BaseModel:
    return section_payloads.parse_and_validate_section(section_key, payload)


def is_demographics_block(section_key: SectionKey) -> bool:
    return section_key == SectionKey.personal
