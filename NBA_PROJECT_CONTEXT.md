# NBA AI Predictor — Project Context

## Overview
Python-based NBA betting picks system running in `C:\NBA`. Generates daily picks, grades them automatically, and outputs a mobile-friendly `app.html` dashboard.

## Current Record
- **All time: 113-19 (85.6%)**
- ML: 95-15 | Total: 18-4 | Prop: 0-0
- By confidence: 50-59% → 73% | 60-69% → 76% | 70-79% → 91% | 80+% → 95%
- P&L on $10 flat bets: +$116.08
- O/U: 18-4 (81.8%) — Overs 4-0, Unders 5-2

## File Structure
```
C:\NBA\
├── nba_picks.py          # Main entry point — run daily
├── config.py             # API keys, paths, constants
├── utils.py              # Helpers (fetch, calc_ev, fmt_odds etc.)
├── espn.py               # ESPN API — schedule, injuries, box scores, B2B detection
├── odds.py               # The Odds API — moneyline odds fetcher
├── predictor.py          # Win probability calculator
├── claude_ai.py          # Claude Sonnet API call (batched, web search)
├── groq_ai.py            # Groq API (free, Llama 3.3 70B) drop-in replacement
├── history.py            # Save/load/grade daily picks
├── record.py             # W/L record tracker with P&L by confidence bucket
├── html_builder.py       # Builds app.html dashboard
├── picks_history/        # Daily pick JSON files (2026-04-03 to present)
├── record_nba.json       # Running record
├── picks_nba.json        # Today's picks
├── rotowire_games_clean.json  # 11,322 historical games with B2B flags
├── app.html              # Main dashboard (open in browser)
├── history_YYYY-MM-DD.html   # Past day dashboards
└── backtest_analysis.py  # Hit rate analysis tools
```

## Tech Stack
- **Language**: Python 3.12
- **AI**: Groq (free, default) — Llama 3.3 70B via `groq_ai.py`
- **AI fallback**: Claude Sonnet 4.6 via `claude_ai.py`
- **Data**: ESPN free API (schedule, injuries, scores) + The Odds API (moneyline odds)
- **Historical data**: RotoWire archive (11,322 games, 2017-2026)

## How It Works
1. `nba_picks.py` runs daily — fetches today's games from ESPN
2. Pulls moneyline odds from The Odds API
3. Fetches injury report and game details per game
4. Detects back-to-back teams (played previous night)
5. Sends all games in ONE API call to Groq/Claude for analysis
6. Claude/Groq returns JSON array with pick, confidence, reasoning, total lean
7. Builds `app.html` dashboard with game cards
8. Next morning, grades yesterday's picks against ESPN results
9. Updates `record_nba.json` with W/L, P&L by confidence bucket

## Switching Between Groq and Claude
In `nba_picks.py`, find the import line and change:
```python
# Use Groq (free):
from groq_ai import groq_analyze_all as claude_analyze_all

# Use Claude (paid, has web search):
from claude_ai import claude_analyze_all
```

## API Keys
- **Groq**: stored in `groq_ai.py` as `GROQ_KEY` — get free key at console.groq.com
- **Anthropic**: stored in `config.py` as `ANTHROPIC_KEY`
- **Odds API**: stored in `config.py` — key: `99600f26a5e11d2adbc779d348de624d`

## Key Findings from Backtesting
- Blind spread-following loses money at every confidence level due to vig on heavy favorites
- Claude's injury analysis adds ~15% hit rate over baseline model
- April 10 (Claude unavailable, model-only): 11-4 (73%) vs normal 90%+
- B2B home team wins only 48.9% — factor heavily into picks
- B2B away team wins only 44.7%
- Pick em games (spread < 1.5): 34.4% hit rate — avoid
- Overs hit 50.9% on totals in 220-230 range
- 2024 season was unusually over-heavy (52.2%)

## Season Simulation Results (2025-26, 1190 games)
| Min Confidence | Picks | Hit% | P&L (blind) |
|---|---|---|---|
| 50% | 1190 | 68.1% | -$1325 |
| 70% | 701 | 79.5% | -$398 |
| 80% | 355 | 83.4% | -$298 |
| 90% | 103 | 95.1% | -$11 |

*Blind picking loses due to vig. Real system profitable because Claude finds mispriced lines.*

## Dashboard Features
- ML record board with confidence buckets and P&L
- O/U record board (at bottom, accessible via "O/U record ↓" link)
- Game cards with projected scores, win probability bar, injury report
- ⚠️ Tight line badge on games where neither team > 60% implied probability
- WIN/LOSS badges on completed games
- ✓ HIT / ✗ MISS badges on total picks
- Day navigation tabs with per-day records
- History pages for each past day

## Prompt Engineering (claude_ai.py / groq_ai.py)
Key factors Claude/Groq is told to weigh:
1. Injuries — especially stars (20+ PPG missing = significant shift)
2. Back-to-back fatigue — B2B teams underperform spread by 2-3 pts on average
3. Only increase confidence above implied odds if clear reason exists

## record.json Structure
```json
{
  "alltime": {"W": 113, "L": 19},
  "by_month": {"2026-04": {"W": 113, "L": 19}},
  "by_week": {"2026-W14": {...}, "2026-W15": {...}},
  "by_day": {"2026-04-12": {"W": 7, "L": 1}},
  "by_type": {"ml": {"W": 95, "L": 15}, "total": {"W": 18, "L": 4}, "prop": {"W": 0, "L": 0}},
  "by_conf": {
    "50-59": {"W": 11, "L": 4, "pnl": 6.08},
    "60-69": {"W": 22, "L": 7, "pnl": 48.34},
    "70-79": {"W": 20, "L": 2, "pnl": 52.22},
    "80+":   {"W": 42, "L": 2, "pnl": 9.84}
  },
  "by_conf_total": {
    "OVER":  {"W": 4, "L": 0, "pnl": 27.27},
    "UNDER": {"W": 5, "L": 2, "pnl": 24.83}
  }
}
```

## What's Next
- NBA Playoffs start April 19, 2026
- Test Groq pick quality vs Claude over first week of playoffs
- Consider Claude-only for 80%+ confidence playoff games
- Build playoff-specific prompt improvements (series context, home court, rest days)
- Continue forward testing — need 200+ picks for statistically meaningful sample
