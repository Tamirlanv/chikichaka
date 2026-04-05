from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from invision_api.commission.application import service as commission_service


def test_board_metrics_program_bucket_normalization(monkeypatch):
    now = datetime.now(tz=UTC)
    in_range = [
        SimpleNamespace(submitted_at=now - timedelta(hours=1), program="Foundation"),
        SimpleNamespace(submitted_at=now - timedelta(hours=2), program="foundation year"),
        SimpleNamespace(submitted_at=now - timedelta(hours=3), program="Бакалавриат"),
        SimpleNamespace(submitted_at=now - timedelta(hours=4), program="bachelor"),
        SimpleNamespace(submitted_at=now - timedelta(hours=5), program="something else"),
    ]

    def _fake_list_projections(_db, **_kwargs):
        return in_range

    monkeypatch.setattr(
        "invision_api.commission.application.service.commission_repository.list_projections",
        _fake_list_projections,
    )

    metrics = commission_service.board_metrics(
        db=None,
        range_value="week",
        search=None,
        program=None,
    )
    assert metrics["foundationApplications"] == 2
    assert metrics["bachelorApplications"] == 2
