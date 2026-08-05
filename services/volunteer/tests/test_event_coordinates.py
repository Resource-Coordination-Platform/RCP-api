import uuid
from unittest.mock import MagicMock
from app.schemas.event_schema import DisasterEventCreate, DisasterEventRead, RequirementCreate
from app.models import DisasterEvent, BroadcastType

def test_disaster_event_schema_with_coordinates():
    data = DisasterEventCreate(
        title="Kelani river flooding — evacuation support",
        description="Evacuation support needed",
        source_district="Colombo",
        latitude=6.9271,
        longitude=79.8612,
        requirements=[RequirementCreate(skill="boat_operator", required_count=5)],
    )

    assert data.title == "Kelani river flooding — evacuation support"
    assert data.source_district == "Colombo"
    assert data.latitude == 6.9271
    assert data.longitude == 79.8612

def test_disaster_event_model_with_coordinates():
    event = DisasterEvent(
        tenant_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        title="Kelani river flooding",
        source_district="Colombo",
        broadcast_type=BroadcastType.RADIUS_L1,
        latitude=6.9271,
        longitude=79.8612,
    )

    assert event.latitude == 6.9271
    assert event.longitude == 79.8612
