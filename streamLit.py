import streamlit as st
import pandas as pd
import joblib

st.set_page_config(layout="wide")

# Load predictions and the matching model's signed away cutoff.
df = pd.read_csv("daily_predictions.csv")
away_cutoff = float(joblib.load("away_cutoff.joblib"))

df = df.rename(columns={
    "start_date": "Start Date",
    "away_team": "Away Team",
    "home_team": "Home Team",
    "venue": "Venue",
    "city": "City",
    "state": "State",
    "spread": "Spread",
    "pred_edge": "Predicted Edge",
})

# Parse timestamps before sorting or formatting.
df["Start Date DT"] = (
    pd.to_datetime(df["Start Date"], utc=True)
    .dt.tz_convert("America/New_York")
)

df = df.sort_values("Start Date DT").reset_index(drop=True)

df["Start Date"] = (
    df["Start Date DT"].dt.strftime("%Y/%m/%d %I:%M %p")
)

# The selected policy uses only away predictions.
away_mask = (
    df["Predicted Edge"].lt(0)
    & df["Predicted Edge"].le(away_cutoff)
)

def highlight_teams(row):
    styles = pd.Series("", index=row.index)

    if (
        row["Predicted Edge"] < 0
        and row["Predicted Edge"] <= away_cutoff
    ):
        styles["Away Team"] = "background-color: lightgreen"

    return styles

number_format = {
    "Predicted Edge": "{:+.3f}",
    "Spread": "{:+.1f}",
}

# Page heading and model interpretation.
st.title("Predicted Edges vs Spread")
st.caption(
    "NCAA Men's Basketball • Historical demo using the 2026 model "
    "• All times Eastern"
)
st.caption(
    "Spread is from the home team's perspective. "
    "Negative predicted edge favors away; positive favors home. "
    "Highlighted selections use the validation-derived away "
    "95th-percentile policy."
)

# Summary metrics.
c1, c2, c3 = st.columns(3)

c1.metric("Eligible games", f"{len(df):,}")
c2.metric("Away selections", f"{away_mask.sum():,}")
c3.metric("Away cutoff", f"{away_cutoff:+.4f}")

st.divider()

# Selected away plays.
st.subheader("Away Selections")
st.caption(f"Predicted edge ≤ {away_cutoff:+.4f}")

selection_cols = [
    "Start Date",
    "Away Team",
    "Home Team",
    "Spread",
    "Predicted Edge",
]

df_away = (
    df.loc[away_mask, selection_cols]
    .sort_values("Predicted Edge")
)

st.dataframe(
    df_away.style
    .format(number_format)
    .set_properties(
        subset=["Away Team"],
        **{"background-color": "lightgreen"},
    ),
    width="stretch",
    hide_index=True,
)

# Full table with team filtering and sorting.
st.subheader("All Eligible Games")

all_teams = sorted(
    pd.unique(
        pd.concat([df["Away Team"], df["Home Team"]])
        .dropna()
    )
)

team_pick = st.selectbox(
    "Filter by team (type to search)",
    options=["(All teams)"] + all_teams,
)

display_cols = [
    "Start Date DT",
    "Start Date",
    "Away Team",
    "Home Team",
    "Spread",
    "Predicted Edge",
    "Venue",
    "City",
    "State",
]

df_all = df[display_cols].copy()

if team_pick != "(All teams)":
    df_all = df_all.loc[
        df_all["Away Team"].eq(team_pick)
        | df_all["Home Team"].eq(team_pick)
    ]

sort_mode = st.radio(
    "Sort",
    [
        "Start time",
        "Predicted edge: lowest first",
        "Predicted edge: highest first",
    ],
    horizontal=True,
)

if sort_mode == "Predicted edge: lowest first":
    df_all = df_all.sort_values("Predicted Edge")
elif sort_mode == "Predicted edge: highest first":
    df_all = df_all.sort_values(
        "Predicted Edge", ascending=False
    )
else:
    df_all = df_all.sort_values("Start Date DT")

df_all = df_all.drop(columns=["Start Date DT"])

st.dataframe(
    df_all.style
    .format(number_format)
    .apply(highlight_teams, axis=1),
    width="stretch",
    hide_index=True,
)