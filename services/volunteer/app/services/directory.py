"""Volunteer directory queries — the portal's read side of the pool.

Deliberately mirrors matching._find_candidates: the coordinator browsing
the dashboard and the matching engine fanning out a broadcast must filter
the same rows through the same indexes, or the UI would promise reach the
engine doesn't deliver.
"""

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.models import VolunteerProfile


def normalise_skill(skill: str) -> str:
    """Same slug rule VolunteerProfileUpdate applies on write, so a filter
    typed as "First Aid" still matches the stored "first_aid"."""
    return skill.strip().lower().replace(" ", "_")


def build_filters(
    *,
    q: str | None = None,
    skill: str | None = None,
    district: str | None = None,
    city: str | None = None,
    available_only: bool = False,
) -> list[ColumnElement[bool]]:
    # Deactivated volunteers (IAM-side) are never listed — dispatching one
    # would fail downstream anyway.
    filters: list[ColumnElement[bool]] = [VolunteerProfile.is_active.is_(True)]
    if available_only:
        filters.append(VolunteerProfile.available_status.is_(True))
    if district:
        filters.append(VolunteerProfile.base_district == district)
    if city:
        filters.append(VolunteerProfile.city.ilike(f"%{city}%"))
    if skill:
        # JSONB containment rides ix_volunteer_profiles_skills (GIN)
        filters.append(VolunteerProfile.skills.contains([normalise_skill(skill)]))
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            VolunteerProfile.full_name.ilike(pattern) | VolunteerProfile.phone.ilike(pattern)
        )
    return filters


def search(
    db: Session,
    *,
    q: str | None = None,
    skill: str | None = None,
    district: str | None = None,
    city: str | None = None,
    available_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[VolunteerProfile], int]:
    """Returns (page, total_matching)."""
    filters = build_filters(
        q=q, skill=skill, district=district, city=city, available_only=available_only
    )
    total = db.scalar(select(func.count()).select_from(VolunteerProfile).where(*filters)) or 0
    items = db.scalars(
        select(VolunteerProfile)
        .where(*filters)
        # available first, then newest — the dispatch-relevant ordering
        .order_by(
            VolunteerProfile.available_status.desc(),
            VolunteerProfile.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return list(items), total


def distinct_skills(db: Session) -> list[str]:
    """Every skill slug present in the pool, for the dashboard's filter."""
    skill = func.jsonb_array_elements_text(VolunteerProfile.skills).column_valued("skill")
    return sorted(db.scalars(select(skill).select_from(VolunteerProfile).distinct()).all())
