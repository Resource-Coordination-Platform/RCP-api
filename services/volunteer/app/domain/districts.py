"""Static district geography for Sri Lanka — the no-GPS routing substrate.

The platform deliberately avoids GPS tracking; proximity is approximated
by administrative-district adjacency. This map is the single source of
truth for both radius broadcasting levels:

- RADIUS_L1: the source district only
- RADIUS_L2: the source district plus its immediate neighbours
- TARGETED : an explicit district list chosen by the tenant, bypassing
             adjacency entirely (e.g. Kandy requesting boat drivers
             from Matara)

Adjacency is land-border adjacency between the 25 administrative
districts. The module self-validates on import: every district present,
no self-loops, and the relation is symmetric — a typo here fails the
service at boot, not silently at match time.
"""

ADJACENCY: dict[str, frozenset[str]] = {
    d: frozenset(neighbours)
    for d, neighbours in {
        # Western
        "Colombo":      ["Gampaha", "Kalutara", "Kegalle", "Ratnapura"],
        "Gampaha":      ["Colombo", "Kegalle", "Kurunegala", "Puttalam"],
        "Kalutara":     ["Colombo", "Galle", "Ratnapura"],
        # Central
        "Kandy":        ["Badulla", "Kegalle", "Kurunegala", "Matale", "Nuwara Eliya"],
        "Matale":       ["Anuradhapura", "Kandy", "Kurunegala", "Polonnaruwa"],
        "Nuwara Eliya": ["Badulla", "Kandy", "Kegalle", "Ratnapura"],
        # Southern
        "Galle":        ["Kalutara", "Matara", "Ratnapura"],
        "Matara":       ["Galle", "Hambantota", "Ratnapura"],
        "Hambantota":   ["Ampara", "Matara", "Moneragala", "Ratnapura"],
        # Northern
        "Jaffna":       ["Kilinochchi"],
        "Kilinochchi":  ["Jaffna", "Mannar", "Mullaitivu"],
        "Mannar":       ["Anuradhapura", "Kilinochchi", "Puttalam", "Vavuniya"],
        "Vavuniya":     ["Anuradhapura", "Mannar", "Mullaitivu", "Trincomalee"],
        "Mullaitivu":   ["Kilinochchi", "Trincomalee", "Vavuniya"],
        # Eastern
        "Trincomalee":  ["Anuradhapura", "Batticaloa", "Mullaitivu", "Polonnaruwa", "Vavuniya"],
        "Batticaloa":   ["Ampara", "Polonnaruwa", "Trincomalee"],
        "Ampara":       ["Badulla", "Batticaloa", "Hambantota", "Moneragala", "Polonnaruwa"],
        # North Western
        "Kurunegala":   ["Anuradhapura", "Gampaha", "Kandy", "Kegalle", "Matale", "Puttalam"],
        "Puttalam":     ["Anuradhapura", "Gampaha", "Kurunegala", "Mannar"],
        # North Central
        "Anuradhapura": ["Kurunegala", "Mannar", "Matale", "Polonnaruwa", "Puttalam",
                         "Trincomalee", "Vavuniya"],
        "Polonnaruwa":  ["Ampara", "Anuradhapura", "Badulla", "Batticaloa", "Matale",
                         "Trincomalee"],
        # Uva
        "Badulla":      ["Ampara", "Kandy", "Moneragala", "Nuwara Eliya", "Polonnaruwa",
                         "Ratnapura"],
        "Moneragala":   ["Ampara", "Badulla", "Hambantota", "Ratnapura"],
        # Sabaragamuwa
        "Ratnapura":    ["Badulla", "Colombo", "Galle", "Hambantota", "Kalutara", "Kegalle",
                         "Matara", "Moneragala", "Nuwara Eliya"],
        "Kegalle":      ["Colombo", "Gampaha", "Kandy", "Kurunegala", "Nuwara Eliya",
                         "Ratnapura"],
    }.items()
}

DISTRICTS: frozenset[str] = frozenset(ADJACENCY)


def _validate() -> None:
    assert len(ADJACENCY) == 25, f"expected 25 districts, found {len(ADJACENCY)}"
    for district, neighbours in ADJACENCY.items():
        assert district not in neighbours, f"{district} lists itself as a neighbour"
        for n in neighbours:
            assert n in ADJACENCY, f"{district} -> unknown district {n!r}"
            assert district in ADJACENCY[n], f"asymmetric edge {district} -> {n}"


_validate()


def is_valid_district(name: str) -> bool:
    return name in DISTRICTS


def neighbours_of(district: str) -> frozenset[str]:
    try:
        return ADJACENCY[district]
    except KeyError:
        raise ValueError(f"Unknown district: {district!r}") from None


def resolve_broadcast_districts(
    *,
    broadcast_type: str,
    source_district: str,
    target_districts: list[str] | None = None,
) -> list[str]:
    """Turn a broadcast decision into the concrete district list the
    matching SQL filters on. Returns a sorted list (deterministic output
    keeps tests and event payloads stable).

    RADIUS_L1  -> [source]
    RADIUS_L2  -> [source] + neighbours(source)
    TARGETED   -> exactly the tenant-chosen districts (adjacency bypassed)
    """
    if source_district not in DISTRICTS:
        raise ValueError(f"Unknown district: {source_district!r}")

    if broadcast_type == "RADIUS_L1":
        return [source_district]
    if broadcast_type == "RADIUS_L2":
        return sorted({source_district, *ADJACENCY[source_district]})
    if broadcast_type == "TARGETED":
        if not target_districts:
            raise ValueError("TARGETED broadcast requires target_districts")
        unknown = [d for d in target_districts if d not in DISTRICTS]
        if unknown:
            raise ValueError(f"Unknown district(s): {unknown}")
        return sorted(set(target_districts))
    raise ValueError(f"Unknown broadcast type: {broadcast_type!r}")
