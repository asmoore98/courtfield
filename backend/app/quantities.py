"""How a task is measured, and the numbers that follow from it.

Each task has a unit. With a production rate, its crew hours are worked out
from the quantity instead of guessed:

    SF, SF per coat, LF, SY   rate = how many units one person does in an hour
    acre, each, CY, ton, lump sum   rate = person-hours for one unit

"SF per coat" tasks (resurfacer, color) multiply the area by the coats.
"hr" tasks have their hours typed in, as before.

What we charge for crew work is quantity x price per unit when the task has
one, otherwise hours x the charge rate. Mirrored in frontend/src/qty.js.

A task is priced one of two ways (estimates):
    built up (the default)  each part has its price: the labor by its rate,
                            each material, machine or other line with its markup
    by the unit ("all in")  the customer pays quantity x price per unit; the
                            task's materials and machine time are our cost
                            inside that price, not charged on top

Base rock, fill and concrete can be worked out from their size: length x
width x depth gives cubic yards, and tons at so many tons per cubic yard.
A line on a task can follow the task's amount: "0.75 hr for every 20 ton"
(machine time per load, whole loads) or "1.05 ton for every 1 ton" (extra
for waste).
"""
import math

UNITS = ("hr", "sf", "sf_coat", "lf", "sy", "cy", "ton", "acre", "ea", "ls")
UNIT_LABEL = {"hr": "hours", "sf": "SF", "sf_coat": "SF per coat", "lf": "LF", "sy": "SY", "cy": "CY",
              "ton": "tons", "acre": "acres", "ea": "each", "ls": "lump sum"}
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


TONS_PER_CY = 1.4  # crushed base rock, roughly; set per task


def size_quantity(unit: str, length_ft: float | None, width_ft: float | None, depth_in: float | None,
                  tons_per_cy: float | None) -> float | None:
    """The quantity from a length and width (SF, SY) or with a depth too
    (CY, tons). None when the sizes it needs aren't there."""
    if not length_ft or not width_ft:
        return None
    sf = length_ft * width_ft
    if unit == "sf":
        return round(sf, 2)
    if unit == "sy":
        return round(sf / 9, 2)
    if unit in ("cy", "ton"):
        if not depth_in:
            return None
        cy = sf * depth_in / 12 / 27
        return round(cy if unit == "cy" else cy * (tons_per_cy or TONS_PER_CY), 2)
    return None


def task_units(t) -> float:
    """How much of the task there is, for lines that follow it: its quantity
    (times coats), or its hours when it's measured in hours."""
    if t.unit == "hr":
        return t.estimated_hours or 0.0
    return total_units(t.unit, t.quantity, t.coats)


def per_task_qty(units: float, amount: float | None, every: float | None, category: str) -> float:
    """A line that follows its task: `amount` for every `every` units of the
    task. Per load or batch (every > 1) counts whole loads; materials are
    bought in whole units."""
    if not amount or units <= 0:
        return 0.0
    every = every or 1.0
    loads = units / every
    if every > 1:
        loads = math.ceil(round(loads, 6))
    q = loads * amount
    return float(math.ceil(round(q, 6))) if category == "material" else round(q, 2)


def material_qty(area: float, coats: float | None, coverage: float) -> float:
    """Units to buy (pails, gallons…) to cover an area: rounded up to whole units."""
    need = area * (coats or 1) / coverage
    return float(math.ceil(round(need, 6)))
