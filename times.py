"""Parse Aladhan timings into next prayer, countdown, and ring progress."""

from datetime import datetime, timedelta

# Shown on the page (Sunrise is informational only).
DISPLAY = ("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha")
# Next-prayer cycle skips Sunrise.
CYCLE = ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha")

SHORT = {
    "Fajr": "Fajr",
    "Sunrise": "Rise",
    "Dhuhr": "Dhuhr",
    "Asr": "Asr",
    "Maghrib": "Maghrib",
    "Isha": "Isha",
}


def _parse_hhmm(s):
    """Aladhan times look like '05:12' or '05:12 (EET)'."""
    if not s:
        return None
    part = str(s).strip().split()[0]
    try:
        h, m = part.split(":")[:2]
        return int(h), int(m)
    except (ValueError, TypeError):
        return None


def at(day, name, timings):
    """datetime for prayer name on calendar day, or None."""
    hm = _parse_hhmm((timings or {}).get(name))
    if not hm:
        return None
    return datetime(day.year, day.month, day.day, hm[0], hm[1])


def schedule(day, timings):
    """List of {name, dt} for DISPLAY prayers that parsed."""
    out = []
    for name in DISPLAY:
        dt = at(day, name, timings)
        if dt:
            out.append({"name": name, "dt": dt})
    return out


def next_prayer(now, timings, tomorrow_timings=None):
    """Next CYCLE prayer after now. If past Isha, uses tomorrow Fajr when given."""
    day = now.date()
    for name in CYCLE:
        dt = at(day, name, timings)
        if dt and dt > now:
            return {"name": name, "dt": dt, "day": day}
    # After Isha → tomorrow Fajr
    nxt = day + timedelta(days=1)
    src = tomorrow_timings if tomorrow_timings is not None else timings
    dt = at(nxt, "Fajr", src)
    if dt:
        return {"name": "Fajr", "dt": dt, "day": nxt}
    return None


def prev_prayer(now, timings, yesterday_timings=None):
    """Most recent CYCLE prayer at or before now (for ring progress)."""
    day = now.date()
    prev = None
    for name in CYCLE:
        dt = at(day, name, timings)
        if dt and dt <= now:
            prev = {"name": name, "dt": dt, "day": day}
        elif dt and dt > now:
            break
    if prev:
        return prev
    # Before Fajr → yesterday Isha
    yday = day - timedelta(days=1)
    src = yesterday_timings if yesterday_timings is not None else timings
    dt = at(yday, "Isha", src)
    if dt:
        return {"name": "Isha", "dt": dt, "day": yday}
    return None


def countdown(until, now=None):
    """Human remaining string like '2h 14m' or '45m'."""
    now = now or datetime.now()
    if until is None:
        return "–"
    secs = max(0, int((until - now).total_seconds()))
    h, rem = divmod(secs, 3600)
    m = rem // 60
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def ring_progress(now, timings, tomorrow_timings=None, yesterday_timings=None):
    """0..1 how far through the current interval (prev → next)."""
    nxt = next_prayer(now, timings, tomorrow_timings)
    prev = prev_prayer(now, timings, yesterday_timings)
    if not nxt or not prev:
        return 0.0
    total = (nxt["dt"] - prev["dt"]).total_seconds()
    if total <= 0:
        return 0.0
    done = (now - prev["dt"]).total_seconds()
    return max(0.0, min(1.0, done / total))


def hijri_line(hijri):
    """e.g. '15 Ramadan 1447'."""
    if not hijri:
        return ""
    day = hijri.get("day") or ""
    month = (hijri.get("month") or {}).get("en") or ""
    year = hijri.get("year") or ""
    parts = [p for p in (day, month, year) if p]
    return " ".join(parts)


def format_clock(dt, clock24=True):
    if dt is None:
        return "–"
    if clock24:
        return f"{dt.hour}:{dt.minute:02d}"
    h = dt.hour % 12 or 12
    ampm = "am" if dt.hour < 12 else "pm"
    return f"{h}:{dt.minute:02d} {ampm}"
