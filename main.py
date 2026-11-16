"""Prayer for Fenn: next prayer and countdown on the tile; today's times,
Hijri date, place search and calculation settings on the page.

Timings from Aladhan (free, no key); city from IP or Open-Meteo search.
"""

import os
import sys
import threading
import time
from datetime import date, datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

import api
import fenn
import times as t

HERE = os.path.dirname(os.path.abspath(__file__))
app = fenn.Plugin()

DEFAULTS = {
    "place": None,       # {"name","region","country","lat","lon"}
    "auto": True,        # use IP "my location"
    "auto_place": None,  # last IP place
    "places": [],        # saved places
    "method": 3,         # Muslim World League
    "school": 0,         # 0 Shafi, 1 Hanafi
    "clock24": True,
}
settings = {**DEFAULTS, **(app.load("settings", {}) or {})}

cache = app.load("timings")  # today's payload
cache_next = None            # tomorrow Fajr when needed
busy = False
error = ""
last_try = 0.0
view = "main"                # main | places | settings
results = None
search_gen = int(time.time()) % 100000
tile = ("wide", 104, 36)
page_sent = False


def save_settings():
    app.save("settings", settings)


def active_place():
    if settings["auto"]:
        return settings.get("auto_place") or settings.get("place")
    return settings.get("place") or settings.get("auto_place")


def clock(dt):
    return t.format_clock(dt, settings["clock24"])


def cache_ok():
    if not cache or cache.get("v") != 1:
        return False
    if cache.get("date") != date.today().isoformat():
        return False
    p = active_place()
    if not p or not cache.get("place"):
        return False
    cp = cache["place"]
    if abs(cp.get("lat", 0) - p["lat"]) > 0.01 or abs(cp.get("lon", 0) - p["lon"]) > 0.01:
        return False
    if cache.get("method") != settings["method"] or cache.get("school") != settings["school"]:
        return False
    return True


def model_now():
    """Derived view of next prayer from cache, or None."""
    if not cache_ok():
        return None
    now = datetime.now()
    timings = cache.get("timings") or {}
    tomorrow = (cache_next or {}).get("timings") if cache_next else None
    nxt = t.next_prayer(now, timings, tomorrow)
    if not nxt:
        return None
    # If next is tomorrow Fajr and we lack tomorrow cache, still show with today Fajr+1d fallback
    return {
        "place": cache.get("place") or active_place(),
        "hijri": t.hijri_line(cache.get("hijri")),
        "schedule": t.schedule(date.today(), timings),
        "next": nxt,
        "countdown": t.countdown(nxt["dt"], now),
        "progress": t.ring_progress(now, timings, tomorrow),
        "now": now,
    }


# ---- fetch

def fetch(force=False):
    global cache, cache_next, busy, error, last_try
    if busy:
        return
    if not force and cache_ok() and time.time() - last_try < 60:
        return
    busy = True
    error = ""
    last_try = time.time()

    def work():
        global cache, cache_next, busy, error
        try:
            place = active_place()
            if settings["auto"] or not place:
                auto = api.place_from_ip()
                settings["auto_place"] = auto
                if settings["auto"]:
                    place = auto
                save_settings()
            if not place:
                raise RuntimeError("No location")
            today = api.timings(place, settings["method"], settings["school"])
            # Tomorrow needed after Isha for next Fajr
            now = datetime.now()
            isha = t.at(date.today(), "Isha", today.get("timings") or {})
            nxt_day = None
            if isha and now >= isha:
                nxt_day = api.timings(place, settings["method"], settings["school"],
                                      date.today() + timedelta(days=1))
            app._inbox.put({"type": "prayer_data", "today": today, "tomorrow": nxt_day})
        except Exception as e:
            app._inbox.put({"type": "prayer_err", "error": f"{type(e).__name__}: {e}"})

    threading.Thread(target=work, daemon=True).start()


