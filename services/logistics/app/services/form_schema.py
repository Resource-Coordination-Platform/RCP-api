"""The form half of the customizable workflow engine.

A tenant admin defines a category's extra fields as JSON
(`ResourceCategory.form_schema`); this module is the single place that
(a) checks a submitted *definition* is well-formed and (b) validates a
request's `extra_fields` *payload* against it. Without (b) the JSONB column
accepts anything at all, which is exactly what a high-stakes deployment
cannot afford.

Definition shape — a list of field specs::

    [
      {"key": "household_size", "label": "Household size",
       "type": "integer", "required": true, "min": 1, "max": 50},
      {"key": "shelter_type", "type": "select",
       "options": ["tent", "community hall"]}
    ]
"""

import enum
import re
from datetime import date, datetime
from typing import Any

MAX_FIELDS = 50
MAX_OPTIONS = 100
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,49}$")

_SPEC_KEYS = {
    "key",
    "label",
    "type",
    "required",
    "options",
    "min",
    "max",
    "max_length",
    "help_text",
}


class FieldType(str, enum.Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    SELECT = "select"
    MULTISELECT = "multiselect"
    PHONE = "phone"


_TEXTUAL = {FieldType.TEXT, FieldType.TEXTAREA, FieldType.PHONE}
_NUMERIC = {FieldType.INTEGER, FieldType.NUMBER}
_CHOICE = {FieldType.SELECT, FieldType.MULTISELECT}

_DEFAULT_MAX_LENGTH = {
    FieldType.TEXT: 500,
    FieldType.TEXTAREA: 5000,
    FieldType.PHONE: 30,
}


class FormSchemaError(ValueError):
    """The category's field definition itself is malformed."""


class FormValidationError(ValueError):
    """A submitted payload does not satisfy the category's definition."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        self.errors = errors
        summary = "; ".join(f"{e['field']}: {e['message']}" for e in errors)
        super().__init__(f"extra_fields does not match the category form: {summary}")


# --------------------------------------------------------------------------
# definition
# --------------------------------------------------------------------------


def validate_definition(form_schema: Any) -> list[dict[str, Any]] | None:
    """Normalise and validate a category's field definition.

    Returns the normalised definition (label defaulted, `required` explicit)
    so what we persist is always the canonical form.
    """
    if form_schema is None:
        return None
    if not isinstance(form_schema, list):
        raise FormSchemaError("form_schema must be a list of field definitions")
    if len(form_schema) > MAX_FIELDS:
        raise FormSchemaError(f"form_schema may define at most {MAX_FIELDS} fields")

    normalised: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(form_schema):
        spec = _validate_field_spec(raw, index)
        if spec["key"] in seen:
            raise FormSchemaError(f"duplicate field key '{spec['key']}'")
        seen.add(spec["key"])
        normalised.append(spec)
    return normalised


def _validate_field_spec(raw: Any, index: int) -> dict[str, Any]:
    where = f"field #{index}"
    if not isinstance(raw, dict):
        raise FormSchemaError(f"{where}: each field definition must be an object")

    unknown = set(raw) - _SPEC_KEYS
    if unknown:
        raise FormSchemaError(f"{where}: unsupported keys {sorted(unknown)}")

    key = raw.get("key")
    if not isinstance(key, str) or not KEY_PATTERN.match(key):
        raise FormSchemaError(
            f"{where}: 'key' must be lower snake_case starting with a letter"
        )
    where = f"field '{key}'"

    try:
        field_type = FieldType(raw.get("type"))
    except ValueError:
        raise FormSchemaError(
            f"{where}: 'type' must be one of {sorted(t.value for t in FieldType)}"
        ) from None

    label = raw.get("label", key)
    if not isinstance(label, str) or not label.strip():
        raise FormSchemaError(f"{where}: 'label' must be a non-empty string")

    required = raw.get("required", False)
    if not isinstance(required, bool):
        raise FormSchemaError(f"{where}: 'required' must be a boolean")

    help_text = raw.get("help_text")
    if help_text is not None and not isinstance(help_text, str):
        raise FormSchemaError(f"{where}: 'help_text' must be a string")

    spec: dict[str, Any] = {
        "key": key,
        "label": label,
        "type": field_type.value,
        "required": required,
    }
    if help_text is not None:
        spec["help_text"] = help_text

    if field_type in _CHOICE:
        options = raw.get("options")
        if not isinstance(options, list) or not options:
            raise FormSchemaError(f"{where}: '{field_type.value}' requires a non-empty 'options' list")
        if len(options) > MAX_OPTIONS:
            raise FormSchemaError(f"{where}: at most {MAX_OPTIONS} options")
        if not all(isinstance(option, str) and option.strip() for option in options):
            raise FormSchemaError(f"{where}: 'options' must be non-empty strings")
        if len(set(options)) != len(options):
            raise FormSchemaError(f"{where}: 'options' contains duplicates")
        spec["options"] = options
    elif "options" in raw:
        raise FormSchemaError(f"{where}: 'options' only applies to select/multiselect")

    if field_type in _NUMERIC:
        minimum = _optional_number(raw, "min", where)
        maximum = _optional_number(raw, "max", where)
        if minimum is not None and maximum is not None and minimum > maximum:
            raise FormSchemaError(f"{where}: 'min' is greater than 'max'")
        if minimum is not None:
            spec["min"] = minimum
        if maximum is not None:
            spec["max"] = maximum
    elif "min" in raw or "max" in raw:
        raise FormSchemaError(f"{where}: 'min'/'max' only apply to numeric fields")

    if field_type in _TEXTUAL:
        max_length = raw.get("max_length", _DEFAULT_MAX_LENGTH[field_type])
        if not isinstance(max_length, int) or isinstance(max_length, bool) or max_length <= 0:
            raise FormSchemaError(f"{where}: 'max_length' must be a positive integer")
        if max_length > _DEFAULT_MAX_LENGTH[field_type]:
            raise FormSchemaError(
                f"{where}: 'max_length' may not exceed {_DEFAULT_MAX_LENGTH[field_type]}"
            )
        spec["max_length"] = max_length
    elif "max_length" in raw:
        raise FormSchemaError(f"{where}: 'max_length' only applies to text fields")

    return spec


def _optional_number(raw: dict[str, Any], name: str, where: str) -> float | int | None:
    if name not in raw:
        return None
    value = raw[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FormSchemaError(f"{where}: '{name}' must be a number")
    return value


# --------------------------------------------------------------------------
# payload
# --------------------------------------------------------------------------


def validate_payload(
    form_schema: Any, extra_fields: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Validate a submitted payload against a category's definition.

    Unknown keys are rejected: a category with no `form_schema` accepts no
    `extra_fields` at all. Returns the coerced payload (or None when empty)
    so what lands in JSONB is already typed.
    """
    payload = extra_fields or {}
    if not isinstance(payload, dict):
        raise FormValidationError([{"field": "extra_fields", "message": "must be an object"}])

    specs = form_schema or []
    by_key = {spec["key"]: spec for spec in specs}

    errors: list[dict[str, str]] = []
    for key in payload:
        if key not in by_key:
            errors.append({"field": key, "message": "not defined on this category"})

    coerced: dict[str, Any] = {}
    for spec in specs:
        key = spec["key"]
        value = payload.get(key)
        if _is_blank(value):
            if spec.get("required"):
                errors.append({"field": key, "message": f"'{spec['label']}' is required"})
            continue
        try:
            coerced[key] = _coerce(spec, value)
        except ValueError as exc:
            errors.append({"field": key, "message": str(exc)})

    if errors:
        raise FormValidationError(errors)
    return coerced or None


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip()) or value == []


