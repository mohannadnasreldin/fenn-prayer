"""Location and prayer timings: geojs IP, Open-Meteo geocode, Aladhan API.
Standard library only."""

import json
import time
import urllib.parse
import urllib.request
from datetime import date

AGENT = "fenn-prayer (+https://fenn.click)"
IP_GEO = "https://get.geojs.io/v1/ip/geo.json"
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
ALADHAN = "https://api.aladhan.com/v1/timings"

METHODS = [
    (3, "Muslim World League"),
    (2, "ISNA"),
    (5, "Egypt"),
    (4, "Umm Al-Qura"),
    (1, "Karachi"),
    (13, "Diyanet"),
]

METHOD_IDS = [m[0] for m in METHODS]
METHOD_LABELS = [m[1] for m in METHODS]


def get_json(url, params=None, timeout=12):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def place_from_ip():
    """City-level location from the IP address (geojs.io, no key)."""
    d = get_json(IP_GEO)
    return {
        "name": d.get("city") or d.get("region") or "Your location",
        "region": d.get("region") or "",
        "country": d.get("country") or "",
        "lat": float(d["latitude"]),
        "lon": float(d["longitude"]),
    }


def search_places(query, language="en"):
    d = get_json(GEOCODE, {"name": query, "count": 6, "language": language, "format": "json"})
    out = []
    for r in d.get("results") or []:
        out.append({
            "name": r.get("name") or query,
            "region": r.get("admin1") or "",
            "country": r.get("country") or "",
            "lat": float(r["latitude"]),
            "lon": float(r["longitude"]),
        })
    return out


def place_line(p):
    rest = p.get("country") or p.get("region") or ""
    return f"{p['name']}, {rest}" if rest and rest != p["name"] else p["name"]


def timings(place, method=3, school=0, day=None):
    """Today's prayer timings for lat/lon. day: date or None = today."""
    d = day or date.today()
    path = f"{ALADHAN}/{d.day:02d}-{d.month:02d}-{d.year}"
    body = get_json(path, {
        "latitude": round(place["lat"], 4),
        "longitude": round(place["lon"], 4),
        "method": int(method),
        "school": int(school),
    })
    data = body.get("data") or {}
    out = {
        "v": 1,
        "fetched": time.time(),
        "date": d.isoformat(),
        "place": place,
        "method": int(method),
        "school": int(school),
        "timings": data.get("timings") or {},
        "hijri": (data.get("date") or {}).get("hijri") or {},
        "gregorian": (data.get("date") or {}).get("gregorian") or {},
        "meta": data.get("meta") or {},
    }
    return out