def apply_data(msg):
    global cache, cache_next, busy, error
    busy = False
    error = ""
    cache = msg["today"]
    cache_next = msg.get("tomorrow")
    app.save("timings", cache)
    if cache_next:
        app.save("timings_next", cache_next)
    else:
        cache_next = None
    update_badge()
    draw()


def apply_err(msg):
    global busy, error
    busy = False
    error = msg.get("error") or "Offline"
    app.log(error, "error")
    draw()


def update_badge():
    m = model_now()
    if not m:
        app.clear_badge()
        return
    # Ring fills as we approach next prayer (invert progress through interval)
    remaining = 1.0 - m["progress"]
    label = t.SHORT.get(m["next"]["name"], m["next"]["name"])[:1]
    app.badge_ring(remaining, label)


# ---- views

def tile_view():
    size = tile[0] or "wide"
    m = model_now()
    if not m:
        label = "Loading" if busy or not error else "Offline"
        return fenn.column([
            fenn.icon("moon-stars", size=20, color="dim"),
            fenn.text(label, size="small", color="dim"),
        ], gap=2, align="center", justify="center")

    name = m["next"]["name"]
    when = clock(m["next"]["dt"])
    left = m["countdown"]

    if size == "small":
        return fenn.column([
            fenn.text(t.SHORT.get(name, name), size="small", bold=True),
            fenn.text(left, size="small", color="dim"),
        ], gap=1, align="center", justify="center")

    if size == "large":
        kids = [
            fenn.text(name, size="title", bold=True),
            fenn.text(when, size="big", bold=True),
            fenn.text(f"in {left}", size="body", color="dim"),
        ]
        if m["hijri"]:
            kids.append(fenn.text(m["hijri"], size="small", color="faint"))
        return fenn.column(kids, gap=4, align="center", justify="center")

    # wide
    return fenn.row([
        fenn.icon("moon-stars", size=22, color="accent"),
        fenn.column([
            fenn.text(name, size="small", bold=True),
            fenn.text(f"{when} · {left}", size="small", color="dim"),
        ], gap=1),
    ], gap=8, align="center")


def prayer_row(item, nxt_name):
    name, dt = item["name"], item["dt"]
    is_next = name == nxt_name and name != "Sunrise"
    is_info = name == "Sunrise"
    color = "accent" if is_next else ("faint" if is_info else "text")
    trailing = clock(dt)
    return fenn.row([
        fenn.icon("circle" if is_next else "circle-dashed", size=12,
                  color="accent" if is_next else "faint",
                  fill=True if is_next else None),
        fenn.text(name, size="body", bold=is_next, color=color),
        fenn.spacer(),
        fenn.text(trailing, size="body", bold=is_next, color=color, mono=True),
    ], gap=8, align="center")


def main_view():
    m = model_now()
    place = active_place()
    place_label = api.place_line(place) if place else "Set a place"
    parts = [
        fenn.row([
            fenn.icon("map-pin", size=14, color="dim"),
            fenn.text(place_label, size="small", color="dim", wrap=True),
        ], gap=4, align="center"),
    ]
    if m and m["hijri"]:
        parts.append(fenn.text(m["hijri"], size="small", color="faint"))

    if not m:
        parts.append(fenn.spacer(8))
        if error:
            parts += [
                fenn.text(error, size="small", color="red", wrap=True),
                fenn.button("retry", label="Retry", icon="arrow-clockwise", primary=True),
            ]
        else:
            parts.append(fenn.text("Loading prayer times…", size="body", color="dim"))
        return fenn.column(parts, gap=8, scroll=True, id="main")

    nxt = m["next"]
    parts += [
        fenn.card([
            fenn.text("Next", size="small", color="dim"),
            fenn.text(nxt["name"], size="title", bold=True),
            fenn.row([
                fenn.text(clock(nxt["dt"]), size="big", bold=True),
                fenn.spacer(),
                fenn.text(f"in {m['countdown']}", size="body", color="accent"),
            ], align="center"),
            fenn.progress(m["progress"], color="accent"),
        ], gap=6, padding=12),
        fenn.divider(),
    ]
    for item in m["schedule"]:
        parts.append(prayer_row(item, nxt["name"]))
    return fenn.column(parts, gap=8, scroll=True, id="main")


