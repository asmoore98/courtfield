"""How a task is measured, and the numbers that follow from it.

Each task has a unit. With a production rate, its crew hours are worked out
from the quantity instead of guessed:

    SF, SF per coat, LF, SY   rate = how many units one person does in an hour
    each, CY, ton, lump sum   rate = person-hours for one unit

"SF per coat" tasks (resurfacer, color) multiply the area by the coats.
"hr" tasks have their hours typed in, as before.

What we charge for crew work is quantity x price per unit when the task has
one, otherwise hours x the charge rate. Mirrored in frontend/src/qty.js.
"""
import math

UNITS = ("hr", "sf", "sf_coat", "lf", "sy", "cy", "ton", "ea", "ls")
UNIT_LABEL = {"hr": "hours", "sf": "SF", "sf_coat": "SF per coat", "lf": "LF", "sy": "SY", "cy": "CY",
              "ton": "tons", "ea": "each", "ls": "lump sum"}
PER_HOUR = {"sf", "sf_coat", "lf", "sy"}  # rate is units per person-hour; the rest are hours per unit

# Where a task's or a material's quantity can come from on an estimate.
FOLLOWS = ("", "surface", "paint", "courts")


def total_units(unit: str, quantity: float | None, coats: float | None) -> float:
    """The quantity, times the coats for per-coat work. A lump sum is one."""
    if unit == "ls":
        return quantity if quantity else 1.0
    q = quantity or 0.0
    if unit == "sf_coat":
        q *= coats if coats is not None else 1.0
    return q


def worked_hours(unit: str, quantity: float | None, coats: float | None, rate: float | None) -> float | None:
    """Crew hours from the quantity and production rate, or None when the
    hours are typed (hourly tasks, or no rate set)."""
    if unit == "hr" or not rate:
        return None
    q = total_units(unit, quantity, coats)
    return round(q / rate if unit in PER_HOUR else q * rate, 2)


def labor_charge(t) -> float:
    """What we charge for a crew task (anything with the task fields)."""
    if t.unit != "hr" and t.unit_price is not None:
        return total_units(t.unit, t.quantity, t.coats) * t.unit_price
    return t.estimated_hours * (t.charge_rate or 0)


def material_qty(area: float, coats: float | None, coverage: float) -> float:
    """Units to buy (pails, gallons…) to cover an area: rounded up to whole units."""
    need = area * (coats or 1) / coverage
    return float(math.ceil(round(need, 6)))
