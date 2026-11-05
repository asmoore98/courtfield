"""The starter task library: common court and site work, with the other
names people use for the same work. Rates are left blank on purpose; the
company's default rates fill in until the GM sets each one.

Different work gets its own task even when it sounds alike (a broom clean
isn't a pressure wash), so hours and costs stay comparable job to job.

    (name, other names, task type, crew or sub)

Everything starts as our own crew's work; any task can be switched to a sub
on an estimate, or in the library by the GM.

STARTER_UNITS says how each one is usually measured (quantities.py), and the
usual coats for per-coat work. Production rates and prices per unit are left
for the GM: they're the company's own numbers.
"""
from .models import TaskKind, TaskType

C, S = TaskKind.crew, TaskKind.sub
T = TaskType

STARTER_TASKS: list[tuple[str, list[str], TaskType, TaskKind]] = [
    # --- getting started ---
    ("Mobilization", ["mobilize", "move in", "set up site", "setup"], T.other, C),
    ("Demobilization", ["demobilize", "demob", "pack up", "move out"], T.other, C),
    ("Permits and inspections", ["permit", "permitting", "inspection", "pull permit"], T.other, C),
    ("Survey and stakeout", ["survey", "stake out", "staking", "layout survey"], T.site_work, C),
    ("Silt fence and erosion control", ["silt fence", "erosion control", "swppp", "turbidity barrier"], T.site_work, C),
    # --- site work ---
    # Clearing is priced by the acre, and how thick it is changes the price.
    ("Clearing and grubbing, grass", ["clear grass", "strip sod", "clear field", "grass clearing"], T.site_work, C),
    ("Clearing and grubbing, light brush", ["land clearing", "clear site", "grub", "brush removal", "brush clearing"], T.site_work, C),
    ("Clearing and grubbing, heavy woods", ["tree removal", "clear trees", "woods clearing", "forestry mulching"], T.site_work, C),
    ("Demolition of existing court", ["demo court", "tear out", "remove existing surface", "break out"], T.site_work, C),
    ("Excavation and haul-off", ["excavate", "dig out", "export dirt", "haul away", "spoils removal"], T.site_work, C),
    ("Rough grading", ["grading", "cut and fill", "earthwork", "dirt work", "mass grading"], T.site_work, C),
    ("Subgrade compaction", ["compaction", "compact subgrade", "rolling", "proof roll"], T.site_work, C),
    ("Base rock install", ["limerock", "base material", "aggregate base", "crushed stone", "base course"], T.site_work, C),
    ("Fine grading", ["finish grade", "laser grade", "base grading", "fine grade base"], T.site_work, C),
    ("Irrigation relocation", ["move sprinklers", "irrigation repair", "sprinkler relocation"], T.other, C),
    # --- drainage ---
    ("French drain", ["perimeter drain", "trench drain", "gravel drain", "underdrain"], T.drainage, C),
    ("Drain pipe and inlets", ["storm pipe", "catch basin", "drain inlet", "yard drain"], T.drainage, C),
    # --- paving and concrete ---
    ("Asphalt paving", ["pave", "blacktop", "asphalt install", "new asphalt"], T.paving, C),
    ("Asphalt overlay", ["overlay", "resurface asphalt", "mill and overlay"], T.paving, C),
    ("Asphalt patching", ["pothole repair", "cold patch", "hot patch", "asphalt repair"], T.paving, C),
    # A court slab is bid in its parts; a court needs a far better finish than a building pad.
    ("Court slab: forms", ["court forms", "form boards", "slab forms"], T.paving, C),
    ("Court slab: vapor barrier", ["vapor barrier", "visqueen", "poly under slab"], T.paving, C),
    ("Court slab: rebar and mesh", ["rebar", "wire mesh", "reinforcing", "steel"], T.paving, C),
    ("Court slab: pour and place", ["pour court", "concrete pour", "place concrete", "concrete court slab"], T.paving, C),
    ("Court slab: finish", ["court finish", "broom finish", "trowel finish", "finish concrete"], T.paving, C),
    ("Sidewalks and flatwork", ["sidewalk", "concrete walk", "concrete pad", "flat work", "concrete flatwork"], T.paving, C),
    ("Concrete curbing and edging", ["curb", "header curb", "mow strip", "edge curb"], T.paving, C),
    ("Concrete forming", ["formwork", "set forms", "form setting"], T.paving, C),
    # --- cleaning and prep ---
    ("Broom clean", ["sweep", "blow off", "leaf blow", "dry clean court"], T.prep, C),
    ("Pressure wash", ["power wash", "pressure clean", "wash court", "water blast"], T.prep, C),
    ("Mildew and algae treatment", ["mold treatment", "bleach wash", "chlorine wash", "algae removal"], T.prep, C),
    ("Flood test (find low spots)", ["flood test", "water test", "puddle test", "birdbath check", "flood court"], T.prep, C),
    ("Grind high spots and ridges", ["grinding", "ridge grinding", "grind bumps"], T.prep, C),
    ("Remove old lines", ["line removal", "grind lines", "strip lines"], T.prep, C),
    ("Primer and adhesion coat", ["primer", "bonding coat", "adhesion promoter", "prime court"], T.prep, C),
    # --- crack and surface repair ---
    ("Crack fill", ["crack repair", "crack patch", "fill cracks", "acrylic crack filler"], T.crack_fill, C),
    ("Crack repair membrane system", ["crack membrane", "crack bridging", "fabric crack repair", "crack system"], T.crack_fill, C),
    ("Low-spot patch", ["birdbath repair", "patch binder", "depression patch", "level low spots"], T.crack_fill, C),
    ("Concrete spall repair", ["concrete patch", "spall patch", "concrete repair"], T.crack_fill, C),
    # --- surfacing ---
    ("Acrylic resurfacer", ["resurfacer", "filler coat", "sand coat", "resurfacer coat"], T.resurfacer, C),
    ("Cushion coat system", ["cushion layers", "rubber cushion", "padded surface", "cushion court"], T.resurfacer, C),
    ("Color coat", ["color coats", "finish coat", "top coat", "acrylic color", "paint court"], T.color_coat, C),
    # --- lines ---
    ("Line layout", ["layout", "tape lines", "measure lines", "court layout", "mark out"], T.lines, C),
    ("Line painting", ["striping", "line striping", "paint lines", "stripe court"], T.lines, C),
    ("Pickleball line conversion", ["add pickleball lines", "blended lines", "tennis to pickleball lines"], T.lines, C),
    # --- equipment ---
    ("Core drill post sleeves", ["core drilling", "sleeve install", "post sleeves"], T.nets_posts, C),
    ("Net post removal", ["remove posts", "pull posts", "tear out posts"], T.nets_posts, C),
    ("Install net posts", ["net post install", "set posts", "post setting"], T.nets_posts, C),
    ("Install nets and center straps", ["hang nets", "net install", "center strap"], T.nets_posts, C),
    ("Basketball goal removal", ["remove hoop", "tear out goal", "remove basketball goal"], T.nets_posts, C),
    ("Basketball goal install", ["hoop install", "backboard install", "basketball system"], T.nets_posts, C),
    ("Windscreen removal", ["remove windscreen", "take down windscreen"], T.fence, C),
    ("Windscreen install", ["wind screen", "privacy screen", "fence screen"], T.fence, C),
    ("Site amenities install", ["benches", "ball holders", "score keepers", "shade structure"], T.other, C),
    # --- fence ---
    ("Chain-link fence, new", ["fence install", "chain link", "new fence"], T.fence, C),
    ("Fence removal", ["tear out fence", "remove fence", "fence demo"], T.fence, C),
    ("Fence repair", ["fence fix", "re-tension fabric", "restretch fence", "fence patch"], T.fence, C),
    ("Gate install", ["new gate", "gate", "swing gate"], T.fence, C),
    # --- lighting ---
    ("Court lighting", ["lights", "led lights", "light poles", "sports lighting"], T.lighting, C),
    ("Electrical", ["electrician", "power", "conduit", "wiring"], T.lighting, C),
    # --- turf ---
    ("Synthetic turf install", ["turf install", "lay turf", "roll out turf", "artificial turf"], T.turf, C),
    ("Turf seaming", ["seams", "seam tape", "glue seams"], T.turf, C),
    ("Turf infill", ["sand infill", "rubber infill", "crumb rubber", "infill install"], T.turf, C),
    ("Inlaid lines and logos", ["inlay", "turf lines", "inlaid logo"], T.turf, C),
    ("Turf grooming", ["brush turf", "groom turf", "power broom"], T.turf, C),
    # --- buildings (more to come when they're bidding buildings) ---
    ("Building plans and engineering", ["architect", "building plans", "drawings", "engineering"], T.building, C),
    ("Building slab and footings", ["building slab", "footings", "foundation", "building pad"], T.building, C),
    ("Building construction", ["concession stand", "restroom building", "bathrooms", "storage building", "pavilion"], T.building, C),
    # --- wrap-up ---
    ("Site cleanup and debris removal", ["clean up", "cleanup", "debris haul", "dumpster", "final clean"], T.cleanup, C),
    ("Landscape restoration", ["sod repair", "restore lawn", "landscape repair"], T.cleanup, C),
]


