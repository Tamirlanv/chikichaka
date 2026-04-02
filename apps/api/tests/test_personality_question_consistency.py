"""Guard against drift between scoring, seed IDs, and the expected 40-question contract."""

from invision_api.services.personality_profile_service import _question_ids, _scoring_config


def _expected_ids() -> list[str]:
    return [f"00000000-0000-4000-8000-{i:012d}" for i in range(1, 41)]


def test_question_ids_match_scoring_keys():
    ids = _question_ids()
    scoring = _scoring_config()
    assert len(ids) == 40
    assert set(ids) == set(scoring.keys())
    assert ids == _expected_ids()


def test_scoring_has_forty_entries():
    assert len(_scoring_config()) == 40
