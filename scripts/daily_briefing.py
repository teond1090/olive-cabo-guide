"""
Olive daily briefing - runs in GitHub Actions each morning (Mountain time).

1. Works out which day of the Great American West trip it is.
2. Fetches the forecast for where the group actually wakes up that day.
3. Posts a good-morning briefing (weather + today's route + a road tip)
   to the crew chat topic as "Olive".

Phones get this as a push notification through the free ntfy app, which is
the point: the app itself cannot wake itself up in the background.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CHAT_TOPIC = os.environ.get("OLIVE_CHAT_TOPIC", "")
if not CHAT_TOPIC:
    sys.exit("Missing OLIVE_CHAT_TOPIC secret")
NTFY = "https://ntfy.sh/"
MT = timezone(timedelta(hours=-6))  # Mountain Daylight Time in August

# date -> (day number, headline, route, overnight, wake-up lat, lng)
ITINERARY = {
    "2026-08-17": (1,  "Arrival & the long first drive", "Denver to Custer, SD", "Custer, SD", 39.7392, -104.9903),
    "2026-08-18": (2,  "Mount Rushmore & Custer State Park", "Rushmore, Iron Mountain Rd, Wildlife Loop", "Custer, SD", 43.7666, -103.5991),
    "2026-08-19": (3,  "Crazy Horse, Deadwood & Spearfish Canyon", "Custer to Spearfish", "Spearfish/Rapid City, SD", 43.7666, -103.5991),
    "2026-08-20": (4,  "Badlands & the road to Dickinson", "Badlands Loop, Wall, north to ND", "Dickinson, ND", 44.4900, -103.8594),
    "2026-08-21": (5,  "Theodore Roosevelt NP & west to Havre", "Medora park loop, then the long haul to Havre", "Havre, MT", 46.8792, -102.7896),
    "2026-08-22": (6,  "The Hi-Line to Glacier", "US-2 west to Whitefish", "Whitefish/Columbia Falls, MT", 48.5500, -109.6841),
    "2026-08-23": (7,  "Going-to-the-Sun Road", "West Glacier to Logan Pass to St. Mary", "Whitefish/Columbia Falls, MT", 48.4111, -114.3376),
    "2026-08-24": (8,  "Glacier at a gentler pace", "Red Bus tour + Many Glacier", "Whitefish/Columbia Falls, MT", 48.4111, -114.3376),
    "2026-08-25": (9,  "Glacier to West Yellowstone", "Helena/Butte corridor south", "West Yellowstone, MT", 48.4111, -114.3376),
    "2026-08-26": (10, "Yellowstone thermal wonders", "Old Faithful, Grand Prismatic, Norris, Mammoth", "Gardiner area", 44.6621, -111.1041),
    "2026-08-27": (11, "Canyon, valleys & over to Cody", "Artist Point, Hayden, Lamar, then Cody", "Cody, WY", 44.9766, -110.7036),
    "2026-08-28": (12, "Buffalo Bill, Little Bighorn & Billings", "Cody to Crow Agency to Billings", "Billings, MT", 44.5263, -109.0565),
    "2026-08-29": (13, "Billings flight & south to Cheyenne", "I-90 south through Sheridan and Buffalo", "Cheyenne, WY", 45.7833, -108.5007),
    "2026-08-30": (14, "Red Rocks & Denver", "Cheyenne to Red Rocks to Denver", "Denver, CO", 41.1400, -104.8202),
    "2026-08-31": (15, "Departure day", "Denver hotel to DIA", "Fly home", 39.7392, -104.9903),
}

TIPS = [
    "Break every 90 minutes. Everybody fully out of the vehicle, not just a fuel stop.",
    "Drink water before you feel thirsty. Altitude and dry air take more out of you than the heat does.",
    "Keep medications in the cabin, never in a hot cargo bay.",
    "Binoculars beat walking closer. Every time.",
    "100 yards from bears and wolves. 25 yards from bison and elk. No photograph is worth less.",
    "Fuel up above a quarter tank whenever you pass a town. The gaps out here are real.",
    "Download tomorrow's maps tonight, while you still have a signal.",
    "Pick the first good viewpoint. The farthest one is rarely better.",
    "Layers. Logan Pass and Yellowstone mornings run far colder than the valleys.",
    "If the day is running late, drop the optional item. That is what it is there for.",
    "Never step off a thermal boardwalk. The crust is thin and the water is boiling.",
    "Bison have the right of way. Always. Stay in the vehicle and enjoy the jam.",
]

WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "freezing fog",
       51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
       71: "light snow", 73: "snow", 75: "heavy snow", 80: "showers", 81: "showers", 82: "heavy showers",
       95: "thunderstorms", 96: "storms with hail", 99: "severe storms"}


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "olive-briefing"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def post(topic, title, body):
    req = urllib.request.Request(
        NTFY + topic + "?title=" + urllib.parse.quote(title),
        data=body.encode("utf-8"), method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()


def main():
    now = datetime.now(MT)
    today = now.strftime("%Y-%m-%d")

    if today not in ITINERARY:
        start = datetime(2026, 8, 17, tzinfo=MT)
        days_out = (start.date() - now.date()).days
        if 0 < days_out <= 14:
            post(CHAT_TOPIC, "Olive",
                 "%d day%s until Denver. Worth doing today: download offline maps for SD, ND, MT and WY, "
                 "confirm the Glacier Red Bus tour, and check that every prescription has a few extra days in it."
                 % (days_out, "" if days_out == 1 else "s"))
        return

    n, headline, route, overnight, lat, lng = ITINERARY[today]

    # forecast for where they wake up
    wx = ""
    try:
        d = get_json(
            "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunset"
            "&temperature_unit=fahrenheit&timezone=America%%2FDenver&forecast_days=1" % (lat, lng))
        dd = d["daily"]
        cond = WMO.get(dd["weather_code"][0], "")
        hi, lo = round(dd["temperature_2m_max"][0]), round(dd["temperature_2m_min"][0])
        rain = dd["precipitation_probability_max"][0]
        _h, _m = dd["sunset"][0].split("T")[1].split(":")[:2]
        _h = int(_h)
        sunset = "%d:%s %s" % (_h % 12 or 12, _m, "AM" if _h < 12 else "PM")
        wx = "%s, %s/%s degrees" % (cond.capitalize(), hi, lo)
        if rain and rain >= 30:
            wx += ", %d%% chance of rain" % rain
        wx += ". Sunset %s." % sunset
        if hi >= 93:
            wx += " Hot one - plan the big walk before 11am."
    except Exception:
        wx = "(forecast unavailable)"

    tip = TIPS[(n - 1) % len(TIPS)]

    body = (
        "Good morning. Day %d of 15 - %s.\n\n"
        "Route: %s\n"
        "Tonight: %s\n\n"
        "Weather: %s\n\n"
        "Today's reminder: %s"
    ) % (n, headline, route, overnight, wx, tip)

    post(CHAT_TOPIC, "Olive", body)
    print("posted day %d briefing" % n)


if __name__ == "__main__":
    main()
