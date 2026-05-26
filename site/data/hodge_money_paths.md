# Hodge Sports: Evidence-Based Money Paths

Generated from the current local artifacts after removing betting/staking and
running real-odds bankroll plus market-residual validations.

## Current Verdict

The current Hodge sports system has predictive signal, but it is not a proven
standalone betting system.

- Straight-up winner accuracy: market favorite beats Hodge in every evaluated sport.
- Broad all-sport real-odds betting loses the bankroll.
- Strict NBA/NHL historical betting was positive, mainly due to NHL, but an out-of-time residual test did not confirm it.
- The safest money path is not live wagering yet. It is productizing Hodge as an analytics/ranking signal while improving the model.

## Evidence Snapshot

### Straight-Up Accuracy

Artifact: `site/data/hodge_winner_accuracy.json`

Across 59,584 evaluated games:

| Method | Accuracy |
|---|---:|
| Market favorite | 62.54% |
| Hodge raw signal | 59.80% |
| Hodge calibrated | 59.80% |
| Elo | 59.69% |
| Home/listed-home | 54.62% |

Market favorite also wins sport-by-sport:

| Sport | Market | Hodge | Elo |
|---|---:|---:|---:|
| CFB | 73.98% | 69.30% | 66.48% |
| EPL | 55.77% | 53.90% | 53.96% |
| MLB | 58.09% | 55.41% | 56.20% |
| NBA | 67.74% | 64.88% | 64.64% |
| NFL | 66.34% | 62.67% | 62.38% |
| NHL | 58.79% | 57.46% | 57.63% |

### Real-Odds Bankroll Agent

Default all-sport agent:

- Artifact: `site/data/hodge_real_sportsbook_agent.json`
- Result: $1,000 -> $0.01
- Bets: 30,566
- Yield: -3.97%
- Max drawdown: 100.00%

Strict all-sport agent:

- Artifact: `site/data/hodge_real_sportsbook_agent_strict.json`
- Result: $1,000 -> $370.42
- Bets: 7,646
- Yield: -2.43%
- Max drawdown: 79.47%

Strict NBA+NHL subset:

- Artifact: `site/data/hodge_real_sportsbook_agent_nba_nhl_strict.json`
- Result: $1,000 -> $1,394.03
- Bets: 2,118
- Yield: +1.68%
- Max drawdown: 36.26%

NHL strict alone:

- Artifact: `site/data/hodge_real_sportsbook_agent_nhl_strict.json`
- Result: $1,000 -> $1,236.98
- Bets: 474
- Yield: +5.03%
- Max drawdown: 20.52%

### Out-of-Time Market-Residual Tests

These are stricter because thresholds are selected on a tune window and then
applied once to an untouched test window.

All sports:

- Artifact: `site/data/hodge_market_residual_strategy.json`
- Test result: $1,000 -> $848.87
- Bets: 158
- Yield: -14.22%

NBA+NHL:

- Artifact: `site/data/hodge_market_residual_strategy_nba_nhl.json`
- Test result: $1,000 -> $860.24
- Bets: 870
- Yield: -1.80%

NHL:

- Artifact: `site/data/hodge_market_residual_strategy_nhl.json`
- Test result: $1,000 -> $857.23
- Bets: 940
- Yield: -1.77%

NBA:

- Artifact: `site/data/hodge_market_residual_strategy_nba.json`
- Test result: $1,000 -> $813.61
- Bets: 134
- Yield: -15.12%

This invalidates the idea that the current residual model is ready for live betting.

## Best Money Paths Now

### 1. Sell Hodge Ratings and Disagreement Analytics

This is the strongest immediate path because it does not require claiming a live betting edge.

Product:

- Weekly Hodge team rankings by sport.
- Market-vs-Hodge disagreement watchlists.
- Upset-risk flags where Hodge and market diverge.
- Curl/harmonic matchup notes for content differentiation.

Who buys:

- Sports content creators.
- Fantasy/betting newsletter operators.
- Small handicapping groups.
- Data-curious fans.

Why it is viable:

- Hodge beats or roughly matches simple Elo in several sports.
- It offers a differentiated explanation layer rather than another black-box pick model.
- You can sell insight without promising positive betting ROI.

### 2. Build a Paid Research Report

Product:

- "Hodge Decomposition in Sports Prediction: 60k-Game Real-Odds Validation"
- Include the negative betting result honestly.
- Emphasize where Hodge adds signal, where market dominates, and why naive betting fails.

Who buys:

- Quant sports bettors.
- Data-science newsletters.
- Sports analytics students.
- Niche paid communities.

Why it is viable:

- The negative result is credible because it catches and fixes multiple leakage/data bugs.
- Honest validation is rarer and more valuable than another unverifiable picks sheet.

### 3. License Hodge Features, Not Picks

Product:

- A feature feed/API:
  - Hodge potential rank.
  - Hodge probability.
  - Market disagreement score.
  - Hodge/Elo disagreement.
  - Sport-specific volatility flags.

Who buys:

- Existing bettors/modelers with richer injury/news/line-movement stacks.
- Newsletter operators who need differentiated features.
- Analytics products that need novel features.

Why it is viable:

- The current system is not enough by itself, but it can be useful as a feature in a bigger model.

### 4. Continue the Betting R&D Only Under Holdout Discipline

Do not risk capital until this condition is met:

- Pick thresholds/model on train+tune only.
- Test on later untouched seasons.
- Positive yield after vig.
- Reasonable drawdown.
- No impossible odds rows.
- Bet count large enough to matter.

The current residual scripts exist to enforce this discipline:

- `scripts/hodge_market_residual_strategy.py`
- `scripts/hodge_real_sportsbook_agent.py`
- `scripts/hodge_winner_accuracy.py`

## Next Technical Improvements

The current model misses core sportsbook information. The next version should add:

- Closing-line movement and open-to-close delta.
- Rest days and travel.
- Starting pitchers for MLB.
- Goalies for NHL.
- Back-to-back games for NBA/NHL.
- Injuries and lineup availability.
- Team form over multiple windows.
- Sport-specific calibration instead of one generic Hodge probability transform.
- Confidence filters by odds bucket; the current model is overconfident at high predicted probabilities.

## Practical Recommendation

Do not position this as "a profitable betting bot" yet.

Position it as:

> A novel Hodge-theory sports analytics signal that finds structure and market disagreement, with transparent historical validation.

The first monetizable deliverable should be a paid dashboard/newsletter/report, while the betting model continues through stricter out-of-time validation.
