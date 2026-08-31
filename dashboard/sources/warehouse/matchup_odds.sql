select
    matchup_id,
    season,
    team_id,
    team_name,
    conference_name,
    opponent_team_id,
    opponent_name,
    opponent_conference,
    predicted_margin_neutral,
    win_probability_neutral
from marts.mart_matchup_odds
