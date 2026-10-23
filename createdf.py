import pandas as pd
import os
import cbbd
from cbbd.rest import ApiException
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Convert cbbd data to dictionary
def to_dict(x):
    return x.model_dump() if hasattr(x, "model_dump") else dict(x)


# For a given year, start date, and end date, fetch all game data, team box score data, and betting line data
def fetch_all_season_data(year: int, start_date: datetime, end_date: datetime):
    api_key = os.getenv("CBBD_API_KEY")
    
    cfg = cbbd.Configuration(access_token=api_key)
    with cbbd.ApiClient(cfg) as api_client:
        games_api = cbbd.GamesApi(api_client)
        lines_api = cbbd.LinesApi(api_client)

        # Team boxscores for ALL games
        game_teams = games_api.get_game_teams(season=year, start_date_range=start_date, end_date_range=end_date)

        # Betting lines for the season (no season_type)
        lines = lines_api.get_lines(season=year, start_date_range=start_date, end_date_range=end_date)

    game_teams_df = pd.DataFrame([to_dict(gt) for gt in game_teams])
    lines_raw_df = pd.DataFrame([to_dict(l) for l in lines])
    return game_teams_df, lines_raw_df


# Method to get the entire years worth of ncaa games (not just first 3000)
def get_entire_year(year: int):
    # Debug check
    print(year)

    # Initialize df and get intial date range of games
    game_teams_df, lines_raw_df = fetch_all_season_data(
        year=year,
        start_date=datetime(year - 1, 10, 28, 0, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(year - 1, 11, 15, 23, 59, 59, tzinfo=timezone.utc),
    )
    print(len(game_teams_df))
    print(len(lines_raw_df))
    print()

    # Ranges for the rest of the dates
    startDates = [(11, 16), (12, 1), (1, 1), (1, 16), (2, 1), (2, 16), (3, 2)]
    endDates = [(11, 30), (12, 31), (1, 15), (1, 31), (2, 15), (3, 1), (5, 5)]

    # Loop to pull games from every range (all games in the season)
    for i in range(len(startDates)):
        cur_year = year
        if (startDates[i][0] > 5):
            cur_year -= 1
        
        game_teams_df_temp, lines_raw_df_temp = fetch_all_season_data(
            year=year,
            start_date=datetime(cur_year, startDates[i][0], startDates[i][1], 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(cur_year, endDates[i][0], endDates[i][1], 23, 59, 59, tzinfo=timezone.utc),
        )

        # Concatenate new info to data frames
        game_teams_df = pd.concat([game_teams_df, game_teams_df_temp], ignore_index=True)
        lines_raw_df = pd.concat([lines_raw_df, lines_raw_df_temp], ignore_index=True)

        # Sanity check
        print(len(game_teams_df_temp))
        print(len(lines_raw_df_temp))
        print()
    
    # Return dfs
    return game_teams_df, lines_raw_df


# Safe div method for stats computations
def safe_div(num, den):
    return (num / den) if den != 0 else 0.0


# Recursive dictionary conversion method for API object
def to_dict_recursive(x):
    if x is None:
        return None

    # Pydantic v2
    if hasattr(x, "model_dump"):
        return to_dict_recursive(x.model_dump())

    # Pydantic v1
    if hasattr(x, "dict"):
        return to_dict_recursive(x.dict())

    # Already a dict
    if isinstance(x, dict):
        return {k: to_dict_recursive(v) for k, v in x.items()}

    # Lists / tuples
    if isinstance(x, (list, tuple)):
        return [to_dict_recursive(v) for v in x]

    # Plain object (like GameBoxScoreTeamStatsPoints, etc.)
    if hasattr(x, "__dict__"):
        return {k: to_dict_recursive(v) for k, v in vars(x).items()}

    # Primitive
    return x


# Missing or undefined ratios should not become artificial zeros.
def game_ratio(numerator, denominator):
    if (numerator is None or denominator is None or denominator <= 0):
        return float("nan")
    return numerator / denominator


def compute_stats_get_lines(game_teams_2024: pd.DataFrame, lines_raw_2024: pd.DataFrame):
    # Sort team_games df by team_id
    game_teams_2024_sorted = game_teams_2024.sort_values(["team_id", "start_date"]).reset_index(drop=True)

    # Dataframe which will hold team stats prior to game_id
    # seasonStats = pd.DataFrame(columns=['game_id', 'team_id', 'season', 'offensive_rating', 'defensive_rating', 'net_rating', 'pace',
                                        # 'effective_field_goal_percentage', 'opp_effective_field_goal_percentage', 'true_shooting_percentage',
                                        # 'opp_true_shooting_percentage', 'three_point_attempt_rate', 'opp_three_point_attempt_rate', 
                                        # 'two_point_field_goal_percentage', 'opp_two_point_field_goal_percentage', 
                                        # 'three_point_field_goal_percentage', 'opp_three_point_field_goal_percentage', 'turnover_rate',
                                        # 'opp_turnover_rate', 'offensive_rebound_percentage', 'defensive_rebound_percentage', 'free_throw_rate',
                                        # 'opp_free_throw_rate', 'assist_rate', 'opp_assist_rate', 'steal_rate', 'block_rate',
                                        # 'points_in_the_paint_share', 'opp_points_in_the_paint_share', 'fast_break_scroing_rate',
                                        # 'points_off_turnovers_rate', 'foul_rate', 'opp_foul_rate', 'effective_field_goal_difference',
                                        # 'turnover_difference', 'free_throw_difference'])

    # List to hold each record of the new dataframe, will do df = pd.DataFrame(rows) after
    rows = []

    # For ewm features
    alpha = 0.15

    ewm_features = [
        "net_rating",
        "offensive_rating",
        "defensive_rating",
        "effective_field_goal_percentage",
        "opp_effective_field_goal_percentage",
        "true_shooting_percentage",
        "turnover_rate",
        "offensive_rebound_percentage",
        "pace",
        "three_point_attempt_rate",
        "free_throw_rate",
        "opp_free_throw_rate",
        "three_point_field_goal_percentage"
    ]

    for team, team_df in game_teams_2024_sorted.groupby("team_id"):
        ## Set up vars to track total values here, at team level right now

        # Reset ewm stats for team.
        ewm_state = {feature: None for feature in ewm_features}

        # Games played
        g = 0
        # Games won
        w = 0

        ## Stats from team_stats field
        # Total field goals made
        fgm = 0
        # Total field goals attempted
        fga = 0
        # Total two point field goals made
        twfga = 0
        # Total two point field goals attempted
        twfgm =0
        # Total three point field goals made
        thfgm = 0
        # Total three point field goals attempted
        thfga = 0
        # (Going to do average per game) Total free throws made
        ftm = 0
        # Total free throws attemped
        fta = 0
        # Total rebounds
        reb = 0
        # Total offensive rebounds
        oreb = 0
        # Total defensive rebounds
        dreb = 0
        # Total turnovers (not team_total)
        turn = 0
        # Total fouls (use total field)
        foul = 0
        # Total fastbreak points
        fbp = 0
        # Total points off turnovers
        pot = 0
        # Total points in the paint
        pitp = 0
        # Total points
        point = 0
        # Total assists
        ass = 0
        # Total blocks
        blk = 0
        # Total steals
        stl = 0
        # Total possessions
        pos = 0

        ## Stats from opponent stats field
        # Total opp fgm
        oppfgm = 0
        # Total opp fga
        oppfga = 0
        # Total opp 2pfgm
        opptwfgm = 0
        # Total opp 2pfga
        opptwfga = 0
        # Total opp 3pfgm
        oppthfgm = 0
        # Total opp 3pfga
        oppthfga = 0
        # Total opp fta
        oppfta = 0
        # Total opp rebounds
        oppreb = 0
        # Total opp off rebounds
        opporeb = 0
        # Total opp def rebounds
        oppdreb = 0
        # Total opp turnovers (total not team_total)
        oppturn = 0
        # Total opp fouls -> fouls drawn
        oppfoul = 0
        # Total opp fastbreak pts
        oppfbp = 0
        # Total opp ptsOffTurnovers
        opppot = 0
        # Total opp points in paint
        opppitp = 0
        # Total opp points
        opppoint = 0
        # Total opp assists
        oppass = 0
        # Total opp blocks
        oppblk = 0
        # Total opp steals
        oppstl = 0
        # Total opp possesions
        opppos = 0

        # Engineered features -> do this in the inner for loop
        # Offensive rating
        # Defensive rating
        # Net rating
        # Pace (pos / g)
        # effective field goal pct ((fgm + 0.5 * thfgm) / fga)
        # opponent effective field goal pct
        # true shooting pct (point / (2 * (fga + 0.44 * fta)))
        # opponent true shooting pct
        # Three point attempt rate (thfga / fga)
        # opp three point attempt rate
        # two point field goal percentage
        # opp two point field goal percentage
        # three point field goal percentage
        # opp three point field goal percentage
        # Turnover rate (turn / pos)
        # opponent turnover rate
        # Offensive rebound percentage (oreb / (oreb + oppdreb))
        # Defensive rebound percentage (dreb / (dreb + opporeb))
        # Free throw rate (fta / fga)
        # opp free throw rate
        # Assist rate (ass / fgm)
        # opp assist rate
        # Steal rate (stl / opppos)
        # Block rate (blk / oppfga)
        # Points in the paint share (pitp / point)
        # opp points in the paint share
        # Fast break scoring rate (fbp / point)
        # Points off turnovers rate (pot / point)
        # foul_rate (foul / pos)
        # fouls drawn (oppfoul / pos)
        # efg diff (efg - opp efg)
        # tov diff (opp tov - tov)
        # free throw diff (ftr - oppftr)



        for _, row in team_df.iterrows():
            # Convert team_stats and opponent_stats fields to dictionary
            team_stats_dict = to_dict_recursive(row["team_stats"])
            opponent_stats_dict = to_dict_recursive(row["opponent_stats"])

            # Check if missing certain stats and skip iteration if so
            if team_stats_dict.get("possessions") is None or opponent_stats_dict.get("possessions") is None:
                continue
            if team_stats_dict.get("points", {}).get("total") is None or opponent_stats_dict.get("points", {}).get("total") is None:
                continue
            if team_stats_dict.get("field_goals", {}).get("attempted") is None or opponent_stats_dict.get("field_goals", {}).get("attempted") is None:
                continue

            rows.append({
                "game_id": row["game_id"],
                "team_id": row["team_id"],
                "season": row["season"],
                "start_date": row["start_date"],
                "opp_id": row["opponent_id"],
                "is_home": row["is_home"],
                "conference_game": row["conference_game"],
                "neutral_site": row["neutral_site"],
                "game_type": row["game_type"],
                "offensive_rating": 100 * safe_div(point, pos),
                "defensive_rating": 100 * safe_div(opppoint, opppos),
                "net_rating": (100 * safe_div(point, pos)) - (100 * safe_div(opppoint, opppos)),
                "pace": safe_div(pos, g),
                "effective_field_goal_percentage": safe_div((fgm + 0.5 * thfgm), fga),
                "opp_effective_field_goal_percentage": safe_div((oppfgm + 0.5 * oppthfgm), oppfga),
                "true_shooting_percentage": safe_div(point, (2 * (fga + 0.44 * fta))),
                "opp_true_shooting_percentage": safe_div(opppoint, (2 * (oppfga + 0.44 * oppfta))),
                "three_point_attempt_rate": safe_div(thfga, fga),
                "opp_three_point_attempt_rate": safe_div(oppthfga, oppfga),
                "two_point_field_goal_percentage": safe_div(twfgm, twfga),
                "opp_two_point_field_goal_percentage": safe_div(opptwfgm, opptwfga),
                "three_point_field_goal_percentage": safe_div(thfgm, thfga),
                "opp_three_point_field_goal_percentage": safe_div(oppthfgm, oppthfga),
                "turnover_rate": safe_div(turn, pos),
                "opp_turnover_rate": safe_div(oppturn, opppos),
                "offensive_rebound_percentage": safe_div(oreb, (oreb + oppdreb)),
                "defensive_rebound_percentage": safe_div(dreb, (dreb + opporeb)),
                "free_throw_rate": safe_div(fta, fga),
                "opp_free_throw_rate": safe_div(oppfta, oppfga),
                "assist_rate": safe_div(ass, fgm),
                "opp_assist_rate": safe_div(oppass, oppfgm),
                "steal_rate": safe_div(stl, opppos),
                "block_rate": safe_div(blk, oppfga),
                "points_in_the_paint_share": safe_div(pitp, point),
                "opp_points_in_the_paint_share": safe_div(opppitp, opppoint),
                "fast_break_scoring_rate": safe_div(fbp, pos),
                "points_off_turnovers_rate": safe_div(pot, pos),
                "foul_rate": safe_div(foul, pos),
                "opp_foul_rate": safe_div(oppfoul, pos),
                "effective_field_goal_difference": safe_div((fgm + 0.5 * thfgm), fga) - safe_div((oppfgm + 0.5 * oppthfgm), oppfga),
                "turnover_difference": safe_div(oppturn, opppos) - safe_div(turn, pos),
                "free_throw_difference": safe_div(fta, fga) - safe_div(oppfta, oppfga),
                "opp_steal_rate": safe_div(oppstl, pos),
                "opp_block_rate": safe_div(oppblk, fga),
                "games_played": g,
                "winning_percentage": safe_div(w, g),
                "points_scored": team_stats_dict['points']['total'],
                "possessions": team_stats_dict['possessions']
            })

            # Copy the state BEFORE incorporating the current game.
            rows[-1].update({
                f"{feature}_ewm": (float("nan") if value is None else value) for feature, value in ewm_state.items()
            })

            t = team_stats_dict
            o = opponent_stats_dict

            game_off = 100 * game_ratio(t["points"]["total"], t["possessions"],)

            game_def = 100 * game_ratio(o["points"]["total"], o["possessions"],)

            game_values = {
                "offensive_rating": game_off,
                "defensive_rating": game_def,
                "net_rating": game_off - game_def,

                "effective_field_goal_percentage": game_ratio(
                    t["field_goals"]["made"]
                    + 0.5 * t["three_point_field_goals"]["made"],
                    t["field_goals"]["attempted"],
                ),

                "opp_effective_field_goal_percentage": game_ratio(
                    o["field_goals"]["made"]
                    + 0.5 * o["three_point_field_goals"]["made"],
                    o["field_goals"]["attempted"],
                ),

                "true_shooting_percentage": game_ratio(
                    t["points"]["total"],
                    2 * (
                        t["field_goals"]["attempted"]
                        + 0.44 * t["free_throws"]["attempted"]
                    ),
                ),

                "turnover_rate": game_ratio(
                    t["turnovers"]["total"],
                    t["possessions"],
                ),

                "offensive_rebound_percentage": game_ratio(
                    t["rebounds"]["offensive"],
                    t["rebounds"]["offensive"]
                    + o["rebounds"]["defensive"],
                ),

                # Matches your existing pace definition.
                "pace": t["possessions"],

                "three_point_attempt_rate": game_ratio(
                    t["three_point_field_goals"]["attempted"],
                    t["field_goals"]["attempted"],
                ),

                "free_throw_rate": game_ratio(
                    t["free_throws"]["attempted"],
                    t["field_goals"]["attempted"],
                ),

                "opp_free_throw_rate": game_ratio(
                    o["free_throws"]["attempted"],
                    o["field_goals"]["attempted"],
                ),

                "three_point_field_goal_percentage": game_ratio(
                    t["three_point_field_goals"]["made"],
                    t["three_point_field_goals"]["attempted"],
                )
            }

            # Update the state for the NEXT game.
            for feature, current_value in game_values.items():
                if pd.isna(current_value):
                    continue  # Preserve the previous state if this value is unavailable.

                previous_value = ewm_state[feature]

                if previous_value is None:
                    ewm_state[feature] = current_value
                else:
                    ewm_state[feature] = (
                        alpha * current_value
                        + (1 - alpha) * previous_value
                    )

            # Update totals
            g += 1

            if (team_stats_dict['points']['total'] > opponent_stats_dict['points']['total']):
                w += 1
            
            # From team_stats_dict
            fgm += team_stats_dict['field_goals']['made']
            fga += team_stats_dict['field_goals']['attempted']
            twfgm += team_stats_dict['two_point_field_goals']['made']
            twfga += team_stats_dict['two_point_field_goals']['attempted']
            thfgm += team_stats_dict['three_point_field_goals']['made']
            thfga += team_stats_dict['three_point_field_goals']['attempted']
            ftm += team_stats_dict['free_throws']['made']
            fta += team_stats_dict['free_throws']['attempted']
            reb += team_stats_dict['rebounds']['total']
            oreb += team_stats_dict['rebounds']['offensive']
            dreb += team_stats_dict['rebounds']['defensive']
            turn += team_stats_dict['turnovers']['total']
            foul += team_stats_dict['fouls']['total']
            fbp += team_stats_dict['points']['fast_break']
            pot += team_stats_dict['points']['off_turnovers']
            pitp += team_stats_dict['points']['in_paint']
            point += team_stats_dict['points']['total']
            ass += team_stats_dict['assists']
            blk += team_stats_dict['blocks']
            stl += team_stats_dict['steals']
            pos += team_stats_dict['possessions']

            # From opponent_stats_dict
            oppfgm += opponent_stats_dict['field_goals']['made']
            oppfga += opponent_stats_dict['field_goals']['attempted']
            opptwfgm += opponent_stats_dict['two_point_field_goals']['made']
            opptwfga += opponent_stats_dict['two_point_field_goals']['attempted']
            oppthfgm += opponent_stats_dict['three_point_field_goals']['made']
            oppthfga += opponent_stats_dict['three_point_field_goals']['attempted']
            oppfta += opponent_stats_dict['free_throws']['attempted']
            oppreb += opponent_stats_dict['rebounds']['total']
            opporeb += opponent_stats_dict['rebounds']['offensive']
            oppdreb += opponent_stats_dict['rebounds']['defensive']
            oppturn += opponent_stats_dict['turnovers']['total']
            oppfoul += opponent_stats_dict['fouls']['total']
            oppfbp += opponent_stats_dict['points']['fast_break']
            opppot += opponent_stats_dict['points']['off_turnovers']
            opppitp += opponent_stats_dict['points']['in_paint']
            opppoint += opponent_stats_dict['points']['total']
            oppass += opponent_stats_dict['assists']
            oppblk += opponent_stats_dict['blocks']
            oppstl += opponent_stats_dict['steals']
            opppos += opponent_stats_dict['possessions']

    # Convert list of rows to dataframe
    seasonStats = pd.DataFrame(rows)

    # Keep only games where both teams are present (2 rows per game)
    seasonStats = seasonStats[
        seasonStats.groupby("game_id")["game_id"].transform("count") == 2
    ].copy()

    # Game metadata and should only appear once
    game_cols = ["game_id", "season", "start_date", "conference_game", "neutral_site", "game_type"]

    # Identifiers
    id_cols = ['team_id', 'opp_id', 'is_home']

    # The rest are feature columns
    feature_cols = [c for c in seasonStats.columns if c not in game_cols + id_cols]

    # Build home and away tables
    home = seasonStats[seasonStats["is_home"] == True].copy()
    away = seasonStats[seasonStats["is_home"] == False].copy()

    # Prefix columns
    home = home[game_cols + ["team_id"] + feature_cols].rename(columns={
        "team_id": "home_team_id",
        **{c: f"home_{c}" for c in feature_cols}
    })

    away = away[game_cols + ["team_id"] + feature_cols].rename(columns={
        "team_id": "away_team_id",
        **{c: f"away_{c}" for c in feature_cols}
    })

    # Merge on the shared game_id key
    game_level = home.merge(
        away.drop(columns=[c for c in game_cols if c != "game_id"]),  # prevent duplicate metadata
        on="game_id",
        how="inner"
    )

    # Add in featuring denoting who won and the margin of victory
    game_level["home_win"] = (
        game_level["home_points_scored"] > game_level["away_points_scored"]
    ).astype(int)

    game_level["home_margin"] = (
        game_level["home_points_scored"] - game_level["away_points_scored"]
    )

    game_level = game_level.sort_values(by="start_date").reset_index(drop=True)

    # Incorporate betting lines and spreads

    # variable to hold records
    rows = []

    for game_id, lines in zip(lines_raw_2024['game_id'], lines_raw_2024['lines']):
        lines_obj = to_dict_recursive(lines)

        # Check for empty list
        if not lines_obj:
            continue

        # try to find DraftKings then fallback to other providers in order, if no lines at all then skip
        selected_line = (
            next((l for l in lines_obj if l.get("provider").lower().replace(" ", "") == "draftkings"), None)
            or next((l for l in lines_obj if l.get("provider").lower().replace(" ", "") == "fanduel"), None)
            or next((l for l in lines_obj if l.get("provider").lower().replace(" ", "") == "caesars"), None)
            or next((l for l in lines_obj if l.get("provider").lower().replace(" ", "") == "espnbet"), None)
            or lines_obj[0]
        )

        rows.append({
            'game_id': game_id,
            'provider': selected_line.get('provider'),
            'spread': selected_line.get('spread'),
            'over_under': selected_line.get('over_under'),
            'home_moneyline': selected_line.get('home_moneyline'),
            'away_moneyline': selected_line.get('away_moneyline')
        })

    lineInfo = pd.DataFrame(rows)

    # Merge into game level df
    game_level = game_level.merge(lineInfo, on="game_id", how="left")

    return game_level


# Method called by main to execute entire pipeline, saving a csv file of structured data
def run_pipeline():

    dfs = []

    # Main loop to get each year
    for i in range(2014, 2027):
        box_scores, lines = get_entire_year(year=i)
        dfs.append(compute_stats_get_lines(game_teams_2024=box_scores, lines_raw_2024=lines))
    
    # Concatentate dfs and save as a csv
    final_df = pd.concat(dfs, ignore_index=True)
    final_df.to_csv("cbbData_2014_2026_endEWM.csv", index=False)

if __name__ == "__main__":
    run_pipeline()