import json
from collections import defaultdict

with open("rotowire_games_clean.json") as f:
    games = json.load(f)

# Filter out games with missing data
games = [g for g in games if g["home_line"] is not None and g["over_under"] is not None]

print(f"Total games analyzed: {len(games)}\n")

# ── 1. OVERALL STATS ──────────────────────────────────────────────────────────
total = len(games)
over_hits  = sum(1 for g in games if g["over_hit"])
under_hits = sum(1 for g in games if g["under_hit"])
pushes_ou  = total - over_hits - under_hits
fav_covers = sum(1 for g in games if g["fav_covered"])
dog_covers = sum(1 for g in games if not g["fav_covered"] and (over_hits + under_hits > 0))
pushes_ats = total - fav_covers - dog_covers

print("=" * 55)
print("OVERALL")
print("=" * 55)
print(f"  Over:      {over_hits}/{total}  ({over_hits/total*100:.1f}%)")
print(f"  Under:     {under_hits}/{total}  ({under_hits/total*100:.1f}%)")
print(f"  O/U Push:  {pushes_ou}")
print(f"  Fav ATS:   {fav_covers}/{total}  ({fav_covers/total*100:.1f}%)")
print(f"  Dog ATS:   {dog_covers}/{total}  ({dog_covers/total*100:.1f}%)")
print(f"  ATS Push:  {pushes_ats}")

# ── 2. BY SPREAD BUCKET ───────────────────────────────────────────────────────
spread_buckets = [
    ("Pick em  (-1.5 to +1.5)",  -1.5,  1.5),
    ("Small    (-1.5 to -4.5)",  -4.5, -1.5),
    ("Mid      (-4.5 to -8.5)",  -8.5, -4.5),
    ("Large    (-8.5 to -14)",  -14.0, -8.5),
    ("Blowout  (-14+)",         -99.0, -14.0),
]

print("\n" + "=" * 55)
print("FAVORITE ATS BY SPREAD SIZE")
print("=" * 55)
print(f"  {'Bucket':<28} {'Fav Cover':>10} {'Dog Cover':>10} {'Push':>6}")
print(f"  {'-'*28} {'-'*10} {'-'*10} {'-'*6}")

for label, low, high in spread_buckets:
    bucket = [g for g in games if low <= g["home_line"] < high or -high >= -g["home_line"] > -low]
    # simpler: just bucket by abs spread
    pass

# Redo cleanly using absolute spread
buckets_ats = [
    ("Pick em  (0 to 1.5)",    0,    1.5),
    ("Small    (1.5 to 4.5)",  1.5,  4.5),
    ("Mid      (4.5 to 8.5)",  4.5,  8.5),
    ("Large    (8.5 to 14)",   8.5, 14.0),
    ("Blowout  (14+)",        14.0, 99.0),
]

for label, low, high in buckets_ats:
    bucket = [g for g in games if low <= abs(g["home_line"]) < high]
    if not bucket:
        continue
    n = len(bucket)
    fav = sum(1 for g in bucket if g["fav_covered"])
    dog = sum(1 for g in bucket if not g["fav_covered"])
    push = n - fav - dog
    print(f"  {label:<28} {fav:>4}/{n:<5} {fav/n*100:>5.1f}%   {dog:>4}/{n:<5} {dog/n*100:>5.1f}%   {push:>4}")

# ── 3. OVER/UNDER BY TOTAL BUCKET ─────────────────────────────────────────────
print("\n" + "=" * 55)
print("OVER/UNDER BY GAME TOTAL (O/U LINE)")
print("=" * 55)
print(f"  {'Bucket':<22} {'Over':>10} {'Under':>10} {'Push':>6}")
print(f"  {'-'*22} {'-'*10} {'-'*10} {'-'*6}")

ou_buckets = [
    ("Under 210",    0,   210),
    ("210 - 220",  210,   220),
    ("220 - 230",  220,   230),
    ("230 - 240",  230,   240),
    ("240+",       240,   999),
]

for label, low, high in ou_buckets:
    bucket = [g for g in games if low <= g["over_under"] < high]
    if not bucket:
        continue
    n = len(bucket)
    over  = sum(1 for g in bucket if g["over_hit"])
    under = sum(1 for g in bucket if g["under_hit"])
    push  = n - over - under
    print(f"  {label:<22} {over:>4}/{n:<5} {over/n*100:>5.1f}%   {under:>4}/{n:<5} {under/n*100:>5.1f}%   {push:>4}")

# ── 4. BY SEASON ──────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
print("BY SEASON")
print("=" * 55)
print(f"  {'Season':<8} {'Games':>6} {'Over%':>7} {'Under%':>8} {'Fav ATS%':>10}")
print(f"  {'-'*8} {'-'*6} {'-'*7} {'-'*8} {'-'*10}")

seasons = sorted(set(g["season"] for g in games))
for s in seasons:
    sg = [g for g in games if g["season"] == s]
    n  = len(sg)
    ov = sum(1 for g in sg if g["over_hit"])
    un = sum(1 for g in sg if g["under_hit"])
    fc = sum(1 for g in sg if g["fav_covered"])
    print(f"  {s:<8} {n:>6} {ov/n*100:>6.1f}%  {un/n*100:>7.1f}%  {fc/n*100:>9.1f}%")

print("\nDone.")