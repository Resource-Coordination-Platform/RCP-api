import pytest

from app.domain.districts import (
    ADJACENCY,
    DISTRICTS,
    neighbours_of,
    resolve_broadcast_districts,
)


def test_exactly_25_districts():
    assert len(DISTRICTS) == 25


def test_adjacency_is_symmetric_and_irreflexive():
    for district, neighbours in ADJACENCY.items():
        assert district not in neighbours
        for n in neighbours:
            assert district in ADJACENCY[n]


def test_radius_l1_is_source_only():
    assert resolve_broadcast_districts(
        broadcast_type="RADIUS_L1", source_district="Ratnapura"
    ) == ["Ratnapura"]


def test_radius_l2_includes_all_neighbours():
    resolved = resolve_broadcast_districts(
        broadcast_type="RADIUS_L2", source_district="Colombo"
    )
    assert resolved == sorted({"Colombo", *neighbours_of("Colombo")})
    assert "Gampaha" in resolved and "Kalutara" in resolved


def test_targeted_bypasses_adjacency():
    # Kandy requesting volunteers directly from distant Matara
    resolved = resolve_broadcast_districts(
        broadcast_type="TARGETED",
        source_district="Kandy",
        target_districts=["Matara"],
    )
    assert resolved == ["Matara"]
    assert "Matara" not in neighbours_of("Kandy")


def test_targeted_requires_targets():
    with pytest.raises(ValueError):
        resolve_broadcast_districts(broadcast_type="TARGETED", source_district="Kandy")


def test_unknown_district_rejected():
    with pytest.raises(ValueError):
        resolve_broadcast_districts(broadcast_type="RADIUS_L1", source_district="Atlantis")
    with pytest.raises(ValueError):
        resolve_broadcast_districts(
            broadcast_type="TARGETED",
            source_district="Kandy",
            target_districts=["Matara", "Gotham"],
        )
