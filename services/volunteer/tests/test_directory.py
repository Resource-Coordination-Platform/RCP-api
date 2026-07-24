"""Directory filter construction — the portal's view of the pool must stay
identical to what the matching engine would select."""

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models import VolunteerProfile
from app.services.directory import build_filters, normalise_skill


def compiled(**kwargs) -> str:
    """The WHERE clause only — the projected column list would otherwise
    make every `not in` assertion below trivially false."""
    stmt = select(VolunteerProfile).where(*build_filters(**kwargs))
    return str(stmt.compile(dialect=postgresql.dialect())).split("WHERE", 1)[1]


def test_inactive_volunteers_are_always_excluded():
    assert "is_active IS true" in compiled()
    assert "is_active IS true" in compiled(district="Colombo", skill="first_aid")


def test_no_filters_does_not_constrain_availability():
    # the directory lists the whole pool; availability is an opt-in filter
    assert "available_status" not in compiled()
    assert "available_status IS true" in compiled(available_only=True)


def test_skill_uses_jsonb_containment_not_equality():
    sql = compiled(skill="first_aid")
    assert "skills @>" in sql  # rides the GIN index, like _find_candidates


def test_skill_input_is_slugified():
    assert normalise_skill("  First Aid ") == "first_aid"
    assert normalise_skill("BOAT DRIVER") == "boat_driver"


def test_district_is_exact_and_city_is_a_fragment():
    sql = compiled(district="Colombo", city="Deh")
    assert "base_district = " in sql
    assert "city ILIKE" in sql


def test_free_text_searches_name_or_phone():
    sql = compiled(q="nim")
    assert "full_name ILIKE" in sql
    assert "phone ILIKE" in sql
    assert " OR " in sql
