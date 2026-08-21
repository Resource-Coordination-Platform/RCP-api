import uuid
from app.models.projection import CategoryProjection, InventoryProjection, RequestProjection, RequestStatus, InventoryStatus

def test_need_vs_fulfillment(client, db_session):
    from tests.conftest import FIXED_TENANT_ID
    
    cat_id = uuid.uuid4()
    
    cat = CategoryProjection(
        category_id=cat_id,
        tenant_id=FIXED_TENANT_ID,
        name="Water",
        unit="liters"
    )
    db_session.add(cat)
    
    req = RequestProjection(
        request_id=uuid.uuid4(),
        tenant_id=FIXED_TENANT_ID,
        category_id=cat_id,
        quantity_needed=100,
        status=RequestStatus.PENDING.value
    )
    db_session.add(req)
    
    inv = InventoryProjection(
        item_id=uuid.uuid4(),
        tenant_id=FIXED_TENANT_ID,
        category_id=cat_id,
        name="Bottled Water",
        quantity_total=50,
        quantity_available=50,
        status=InventoryStatus.AVAILABLE.value
    )
    db_session.add(inv)
    
    db_session.commit()
    
    response = client.get("/api/reports/need-vs-fulfillment")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    
    # Find the "Water" category
    water = next(x for x in data if x["category_id"] == str(cat_id))
    assert water["category"] == "Water"
    assert water["quantity_needed"] == 100
    assert water["stock_available"] == 50

def test_request_summary(client, db_session):
    from tests.conftest import FIXED_TENANT_ID
    
    # Add requests of different statuses
    db_session.add(RequestProjection(
        request_id=uuid.uuid4(),
        tenant_id=FIXED_TENANT_ID,
        category_id=uuid.uuid4(),
        status=RequestStatus.PENDING.value
    ))
    db_session.add(RequestProjection(
        request_id=uuid.uuid4(),
        tenant_id=FIXED_TENANT_ID,
        category_id=uuid.uuid4(),
        status=RequestStatus.PENDING.value
    ))
    db_session.add(RequestProjection(
        request_id=uuid.uuid4(),
        tenant_id=FIXED_TENANT_ID,
        category_id=uuid.uuid4(),
        status=RequestStatus.FULFILLED.value
    ))
    db_session.commit()
    
    response = client.get("/api/reports/request-summary")
    assert response.status_code == 200
    data = response.json()
    
    # Since tests run in random order, there might be other data in the DB
    # We just ensure the endpoint returns correct structure and expected sums
    assert "pending" in data
    assert "fulfilled" in data
    assert data["pending"] >= 2
    assert data["fulfilled"] >= 1
