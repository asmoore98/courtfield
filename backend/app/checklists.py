"""The site checklist sales fills in on site, one per kind of work.

Every lead gets the court size block, then the questions for its scope.
Follow-up questions only show once the question they hang off is answered a
certain way ("show_if"): cracks? yes -> how many feet, how wide.

"tasks" ties an answer to the task library: when the answer matches "when",
an estimate started from the lead gets that task, with its quantity taken
from "qty" (another question, or the court size). Any other answer takes the
task off the starter list. Names match the starter task list.

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
    q("posts", "Do the posts need replaced?", tasks=[{"name": "Install net posts", "qty": "post_count"}]),
    q("post_count", "How many posts?", "number", unit="posts", show_if=when_yes("posts")),
    q("post_type", "What kind of posts?", "choice", options=["Round", "Square", "Not sure"], show_if=when_yes("posts")),
    q("sleeves_ok", "Are the post sleeves and footers in good shape?", show_if=when_yes("posts"),
      tasks=[{"name": "Core drill post sleeves", "when": "no", "qty": "post_count"}]),
]

EXTRAS = [
    q("windscreen", "Do they want windscreen?", tasks=[{"name": "Windscreen install", "qty": "windscreen_lf"}]),
    q("windscreen_lf", "How many feet of windscreen?", "number", unit="LF", show_if=when_yes("windscreen")),
    q("windscreen_color", "Windscreen color", "text", show_if=when_yes("windscreen")),
    q("fence_repair", "Does the fence need repairs?", tasks=[{"name": "Fence repair", "qty": "fence_lf"}]),
    q("fence_lf", "About how many feet of fence need work?", "number", unit="LF", show_if=when_yes("fence_repair")),
    q("fence_notes", "What's wrong with it?", "text", show_if=when_yes("fence_repair"), required=True),
    q("goals", "Basketball goals to install or replace?", tasks=[{"name": "Basketball goal install", "qty": "goal_count"}]),
    q("goal_count", "How many goals?", "number", unit="goals", show_if=when_yes("goals")),
    q("amenities", "Benches, ball holders or other amenities?", tasks=[{"name": "Site amenities install"}]),
    q("amenities_notes", "What, and how many?", "text", show_if=when_yes("amenities"), required=True),
    q("lighting", "Any lighting work?", tasks=[{"name": "Court lighting"}]),
    q("lighting_notes", "What do they want lit, and is there power there now?", "text", show_if=when_yes("lighting"), required=True),
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
    q("photos", "Photos of the whole court, the cracks and problem spots added to the lead's links?"),
]

NEW_SITE = [
    q("site_now", "What's there now?", "choice", options=["Open grass or field", "Trees or brush", "An old court or slab", "Other"],
      tasks=[{"name": "Clearing and grubbing", "when": "Trees or brush", "qty": "surface"},
             {"name": "Demolition of existing court", "when": "An old court or slab", "qty": "surface"}]),
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
    q("base", "What base do they want?", "choice", options=["Asphalt", "Post-tensioned concrete", "Not decided"],
      tasks=[{"name": "Asphalt paving", "when": "Asphalt", "qty": "surface"},
             {"name": "Post-tensioned concrete slab", "when": "Post-tensioned concrete", "qty": "surface"}]),
    *LINES[:2],
    LINES[3],
    q("net_count", "How many nets?", "number", unit="nets"),
    q("net_type", "What kind of net?", "choice", options=["Tennis", "Pickleball", "Portable pickleball", "Other"]),
    q("fence_new", "Do they want a fence?", tasks=[{"name": "Chain-link fence, new", "qty": "fence_lf"}]),
    q("fence_lf", "About how many feet of fence?", "number", unit="LF", show_if=when_yes("fence_new")),
    q("fence_height", "How tall?", "choice", options=["4 ft", "6 ft", "8 ft", "10 ft", "12 ft"], show_if=when_yes("fence_new")),
    q("gates", "How many gates?", "number", unit="gates", show_if=when_yes("fence_new")),
    *EXTRAS[:3],
    *EXTRAS[6:],
]

CHECKLISTS = {
    "resurfacing": [
        {"title": "Surface", "questions": [SURFACE, *CRACKS, *SURFACE_PROBLEMS]},
        {"title": "Lines and color", "questions": LINES},
        {"title": "Nets and posts", "questions": NETS_POSTS},
        {"title": "Fence, screens and extras", "questions": EXTRAS},
        {"title": "Site and access", "questions": SITE},
    ],
    "repair": [
        {"title": "Surface", "questions": [SURFACE, *CRACKS, *SURFACE_PROBLEMS]},
        {"title": "Color and lines", "questions": [
            q("recoat", "New color on the whole court, or just over the repairs?", "choice", options=["Whole court", "Just the repairs"]),
            q("relines", "Do the lines need repainting?", tasks=[{"name": "Line painting", "qty": "courts"}]),
            LINES[3],
        ]},
        {"title": "Nets and posts", "questions": NETS_POSTS},
        {"title": "Site and access", "questions": SITE},
    ],
    "new_construction": [
        {"title": "The site", "questions": NEW_SITE},
        {"title": "The court", "questions": NEW_COURT},
        {"title": "Getting in", "questions": SITE},
    ],
}

# The court size block every checklist starts with (sales_schemas.CourtInfo).
COURT_BLOCK = {"title": "Court size", "help": "Number of courts and the size of one, or a measured total for odd shapes."}


def checklist(scope: str | None) -> list[dict]:
    return deepcopy(CHECKLISTS.get(scope or "", []))


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


def tidy(scope: str | None, answers: dict) -> dict:
    """Keep only answers to questions in this checklist that are showing.
    A follow-up whose yes was changed to no is dropped with it."""
    out = {}
    for sec in checklist(scope):
        for qq in sec["questions"]:  # a follow-up always comes after the question it hangs off
            v = answers.get(qq["id"])
            if _shown(qq, out) and _answered(qq, v):
                out[qq["id"]] = v
    return out


def progress(scope: str | None, survey: dict) -> dict | None:
    """How much of the checklist is filled in: {done, total, missing: [labels]}."""
    secs = checklist(scope)
    if not secs:
        return None
    answers = survey.get("answers", {})
    court = survey.get("court", {})
    has_size = bool(court.get("surface_sf") or (court.get("length_ft") and court.get("width_ft")))
    done, total, missing = (1 if has_size else 0), 1, ([] if has_size else ["Court size"])
    for sec in secs:
        for qq in sec["questions"]:
            if not qq["required"] or not _shown(qq, answers):
                continue
            total += 1
            if _answered(qq, answers.get(qq["id"])):
                done += 1
            else:
                missing.append(qq["label"])
    return {"done": done, "total": total, "missing": missing}


def labels(scope: str | None) -> dict[str, dict]:
    """Question id -> question, across every checklist (so answers saved under
    an older scope still have their label)."""
    out = {}
    for s in [scope or "", *CHECKLISTS]:
        for sec in CHECKLISTS.get(s, []):
            for qq in sec["questions"]:
                out.setdefault(qq["id"], qq)
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
