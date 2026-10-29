"""Turn a street address into a map pin for a job.

Uses the U.S. Census Bureau geocoder: free, no account or key, U.S.
addresses only. It knows addresses that existed when its data was last
updated, so brand-new lots may not be found; the job form falls back to
"Use my current location" or typed coordinates.
"""
import json
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import EDITS_JOBS, require_roles
from ..models import User

router = APIRouter(prefix="/api/geocode", tags=["geocode"])

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def census_lookup(address: str) -> dict | None:
    """Best match for `address` as {lat, lng, matched_address}, or None.
    Raises OSError / ValueError when the service can't be reached or answers
    with something unexpected."""
    qs = urllib.parse.urlencode({"address": address, "benchmark": "Public_AR_Current", "format": "json"})
    req = urllib.request.Request(f"{CENSUS_URL}?{qs}", headers={"User-Agent": "Courtfield job-costing"})
    with urllib.request.urlopen(req, timeout=10) as res:  # noqa: S310 - fixed https URL
        data = json.load(res)
    matches = data.get("result", {}).get("addressMatches") or []
    if not matches:
        return None
    best = matches[0]
    c = best["coordinates"]
    return {"lat": round(float(c["y"]), 6), "lng": round(float(c["x"]), 6), "matched_address": best.get("matchedAddress", "")}


@router.get("")
def geocode(address: str = Query(min_length=5, max_length=300), _user: User = Depends(require_roles(*EDITS_JOBS))):
    try:
        hit = census_lookup(address.strip())
    except (OSError, ValueError, KeyError):
        raise HTTPException(502, "The address lookup isn't answering right now. Try again, or use your current location.")
    if hit is None:
        raise HTTPException(
            404,
            "Couldn't find that address. Include the city and ZIP. New lots often aren't listed yet; "
            "use your current location on site or type the coordinates.",
        )
    return hit
