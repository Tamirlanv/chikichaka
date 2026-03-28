"""Decision service rejects wrong stage."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from invision_api.models.enums import ApplicationStage, ApplicationState
from invision_api.services.stages import decision_service


def test_record_decision_wrong_stage() -> None:
    app = MagicMock()
    app.id = uuid4()
    app.current_stage = ApplicationStage.committee_review.value
    app.state = ApplicationState.committee_review.value

    db = MagicMock()
    with pytest.raises(ValueError, match="decision"):
        decision_service.record_final_decision(
            db,
            app,
            actor_user_id=uuid4(),
            final_decision_status="admitted",
            candidate_message=None,
            internal_note=None,
            next_steps=None,
        )
