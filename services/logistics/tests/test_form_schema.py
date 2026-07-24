"""The customizable form engine: definitions and submitted payloads."""

import pytest

from app.services.form_schema import (
    FormSchemaError,
    FormValidationError,
    validate_definition,
    validate_payload,
)

SHELTER_FORM = [
    {"key": "household_size", "label": "Household size", "type": "integer",
     "required": True, "min": 1, "max": 50},
    {"key": "has_infants", "type": "boolean"},
    {"key": "shelter_type", "type": "select", "options": ["tent", "community hall"]},
    {"key": "needs", "type": "multiselect", "options": ["bedding", "water", "medicine"]},
    {"key": "notes", "type": "textarea", "max_length": 200},
]


# --- definitions ----------------------------------------------------------


def test_definition_is_normalised():
    definition = validate_definition([{"key": "household_size", "type": "integer"}])
    assert definition == [
        {"key": "household_size", "label": "household_size", "type": "integer", "required": False}
    ]


def test_none_definition_is_allowed():
    assert validate_definition(None) is None


@pytest.mark.parametrize(
    "bad",
    [
        {"key": "x", "type": "text"},                                  # not a list
        [{"type": "text"}],                                            # no key
        [{"key": "Household Size", "type": "text"}],                   # not snake_case
        [{"key": "a", "type": "colour_picker"}],                       # unknown type
        [{"key": "a", "type": "select"}],                              # select without options
        [{"key": "a", "type": "select", "options": []}],               # empty options
        [{"key": "a", "type": "select", "options": ["x", "x"]}],       # duplicate options
        [{"key": "a", "type": "text", "options": ["x"]}],              # options on a text field
        [{"key": "a", "type": "integer", "min": 10, "max": 1}],        # inverted range
        [{"key": "a", "type": "text", "min": 1}],                      # range on a text field
        [{"key": "a", "type": "boolean", "max_length": 5}],            # max_length on a boolean
        [{"key": "a", "type": "text", "max_length": 0}],               # non-positive max_length
        [{"key": "a", "type": "text", "requried": True}],              # typo'd key
        [{"key": "a", "type": "text"}, {"key": "a", "type": "text"}],  # duplicate keys
    ],
)
def test_malformed_definitions_are_rejected(bad):
    with pytest.raises(FormSchemaError):
        validate_definition(bad)


def test_field_limit():
    with pytest.raises(FormSchemaError):
        validate_definition([{"key": f"f{i}", "type": "text"} for i in range(51)])


# --- payloads -------------------------------------------------------------


def test_valid_payload_is_coerced():
    definition = validate_definition(SHELTER_FORM)
    result = validate_payload(
        definition,
        {
            "household_size": 4,
            "has_infants": "true",
            "shelter_type": "tent",
            "needs": ["water", "bedding"],
            "notes": "  needs help at night  ",
        },
    )
    assert result == {
        "household_size": 4,
        "has_infants": True,
        "shelter_type": "tent",
        "needs": ["water", "bedding"],
        "notes": "needs help at night",
    }


def test_unknown_keys_are_rejected():
    """The whole point: JSONB must not become a dumping ground."""
    definition = validate_definition(SHELTER_FORM)
    with pytest.raises(FormValidationError) as exc:
        validate_payload(definition, {"household_size": 1, "smuggled": "anything"})
    assert [e["field"] for e in exc.value.errors] == ["smuggled"]


def test_category_without_a_form_accepts_no_extra_fields():
    assert validate_payload(None, None) is None
    assert validate_payload(None, {}) is None
    with pytest.raises(FormValidationError):
        validate_payload(None, {"anything": 1})


def test_missing_required_field_is_reported():
    definition = validate_definition(SHELTER_FORM)
    with pytest.raises(FormValidationError) as exc:
        validate_payload(definition, {"shelter_type": "tent"})
    assert exc.value.errors == [
        {"field": "household_size", "message": "'Household size' is required"}
    ]


def test_optional_fields_may_be_omitted():
    definition = validate_definition(SHELTER_FORM)
    assert validate_payload(definition, {"household_size": 2}) == {"household_size": 2}


@pytest.mark.parametrize(
    "payload",
    [
        {"household_size": "four"},          # not a number
        {"household_size": 2.5},             # not a whole number
        {"household_size": 0},               # below min
        {"household_size": 99},              # above max
        {"household_size": True},            # bool is not an integer here
        {"household_size": 1, "shelter_type": "hotel"},          # not an offered option
        {"household_size": 1, "needs": ["water", "water"]},      # duplicate options
        {"household_size": 1, "needs": "water"},                 # not a list
        {"household_size": 1, "has_infants": "maybe"},           # not a boolean
        {"household_size": 1, "notes": "x" * 201},               # over max_length
    ],
)
def test_bad_values_are_rejected(payload):
    definition = validate_definition(SHELTER_FORM)
    with pytest.raises(FormValidationError):
        validate_payload(definition, payload)


def test_all_errors_are_reported_at_once():
    definition = validate_definition(SHELTER_FORM)
    with pytest.raises(FormValidationError) as exc:
        validate_payload(definition, {"shelter_type": "hotel", "stray": 1})
    assert {e["field"] for e in exc.value.errors} == {"household_size", "shelter_type", "stray"}


def test_dates_are_normalised_to_iso():
    definition = validate_definition([{"key": "displaced_on", "type": "date"}])
    assert validate_payload(definition, {"displaced_on": "2026-07-23T09:15:00Z"}) == {
        "displaced_on": "2026-07-23"
    }
    with pytest.raises(FormValidationError):
        validate_payload(definition, {"displaced_on": "23/07/2026"})
