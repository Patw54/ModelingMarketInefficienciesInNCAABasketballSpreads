import pandas as pd
import os
import cbbd
from cbbd.rest import ApiException
import joblib
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
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

# # Method to get the entire years worth of ncaa games (not just first 3000) (changed to be year to date in this file)
# def get_entire_year(month: int, day: int, year: int):
#     # Debug check
#     print(year)

#     eastern = ZoneInfo("America/New_York")

#     # Initialize df and get intial date range of games
#     game_teams_df, lines_raw_df = fetch_all_season_data(
#         year=year,
#         start_date=datetime(year - 1, 10, 28, 0, 0, 0, tzinfo=timezone.utc),
#         end_date=datetime(year - 1, 11, 15, 23, 59, 59, tzinfo=timezone.utc),
#     )
#     print(len(game_teams_df))
#     print(len(lines_raw_df))
#     print()

#     # Ranges for the rest of the dates
#     startDates = [(11, 16), (12, 1), (1, 1), (1, 16), (2, 1), (2, 16), (3, 2)]
#     endDates = [(11, 30), (12, 31), (1, 15), (1, 31), (2, 15), (3, 1), (5, 5)]


#     hitEnd = False

#     # Loop to pull games from every range (all games in the season)
#     for i in range(len(startDates)):
#         cur_year = year
#         if (startDates[i][0] > 5):
#             cur_year -= 1

#         start_date = datetime(cur_year, startDates[i][0], startDates[i][1], 0, 0, 0, tzinfo=eastern)

#         if (endDates[i][0] >= month and endDates[i][1] >= day):
#             print("hit end date")
#             hitEnd = True
#             end_date = datetime(cur_year, month, day - 1, 23, 59, 59, tzinfo=eastern)
#         else:
#             end_date=datetime(cur_year, endDates[i][0], endDates[i][1], 23, 59, 59, tzinfo=eastern)
            
        
#         game_teams_df_temp, lines_raw_df_temp = fetch_all_season_data(
#             year=year,
#             start_date=start_date,
#             end_date=end_date,
#         )

#         # Concatenate new info to data frames
#         game_teams_df = pd.concat([game_teams_df, game_teams_df_temp], ignore_index=True)
#         lines_raw_df = pd.concat([lines_raw_df, lines_raw_df_temp], ignore_index=True)

#         # Sanity check
#         print(len(game_teams_df_temp))
#         print(len(lines_raw_df_temp))
#         print()

#         # if hit end date break loop
#         if hitEnd:
#             break
    
#     # Return dfs
#     return game_teams_df, lines_raw_df


