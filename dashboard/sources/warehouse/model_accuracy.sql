select
    model_season_id,
    season,
    model_name,
    is_point_in_time,
    game_type,
    games_scored,
    accuracy,
    log_loss,
    brier_score,
    brier_skill_score,
    mean_absolute_margin_error,
    mean_margin_bias
from marts.mart_model_accuracy
