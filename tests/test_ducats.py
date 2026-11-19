from voidtrace.ducats import DucatRow, ducat_rows
from voidtrace.items import CatalogItem

CATALOG = [
    CatalogItem("Paris Prime Grip", "paris_prime_grip", None, ("prime", "component"), "id-grip"),
    CatalogItem("Caliban Prime Blueprint", "caliban_prime_blueprint", None, ("prime", "blueprint"), "id-bp"),
    CatalogItem("Volt Prime Set", "volt_prime_set", None, ("prime", "set"), "id-set"),
]


def entry(item, ducats, wa, per, volume=50):
    return {"item": item, "ducats": ducats, "wa_price": wa, "ducats_per_platinum_wa": per, "volume": volume,
            "median": wa, "ducats_per_platinum": per}


PAYLOAD = {"previous_hour": [], "previous_day": [
    entry("id-grip", 45, 4.0, 11.25, 234),
    entry("id-bp", 45, 3.6, 12.5, 517),
    entry("id-set", 300, 40.0, 7.5),      # sets: Baro doesn't take them
    entry("id-unknown", 15, 1.0, 15.0),   # not in the catalog
    entry("id-grip", 45, 0, 0),           # no price
]}


def test_rows_map_ids_drop_sets_and_unknowns_and_sort_best_first():
    assert ducat_rows(PAYLOAD, CATALOG) == [
        DucatRow("Caliban Prime Blueprint", "caliban_prime_blueprint", 45, 3.6, 12.5, 517),
        DucatRow("Paris Prime Grip", "paris_prime_grip", 45, 4.0, 11.25, 234),
    ]


def test_empty_payload_gives_no_rows():
    assert ducat_rows({}, CATALOG) == []
