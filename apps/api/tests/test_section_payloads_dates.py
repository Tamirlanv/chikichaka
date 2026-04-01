"""Date parsing for section payloads (DD.MM.YYYY matches frontend input-constraints)."""

from datetime import date

import pytest
from pydantic import ValidationError

from invision_api.services.section_payloads import (
    AchievementsActivitiesSectionPayload,
    EducationItemPayload,
    EducationSectionPayload,
    PersonalSectionPayload,
    parse_optional_date,
)


def test_parse_optional_date_dd_mm_yyyy() -> None:
    assert parse_optional_date("13.08.2007") == date(2007, 8, 13)
    assert parse_optional_date("01.01.2000") == date(2000, 1, 1)


def test_parse_optional_date_iso() -> None:
    assert parse_optional_date("2007-08-13") == date(2007, 8, 13)


def test_parse_optional_date_empty() -> None:
    assert parse_optional_date(None) is None
    assert parse_optional_date("") is None
    assert parse_optional_date("  ") is None


def test_personal_payload_dd_mm_yyyy() -> None:
    p = PersonalSectionPayload.model_validate(
        {
            "preferred_first_name": "A",
            "preferred_last_name": "B",
            "date_of_birth": "13.08.2007",
        }
    )
    assert p.date_of_birth == date(2007, 8, 13)


def test_education_nested_dates() -> None:
    payload = EducationSectionPayload.model_validate(
        {
            "entries": [
                {
                    "institution_name": "School",
                    "start_date": "01.09.2020",
                    "end_date": "31.05.2024",
                }
            ],
        }
    )
    assert payload.entries[0].start_date == date(2020, 9, 1)
    assert payload.entries[0].end_date == date(2024, 5, 31)


def test_achievements_flat_model() -> None:
    a = AchievementsActivitiesSectionPayload.model_validate(
        {
            "achievements_text": "x" * 250,
            "role": "Координатор",
            "year": "2024",
            "links": [{"link_type": "github", "label": "GitHub", "url": "https://github.com/test"}],
        }
    )
    assert len(a.achievements_text) == 250
    assert a.role == "Координатор"
    assert a.year == "2024"
    assert len(a.links) == 1


def test_invalid_date_rejected() -> None:
    with pytest.raises(ValidationError):
        PersonalSectionPayload.model_validate(
            {
                "preferred_first_name": "A",
                "preferred_last_name": "B",
                "date_of_birth": "not-a-date",
            }
        )
