import requests
import json
import re

BASE_URL = "https://www.rotowire.com/betting/nba/tables/games-archive.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.rotowire.com/betting/nba/archive.php",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_all_games(team=None):
    url = BASE_URL
    if team:
        url += f"?team={team}"
    print(f"Fetching from: {url}")
    try:
        session = requests.Session()
        session.get("https://www.rotowire.com/betting/nba/archive.php", headers=HEADERS)
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print(f"Status: {resp.status_code} | Games returned: {len(data)}")
        return data
    except requests.exceptions.JSONDecodeError:
        print("Response wasn't JSON. Raw snippet:")
        print(resp.text[:500])
        return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def parse_games(raw_data):
    games = []
    for row in raw_data:
        games.append({
            "game":        row.get("name", ""),
            "tipoff":      row.get("tipoff", ""),
            "season":      row.get("season", ""),
            "score":       row.get("score", ""),
            "over_under":  row.get("game_over_under", ""),
            "home_line":   row.get("line", ""),
            "over_hit":    row.get("over_hit", False),
            "under_hit":   row.get("under_hit", False),
            "fav_covered": row.get("favorite_covered", False),
        })
    return games

def clean_game_data(games):
    cleaned = []
    for g in games:
        raw = g["game"]
        teams = re.findall(r'>([A-Z]{2,3})<', raw)
        if len(teams) < 2:
            continue
        away_team, home_team = teams[0], teams[1]

        winner_match = re.search(r'font-weight:700.*?>([A-Z]{2,3})<', raw)
        winner = winner_match.group(1) if winner_match else None

        ats_cover_match = re.search(r'color:#1da561.*?>([A-Z]{2,3})<', raw)
        ats_cover = ats_cover_match.group(1) if ats_cover_match else None

        score = g["score"]
        try:
            away_score, home_score = map(int, score.split("-"))
        except:
            away_score = home_score = None

        cleaned.append({
            "away_team":   away_team,
            "home_team":   home_team,
            "winner":      winner,
            "ats_cover":   ats_cover,
            "tipoff":      g["tipoff"],
            "season":      int(g["season"]),
            "away_score":  away_score,
            "home_score":  home_score,
            "total_score": (away_score + home_score) if away_score else None,
            "over_under":  float(g["over_under"]) if g["over_under"] else None,
            "home_line":   float(g["home_line"]) if g["home_line"] else None,
            "over_hit":    bool(g["over_hit"]),
            "under_hit":   bool(g["under_hit"]),
            "fav_covered": bool(g["fav_covered"]),
        })
    return cleaned

if __name__ == "__main__":
    raw = fetch_all_games()
    if raw:
        games = parse_games(raw)
        cleaned = clean_game_data(games)

        print(f"\nCleaned sample (first 3):")
        for g in cleaned[:3]:
            print(g)

        with open("rotowire_games_clean.json", "w") as f:
            json.dump(cleaned, f, indent=2)
        print(f"\nSaved {len(cleaned)} cleaned games to rotowire_games_clean.json")
    else:
        print("No data returned.")