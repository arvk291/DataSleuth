"""Generate a synthetic app-metrics database (play.db) plus golden.json.

Synthetic on purpose: never point a free-tier LLM at your employer's data.
The data has four planted facts the agent should be able to discover.
"""
import datetime as dt
import json
import random
import sqlite3

random.seed(42)
START, DAYS = dt.date(2026, 6, 1), 92
COUNTRIES = {"IN": 1.0, "US": 0.8, "BR": 0.6, "DE": 0.4}
ARPDAU = {"Games": 0.05, "Finance": 0.12, "Productivity": 0.08, "Health": 0.06}
APPS = [("PixelPets", "Games"), ("ZenTimer", "Productivity"), ("CoinNest", "Finance")]
APPS += [(f"{p}{i}", c) for i, (p, c) in enumerate(
    [("Quest", "Games"), ("Racer", "Games"), ("Ledger", "Finance"), ("Budgeto", "Finance"),
     ("Notely", "Productivity"), ("Plan", "Productivity"), ("Fit", "Health"), ("Sleep", "Health")] * 3)]

con = sqlite3.connect("play.db")
con.executescript("""
DROP TABLE IF EXISTS apps; DROP TABLE IF EXISTS daily_metrics;
CREATE TABLE apps (app_id INTEGER PRIMARY KEY, name TEXT, category TEXT);
CREATE TABLE daily_metrics (date TEXT, app_id INTEGER, country TEXT,
  installs INTEGER, dau INTEGER, revenue_usd REAL, crash_rate REAL);
""")
for app_id, (name, cat) in enumerate(APPS, 1):
    con.execute("INSERT INTO apps VALUES (?,?,?)", (app_id, name, cat))
    scale = random.uniform(0.5, 2.0)
    for d in range(DAYS):
        day = START + dt.timedelta(days=d)
        for cc, cf in COUNTRIES.items():
            dau = int(20000 * scale * cf * random.uniform(0.92, 1.08))
            installs = int(900 * scale * cf * random.uniform(0.9, 1.1))
            revenue = dau * ARPDAU[cat] * random.uniform(0.9, 1.1)
            crash = 0.005 * random.uniform(0.8, 1.2)
            if name == "ZenTimer":                      # planted: steady install growth
                installs = int(installs * (1 + 2 * d / (DAYS - 1)))
            if name == "PixelPets" and cc == "BR" and day >= dt.date(2026, 7, 14):
                crash *= 5                              # planted: crash spike
            if cat == "Finance" and cc == "US" and day >= dt.date(2026, 8, 1):
                revenue *= 0.7                          # planted: revenue drop
            if day == dt.date(2026, 7, 4):              # planted: logging outage
                dau, installs, revenue, crash = 0, 0, 0.0, None
            con.execute("INSERT INTO daily_metrics VALUES (?,?,?,?,?,?,?)",
                        (day.isoformat(), app_id, cc, installs, dau, round(revenue, 2),
                         None if crash is None else round(crash, 5)))
con.commit()

golden = [
    {"id": "crash", "question": "Which app had a crash-rate spike, in which country, and from what date?",
     "must_include": ["PixelPets", "BR", "07-14"]},
    {"id": "finance", "question": "Did US revenue for Finance apps change in August 2026 versus July? Roughly by how much?",
     "must_include": ["Finance", "US"], "expected_change_pct": [-33, -25]},
    {"id": "growth", "question": "Which app grew daily installs the most between June and August 2026?",
     "must_include": ["ZenTimer"]},
    {"id": "outage", "question": "DAU is zero on 2026-07-04. Is that a real drop in users?",
     "must_include": ["2026-07-04"], "must_flag": "data/logging outage, not a real user drop"},
]
json.dump(golden, open("golden.json", "w"), indent=2)
print("play.db and golden.json written:", con.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0], "rows")
