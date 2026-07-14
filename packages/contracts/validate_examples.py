"""Contract validation: every example envelope must satisfy the envelope
schema, and its data payload must satisfy the event's payload schema.

Example files live in examples/<event.type>.vN.json; the payload schema is
resolved by convention:

    <producer>.<entity>.<action>  ->  events/<producer>/<entity>-<action>.vN.schema.json

Run locally with:  python packages/contracts/validate_examples.py
CI runs it on every contracts change (see .github/workflows/contracts-check.yml).
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parent
ENVELOPE_SCHEMA = ROOT / "events" / "envelope.schema.json"
EXAMPLES_DIR = ROOT / "examples"


def payload_schema_path(event_type: str, version: int) -> Path:
    producer, _, rest = event_type.partition(".")
    name = rest.replace(".", "-")
    return ROOT / "events" / producer / f"{name}.v{version}.schema.json"


def main() -> int:
    envelope_validator = Draft202012Validator(json.loads(ENVELOPE_SCHEMA.read_text()))
    failures = 0

    examples = sorted(EXAMPLES_DIR.glob("*.json"))
    if not examples:
        print("ERROR: no examples found in", EXAMPLES_DIR)
        return 1

    for example_file in examples:
        envelope = json.loads(example_file.read_text())
        errors = [e.message for e in envelope_validator.iter_errors(envelope)]

        event_type = envelope.get("event_type", "")
        expected_stem = f"{event_type}.v{envelope.get('schema_version', 1)}"
        if example_file.stem != expected_stem:
            errors.append(
                f"filename {example_file.name} does not match "
                f"event_type/schema_version ({expected_stem}.json expected)"
            )

        schema_file = payload_schema_path(event_type, envelope.get("schema_version", 1))
        if not schema_file.exists():
            errors.append(f"missing payload schema: {schema_file.relative_to(ROOT)}")
        else:
            payload_validator = Draft202012Validator(json.loads(schema_file.read_text()))
            errors.extend(
                f"data: {e.message}" for e in payload_validator.iter_errors(envelope.get("data", {}))
            )

        if errors:
            failures += 1
            print(f"FAIL {example_file.name}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"ok   {example_file.name}")

    if failures:
        print(f"\n{failures} of {len(examples)} examples failed validation")
        return 1
    print(f"\nall {len(examples)} examples valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
