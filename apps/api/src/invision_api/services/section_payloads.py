"""Pydantic validation for application section JSON payloads."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from invision_api.models.enums import SectionKey


class PersonalSectionPayload(BaseModel):
    preferred_first_name: str = Field(min_length=1, max_length=128)
    preferred_last_name: str = Field(min_length=1, max_length=128)
    middle_name: str | None = Field(default=None, max_length=128)
    date_of_birth: date | None = None
    pronouns: str | None = Field(default=None, max_length=64)
    gender: str | None = Field(default=None, max_length=64)
    nationality: str | None = Field(default=None, max_length=128)
    city: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    short_self_introduction: str | None = Field(default=None, max_length=2000)
    identity_document_id: UUID | None = None


class ContactSectionPayload(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=32)
    alternate_phone_e164: str | None = Field(default=None, max_length=32)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    postal_code: str | None = Field(default=None, max_length=32)
    country: str = Field(min_length=2, max_length=2)
    street: str | None = Field(default=None, max_length=255)
    house: str | None = Field(default=None, max_length=64)
    apartment: str | None = Field(default=None, max_length=32)
    instagram: str | None = Field(default=None, max_length=128)
    telegram: str | None = Field(default=None, max_length=128)
    whatsapp: str | None = Field(default=None, max_length=32)
    preferred_communication_channel: str | None = Field(default=None, max_length=64)
    guardian_name: str | None = Field(default=None, max_length=255)
    guardian_phone_e164: str | None = Field(default=None, max_length=32)
    guardian_email: str | None = Field(default=None, max_length=255)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone_e164: str | None = Field(default=None, max_length=32)


class EducationItemPayload(BaseModel):
    institution_name: str = Field(min_length=1, max_length=255)
    degree_or_program: str | None = Field(default=None, max_length=255)
    field_of_study: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    gpa_or_equivalent: str | None = Field(default=None, max_length=32)
    honors_or_awards: str | None = Field(default=None, max_length=500)
    coursework_highlights: str | None = Field(default=None, max_length=2000)


class EducationSectionPayload(BaseModel):
    entries: list[EducationItemPayload] = Field(default_factory=list, max_length=20)
    presentation_video_url: str | None = Field(default=None, max_length=2048)
    english_proof_kind: str | None = Field(default=None, max_length=32)
    certificate_proof_kind: str | None = Field(default=None, max_length=32)
    english_document_id: UUID | None = None
    certificate_document_id: UUID | None = None
    additional_document_id: UUID | None = None


class AchievementActivityItem(BaseModel):
    category: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    role: str | None = Field(default=None, max_length=255)
    impact_summary: str | None = Field(default=None, max_length=2000)
    reference_contact: str | None = Field(default=None, max_length=500)


class AchievementsActivitiesSectionPayload(BaseModel):
    activities: list[AchievementActivityItem] = Field(min_length=1, max_length=50)


class LeadershipEvidenceItem(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    scope: str | None = Field(default=None, max_length=500)
    outcome: str | None = Field(default=None, max_length=2000)
    supporting_document_ids: list[UUID] = Field(default_factory=list, max_length=10)


class LeadershipEvidenceSectionPayload(BaseModel):
    items: list[LeadershipEvidenceItem] = Field(min_length=1, max_length=20)


class MotivationGoalsSectionPayload(BaseModel):
    narrative: str = Field(min_length=50, max_length=8000)
    motivation_document_id: UUID | None = None


class GrowthJourneySectionPayload(BaseModel):
    narrative: str = Field(min_length=50, max_length=8000)
    growth_document_id: UUID | None = None


class InternalTestSectionPayload(BaseModel):
    """Placeholder in section state; real answers live in internal_test_answers."""

    acknowledged_instructions: bool = True


class SocialStatusSectionPayload(BaseModel):
    """Certificate upload tracked via documents; this confirms attestation text."""

    attestation: str = Field(min_length=10, max_length=2000)


class DocumentsManifestSectionPayload(BaseModel):
    """Acknowledgment that required documents are uploaded or will be."""

    acknowledged_required_documents: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class ConsentAgreementSectionPayload(BaseModel):
    accepted_terms: bool = False
    accepted_privacy: bool = False
    consent_policy_version: str = Field(min_length=1, max_length=64)
    accepted_at: datetime | None = None

    @field_validator("accepted_at", mode="before")
    @classmethod
    def parse_accepted_at(cls, v: Any) -> datetime | None:
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


def parse_and_validate_section(section_key: SectionKey, payload: dict[str, Any]) -> BaseModel:
    match section_key:
        case SectionKey.personal:
            return PersonalSectionPayload.model_validate(payload)
        case SectionKey.contact:
            return ContactSectionPayload.model_validate(payload)
        case SectionKey.education:
            return EducationSectionPayload.model_validate(payload)
        case SectionKey.achievements_activities:
            return AchievementsActivitiesSectionPayload.model_validate(payload)
        case SectionKey.leadership_evidence:
            return LeadershipEvidenceSectionPayload.model_validate(payload)
        case SectionKey.motivation_goals:
            return MotivationGoalsSectionPayload.model_validate(payload)
        case SectionKey.growth_journey:
            return GrowthJourneySectionPayload.model_validate(payload)
        case SectionKey.internal_test:
            return InternalTestSectionPayload.model_validate(payload)
        case SectionKey.social_status_cert:
            return SocialStatusSectionPayload.model_validate(payload)
        case SectionKey.documents_manifest:
            return DocumentsManifestSectionPayload.model_validate(payload)
        case SectionKey.consent_agreement:
            return ConsentAgreementSectionPayload.model_validate(payload)
    raise ValueError("Unknown section")
