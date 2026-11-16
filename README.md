# Prayer for Fenn

Islamic prayer times on a Fenn tile: next prayer and countdown in the notch,
today's schedule and Hijri date on the page.

## Requirements

Windows and Python 3 (standard library only; Fenn can install Python for you).

## Install

```powershell
git clone https://github.com/mohannadnasreldin/fenn-prayer.git "$env:APPDATA\Fenn\plugins\prayer"
```

Or use **Install** on the Fenn marketplace listing once it is reviewed.
Fenn picks the folder up on its own; restart once so the page gets its height.

## What it shows

- **Tile:** next prayer name, clock time, and countdown (small / wide / large).
- **Page:** place, Hijri date, Fajr–Isha list (Sunrise as info), progress to next.
- **Places:** auto city from IP, or search and save cities.
- **Settings:** calculation method (MWL, ISNA, Egypt, Umm Al-Qura, Karachi, Diyanet), Asr school (Shafi / Hanafi), 12/24-hour clock.
- **Badge:** ring that empties toward the next prayer.

## Privacy and network

- **Prayer timings:** `api.aladhan.com` gets your place's coordinates (rounded), calculation method and Asr school, once per day and when you change place or method.
- **City search:** `geocoding-api.open-meteo.com` gets what you type.
- **"My location"** asks `get.geojs.io` for the city of your connection's IP while auto location is on.
- No account, no API key, no tracking.

Kept in the plugin's data folder (`FENN_DATA_DIR`): `settings.json`, `timings.json` (and `timings_next.json` after Isha), and an empty `reloaded` marker for self-restart on code changes.

## Files

`main.py` (state, UI, fetch), `api.py` (IP, geocode, Aladhan), `times.py` (next prayer and countdown), `fenn.py` (Fenn Python helper).

## License

MIT, see [LICENSE](LICENSE). Timings by [AlAdhan](https://aladhan.com/). Places by [Open-Meteo](https://open-meteo.com/) geocoding; IP city from [geojs.io](https://www.geojs.io/).