def places_view():
    parts = [
        fenn.text_input(f"search:{search_gen}", "", hint="Search city", width=0),
    ]
    auto_p = settings.get("auto_place")
    selected_auto = settings["auto"]
    parts.append(fenn.list_view([
        fenn.item("city:auto",
                  "My location",
                  subtitle=api.place_line(auto_p) if auto_p else "Detect from IP",
                  icon="crosshair",
                  selected=selected_auto),
    ]))

    saved = settings.get("places") or []
    if saved:
        items = []
        for i, p in enumerate(saved):
            sel = (not settings["auto"] and settings.get("place")
                   and abs(settings["place"]["lat"] - p["lat"]) < 1e-4
                   and abs(settings["place"]["lon"] - p["lon"]) < 1e-4)
            items.append(fenn.item(f"city:{i}", p["name"],
                                   subtitle=api.place_line(p),
                                   icon="map-pin", selected=sel))
        parts.append(fenn.list_view(items))

    if results and results.get("results"):
        parts.append(fenn.divider())
        parts.append(fenn.text("Results", size="small", color="dim", bold=True))
        items = []
        for i, p in enumerate(results["results"]):
            items.append(fenn.item(f"add:{i}", p["name"],
                                   subtitle=api.place_line(p), icon="plus"))
        parts.append(fenn.list_view(items))
    elif results is not None and not results.get("results"):
        parts.append(fenn.text("No places found.", size="small", color="dim"))

    return fenn.column(parts, gap=8, scroll=True, id="places")


def settings_view():
    method_idx = 0
    if settings["method"] in api.METHOD_IDS:
        method_idx = api.METHOD_IDS.index(settings["method"])
    parts = [
        fenn.text("Calculation", size="small", color="dim", bold=True),
        fenn.chips("method", api.METHOD_LABELS, selected=method_idx),
        fenn.text("Asr school", size="small", color="dim", bold=True),
        fenn.chips("school", ["Shafi / standard", "Hanafi"], selected=settings["school"]),
        fenn.divider(),
        fenn.text("Clock", size="small", color="dim", bold=True),
        fenn.chips("clock", ["24-hour", "12-hour"], selected=0 if settings["clock24"] else 1),
        fenn.divider(),
        fenn.toggle("auto", settings["auto"], label="Auto location (IP)"),
        fenn.text("Timings by Aladhan.com. Places by Open-Meteo geocoding; "
                  "IP city from geojs.io.", size="small", color="faint", wrap=True),
    ]
    return fenn.column(parts, gap=8, scroll=True, id="settings")


def actions():
    if view == "settings":
        return [{"id": "done", "icon": "check", "tooltip": "Done"}]
    if view == "places":
        return [{"id": "done", "icon": "x", "tooltip": "Close"}]
    return [
        {"id": "places", "icon": "map-pin", "tooltip": "Places"},
        {"id": "refresh", "icon": "arrows-clockwise", "tooltip": "Refresh"},
        {"id": "settings", "icon": "gear-six", "tooltip": "Method and clock"},
    ]


def draw():
    global page_sent
    try:
        app.tile(tile_view())
    except Exception as e:
        app.log(f"tile: {type(e).__name__}: {e}", "error")
    if app.page_open or not page_sent:
        body = {"settings": settings_view, "places": places_view}.get(view, main_view)()
        app.page(body, actions())
        page_sent = True


def show_place(place):
    """None = auto IP; else a place dict."""
    if place is None:
        settings["auto"] = True
    else:
        settings["auto"] = False
        settings["place"] = place
        # keep in recent list
        key = (round(place["lat"], 4), round(place["lon"], 4))
        settings["places"] = [p for p in settings["places"]
                              if (round(p["lat"], 4), round(p["lon"], 4)) != key]
        settings["places"].insert(0, place)
        settings["places"] = settings["places"][:8]
    save_settings()
    fetch(force=True)


