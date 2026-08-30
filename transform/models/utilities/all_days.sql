{{ config(materialized='table') }}

-- Daily time spine required by the dbt semantic layer. Spans a fixed window
-- rather than the observed data so metric queries can ask for periods that
-- have no rows yet.

with spine as (

    select unnest(generate_series(
        date '2020-01-01',
        date '2030-12-31',
        interval 1 day
    )) as date_day

)

select cast(date_day as date) as date_day
from spine
