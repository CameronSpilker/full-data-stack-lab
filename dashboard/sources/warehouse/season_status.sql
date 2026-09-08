select
    season_status_id,
    schedule_season,
    schedule_season_label,
    data_season,
    data_season_label,
    awaited_season,
    awaited_season_label,
    is_preseason,
    is_offseason,
    phase,
    completed_games,
    unplayed_games,
    upcoming_games,
    next_game_date,
    last_completed_game_date
from marts.mart_season_status
