"""Addresses are kept in parts (street, city, state, ZIP) so forms and phones
can fill them in, and as one line ("100 Main St, Stuart, FL 34994") for
lists, the map lookup and the proposal."""
from pydantic import Field

PARTS = ("street", "city", "state", "zip")
LIMITS = {"street": 200, "city": 100, "state": 40, "zip": 10}


def compose(street: str = "", city: str = "", state: str = "", zip: str = "") -> str:
    region = " ".join(x for x in (state.strip(), zip.strip()) if x)
    place = ", ".join(x for x in (city.strip(), region) if x)
    return ", ".join(x for x in (street.strip(), place) if x)


def part_fields(prefix: str) -> dict:
    """Pydantic fields site_street, site_city… for a request shape."""
    return {f"{prefix}_{p}": (str, Field(default="", max_length=LIMITS[p])) for p in PARTS}


def fill(model, prefix: str, target: str):
    """When any part was sent, the one-line address is built from the parts."""
    parts = {p: getattr(model, f"{prefix}_{p}").strip() for p in PARTS}
    for p, v in parts.items():
        setattr(model, f"{prefix}_{p}", v)
    if any(parts.values()):
        setattr(model, target, compose(**parts)[:300])
    return model
