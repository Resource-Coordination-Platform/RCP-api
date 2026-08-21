import pytest
import uuid

def test_create_category(client):
    payload = {
        "name": "Food supplies",
        "description": "Canned and dry food",
        "unit": "kg"
    }
    response = client.post("/api/inventory/categories", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Food supplies"
    assert data["unit"] == "kg"
    assert "id" in data

def test_list_categories(client):
    # First create one
    client.post("/api/inventory/categories", json={
        "name": "Medical",
        "description": "First aid",
        "unit": "boxes"
    })
    
    response = client.get("/api/inventory/categories")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert any(c["name"] == "Medical" for c in data)

def test_add_inventory_item(client):
    # Create category first
    cat_res = client.post("/api/inventory/categories", json={
        "name": "Water",
        "description": "Drinking water",
        "unit": "liters"
    })
    cat_id = cat_res.json()["id"]
    
    # Add item
    payload = {
        "category_id": cat_id,
        "name": "Bottled Water",
        "quantity_total": 100,
        "storage_location": "Warehouse A"
    }
    response = client.post("/api/inventory/items", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["quantity_total"] == 100
    assert data["quantity_available"] == 100
    assert data["storage_location"] == "Warehouse A"

def test_reserve_inventory_item(client):
    # Create category and item
    cat_res = client.post("/api/inventory/categories", json={
        "name": "Blankets",
        "description": "Warm blankets",
        "unit": "pieces"
    })
    cat_id = cat_res.json()["id"]
    
    item_res = client.post("/api/inventory/items", json={
        "category_id": cat_id,
        "name": "Wool Blankets",
        "quantity_total": 50,
        "storage_location": "Warehouse B"
    })
    item_id = item_res.json()["id"]
    
    # Reserve 20
    response = client.post(f"/api/inventory/items/{item_id}/reserve?quantity=20")
    assert response.status_code == 200
    data = response.json()
    assert data["quantity_total"] == 50
    assert data["quantity_available"] == 30
