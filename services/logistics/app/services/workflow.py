"""The state-machine half of the customizable workflow engine.

Approval steps differ per resource category: a food-bank hand-out may go
straight from `pending` to `approved`, while emergency shelter needs a
field verification first. Those steps used to be a module-level dict in
`services/requests.py`, so changing them meant a code deploy. They now live
on the category (`ResourceCategory.workflow`) and are validated here.

Definition shape::

    {"initial": "pending",
     "transitions": {"pending": ["approved", "rejected"],
                     "approved": ["fulfilled", "cancelled"]}}

States are drawn from `RequestStatus` — the column is a Postgres enum, so
admins compose *which* of the platform's states their process uses and how
they connect, rather than inventing new names. A category with no workflow
falls back to `DEFAULT_TRANSITIONS`, the platform default.
"""

from typing import Any

from app.models import RequestStatus

DEFAULT_INITIAL = RequestStatus.PENDING

DEFAULT_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.PENDING: {RequestStatus.VERIFIED, RequestStatus.REJECTED, RequestStatus.CANCELLED},
    RequestStatus.VERIFIED: {RequestStatus.APPROVED, RequestStatus.REJECTED, RequestStatus.CANCELLED},
    RequestStatus.APPROVED: {RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED},
    RequestStatus.IN_PROGRESS: {RequestStatus.FULFILLED, RequestStatus.CANCELLED},
}

# A workflow that can never finish is a trap in a crisis, so at least one of
# these has to stay reachable from the initial state.
TERMINAL_STATES = {
    RequestStatus.FULFILLED,
    RequestStatus.REJECTED,
    RequestStatus.CANCELLED,
}

_DEFINITION_KEYS = {"initial", "transitions"}


class WorkflowError(ValueError):
    """The category's workflow definition is malformed."""


def validate_definition(workflow: Any) -> dict[str, Any] | None:
    """Normalise and validate a category's workflow definition."""
    if workflow is None:
        return None
    if not isinstance(workflow, dict):
        raise WorkflowError("workflow must be an object")

    unknown = set(workflow) - _DEFINITION_KEYS
    if unknown:
        raise WorkflowError(f"workflow: unsupported keys {sorted(unknown)}")

    raw_transitions = workflow.get("transitions")
    if not isinstance(raw_transitions, dict) or not raw_transitions:
        raise WorkflowError("workflow.transitions must be a non-empty object")

    transitions: dict[RequestStatus, list[RequestStatus]] = {}
    for state, targets in raw_transitions.items():
        source = _state(state, "workflow.transitions")
        if source in TERMINAL_STATES:
            raise WorkflowError(f"workflow: '{source.value}' is terminal and cannot have transitions")
        if not isinstance(targets, list) or not targets:
            raise WorkflowError(f"workflow: '{source.value}' must list at least one next state")
        parsed = [_state(target, f"workflow.transitions.{source.value}") for target in targets]
        if len(set(parsed)) != len(parsed):
            raise WorkflowError(f"workflow: '{source.value}' lists a duplicate next state")
        if source in parsed:
            raise WorkflowError(f"workflow: '{source.value}' cannot transition to itself")
        transitions[source] = parsed

    initial = _state(workflow.get("initial", DEFAULT_INITIAL.value), "workflow.initial")
    if initial not in transitions:
        raise WorkflowError(
            f"workflow.initial '{initial.value}' must be one of the transition sources"
        )

    reachable = _reachable_from(initial, transitions)
    unreachable = sorted(state.value for state in transitions if state not in reachable)
    if unreachable:
        raise WorkflowError(f"workflow: unreachable states {unreachable}")
    if not (reachable & TERMINAL_STATES):
        raise WorkflowError(
            "workflow: no terminal state (fulfilled/rejected/cancelled) is reachable"
        )

    return {
        "initial": initial.value,
        "transitions": {
            source.value: [target.value for target in targets]
            for source, targets in transitions.items()
        },
    }


def initial_status(workflow: Any) -> RequestStatus:
    if not workflow:
        return DEFAULT_INITIAL
    return RequestStatus(workflow.get("initial", DEFAULT_INITIAL.value))


def allowed_next(workflow: Any, current: RequestStatus) -> set[RequestStatus]:
    if not workflow:
        return set(DEFAULT_TRANSITIONS.get(current, set()))
    targets = workflow.get("transitions", {}).get(current.value, [])
    return {RequestStatus(target) for target in targets}


def _state(value: Any, where: str) -> RequestStatus:
    try:
        return RequestStatus(value)
    except ValueError:
        raise WorkflowError(
            f"{where}: '{value}' is not a request status "
            f"({sorted(status.value for status in RequestStatus)})"
        ) from None


def _reachable_from(
    initial: RequestStatus, transitions: dict[RequestStatus, list[RequestStatus]]
) -> set[RequestStatus]:
    seen = {initial}
    queue = [initial]
    while queue:
        for target in transitions.get(queue.pop(), []):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen
