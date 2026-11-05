"""The site checklist sales fills in on site, one per kind of work.

Every lead gets the court size block, then the questions for its scope.
Follow-up questions only show once the question they hang off is answered a
certain way ("show_if"): cracks? yes -> how many feet, how wide.

"courts" limits a question or a whole section to some court types (no net
questions on a basketball court). With no court type picked, everything shows.

"tasks" ties an answer to the task library: when the answer matches "when"
(one value or a list), an estimate started from the lead gets that task, with
its quantity taken from "qty" (another question, or the court size). Any other
answer takes the task off the starter list. "only_remove" tasks are taken off
on any other answer but never added (the follow-up adds the right one).
Names match the starter task list.

Choices with an "Other" option get a "What is it?" box automatically
("<id>_other"), and any question can carry a note ("<id>_note").

Question ids are saved with the answers. Don't reuse or rename an id; add a
new one and retire the old (old answers keep showing under their label).
"""
from copy import deepcopy

YES = "yes"


def q(id, label, kind="yesno", **kw):
    """kind: yesno | number | choice | multi | text. Text is optional unless required=True."""
    return {"id": id, "label": label, "kind": kind, "required": kw.pop("required", kind != "text"), **kw}


def when_yes(id):
    return {id: YES}


NET_COURTS = ["tennis", "pickleball", "multi_court"]
HOOP_COURTS = ["basketball", "multi_court"]
REPLACE, NEW = "Replace existing", "Install new"


# ---------- pieces shared by more than one checklist ----------

SURFACE = q("surface", "What's the court surface now?", "choice", options=["Asphalt", "Concrete", "Other"])

CRACKS = [
    q("cracks", "Do cracks need filled?", tasks=[{"name": "Crack fill", "qty": "crack_lf"}]),
    q("crack_lf", "About how many feet of cracks?", "number", unit="LF", show_if=when_yes("cracks"),
      help="Walk them and add them up. Better a little over than under."),
    q("crack_width", "How wide is the widest crack?", "choice", options=['Hairline', 'Up to 1/4"', '1/4" to 1/2"', 'Over 1/2"'],
      show_if=when_yes("cracks")),
    q("membrane", "Any cracks that keep coming back, or over 1/2\" wide? (crack repair system)", show_if=when_yes("cracks"),
      tasks=[{"name": "Crack repair membrane system", "qty": "membrane_lf"}]),
    q("membrane_lf", "About how many feet of those?", "number", unit="LF", show_if=when_yes("membrane")),
]

SURFACE_PROBLEMS = [
    q("low_spots", "Low spots or standing water (birdbaths)?", tasks=[{"name": "Low-spot patch", "qty": "low_sf"}]),
    q("low_sf", "About how many square feet of low spots, all together?", "number", unit="SF", show_if=when_yes("low_spots"),
      help="Water left 1/8\" deep or more an hour after a rain or a hose-down."),
    q("peeling", "Is the old coating peeling or bubbling?"),
    q("peeling_sf", "About how many square feet?", "number", unit="SF", show_if=when_yes("peeling")),
    q("mildew", "Mildew, algae or moss on the court?", tasks=[{"name": "Mildew and algae treatment", "qty": "surface"}]),
    q("heaving", "Tree roots, heaving or settling?"),
    q("heaving_notes", "Where, and how bad?", "text", show_if=when_yes("heaving"), required=True),
]

LINES = [
    q("lines", "What lines do they want?", "multi", options=["Tennis", "Pickleball", "Basketball", "Other"]),
    q("pb_courts", "How many pickleball courts lined?", "number", unit="courts", show_if={"lines": "Pickleball"}),
    q("lines_change", "Changing the line layout from what's there now?", tasks=[{"name": "Remove old lines"}]),
    q("colors", "Colors they want (inside / outside)", "text"),
]

NETS_POSTS = [
    q("nets", "Do the nets need replaced?", tasks=[{"name": "Install nets and center straps", "qty": "net_count"}]),
    q("net_type", "What kind of net?", "choice", options=["Tennis", "Pickleball", "Portable pickleball", "Other"], show_if=when_yes("nets")),
    q("net_count", "How many nets?", "number", unit="nets", show_if=when_yes("nets")),
    q("posts", "Any net post work?", tasks=[{"name": "Install net posts", "only_remove": True},
                                            {"name": "Net post removal", "only_remove": True}]),
    q("posts_work", "Replace the posts that are there, or put in new ones?", "choice", options=[REPLACE, NEW], show_if=when_yes("posts"),
      tasks=[{"name": "Net post removal", "when": REPLACE, "qty": "post_count"},
             {"name": "Install net posts", "when": [REPLACE, NEW], "qty": "post_count"}]),
    q("post_count", "How many posts?", "number", unit="posts", show_if=when_yes("posts")),
    q("post_type", "What kind of posts?", "choice", options=["Round", "Square", "Not sure"], show_if=when_yes("posts")),
    q("sleeves_ok", "Are the post sleeves and footers in good shape?", show_if={"posts_work": REPLACE},
      tasks=[{"name": "Core drill post sleeves", "when": "no", "qty": "post_count"}]),
]

GOALS = [
    q("goals", "Any basketball goal work?", tasks=[{"name": "Basketball goal install", "only_remove": True},
                                                  {"name": "Basketball goal removal", "only_remove": True}]),
    q("goals_work", "Replace the goals that are there, or install new ones?", "choice", options=[REPLACE, NEW], show_if=when_yes("goals"),
      tasks=[{"name": "Basketball goal removal", "when": REPLACE, "qty": "goal_count"},
             {"name": "Basketball goal install", "when": [REPLACE, NEW], "qty": "goal_count"}]),
    q("goal_count", "How many goals?", "number", unit="goals", show_if=when_yes("goals")),
    q("goal_type", "What kind of goal do they want?", "choice", show_if=when_yes("goals"),
      options=["In-ground, fixed height", "In-ground, adjustable", "Portable", "Wall-mount", "Other"]),
    q("goal_footing", "Are the old goals set in concrete?", "choice", options=["Yes", "No", "Not sure"], show_if={"goals_work": REPLACE},
      help="Tearing out an old footing takes longer and may need a core drill or jackhammer."),
]

WINDSCREEN = [
    q("windscreen", "Any windscreen work?", tasks=[{"name": "Windscreen install", "only_remove": True},
                                                 {"name": "Windscreen removal", "only_remove": True}]),
    q("windscreen_work", "Replace the windscreen that's there, or put up new?", "choice", options=[REPLACE, NEW],
      show_if=when_yes("windscreen"),
      tasks=[{"name": "Windscreen removal", "when": REPLACE, "qty": "windscreen_lf"},
             {"name": "Windscreen install", "when": [REPLACE, NEW], "qty": "windscreen_lf"}]),
    q("windscreen_lf", "How many feet of windscreen?", "number", unit="LF", show_if=when_yes("windscreen")),
    q("windscreen_color", "Windscreen color", "text", show_if=when_yes("windscreen")),
]

FENCE = [
    q("fence", "Any fence work?", tasks=[{"name": n, "only_remove": True} for n in
                                        ("Fence repair", "Fence removal", "Chain-link fence, new", "Gate install")]),
    q("fence_work", "Repair it, replace it, or put up a new fence?", "choice", options=["Repair", "Replace", "New fence"],
      show_if=when_yes("fence"),
      tasks=[{"name": "Fence repair", "when": "Repair", "qty": "fence_lf"},
             {"name": "Fence removal", "when": "Replace", "qty": "fence_lf"},
             {"name": "Chain-link fence, new", "when": ["Replace", "New fence"], "qty": "fence_lf"},
             {"name": "Gate install", "when": ["Replace", "New fence"], "qty": "gates"}]),
    q("fence_lf", "About how many feet of fence?", "number", unit="LF", show_if=when_yes("fence")),
    q("fence_notes", "What's wrong with it?", "text", show_if={"fence_work": "Repair"}, required=True),
    q("fence_height", "How tall?", "choice", options=["4 ft", "6 ft", "8 ft", "10 ft", "12 ft", "Other"],
      show_if={"fence_work": ["Replace", "New fence"]}),
    q("gates", "How many gates?", "number", unit="gates", show_if={"fence_work": ["Replace", "New fence"]}),
]

EXTRAS = [
    q("amenities", "Benches, ball holders or other amenities?", tasks=[{"name": "Site amenities install"}]),
    q("amenities_notes", "What, and how many?", "text", show_if=when_yes("amenities"), required=True),
    q("lighting", "Any lighting work?", tasks=[{"name": "Court lighting"}]),
    q("lighting_notes", "What do they want lit?", "text", show_if=when_yes("lighting"), required=True),
    q("power_ft", "About how far is the nearest electrical service (panel, meter or transformer) from the court?", "number",
      unit="ft", show_if=when_yes("lighting"),
      help="They may have power, but if it's a quarter mile away, running it there is a big part of the price."),
]

SITE = [
    q("water", "Is there water we can use within hose reach of the court?"),
    q("power", "Is there power we can use?"),
    q("truck_access", "Can a truck and trailer get to the court?"),
    q("access_notes", "How do we get equipment and material in? (gate widths, distance to carry)", "text",
      show_if={"truck_access": "no"}, required=True),
    q("staging", "Where can we park and stage material?", "text"),
    q("rules", "Work-hour limits, HOA or gate rules?"),
    q("rules_notes", "What are they?", "text", show_if=when_yes("rules"), required=True),
    q("timeline", "When do they want it done? Any events it has to be ready for?", "text"),
    q("photos", "Photos added of the whole court, the cracks and problem spots?",
      help="Add them in Photos on the lead, straight from the camera roll."),
]

NEW_SITE = [
    q("site_now", "What's there now?", "choice", options=["Open grass or field", "Light brush", "Heavy woods", "An old court or slab", "Other"],
      tasks=[{"name": "Clearing and grubbing, grass", "when": "Open grass or field", "qty": "clear_acres"},
             {"name": "Clearing and grubbing, light brush", "when": "Light brush", "qty": "clear_acres"},
             {"name": "Clearing and grubbing, heavy woods", "when": "Heavy woods", "qty": "clear_acres"},
             {"name": "Demolition of existing court", "when": "An old court or slab", "qty": "surface"}]),
    q("clear_acres", "How much of the land needs clearing?", "number", unit="acres",
      show_if={"site_now": ["Open grass or field", "Light brush", "Heavy woods"]},
      help="Just the court area, or the whole lot? A 10-acre parcel might all need clearing, or only the half acre the courts sit on. "
           "1 acre = 43,560 SF."),
    q("grade_acres", "How much of the land needs grading?", "number", unit="acres",
      tasks=[{"name": "Rough grading", "qty": "grade_acres", "when_answered": True}],
      help="Usually the same area as the clearing, plus room around the courts."),
    q("slope", "Is the ground flat or sloped?", "choice", options=["Flat", "Gentle slope", "Steep slope"]),
    q("fall_ft", "About how many feet of fall across the court area?", "number", unit="ft",
      show_if={"slope": ["Gentle slope", "Steep slope"]}),
    q("drainage", "Any drainage problems (standing water, runoff onto the site)?", tasks=[{"name": "French drain"}]),
    q("drainage_notes", "Where does the water come from and go?", "text", show_if=when_yes("drainage"), required=True),
    q("irrigation", "Sprinklers in the way?", tasks=[{"name": "Irrigation relocation"}]),
    q("utilities", "Any underground utilities or septic near the court?"),
    q("utilities_notes", "What, and where?", "text", show_if=when_yes("utilities"), required=True),
    q("plans", "Is there a survey, site plan or drawings?"),
    q("permits", "Does the city, county or HOA need permits or approval?", "choice", options=["Yes", "No", "Not sure"],
      tasks=[{"name": "Permits and inspections", "when": "Yes"}]),
]

NEW_COURT = [
    q("base", "What base do they want?", "choice", options=["Asphalt", "Concrete", "Not decided"],
      tasks=[{"name": "Asphalt paving", "when": "Asphalt", "qty": "surface"},
             *({"name": n, "when": "Concrete", "qty": qty} for n, qty in (
                 ("Court slab: forms", None), ("Court slab: vapor barrier", "surface"), ("Court slab: rebar and mesh", "surface"),
                 ("Court slab: pour and place", None), ("Court slab: finish", "surface")))]),
    q("sidewalks", "Sidewalks or concrete pads to go with it?", tasks=[{"name": "Sidewalks and flatwork", "qty": "sidewalk_sf"}]),
    q("sidewalk_sf", "About how many square feet?", "number", unit="SF", show_if=when_yes("sidewalks")),
    *LINES[:2],
    LINES[3],
    q("net_count", "How many nets?", "number", unit="nets", courts=NET_COURTS,
      tasks=[{"name": "Install nets and center straps", "qty": "net_count", "when_answered": True}]),
    q("net_type", "What kind of net?", "choice", options=["Tennis", "Pickleball", "Portable pickleball", "Other"], courts=NET_COURTS),
    q("goals_new", "Basketball goals?", courts=HOOP_COURTS, tasks=[{"name": "Basketball goal install", "qty": "goal_count"}]),
    q("goal_count", "How many goals?", "number", unit="goals", show_if=when_yes("goals_new"), courts=HOOP_COURTS),
    q("goal_type", "What kind of goal do they want?", "choice", show_if=when_yes("goals_new"), courts=HOOP_COURTS,
      options=["In-ground, fixed height", "In-ground, adjustable", "Portable", "Wall-mount", "Other"]),
    q("fence_new", "Do they want a fence?", tasks=[{"name": "Chain-link fence, new", "qty": "fence_lf"},
                                                  {"name": "Gate install", "qty": "gates"}]),
    q("fence_lf", "About how many feet of fence?", "number", unit="LF", show_if=when_yes("fence_new")),
    q("fence_height", "How tall?", "choice", options=["4 ft", "6 ft", "8 ft", "10 ft", "12 ft", "Other"], show_if=when_yes("fence_new")),
    q("gates", "How many gates?", "number", unit="gates", show_if=when_yes("fence_new")),
    q("windscreen_new", "Do they want windscreen?", tasks=[{"name": "Windscreen install", "qty": "windscreen_lf"}]),
    q("windscreen_lf", "How many feet of windscreen?", "number", unit="LF", show_if=when_yes("windscreen_new")),
    q("windscreen_color", "Windscreen color", "text", show_if=when_yes("windscreen_new")),
    *EXTRAS,
]

# ---------- buildings: concession stand, restrooms, storage… ----------
# With plans in hand we just need them. Without, plans have to be drawn, and
# that costs money, so ask everything now and get it right the first time.

NO_PLANS = ["Some sketches or ideas", "No plans"]


def _no_plans(**kw):
    return {"bldg_plans": NO_PLANS, **kw}


BUILDINGS = [
    q("bldg", "Do they want any buildings? (concession stand, restrooms, storage, pavilion)",
      tasks=[{"name": "Building construction"}]),
    q("bldg_types", "Which ones?", "multi", show_if=when_yes("bldg"),
      options=["Concession stand", "Restrooms", "Storage", "Pavilion or shade structure", "Pro shop or office", "Other"]),
    q("bldg_together", "One building, or separate buildings?", "choice", show_if=when_yes("bldg"),
      options=["Everything in one building", "Separate buildings", "Some together, some separate"],
      help="A concession stand and restrooms under one roof is a very different job from two buildings."),
    q("bldg_together_notes", "What goes together, and what's on its own?", "text", required=True,
      show_if={"bldg_together": "Some together, some separate"}),
    q("bldg_count", "How many buildings in all?", "number", unit="buildings", show_if={"bldg_together": ["Separate buildings", "Some together, some separate"]}),
    q("bldg_plans", "Do they already have plans for the building?", "choice", show_if=when_yes("bldg"),
      options=["Yes, drawn plans", *NO_PLANS],
      tasks=[{"name": "Building plans and engineering", "when": NO_PLANS}]),
    # they have plans: just get them
    q("bldg_plans_added", "Plans added to the lead (link or photos)?", show_if={"bldg_plans": "Yes, drawn plans"}),
    q("bldg_permit", "Are the plans approved or permitted yet?", "choice", show_if={"bldg_plans": "Yes, drawn plans"},
      options=["Approved", "Submitted", "Not yet", "Not sure"]),
    q("bldg_designer", "Who drew them? (architect or engineer, phone)", "text", show_if={"bldg_plans": "Yes, drawn plans"}),
    # no plans: what exactly do they want?
    q("bldg_length", "About how long? (outside)", "number", unit="ft", show_if=_no_plans(bldg_together="Everything in one building")),
    q("bldg_width", "About how wide?", "number", unit="ft", show_if=_no_plans(bldg_together="Everything in one building")),
    q("bldg_sizes", "Each building: what's in it and about how big? (e.g. Restrooms 20 × 24; Concession 16 × 20)", "text", required=True,
      show_if=_no_plans(bldg_together=["Separate buildings", "Some together, some separate"])),
    q("bldg_stories", "How many stories?", "choice", options=["1", "2"], show_if=_no_plans()),
    q("bldg_build", "What kind of building?", "choice", show_if=_no_plans(),
      options=["Block (CMU)", "Wood frame", "Metal building", "Prefab or modular", "Not sure"]),
    q("bldg_roof", "Roof?", "choice", options=["Shingle", "Metal", "Flat", "Match what's there", "Not sure"], show_if=_no_plans()),
    q("bldg_match", "Should it match a building already on site?", show_if=_no_plans()),
    q("bldg_match_notes", "Which one, and what about it? (colors, roof, trim)", "text", show_if={"bldg_match": "yes"}, required=True),
    q("bldg_location", "Where on the site does it go?", "text", show_if=_no_plans(), required=True,
      help="Mark it on a photo or sketch if you can and add it to the lead."),
    # restrooms
    q("rr_layout", "Restrooms: what layout?", "choice", show_if=_no_plans(bldg_types="Restrooms"),
      options=["One unisex", "Two unisex", "Men's and women's", "Other"]),
    q("rr_toilets", "Toilets in each restroom?", "number", unit="toilets", show_if={"rr_layout": ["One unisex", "Two unisex", "Other"]}),
    q("rr_toilets_women", "Toilets in the women's room?", "number", unit="toilets", show_if={"rr_layout": "Men's and women's"},
      help="Usually more than the men's, since the men's has urinals."),
    q("rr_toilets_men", "Toilets in the men's room?", "number", unit="toilets", show_if={"rr_layout": "Men's and women's"}),
    q("rr_urinals", "Urinals in the men's room?", "number", unit="urinals", show_if={"rr_layout": "Men's and women's"}),
    q("rr_sinks", "Sinks in each restroom?", "number", unit="sinks", show_if=_no_plans(bldg_types="Restrooms")),
    q("rr_extras", "Anything else in the restrooms?", "multi", show_if=_no_plans(bldg_types="Restrooms"),
      options=["Baby changing station", "Hand dryers", "Paper towels", "Showers", "Family / changing room", "Drinking fountain outside", "Other"]),
    # concession stand
    q("cs_food", "Concession stand: what will they serve?", "choice", show_if=_no_plans(bldg_types="Concession stand"),
      options=["Drinks and prepackaged snacks only", "Hot food (grill, fryer)", "Not sure yet"],
      help="Hot food means a vent hood, fire suppression and a grease trap, and a tougher health inspection."),
    q("cs_windows", "How many serving windows?", "number", unit="windows", show_if=_no_plans(bldg_types="Concession stand")),
    q("cs_equipment", "What equipment needs a spot (and power or water)?", "multi", show_if=_no_plans(bldg_types="Concession stand"),
      options=["Fridge / freezer", "Ice machine", "3-compartment sink", "Hand sink", "Grill or fryer", "Vent hood", "Other"]),
    q("cs_storage", "A storage room inside the stand?", show_if=_no_plans(bldg_types="Concession stand")),
    # storage
    q("st_contents", "Storage: what's kept in it? (mowers, nets, chairs…)", "text", show_if=_no_plans(bldg_types="Storage"), required=True),
    q("st_door", "Roll-up or garage door?", show_if=_no_plans(bldg_types="Storage")),
    q("st_door_size", "Door size (width × height)", "text", show_if={"st_door": "yes"}),
    # pavilion
    q("pv_size", "Pavilion: about how big, and how many people should it seat?", "text",
      show_if=_no_plans(bldg_types="Pavilion or shade structure"), required=True),
    q("pv_sides", "Open sides, or enclosed?", "choice", options=["Open", "Partly enclosed", "Enclosed"],
      show_if=_no_plans(bldg_types="Pavilion or shade structure")),
    # utilities and features, any building
    q("bldg_water", "Water to the building?", "choice", options=["City water nearby", "Well", "None nearby", "Not sure"], show_if=_no_plans()),
    q("bldg_water_ft", "About how far to the water line?", "number", unit="ft", show_if={"bldg_water": ["City water nearby", "Well"]}),
    q("bldg_sewer", "Sewer?", "choice", options=["City sewer nearby", "Needs a septic system", "Not needed", "Not sure"], show_if=_no_plans()),
    q("bldg_sewer_ft", "About how far to the sewer line?", "number", unit="ft", show_if={"bldg_sewer": "City sewer nearby"}),
    q("bldg_power_ft", "About how far to the nearest electrical service?", "number", unit="ft", show_if=_no_plans()),
    q("bldg_ac", "Air conditioning?", "choice", show_if=_no_plans(),
      options=["Whole building", "Just the office or concession", "No, fans only", "Not sure"]),
    q("bldg_features", "Anything else they want?", "multi", show_if=_no_plans(),
      options=["Lights inside and out", "Security cameras", "Wi-Fi", "Bottle filler / fountain", "Covered porch", "Signs", "Other"]),
    q("bldg_budget", "Do they have a budget in mind for the building?", "text", show_if=when_yes("bldg")),
    q("bldg_draw", "Do they want us to get the plans drawn?", show_if=_no_plans()),
]

CHECKLISTS = {
    "resurfacing": [
        {"title": "Surface", "questions": [SURFACE, *CRACKS, *SURFACE_PROBLEMS]},
        {"title": "Lines and color", "questions": LINES},
        {"title": "Nets and posts", "questions": NETS_POSTS, "courts": NET_COURTS},
        {"title": "Basketball goals", "questions": GOALS, "courts": HOOP_COURTS},
        {"title": "Fence, screens and extras", "questions": [*FENCE, *WINDSCREEN, *EXTRAS]},
        {"title": "Buildings", "questions": BUILDINGS},
        {"title": "Site and access", "questions": SITE},
    ],
    "repair": [
        {"title": "Surface", "questions": [SURFACE, *CRACKS, *SURFACE_PROBLEMS]},
        {"title": "Color and lines", "questions": [
            q("recoat", "New color on the whole court, or just over the repairs?", "choice", options=["Whole court", "Just the repairs"]),
            q("relines", "Do the lines need repainting?", tasks=[{"name": "Line painting"}]),
            LINES[3],
        ]},
        {"title": "Nets and posts", "questions": NETS_POSTS, "courts": NET_COURTS},
        {"title": "Basketball goals", "questions": GOALS, "courts": HOOP_COURTS},
        {"title": "Site and access", "questions": SITE},
    ],
    "new_construction": [
        {"title": "The site", "questions": NEW_SITE},
        {"title": "The court", "questions": NEW_COURT},
        {"title": "Buildings", "questions": BUILDINGS},
        {"title": "Getting in", "questions": SITE},
    ],
}

def _with_other_boxes(sections: list[dict]) -> list[dict]:
    """Right after every choice with "Other", a box to say what it is."""
    out = []
    for sec in sections:
        qs = []
        for qq in sec["questions"]:
            qs.append(qq)
            if qq["kind"] in ("choice", "multi") and "Other" in qq.get("options", []):
                extra = {k: qq[k] for k in ("courts",) if k in qq}
                qs.append(q(f"{qq['id']}_other", "What is it?", "text", show_if={qq["id"]: "Other"}, required=True,
                            long_label=f"{qq['label']} (other)", **extra))
        out.append({**sec, "questions": qs})
    return out


CHECKLISTS = {k: _with_other_boxes(v) for k, v in CHECKLISTS.items()}

# The court size block every checklist starts with (sales_schemas.CourtInfo).
COURT_BLOCK = {"title": "Court size", "help": "Number of courts and the size of one, or a measured total for odd shapes."}


def checklist(scope: str | None) -> list[dict]:
    return deepcopy(CHECKLISTS.get(scope or "", []))


def _for_court(item: dict, court: str | None) -> bool:
    return not court or not item.get("courts") or court in item["courts"]


def questions(scope: str | None, court: str | None):
    """The questions that apply to this kind of work and court, in order."""
    for sec in checklist(scope):
        if _for_court(sec, court):
            for qq in sec["questions"]:
                if _for_court(qq, court):
                    yield qq


def _shown(question: dict, answers: dict) -> bool:
    cond = question.get("show_if")
    if not cond:
        return True
    for qid, want in cond.items():
        have = answers.get(qid)
        wants = want if isinstance(want, list) else [want]
        if isinstance(have, list):
            if not set(have) & set(wants):
                return False
        elif have not in wants:
            return False
    return True


def _answered(question: dict, v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, list):
        return bool(v)
    return True


def tidy(scope: str | None, answers: dict, court: str | None = None) -> dict:
    """Keep only answers (and notes) to questions in this checklist that are
    showing. A follow-up whose yes was changed to no is dropped with it."""
    out = {}
    for qq in questions(scope, court):  # a follow-up always comes after the question it hangs off
        if not _shown(qq, out):
            continue
        v = answers.get(qq["id"])
        if _answered(qq, v):
            out[qq["id"]] = v.strip() if isinstance(v, str) else v
        note = answers.get(f"{qq['id']}_note")
        if isinstance(note, str) and note.strip() and qq["kind"] != "text":
            out[f"{qq['id']}_note"] = note.strip()
    return out


def progress(scope: str | None, survey: dict, court_type: str | None = None) -> dict | None:
    """How much of the checklist is filled in: {done, total, missing: [labels]}."""
    if not checklist(scope):
        return None
    answers = survey.get("answers", {})
    court = survey.get("court", {})
    has_size = bool(court.get("surface_sf") or (court.get("length_ft") and court.get("width_ft")))
    done, total, missing = (1 if has_size else 0), 1, ([] if has_size else ["Court size"])
    for qq in questions(scope, court_type):
        if not qq["required"] or not _shown(qq, answers):
            continue
        total += 1
        if _answered(qq, answers.get(qq["id"])):
            done += 1
        else:
            missing.append(qq.get("long_label", qq["label"]))
    return {"done": done, "total": total, "missing": missing}


def labels(scope: str | None) -> dict[str, dict]:
    """Question id -> question, across every checklist (so answers saved under
    an older scope still have their label)."""
    out = {}
    for s in [scope or "", *CHECKLISTS]:
        for sec in CHECKLISTS.get(s, []):
            for qq in sec["questions"]:
                # "What is it?" means little in the history on its own
                out.setdefault(qq["id"], {**qq, "label": qq.get("long_label", qq["label"])})
    for qid, qq in list(out.items()):
        if qq["kind"] != "text":
            out[f"{qid}_note"] = {"id": f"{qid}_note", "label": f"Note on: {qq['label']}", "kind": "text"}
    return out


def answer_text(question: dict | None, v) -> str:
    if v is None or v == "" or v == []:
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if v in ("yes", "no"):
        return v.capitalize()
    if isinstance(v, list):
        return ", ".join(v)
    if isinstance(v, float):
        v = int(v) if v.is_integer() else v
    unit = (question or {}).get("unit")
    return f"{v:,} {unit}" if unit and isinstance(v, (int, float)) else str(v)
