"""
config.py — Keys, paths, and API base URLs for NBA AI Predictor.
Edit your API keys here.
"""

import os

# ── API KEYS ──────────────────────────────────────────────────────────────────
ANTHROPIC_KEY = "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"
ODDS_KEY      = "4a1f5f362931422c9b741a756b9a63f5"

# ── PATHS ─────────────────────────────────────────────────────────────────────
DIR         = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR   = os.path.join(DIR, "cache_nba")
HISTORY_DIR = os.path.join(DIR, "picks_history")
RECORD_FILE = os.path.join(DIR, "record_nba.json")
APP_FILE    = os.path.join(DIR, "app.html")

# Create directories on import
for _d in [CACHE_DIR, HISTORY_DIR]:
    os.makedirs(_d, exist_ok=True)

# ── API BASE URLS ──────────────────────────────────────────────────────────────
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ODDS_BASE = "https://api.the-odds-api.com/v4/sports/basketball_nba"