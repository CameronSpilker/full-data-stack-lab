select
    season_status_id,
    schedule_season,
    schedule_season_label,
    data_season,
    data_season_label,
    is_preseason,
    completed_games,
    scheduled_games,
    next_game_date
from marts.mart_season_status
