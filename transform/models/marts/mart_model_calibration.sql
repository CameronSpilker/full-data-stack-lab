-- Calibration: when a model says 70%, does it happen 70% of the time?
--
-- This is the chart that decides whether a tournament probability can be
-- believed. A model can rank teams perfectly and still be badly calibrated —
-- systematically overconfident, say — and a bracket built on overconfident
-- numbers will look far more certain than the tournament actually is.

with predictions as (

    select * from {{ ref('int_game_predictions') }}

),

bucketed as (

    select
        model_name,
        is_point_in_time,
        least(floor(home_win_probability * 10), 9) as bucket_index,
        home_win_probability,
        case when home_won then 1.0 else 0.0 end as outcome
    from predictions

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['model_name', 'bucket_index']) }}
            as calibration_bucket_id,
        model_name,
        is_point_in_time,
        cast(bucket_index * 10 as integer) as bucket_floor_pct,
        cast(bucket_index * 10 + 10 as integer) as bucket_ceiling_pct,
        concat(
            cast(cast(bucket_index * 10 as integer) as varchar), '-',
            cast(cast(bucket_index * 10 + 10 as integer) as varchar), '%'
        ) as bucket_label,
        count(*) as games,
        avg(home_win_probability) as mean_predicted_probability,
        avg(outcome) as observed_win_rate,
        avg(outcome) - avg(home_win_probability) as calibration_error

    from bucketed
    group by 1, 2, 3, 4, 5, 6

)

select * from final
