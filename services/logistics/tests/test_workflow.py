"""The customizable approval flow: definitions and transition checks."""

import pytest

from app.models import RequestStatus
from app.services.workflow import (
    DEFAULT_TRANSITIONS,
    WorkflowError,
    allowed_next,
    initial_status,
    validate_definition,
)

# a food bank that skips field verification
FAST_TRACK = {
    "initial": "pending",
    "transitions": {
        "pending": ["approved", "rejected"],
        "approved": ["fulfilled", "cancelled"],
    },
}


def test_none_falls_back_to_the_platform_default():
    assert validate_definition(None) is None
    assert initial_status(None) is RequestStatus.PENDING
    assert allowed_next(None, RequestStatus.PENDING) == DEFAULT_TRANSITIONS[RequestStatus.PENDING]
    assert allowed_next(None, RequestStatus.FULFILLED) == set()


def test_definition_is_normalised():
    assert validate_definition(FAST_TRACK) == FAST_TRACK


def test_initial_defaults_to_pending():
    definition = validate_definition({"transitions": {"pending": ["fulfilled"]}})
    assert definition["initial"] == "pending"


def test_custom_flow_drives_transitions():
    definition = validate_definition(FAST_TRACK)
    assert initial_status(definition) is RequestStatus.PENDING
    assert allowed_next(definition, RequestStatus.PENDING) == {
        RequestStatus.APPROVED,
        RequestStatus.REJECTED,
    }
    # verified is not part of this tenant's process at all
    assert allowed_next(definition, RequestStatus.VERIFIED) == set()
    assert allowed_next(definition, RequestStatus.FULFILLED) == set()


def test_a_custom_flow_may_start_somewhere_other_than_pending():
    definition = validate_definition(
        {"initial": "verified", "transitions": {"verified": ["fulfilled", "rejected"]}}
    )
    assert initial_status(definition) is RequestStatus.VERIFIED


@pytest.mark.parametrize(
    "bad",
    [
        [],                                                              # not an object
        {"transitions": {}},                                             # empty
        {"transitions": {"pending": []}},                                # no next state
        {"transitions": {"pendign": ["fulfilled"]}},                     # unknown source
        {"transitions": {"pending": ["done"]}},                          # unknown target
        {"transitions": {"pending": ["pending"]}},                       # self-transition
        {"transitions": {"pending": ["approved", "approved"]}},          # duplicate target
        {"transitions": {"fulfilled": ["pending"]}},                     # terminal source
        {"transitions": {"pending": ["approved"]}, "inital": "pending"}, # typo'd key
        {"initial": "approved", "transitions": {"pending": ["fulfilled"]}},  # initial not a source
        {"initial": "pending",                                           # dead branch
         "transitions": {"pending": ["fulfilled"], "verified": ["approved"]}},
        {"initial": "pending",                                           # never terminates
         "transitions": {"pending": ["verified"], "verified": ["in_progress"],
                         "in_progress": ["approved"], "approved": ["verified"]}},
    ],
)
def test_malformed_workflows_are_rejected(bad):
    with pytest.raises(WorkflowError):
        validate_definition(bad)
