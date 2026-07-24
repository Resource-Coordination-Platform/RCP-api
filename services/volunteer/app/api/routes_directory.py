"""Volunteer directory — web portal, tenant-bound actors only.

The read-side counterpart of routes_profiles: coordinators browse and
filter the volunteer pool the matching engine draws from, so what the
dashboard shows and what a broadcast will reach are the same rows.

Volunteers are *global* actors (no tenant_id), so this endpoint is
deliberately not tenant-filtered. The guard is `require_tenant_roles`,
which rejects global principals: a volunteer on the mobile app cannot
enumerate other volunteers.
"""

from fastapi import APIRouter, Depends, Query
from rcp_common.auth import Principal
from sqlalchemy.orm import Session

from app.api.dependencies import require_tenant_roles
from app.db.database import get_db
from app.schemas.volunteer_schema import VolunteerDirectoryPage
from app.services import directory

router = APIRouter(prefix="/api/volunteer/directory", tags=["volunteer-directory"])

_portal = require_tenant_roles("tenant_admin", "coordinator")


@router.get("/skills", response_model=list[str])
def list_skills(
    principal: Principal = Depends(_portal),
    db: Session = Depends(get_db),
):
    """Distinct skill slugs actually present in the pool — the facet list
    the dashboard's skill filter offers instead of free text."""
    return directory.distinct_skills(db)


@router.get("", response_model=VolunteerDirectoryPage)
def search_volunteers(
    q: str | None = Query(None, description="Name or phone fragment"),
    skill: str | None = Query(None, description="Skill slug, e.g. first_aid"),
    district: str | None = Query(None, description="Exact base district"),
    city: str | None = Query(None, description="City fragment"),
    available_only: bool = Query(False, description="Only volunteers currently available"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(_portal),
    db: Session = Depends(get_db),
):
    items, total = directory.search(
        db,
        q=q,
        skill=skill,
        district=district,
        city=city,
        available_only=available_only,
        limit=limit,
        offset=offset,
    )
    return VolunteerDirectoryPage(items=items, total=total, limit=limit, offset=offset)
