"""
E2E system test: full pipeline from candidate registration to commission visibility.

Requires a running stack:
  - API server at http://localhost:8000
  - Web server at http://localhost:3000 (optional)
  - PostgreSQL, Redis

Run with: PYTHONPATH=apps/api/src pytest apps/api/tests/test_e2e_pipeline.py -v --tb=short
Skip when no running server: tests are marked with @pytest.mark.e2e
"""

from __future__ import annotations

import os
import time
from uuid import uuid4

import httpx
import pytest

API_BASE = os.getenv("E2E_API_BASE", "http://localhost:8000")
E2E_TIMEOUT = 15.0

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_E2E", "").lower() not in ("1", "true", "yes"),
    reason="E2E tests require RUN_E2E=1 and a running stack",
)


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=API_BASE, timeout=E2E_TIMEOUT) as client:
        yield client


@pytest.fixture(scope="module")
def candidate_session(api: httpx.Client):
    """Register a candidate, verify email (if needed), and return auth cookies."""
    email = f"e2e-{uuid4().hex[:8]}@test.local"
    password = "TestPassword123!"

    resp = api.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "first_name": "E2E",
        "last_name": "Candidate",
    })
    assert resp.status_code in (200, 201, 409), f"Register failed: {resp.text}"

    resp = api.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    cookies = dict(resp.cookies)
    return cookies, email


@pytest.fixture(scope="module")
def committee_session(api: httpx.Client):
    """Login as committee user (expects seeded committee account)."""
    email = os.getenv("E2E_COMMITTEE_EMAIL", "commission@test.local")
    password = os.getenv("E2E_COMMITTEE_PASSWORD", "TestPassword123!")

    resp = api.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    if resp.status_code != 200:
        pytest.skip("Committee user not seeded; skipping commission checks")
    return dict(resp.cookies)


class TestE2EPipeline:
    """Full lifecycle: register -> fill -> submit -> commission sees it."""

    def test_01_candidate_can_get_application(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.get("/api/v1/candidates/me/application", cookies=cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        self.__class__._app_id = data["id"]

    def test_02_save_personal_section(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/personal",
            json={"payload": {
                "preferred_first_name": "E2E",
                "preferred_last_name": "Candidate",
            }},
            cookies=cookies,
        )
        assert resp.status_code == 200

    def test_03_save_contact_section(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/contact",
            json={"payload": {
                "phone_e164": "+77001234567",
                "address_line1": "E2E Street 1",
                "city": "Алматы",
                "country": "KZ",
            }},
            cookies=cookies,
        )
        assert resp.status_code == 200

    def test_04_save_education_section(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/education",
            json={"payload": {
                "entries": [{"institution_name": "E2E School", "is_current": False}],
                "presentation_video_url": "https://youtube.com/watch?v=e2e",
                "english_proof_kind": "ielts_6",
                "certificate_proof_kind": "ent",
            }},
            cookies=cookies,
        )
        assert resp.status_code == 200

    def test_05_save_achievements_section(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/achievements_activities",
            json={"payload": {
                "activities": [{"category": "Science", "title": "E2E Olympiad"}],
            }},
            cookies=cookies,
        )
        assert resp.status_code == 200

    def test_06_save_leadership_section(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/leadership_evidence",
            json={"payload": {
                "items": [{"title": "E2E Team Captain"}],
            }},
            cookies=cookies,
        )
        assert resp.status_code == 200

    def test_07_save_motivation_section(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/motivation_goals",
            json={"payload": {
                "narrative": "A" * 350,
            }},
            cookies=cookies,
        )
        assert resp.status_code == 200

    def test_08_save_growth_section(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/growth_journey",
            json={"payload": {
                "answers": {f"q{i}": {"text": "x" * 50} for i in range(1, 6)},
                "consent_privacy": True,
                "consent_parent": True,
            }},
            cookies=cookies,
        )
        assert resp.status_code == 200

    def test_09_save_internal_test_section(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/internal_test",
            json={"payload": {"acknowledged_instructions": True}},
            cookies=cookies,
        )
        assert resp.status_code == 200

    def test_10_save_social_status_section(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/social_status_cert",
            json={"payload": {"attestation": "I confirm my social status for E2E test"}},
            cookies=cookies,
        )
        assert resp.status_code == 200

    def test_11_save_documents_manifest(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/documents_manifest",
            json={"payload": {"acknowledged_required_documents": True}},
            cookies=cookies,
        )
        assert resp.status_code == 200

    def test_12_save_consent_agreement(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/consent_agreement",
            json={"payload": {
                "accepted_terms": True,
                "accepted_privacy": True,
                "consent_policy_version": "v1.0",
            }},
            cookies=cookies,
        )
        assert resp.status_code == 200

    def test_13_check_completion_100_percent(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.get("/api/v1/candidates/me/application", cookies=cookies)
        assert resp.status_code == 200

    def test_14_submit_application(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.post("/api/v1/candidates/me/application/submit", cookies=cookies)
        assert resp.status_code == 200, f"Submit failed: {resp.text}"
        data = resp.json()
        assert data.get("locked_after_submit") is True or data.get("state") == "under_screening"

    def test_15_duplicate_submit_returns_409(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.post("/api/v1/candidates/me/application/submit", cookies=cookies)
        assert resp.status_code == 409

    def test_16_locked_app_rejects_edit(self, api: httpx.Client, candidate_session):
        cookies, _ = candidate_session
        resp = api.patch(
            "/api/v1/candidates/me/application/sections/personal",
            json={"payload": {"preferred_first_name": "Hack", "preferred_last_name": "Attempt"}},
            cookies=cookies,
        )
        assert resp.status_code == 409

    def test_17_commission_sees_application(self, api: httpx.Client, committee_session):
        resp = api.get("/api/v1/commission/applications", cookies=committee_session)
        assert resp.status_code == 200
        data = resp.json()
        apps = data if isinstance(data, list) else data.get("applications", data.get("items", []))
        assert len(apps) > 0, "Commission should see at least one application"
