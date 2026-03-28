"""Stage transition names and policy surface."""

from invision_api.services.stage_transition_policy import TransitionName


def test_transition_names_stable() -> None:
    assert TransitionName.screening_passed.value == "screening_passed"
    assert TransitionName.revision_required.value == "revision_required"
    assert TransitionName.human_advances_to_decision.value == "human_advances_to_decision"

