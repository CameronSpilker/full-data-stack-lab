-- Four regions, sixteen seeds each, four teams on every seed line.
--
-- The S-curve that assigns regions is easy to get subtly wrong — an off-by-one
-- in the snake puts five teams on one seed line and three on another, which
-- changes every downstream probability and is invisible in a chart.

with by_seed as (

    select seed, count(*) as teams
    from {{ ref('mart_bracket') }}
    group by 1

),

by_region as (

    select region_name, count(*) as teams
    from {{ ref('mart_bracket') }}
    group by 1

)

select 'seed' as grouping, cast(seed as varchar) as value, teams
from by_seed
where teams != 4

union all

select 'region', region_name, teams
from by_region
where teams != 16