# Method to get the season's NCAA games through the previous day
def get_entire_year(month: int, day: int, year: int):
    print(year)

    eastern = ZoneInfo("America/New_York")

    # Determine which calendar year the requested month belongs to.
    # For a 2026 season:
    #   Oct-Dec belong to 2025
    #   Jan-May belong to 2026
    target_year = year - 1 if month >= 10 else year

    # Stop at 11:59:59 PM on the day before the requested date.
    target_end = (
        datetime(
            target_year,
            month,
            day,
            0,
            0,
            0,
            tzinfo=eastern,
        )
        - timedelta(seconds=1)
    )

    # First fixed range
    initial_start = datetime(
        year - 1,
        10,
        28,
        0,
        0,
        0,
        tzinfo=eastern,
    )

    initial_scheduled_end = datetime(
        year - 1,
        11,
        15,
        23,
        59,
        59,
        tzinfo=eastern,
    )

    # Do not fetch beyond the requested target date.
    initial_end = min(initial_scheduled_end, target_end)

    game_teams_df, lines_raw_df = fetch_all_season_data(
        year=year,
        start_date=initial_start,
        end_date=initial_end,
    )

    print(len(game_teams_df))
    print(len(lines_raw_df))
    print()

    # If the requested cutoff occurred during the initial range,
    # there is no need to process later ranges.
    if target_end <= initial_scheduled_end:
        return game_teams_df, lines_raw_df

    start_dates = [
        (11, 16),
        (12, 1),
        (1, 1),
        (1, 16),
        (2, 1),
        (2, 16),
        (3, 2),
    ]

    end_dates = [
        (11, 30),
        (12, 31),
        (1, 15),
        (1, 31),
        (2, 15),
        (3, 1),
        (5, 5),
    ]

    # Pull each range until reaching the requested cutoff.
    for (start_month, start_day), (end_month, end_day) in zip(
        start_dates,
        end_dates,
    ):
        start_year = year - 1 if start_month >= 10 else year
        end_year = year - 1 if end_month >= 10 else year

        start_date = datetime(
            start_year,
            start_month,
            start_day,
            0,
            0,
            0,
            tzinfo=eastern,
        )

        scheduled_end_date = datetime(
            end_year,
            end_month,
            end_day,
            23,
            59,
            59,
            tzinfo=eastern,
        )

        # All remaining ranges occur after the desired cutoff.
        if start_date > target_end:
            print("Hit end date")
            break

        # Use either the full range end or the requested cutoff,
        # whichever comes first.
        end_date = min(scheduled_end_date, target_end)

        game_teams_df_temp, lines_raw_df_temp = fetch_all_season_data(
            year=year,
            start_date=start_date,
            end_date=end_date,
        )

        game_teams_df = pd.concat(
            [game_teams_df, game_teams_df_temp],
            ignore_index=True,
        )

        lines_raw_df = pd.concat(
            [lines_raw_df, lines_raw_df_temp],
            ignore_index=True,
        )

        print(len(game_teams_df_temp))
        print(len(lines_raw_df_temp))
        print()

        # The requested cutoff fell inside this range.
        if end_date == target_end:
            print("Hit end date")
            break

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


def compute_stats_get_lines(game_teams_2024: pd.DataFrame, lines_raw_2024: pd.DataFrame, todaysGames: pd.DataFrame):
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

        # after processing every game for this team, append a FINAL state snapshot
        # this contains totals INCLUDING the last game
        rows.append({
            "game_id": None,
            "team_id": team,
            "season": int(team_df["season"].iloc[-1]) if len(team_df) else None,
            "start_date": team_df["start_date"].max() if len(team_df) else None,  # last played date
            "opp_id": None,
            "is_home": None,
            "conference_game": None,
            "neutral_site": None,
            "game_type": "SNAPSHOT",

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

            # snapshot has no single-game points_scored
            "points_scored": None,
        })
        # Attach EWM state including the team's last completed game.
        rows[-1].update({
            f"{feature}_ewm": (
                float("nan") if value is None else value
            )
            for feature, value in ewm_state.items()
        })

    # Convert list of rows to dataframe
    seasonStats = pd.DataFrame(rows)

    ## In snapshots if home_team_id or away_team_id == team_id, then map in game_id from lines_raw_2024 -> ensure only correct days dates are in lines_raw_2024
    # lines_raw has strictly the day to predicts games
    snapshots = seasonStats[seasonStats["game_type"] == "SNAPSHOT"].copy()
    seasonStats = seasonStats[seasonStats["game_type"] != "SNAPSHOT"].copy()

    # keep only one snapshot per (team_id, season) (safest)
    snapshots = (
        snapshots.sort_values(["team_id", "season", "start_date"])
                .drop_duplicates(subset=["team_id", "season"], keep="last")
    )

    # columns to bring (exclude identifiers + metadata)
    snap_feature_cols = [c for c in snapshots.columns if c not in [
        "game_id", "team_id", "season", "start_date",
        "opp_id", "is_home", "conference_game", "neutral_site",
        "game_type", "points_scored"
    ]]

    # Build a "snapshot lookup" keyed by team_id + season
    snap_lookup = snapshots[["team_id", "season"] + snap_feature_cols].copy()

    # Build HOME team rows for today (shape matches seasonStats)
    today_home = todaysGames.merge(
        snap_lookup,
        left_on=["home_team_id", "season"],
        right_on=["team_id", "season"],
        how="left"
    ).assign(
        team_id=lambda d: d["home_team_id"],
        opp_id=lambda d: d["away_team_id"],
        is_home=True,   # or "PREDICT"
    )

    # Build AWAY team rows for today
    today_away = todaysGames.merge(
        snap_lookup,
        left_on=["away_team_id", "season"],
        right_on=["team_id", "season"],
        how="left"
    ).assign(
        team_id=lambda d: d["away_team_id"],
        opp_id=lambda d: d["home_team_id"],
        is_home=False,
    )

    # Ensure we carry required metadata columns that exist in seasonStats
    meta_cols = ["game_id", "season", "start_date", "conference_game", "neutral_site", "game_type"]
    id_cols   = ["team_id", "opp_id", "is_home"]

    # All feature columns in seasonStats (everything else)
    feature_cols = [c for c in seasonStats.columns if c not in meta_cols + id_cols]

    # Keep only columns that actually exist (to avoid KeyErrors)
    def keep_existing(df, cols):
        return [c for c in cols if c in df.columns]

    cols_needed = keep_existing(today_home, meta_cols + id_cols + feature_cols)

    today_home_teamrows = today_home[cols_needed].copy()
    today_away_teamrows = today_away[cols_needed].copy()

    today_team_rows = pd.concat([today_home_teamrows, today_away_teamrows], ignore_index=True)

    seasonStats = pd.concat([seasonStats, today_team_rows], ignore_index=True)

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

    for game_id, line_obj in zip(lines_raw_2024['game_id'], lines_raw_2024['lines']):
        lines_obj = to_dict_recursive(line_obj)

        # Check for empty list
        if not lines_obj:
            continue

        # try to find DraftKings then ESPN BET, then fallback to first available line
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