def add_place(p):
    show_place(p)


def search(q):
    global results

    def work():
        try:
            found = api.search_places(q)
            app._inbox.put({"type": "search_done", "results": found, "q": q})
        except Exception as e:
            app._inbox.put({"type": "search_done", "results": [], "error": str(e)})

    threading.Thread(target=work, daemon=True).start()


# ---- events

@app.on_message("prayer_data")
def _(msg):
    apply_data(msg)


@app.on_message("prayer_err")
def _(msg):
    apply_err(msg)


@app.on_message("search_done")
def _(msg):
    global results
    results = {"results": msg.get("results") or []}
    if msg.get("error"):
        app.log(msg["error"], "error")
    draw()


@app.on_message("event")
def on_event(e):
    global view, results, search_gen
    eid, value, kind = e.get("id", ""), e.get("value"), e.get("kind")

    if eid == "settings":
        view, results = "settings", None
    elif eid == "places":
        view, results = "places", None
    elif eid == "done":
        view, results = "main", None
    elif eid == "refresh" or eid == "retry":
        fetch(force=True)
    elif eid.startswith("search:") and kind == "submit":
        q = (value or "").strip()
        if q:
            search(q)
    elif eid.startswith("add:") and results:
        k = int(eid[4:])
        if k < len(results["results"]):
            search_gen += 1
            p = results["results"][k]
            results = None
            view = "main"
            add_place(p)
            draw()
            return
    elif eid == "city:auto":
        view = "main"
        show_place(None)
        draw()
        return
    elif eid.startswith("city:") and eid[5:].isdigit():
        i = int(eid[5:])
        if i < len(settings["places"]):
            view = "main"
            show_place(settings["places"][i])
            draw()
            return
    elif eid == "method" and isinstance(value, dict):
        settings["method"] = api.METHOD_IDS[value["index"]]
        save_settings()
        fetch(force=True)
    elif eid == "school" and isinstance(value, dict):
        settings["school"] = value["index"]
        save_settings()
        fetch(force=True)
    elif eid == "clock" and isinstance(value, dict):
        settings["clock24"] = value["index"] == 0
        save_settings()
    elif eid == "auto":
        settings["auto"] = bool(value)
        save_settings()
        fetch(force=True)
    draw()


@app.on_message("layout")
def on_layout(msg):
    global tile
    if msg.get("target") == "tile":
        tile = (msg.get("size") or "wide", msg.get("width"), msg.get("height"))
    draw()


@app.on_message("page_open")
def on_open(_):
    fetch()
    draw()


@app.on_message("page_close")
def on_close(_):
    global view, results
    view, results = "main", None


@app.on_message("theme")
def on_theme(_):
    draw()


@app.on_message("hello")
def on_hello(_):
    draw()
    fetch()


def tick():
    # After midnight, cache date fails → refetch
    if cache and cache.get("date") != date.today().isoformat():
        fetch(force=True)
    else:
        # After Isha, ensure tomorrow timings
        m = model_now()
        if m and m["next"]["day"] > date.today() and not cache_next:
            fetch(force=True)
    update_badge()
    draw()


_stamps = {f: os.path.getmtime(os.path.join(HERE, f)) for f in os.listdir(HERE) if f.endswith(".py")}


def check_code():
    for f, stamp in _stamps.items():
        try:
            if os.path.getmtime(os.path.join(HERE, f)) != stamp:
                mark = os.path.join(app.data_dir, "reloaded")
                if os.path.exists(mark) and time.time() - os.path.getmtime(mark) < 25:
                    return
                open(mark, "w").close()
                app.stop()
                return
        except OSError:
            pass


# Warm tomorrow cache from disk if present
_next = app.load("timings_next")
if _next and _next.get("date") == (date.today() + timedelta(days=1)).isoformat():
    cache_next = _next

app.every(30, tick)
app.every(2, check_code)
draw()
fetch()
app.run()
