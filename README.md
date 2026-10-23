# Modeling Market Error in NCAA Basketball Spreads

An end-to-end Python project that collects NCAA men's basketball data, engineers pregame features, predicts point-spread residuals with XGBoost, and displays matchup predictions in a Streamlit dashboard.

The project combines historical data preparation, chronological model evaluation, validation-based feature selection, and a historical prediction demo.

## Run the demo

The included dashboard uses predictions for **December 13, 2025**, generated with the saved model from the **2026 test-season experiment**. Season labels refer to the year in which the season ends.

The included CSV and model artifacts let you explore the dashboard without an API key or retraining. The demo is a historical example, not a live or automatically refreshed prediction feed.

From the repository directory:

```bash
python -m venv .venv
```

Activate the environment on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies and start the dashboard:

```bash
python -m pip install -r requirements.txt
python -m streamlit run streamLit.py
```

The dashboard displays game times in Eastern Time, team names, home-team spreads, and predicted edges. It supports team filtering and sorting, and highlights away selections that meet the saved validation-derived cutoff.

## Prediction target

The model predicts the residual between the final home scoring margin and the market's implied margin:

```text
edge = home_margin + home_spread
home_margin = home_points - away_points
```

For example, a home team favored by five points has a spread of `-5`. Winning by eight produces an actual edge of `+3`.

- **Positive actual edge:** the home team covered.
- **Negative actual edge:** the away team covered.
- **Zero actual edge:** a push.

Predicted edge uses the same sign convention: negative predictions favor away and positive predictions favor home. Predictions are measured in points, not win probabilities. The market baseline predicts an edge of zero.

## Data and features

