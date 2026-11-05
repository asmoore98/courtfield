"""A starter material list with ballpark prices, so estimates have
something to work from on day one. Every item is marked as a starter price:
the GM or an estimator should check and fix each one against real supplier
quotes in the price list. Generic items only; no supplier's prices.

    (name, category, unit, ballpark cost, SF one unit covers per coat, keep in stock)

Coverage is for coatings and sheet goods (how many square feet one pail or
roll covers in one coat); the rest are counted.
"""
from .models import CostCategory

M, E, O = CostCategory.material, CostCategory.equipment, CostCategory.other

STARTER_MATERIALS: list[tuple[str, CostCategory, str, float, float | None, bool]] = [
    # --- court surfacing ---
    ("Acrylic resurfacer", M, "pail", 120.0, 600.0, True),
    ("Color coat concentrate", M, "pail", 150.0, 700.0, True),
    ("Cushion coat (rubber)", M, "pail", 140.0, 400.0, True),
    ("Primer / adhesion coat", M, "pail", 130.0, 1000.0, True),
    ("Line paint", M, "gal", 55.0, None, True),
    ("Crack filler", M, "gal", 38.0, None, True),
    ("Patch binder", M, "pail", 110.0, None, True),
    ("Crack repair membrane", M, "roll", 160.0, None, True),
    ("Silica sand", M, "bag", 9.0, None, True),
    # --- site work and base ---
    ("Base rock (crushed limerock)", M, "ton", 28.0, None, False),
    ("Fill dirt", M, "CY", 15.0, None, False),
    ("Washed sand", M, "ton", 30.0, None, False),
    ("Silt fence", M, "LF", 1.25, None, False),
    ("Drain pipe (4 in perforated)", M, "LF", 2.5, None, False),
    ("Drain gravel", M, "ton", 38.0, None, False),
    # --- concrete and asphalt ---
    ("Ready-mix concrete", M, "CY", 165.0, None, False),
    ("Rebar #4 (20 ft stick)", M, "each", 12.0, None, True),
    ("Welded wire mesh (sheet)", M, "each", 14.0, None, True),
    ("Vapor barrier (10 mil roll)", M, "roll", 120.0, 1000.0, True),
    ("Form lumber 2x6x16", M, "each", 12.0, None, True),
    ("Hot-mix asphalt", M, "ton", 95.0, None, False),
    ("Asphalt tack coat", M, "gal", 4.0, None, False),
    # --- fence, nets and goals ---
    ("Chain-link fabric 10 ft (50 ft roll)", M, "roll", 380.0, None, True),
    ("Fence line post 10 ft", M, "each", 45.0, None, True),
    ("Windscreen", M, "LF", 3.5, None, True),
    ("Tennis posts and net set", M, "set", 650.0, None, True),
    ("Pickleball posts and net set", M, "set", 450.0, None, True),
    ("Basketball goal system", M, "each", 2500.0, None, False),
    # --- equipment ---
    ("Skid steer rental", E, "day", 350.0, None, False),
    ("Mini excavator rental", E, "day", 450.0, None, False),
    ("Plate compactor rental", E, "day", 95.0, None, False),
    ("Vibratory roller rental", E, "day", 300.0, None, False),
    ("Dump truck haul", E, "load", 450.0, None, False),
    ("Concrete pump truck", E, "hr", 200.0, None, False),
    ("Pressure washer rental", E, "day", 110.0, None, False),
    # --- other ---
    ("Dumpster (20 yd)", O, "each", 550.0, None, False),
    ("Portable toilet", O, "month", 175.0, None, False),
]

# What some starter tasks bring onto an estimate (routers/library.py PartIn).
# Amounts are ballpark: e.g. 1 pail of resurfacer for every 600 SF a coat.
STARTER_PARTS: dict[str, list[dict]] = {
    "Base rock install": [
        {"category": "material", "description": "Base rock (crushed limerock)", "unit": "ton", "how": "task", "per_amount": 1.05, "per_every": 1},
        {"category": "equipment", "description": "Dump truck haul", "unit": "load", "how": "task", "per_amount": 1, "per_every": 20},
        {"category": "equipment", "description": "Skid steer rental", "unit": "day", "how": "task", "per_amount": 1, "per_every": 150},
    ],
    "Acrylic resurfacer": [
        {"category": "material", "description": "Acrylic resurfacer", "unit": "pail", "how": "task", "per_amount": 1, "per_every": 600},
        {"category": "material", "description": "Silica sand", "unit": "bag", "how": "task", "per_amount": 1, "per_every": 300},
    ],
    "Color coat": [
        {"category": "material", "description": "Color coat concentrate", "unit": "pail", "how": "task", "per_amount": 1, "per_every": 700},
    ],
    "Cushion coat system": [
        {"category": "material", "description": "Cushion coat (rubber)", "unit": "pail", "how": "task", "per_amount": 1, "per_every": 400},
    ],
    "Primer and adhesion coat": [
        {"category": "material", "description": "Primer / adhesion coat", "unit": "pail", "how": "task", "per_amount": 1, "per_every": 1000},
    ],
    "Line painting": [
        {"category": "material", "description": "Line paint", "unit": "gal", "how": "task", "per_amount": 1, "per_every": 350},
    ],
    "Crack fill": [
        {"category": "material", "description": "Crack filler", "unit": "gal", "how": "task", "per_amount": 1, "per_every": 40},
    ],
    "Pressure wash": [
        {"category": "equipment", "description": "Pressure washer rental", "unit": "day", "how": "task", "per_amount": 1, "per_every": 15000},
    ],
    "Court slab: pour and place": [
        {"category": "material", "description": "Ready-mix concrete", "unit": "CY", "how": "task", "per_amount": 1.05, "per_every": 1},
        {"category": "equipment", "description": "Concrete pump truck", "unit": "hr", "how": "task", "per_amount": 1, "per_every": 20},
    ],
    "Court slab: vapor barrier": [
        {"category": "material", "description": "Vapor barrier (10 mil roll)", "unit": "roll", "how": "task", "per_amount": 1, "per_every": 900},
    ],
    "Silt fence and erosion control": [
        {"category": "material", "description": "Silt fence", "unit": "LF", "how": "task", "per_amount": 1.1, "per_every": 1},
    ],
    "Site cleanup and debris removal": [
        {"category": "other", "description": "Dumpster (20 yd)", "unit": "each", "how": "fixed", "quantity": 1},
    ],
}


def add_starter_materials(db, company_id: str) -> int:
    """Add the starter materials. Names already on the price list are skipped."""
    from sqlalchemy import func, select

    from .models import StockItem
    taken = {n.lower() for n in db.scalars(select(func.lower(StockItem.name)).where(StockItem.company_id == company_id))}
    added = 0
    for name, cat, unit, cost, coverage, track in STARTER_MATERIALS:
        if name.lower() in taken:
            continue
        db.add(StockItem(company_id=company_id, name=name, category=cat, unit=unit, unit_cost=cost, coverage_sf=coverage,
                         track_stock=track, starter_price=True))
        added += 1
    return added
