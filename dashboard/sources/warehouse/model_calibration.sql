select
    calibration_bucket_id,
    model_name,
    is_point_in_time,
    bucket_label,
    bucket_floor_pct,
    games,
    mean_predicted_probability,
    observed_win_rate,
    calibration_error
from marts.mart_model_calibration