Historical data covers the **2014–2026 seasons** and comes from [CollegeBasketballData.com](https://collegebasketballdata.com/). The pipeline combines team box scores, game metadata, and historical betting lines.

Line selection prioritizes DraftKings, followed by FanDuel, Caesars, ESPN BET, and then the first available provider. Availability can vary across games and seasons.

Pregame features describe:

- Offensive and defensive efficiency, net rating, and winning percentage.
- Shooting efficiency and shot selection.
- Turnovers, rebounding, assists, steals, and blocks.
- Free throws, fouls, scoring profile, and pace.
- Market spread, neutral-site status, conference games, and tournaments.

Team comparisons use home-minus-away differences. Two feature families summarize recent information: exponentially weighted individual-game statistics (`*_ewm`) and smoothed pregame season-to-date statistics (`*_smoothed_ewm`). Both use an alpha of `0.15` and combine each team's home and away appearances.

Historical pregame statistics exclude the current game's performance. Daily prediction rows use each team's state after its last completed game. Games are eligible when a spread is available and both teams have played at least five prior games.

## Model development and evaluation

Each experiment predicts one season using earlier seasons for model development:

1. Divide prior seasons chronologically into approximately 70% training and 30% validation seasons.
2. Fit an XGBoost regressor using the full candidate feature pool, with validation MAE for early stopping.
3. Calculate permutation importance on validation data and select the top 20 features.
4. Fit a new model using those features, again with early stopping.
5. Calculate prediction-strength cutoffs from that model's validation predictions.
6. Apply the model and fixed numerical cutoffs to the following test season.

| Test season | Training seasons | Validation seasons |
|---|---|---|
| 2024 | 2014–2020 | 2021–2023 |
| 2025 | 2014–2021 | 2022–2024 |
| 2026 | 2014–2021 | 2022–2025 |

Validation data supports early stopping, feature selection, and cutoff calibration; its performance is not an independent generalization estimate.

### Overall prediction error

The values below are from the saved notebook outputs. MAE is measured in points; lower is better. Overall against-the-spread (ATS) accuracy excludes pushes and zero predictions.

| Test season | Model MAE | Market baseline MAE | Overall ATS accuracy |
|---|---:|---:|---:|
| 2024 | 8.8277 | 8.8499 | 51.90% |
| 2025 | 8.6039 | 8.6266 | 52.35% |
| 2026 | 8.9315 | 8.9418 | 50.86% |

The model's overall MAE improvements are small. The notebook separately examines a more selective away policy.

### Selected away policy

The policy selects away teams when predicted edge is at or below the negative of the 95th percentile of absolute validation away predictions. This represents the strongest 5% of negative validation predictions. The same numerical cutoff is applied to test predictions, so test selection volume need not equal 5%.

| Test season | Away cutoff | Selections | Wins | Losses | Pushes | Win rate |
|---|---:|---:|---:|---:|---:|---:|
| 2024 | -1.3854 | 99 | 60 | 39 | 0 | 60.61% |
| 2025 | -1.3114 | 115 | 68 | 47 | 0 | 59.13% |
| 2026 | -1.2408 | 85 | 51 | 34 | 0 | 60.00% |

Cutoffs are rounded for display; the dashboard uses the saved full-precision cutoff. Win rates exclude pushes. The policy was chosen during development using 2024 and 2025 results. Prior experimentation also involved 2026, so these results should be interpreted as retrospective rather than a completely untouched final holdout.

## Repository contents

| File | Purpose |
|---|---|
| `createdf.py` | Fetch historical data and construct pregame team statistics |
| `ModelingEdge.ipynb` | Prepare features, train and evaluate experiments, and export artifacts |
| `predictToday.py` | Build features for a requested date and export matchup predictions |
| `streamLit.py` | Display predictions and highlight the selected away policy |
| `model.joblib` | Saved final model from the 2026 experiment |
| `model_features.joblib` | Ordered feature list required by that model |
| `away_cutoff.joblib` | Matching signed validation-derived away cutoff |
| `daily_predictions.csv` | Historical demo predictions for December 13, 2025 |
| `.env.example` | API-key configuration template |
| `requirements.txt` | Python dependencies |

The large historical modeling dataset is excluded from the repository and can be generated with `createdf.py`.

## Reproduce the pipeline

### 1. Configure API access

Obtain a CollegeBasketballData.com API key. Copy `.env.example` to `.env` and set:

```dotenv
CBBD_API_KEY=your_api_key_here
```

Keep `.env` out of version control. API access is needed to rebuild historical data or generate predictions for another date; it is not needed for the included dashboard demo.

### 2. Build historical data

```bash
python createdf.py
```

The script fetches seasons 2014–2026 and writes `cbbData_2014_2026_endEWM.csv`. This step makes multiple API requests and may take time.

### 3. Run the modeling notebook

Open `ModelingEdge.ipynb` in a notebook-capable environment such as VS Code or Jupyter and run its cells in order. The notebook reads the generated dataset, evaluates the 2024–2026 experiments, and exports the 2026 model, ordered features, and away cutoff.

Keep these three artifacts together: their feature list and cutoff belong to the same fitted model.

### 4. Generate predictions for a date

Set the call at the bottom of `predictToday.py`, for example:

```python
form_df(day=13, month=12, year=2025)
```

Then run:

```bash
python predictToday.py
```

This overwrites `daily_predictions.csv`. For the included model, use a date in the 2025–2026 season to reproduce the historical-demo workflow. The function fetches prior games, builds pregame snapshots, applies feature preprocessing, selects the saved model's ordered inputs, and attaches predictions to game details by game ID.

The exported columns are `game_id`, `start_date`, `away_team`, `home_team`, `spread`, `pred_edge`, `venue`, `city`, and `state`. Selection rules and highlighting are applied in Streamlit.

### 5. View the dashboard

```bash
python -m streamlit run streamLit.py
```

Run commands from the repository root because input and output paths are relative to the working directory.

## Limitations

- Multiple features, modeling approaches, and thresholds were explored during development, including experiments involving 2026. These evaluations are retrospective.
- Strict cutoffs produce small samples; season-stage subsets are smaller still. A few outcomes can materially change observed win rates.
- Quantile selections overlap and are not independent experiments. The notebook's quantile chart omits points with fewer than 50 non-push decisions.
- Results depend on source-data coverage and historical line timing. A historical reconstruction does not establish that the same line was available at a particular decision time.
- Win rates alone do not establish achievable profitability. Pricing, line movement, and execution conditions matter.
- The included CSV illustrates the application on one historical date; it is not a prospective prediction record.

## Planned improvements

- Refactor repeated feature engineering into shared functions used by training and inference.
- Compare historical-date inference features and predictions against the notebook.
- Improve configuration, API-response handling, and empty-schedule behavior.
- Record predictions before games in a future season for prospective evaluation.
