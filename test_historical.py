"""
Run this to check if your Odds API key has historical data access.
python test_historical.py
"""
import urllib.request, json

KEY = "99600f26a5e11d2adbc779d348de624d"
url = (f"https://api.the-odds-api.com/v4/historical/sports/basketball_nba/odds/"
       f"?apiKey={KEY}&date=2026-01-15T00:00:00Z&regions=us&markets=h2h&oddsFormat=american")

try:
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.loads(r.read())
    games = data.get("data", [])
    print(f"✅ Historical access works! Found {len(games)} games for Jan 15")
    if games:
        print(f"   Example: {games[0].get('home_team')} vs {games[0].get('away_team')}")
    remaining = r.headers.get("x-requests-remaining", "?")
    print(f"   API calls remaining: {remaining}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"❌ HTTP {e.code}: {body}")
    if e.code == 401:
        print("   → Your plan doesn't include historical data")
        print("   → Upgrade at https://the-odds-api.com or use a free alternative")
except Exception as e:
    print(f"❌ Error: {e}")