def _coerce(spec: dict[str, Any], value: Any) -> Any:
    field_type = FieldType(spec["type"])

    if field_type in _TEXTUAL:
        if not isinstance(value, str):
            raise ValueError("must be text")
        text = value.strip()
        max_length = spec.get("max_length", _DEFAULT_MAX_LENGTH[field_type])
        if len(text) > max_length:
            raise ValueError(f"must be at most {max_length} characters")
        return text

    if field_type is FieldType.INTEGER:
        number = _to_number(value)
        if int(number) != number:
            raise ValueError("must be a whole number")
        return _check_range(spec, int(number))

    if field_type is FieldType.NUMBER:
        return _check_range(spec, _to_number(value))

    if field_type is FieldType.BOOLEAN:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise ValueError("must be true or false")

    if field_type is FieldType.DATE:
        if not isinstance(value, str):
            raise ValueError("must be an ISO date (YYYY-MM-DD)")
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
            except ValueError:
                raise ValueError("must be an ISO date (YYYY-MM-DD)") from None
        return parsed.isoformat()

    if field_type is FieldType.SELECT:
        if value not in spec["options"]:
            raise ValueError(f"must be one of {spec['options']}")
        return value

    # multiselect
    if not isinstance(value, list):
        raise ValueError("must be a list of options")
    invalid = [item for item in value if item not in spec["options"]]
    if invalid:
        raise ValueError(f"contains options not offered: {invalid}")
    if len(set(value)) != len(value):
        raise ValueError("contains duplicate options")
    return value


def _to_number(value: Any) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("must be a number")
    return value


def _check_range(spec: dict[str, Any], number: float | int) -> float | int:
    if "min" in spec and number < spec["min"]:
        raise ValueError(f"must be at least {spec['min']}")
    if "max" in spec and number > spec["max"]:
        raise ValueError(f"must be at most {spec['max']}")
    return number