def form_df(day: int, month: int, year: int):
    # Define the current season (2025-2026 season is represented by the year 2026)
    season = year + 1 if month >= 9 else year

    box_scores, lines = get_entire_year(month=month, day=day, year=season)

    eastern = ZoneInfo("America/New_York")

    # Pull today's games and map to team ids to stats
    api_key = os.getenv("CBBD_API_KEY")
    cfg = cbbd.Configuration(access_token=api_key)
    with cbbd.ApiClient(cfg) as api_client:
        games_api = cbbd.GamesApi(api_client)
        lines_api = cbbd.LinesApi(api_client)

        # Define time window to pull games from
        start_date = datetime(year, month, day, 0, 0, 0, tzinfo=eastern)
        end_date   = datetime(year, month, day, 23, 59, 59, tzinfo=eastern)

        games = games_api.get_games(season=season, start_date_range=start_date, end_date_range=end_date)
        games_df = pd.DataFrame([to_dict(g) for g in games])

        # Betting lines for the season (no season_type)
        lines2 = lines_api.get_lines(season=season, start_date_range=start_date, end_date_range=end_date)

        lines_raw_df = pd.DataFrame([to_dict(l) for l in lines2])

    games_df['game_id'] = games_df['id']
    games_df = games_df.drop(columns=['id'])

    df2026 = compute_stats_get_lines(game_teams_2024=box_scores, lines_raw_2024=lines_raw_df, todaysGames=games_df)
    df2026 = df2026.sort_values(by='start_date').reset_index(drop=True)

    # Prepare historical games and today's pregame matchup rows.
    df = df2026.copy()
    df["start_date"] = pd.to_datetime(df["start_date"], utc=True)

    # Smooth pregame season-to-date statistics.
    # Individual-game *_ewm columns already exist and remain unchanged.
    smooth_feats = [
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

    smooth_cols = [
        f"{side}_{feature}_smoothed_ewm"
        for side in ["home", "away"]
        for feature in smooth_feats
    ]

    df = df.drop(columns=smooth_cols, errors="ignore")

    # Combine home and away appearances into each team's history.
    team_tables = []

    for side in ["home", "away"]:
        columns = ["game_id", "season", "start_date", f"{side}_team_id", *[f"{side}_{feature}" for feature in smooth_feats]]

        rename_map = {
            f"{side}_team_id": "team_id",
            **{
                f"{side}_{feature}": feature
                for feature in smooth_feats
            },
        }

        team_tables.append(df[columns].rename(columns=rename_map))

    team_history = pd.concat(team_tables, ignore_index=True)

    if team_history.duplicated(["season", "team_id", "game_id"]).any():
        raise ValueError("Duplicate team appearances found.")

    team_history = team_history.sort_values(["season", "team_id", "start_date", "game_id"]).reset_index(drop=True)

    # These inputs already exclude the current game's performance,
    # so no additional shift is needed.
    for feature in smooth_feats:
        team_history[f"{feature}_smoothed_ewm"] = (
            team_history.groupby(["season", "team_id"])[feature]
            .transform(
                lambda s: s.ewm(
                    alpha=0.15,
                    adjust=False,
                ).mean()
            )
        )

    # Attach smoothed pregame statistics to each matchup.
    for side in ["home", "away"]:
        lookup = team_history[
            [
                "game_id",
                "season",
                "team_id",
                *[
                    f"{feature}_smoothed_ewm"
                    for feature in smooth_feats
                ],
            ]
        ].rename(
            columns={
                "team_id": f"{side}_team_id",
                **{
                    f"{feature}_smoothed_ewm":
                        f"{side}_{feature}_smoothed_ewm"
                    for feature in smooth_feats
                },
            }
        )

        df = df.merge(
            lookup,
            on=["game_id", "season", f"{side}_team_id"],
            how="left",
            validate="one_to_one",
        )

    df = df.sort_values(["start_date", "game_id"]).reset_index(drop=True)

    # Explicitly create the tournament feature used by the notebook.
    # This also works when the fetched games contain no tournaments.
    df["game_type_TRNMNT"] = df["game_type"].eq("TRNMNT")

    # Match the notebook's eligibility criteria.
    # Apply this AFTER smoothing so earlier games remain in team histories.
    df_filtered = df.loc[df["spread"].notna() & (df["home_games_played"] >= 5) & (df["away_games_played"] >= 5)].copy()

    # Create home-minus-away differential features.
    home_cols = [
        c for c in df_filtered.columns
        if c.startswith("home_")
        and c not in ["home_games_played",  "home_margin"]
    ]

    for home_col in home_cols:
        away_col = home_col.replace("home_", "away_", 1)

        if away_col in df_filtered.columns:
            diff_col = home_col.replace("home_", "diff_", 1)
            df_filtered[diff_col] = (df_filtered[home_col] - df_filtered[away_col])

    # Only now restrict the prepared data to today's matchups.
    df_filtered["game_id"] = (df_filtered["game_id"].astype("Int64"))
    today_game_ids = games_df["game_id"].astype("Int64")

    df_today = df_filtered.loc[df_filtered["game_id"].isin(today_game_ids)].copy().reset_index(drop=True)

    # Load the model and its ordered feature list.
    model = joblib.load("model.joblib")
    model_features = joblib.load("model_features.joblib")

    # Prepare model inputs and attach predictions.
    X_today = df_today.loc[:, model_features].copy()

    if "neutral_site" in X_today.columns:
        X_today["neutral_site"] = pd.to_numeric(
            X_today["neutral_site"],
            errors="raise",
        ).astype(float)

    predictions = df_today[["game_id", "spread"]].copy()
    predictions["pred_edge"] = model.predict(X_today)

    # Attach game details.
    schedule = games_df[["game_id", "start_date", "away_team", "home_team", "venue", "city", "state"]].copy()

    schedule["game_id"] = schedule["game_id"].astype("Int64")

    game_preds_df = predictions.merge(
        schedule,
        on="game_id",
        how="left",
        validate="one_to_one",
    )

    game_preds_df["start_date"] = (pd.to_datetime(game_preds_df["start_date"], utc=True).dt.tz_convert("America/New_York"))

    # Choose the exported columns.
    game_preds_df = game_preds_df[["game_id", "start_date", "away_team", "home_team", "spread", "pred_edge", "venue", "city", "state"]]

    game_preds_df.to_csv("daily_predictions.csv", index=False)

    return game_preds_df

if __name__ == "__main__":
    form_df(day = 13, month = 12, year=2025)