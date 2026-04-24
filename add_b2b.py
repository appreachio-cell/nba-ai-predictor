import json
from datetime import datetime, timedelta

with open("rotowire_games_clean.json") as f:
    games = json.load(f)

def parse_game_date(tipoff, season):
    """Reconstruct full date from tipoff string like 'Oct 17 8:00 PM' and season year."""
    try:
        # Strip time, just get month/day
        date_part = " ".join(tipoff.split()[:2])  # "Oct 17"
        month = datetime.strptime(date_part, "%b %d").month
        # Oct-Dec = season year, Jan-Jun = season year + 1
        year = season if month >= 9 else season + 1
        return datetime.strptime(f"{date_part} {year}", "%b %d %Y").date()
    except:
        return None

# Parse dates for all games
print("Parsing dates...")
for g in games:
    g["_date"] = parse_game_date(g["tipoff"], g["season"])

# Sort by date then tipoff time
games.sort(key=lambda g: (g["_date"] or datetime.max.date(), g["tipoff"]))

# Build a set of (date, team) pairs for fast lookup
print("Flagging back-to-backs...")
played = {}  # date -> set of teams that played

for g in games:
    d = g["_date"]
    if d is None:
        g["home_b2b"] = False
        g["away_b2b"] = False
        continue

    yesterday = d - timedelta(days=1)
    yd_teams = played.get(yesterday, set())

    g["home_b2b"] = g["home_team"] in yd_teams
    g["away_b2b"] = g["away_team"] in yd_teams

    # Add today's teams to played
    if d not in played:
        played[d] = set()
    played[d].add(g["home_team"])
    played[d].add(g["away_team"])

# Count B2Bs
home_b2b = sum(1 for g in games if g["home_b2b"])
away_b2b = sum(1 for g in games if g["away_b2b"])
both_b2b = sum(1 for g in games if g["home_b2b"] and g["away_b2b"])
print(f"Home team on B2B: {home_b2b}")
print(f"Away team on B2B: {away_b2b}")
print(f"Both teams on B2B: {both_b2b}")

# Remove temp date field and save
for g in games:
    g.pop("_date", None)

with open("rotowire_games_clean.json", "w") as f:
    json.dump(games, f, indent=2)
# ── B2B IMPACT ────────────────────────────────────────────
print(f"\n{'=' * 55}")
print("BACK-TO-BACK IMPACT (2025-26 season)")
print("=" * 55)

# Reload with B2B flags
with open("rotowire_games_clean.json") as f:
    all_games = json.load(f)

season_b2b = [g for g in all_games if g["season"] == 2025 and g["winner"] is not None]

scenarios = [
    ("Neither on B2B",  lambda g: not g.get("home_b2b") and not g.get("away_b2b")),
    ("Home on B2B",     lambda g: g.get("home_b2b") and not g.get("away_b2b")),
    ("Away on B2B",     lambda g: g.get("away_b2b") and not g.get("home_b2b")),
    ("Both on B2B",     lambda g: g.get("home_b2b") and g.get("away_b2b")),
]

print(f"  {'Scenario':<22} {'Games':>6} {'Home Win%':>10} {'Fav Win%':>10}")
print(f"  {'-'*22} {'-'*6} {'-'*10} {'-'*10}")

for label, fn in scenarios:
    sg = [g for g in season_b2b if fn(g)]
    if not sg: continue
    n = len(sg)
    home_wins = sum(1 for g in sg if g["winner"] == g["home_team"])
    # favorite = team with negative home_line (home fav) or positive (away fav)
    fav_wins = sum(1 for g in sg if g["home_line"] is not None and (
        (g["home_line"] < 0 and g["winner"] == g["home_team"]) or
        (g["home_line"] > 0 and g["winner"] == g["away_team"])
    ))
    fav_total = sum(1 for g in sg if g["home_line"] is not None and g["home_line"] != 0)
    print(f"  {label:<22} {n:>6} {home_wins/n*100:>9.1f}%  {fav_wins/fav_total*100:>9.1f}%")

# B2B team specifically — do they win less?
print(f"\n  {'Scenario':<30} {'Games':>6} {'B2B team wins':>14}")
print(f"  {'-'*30} {'-'*6} {'-'*14}")

home_b2b_only = [g for g in season_b2b if g.get("home_b2b") and not g.get("away_b2b")]
away_b2b_only = [g for g in season_b2b if g.get("away_b2b") and not g.get("home_b2b")]

if home_b2b_only:
    hw = sum(1 for g in home_b2b_only if g["winner"] == g["home_team"])
    print(f"  {'Home team on B2B':<30} {len(home_b2b_only):>6} {hw/len(home_b2b_only)*100:>13.1f}%")

if away_b2b_only:
    aw = sum(1 for g in away_b2b_only if g["winner"] == g["away_team"])
    print(f"  {'Away team on B2B':<30} {len(away_b2b_only):>6} {aw/len(away_b2b_only)*100:>13.1f}%")
print(f"\nSaved {len(games)} games with B2B flags to rotowire_games_clean.json")