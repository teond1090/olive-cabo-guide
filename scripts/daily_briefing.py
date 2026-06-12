"""
Olive daily briefing — runs in GitHub Actions every morning (Cabo time).

1. Reads the family schedule from the ntfy events topic.
2. Re-publishes a full snapshot (ntfy only retains ~12h; this makes the
   schedule durable even if nobody opens Olive for days).
3. Fetches today's Cabo weather.
4. Posts a good-morning briefing (weather + today's agenda + a Cabo tip)
   to the family chat topic as "Olive".
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

EV_TOPIC = "olive-cabo-events-x9k4t2-2026"
CHAT_TOPIC = "olive-cabo-crew-x9k4t2-2026"
NTFY = "https://ntfy.sh/"
MAZATLAN = timezone(timedelta(hours=-7))  # America/Mazatlan (no DST)

TIPS = [
    "Morning water is glass-calm — best snorkeling is before 10 am. 🤿",
    "Pesos get better prices from beach vendors — and a smile gets the best ones. 😄",
    "The resort beach is for walking, not swimming — pools at home base, ocean swims at Chileno or Medano. 🌊",
    "Specialty restaurants at the Ziva fill up — ask the concierge about dinner in the morning. 🍽️",
    "Agree on the taxi fare BEFORE getting in, or use Uber. 🚕",
    "Reapply SPF 50 after every swim — the July sun doesn't negotiate. ☀️",
    "Quick afternoon shower? It'll pass in under an hour — perfect time for ice cream at the marina. 🍦",
    "Hydrate twice as much as you think you need. Agua, agua, agua. 💧",
    "Sea-turtle nests are marked on the beaches — give them space, July is nesting season. 🐢",
    "The marina boardwalk at 6 pm = boats coming in, pelicans diving, golden light. 📸",
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "olive-briefing"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def post(topic, body):
    req = urllib.request.Request(NTFY + topic, data=body.encode("utf-8"), method="POST",
                                 headers={"User-Agent": "olive-briefing"})
    urllib.request.urlopen(req, timeout=30).read()


def load_events():
    """Merge all retained ev/snap messages, last-writer-wins by ts."""
    evs = {}
    try:
        raw = get(NTFY + EV_TOPIC + "/json?poll=1&since=all")
    except Exception:
        return evs
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            j = json.loads(line)
            if j.get("event") not in (None, "message"):
                continue
            m = json.loads(j.get("message", ""))
        except Exception:
            continue
        items = m.get("evs", []) if m.get("k") == "snap" else [m] if m.get("k") == "ev" else []
        for e in items:
            eid = e.get("id")
            if not eid:
                continue
            if eid not in evs or (e.get("ts") or 0) > (evs[eid].get("ts") or 0):
                evs[eid] = e
    return evs


def main():
    now = datetime.now(MAZATLAN)
    today = now.strftime("%Y-%m-%d")
    evs = load_events()

    # 1) republish snapshot for durability
    if evs:
        snap = {"k": "snap", "ts": int(now.timestamp() * 1000), "evs": list(evs.values())}
        post(EV_TOPIC, json.dumps(snap))
        print(f"snapshot republished: {len(evs)} entries")

    # 2) today's agenda (live events with today's date)
    todays = sorted(
        [e for e in evs.values() if not e.get("del") and not e.get("inbox") and e.get("d") == today],
        key=lambda e: str(e.get("tm") or "99:99"),
    )

    # 3) weather
    wx = ""
    try:
        w = json.loads(get("https://api.open-meteo.com/v1/forecast?latitude=22.89&longitude=-109.91"
                           "&daily=temperature_2m_max,precipitation_probability_max"
                           "&temperature_unit=fahrenheit&timezone=America%2FMazatlan&forecast_days=1"))
        hi = round(w["daily"]["temperature_2m_max"][0])
        rain = w["daily"]["precipitation_probability_max"][0]
        wx = f"☀️ High of {hi}°F" + (f", {rain}% chance of a quick shower" if rain >= 20 else ", clear skies")
    except Exception:
        wx = "☀️ Another beautiful Cabo day"

    # 4) compose + post briefing to the family chat
    lines = [f"¡Buenos días, Cabo Crew! {wx}."]
    if todays:
        lines.append("📅 Today's plan:")
        for e in todays:
            t = f"  {e.get('e', '📌')} {e.get('t', '?')}"
            if e.get("tm"):
                t += f" at {e['tm']}"
            if e.get("p"):
                t += f" ({e['p']} people)"
            lines.append(t)
    else:
        lines.append("📅 Nothing scheduled today — pool day? Or open the Activities tab and make a play. 🏄")
    lines.append("💡 " + TIPS[now.timetuple().tm_yday % len(TIPS)])
    msg = "\n".join(lines)
    post(CHAT_TOPIC, json.dumps({"n": "Olive 🫒", "x": msg}))
    print("briefing posted:\n" + msg)


if __name__ == "__main__":
    main()