# How each starter task is measured: (unit, usual coats). Anything not listed is hourly.
STARTER_UNITS: dict[str, tuple[str, float | None]] = {
    "Mobilization": ("ls", None), "Demobilization": ("ls", None), "Permits and inspections": ("ls", None),
    "Survey and stakeout": ("ls", None), "Silt fence and erosion control": ("lf", None),
    "Clearing and grubbing, grass": ("acre", None), "Clearing and grubbing, light brush": ("acre", None),
    "Clearing and grubbing, heavy woods": ("acre", None), "Demolition of existing court": ("sf", None),
    "Excavation and haul-off": ("cy", None), "Rough grading": ("acre", None), "Subgrade compaction": ("sf", None),
    "Base rock install": ("ton", None), "Fine grading": ("acre", None), "Irrigation relocation": ("ls", None),
    "French drain": ("lf", None), "Drain pipe and inlets": ("lf", None),
    "Asphalt paving": ("sf", None), "Asphalt overlay": ("sf", None), "Asphalt patching": ("sf", None),
    "Court slab: forms": ("lf", None), "Court slab: vapor barrier": ("sf", None), "Court slab: rebar and mesh": ("sf", None),
    "Court slab: pour and place": ("cy", None), "Court slab: finish": ("sf", None), "Sidewalks and flatwork": ("sf", None),
    "Building slab and footings": ("sf", None),
    "Concrete curbing and edging": ("lf", None), "Concrete forming": ("lf", None),
    "Broom clean": ("sf", None), "Pressure wash": ("sf", None), "Mildew and algae treatment": ("sf", None),
    "Flood test (find low spots)": ("ls", None), "Building plans and engineering": ("ls", None), "Building construction": ("ls", None), "Remove old lines": ("lf", None), "Primer and adhesion coat": ("sf_coat", 1),
    "Crack fill": ("lf", None), "Crack repair membrane system": ("lf", None), "Low-spot patch": ("sf", None),
    "Concrete spall repair": ("sf", None),
    "Acrylic resurfacer": ("sf_coat", 2), "Cushion coat system": ("sf_coat", 2), "Color coat": ("sf_coat", 2),
    # Lines are painted (and their paint taken off) by the linear foot.
    "Line layout": ("lf", None), "Line painting": ("lf", None), "Pickleball line conversion": ("lf", None),
    "Core drill post sleeves": ("ea", None), "Net post removal": ("ea", None), "Basketball goal removal": ("ea", None),
    "Windscreen removal": ("lf", None), "Fence removal": ("lf", None), "Install net posts": ("ea", None), "Install nets and center straps": ("ea", None),
    "Basketball goal install": ("ea", None), "Windscreen install": ("lf", None), "Site amenities install": ("ls", None),
    "Chain-link fence, new": ("lf", None), "Fence repair": ("lf", None), "Gate install": ("ea", None),
    "Court lighting": ("ea", None), "Electrical": ("ls", None),
    "Synthetic turf install": ("sf", None), "Turf seaming": ("lf", None), "Turf infill": ("sf", None),
    "Inlaid lines and logos": ("ls", None), "Turf grooming": ("sf", None),
    "Site cleanup and debris removal": ("ls", None), "Landscape restoration": ("sf", None),
}
