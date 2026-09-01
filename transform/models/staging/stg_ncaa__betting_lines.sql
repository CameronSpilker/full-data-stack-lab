-- Betting lines, one row per game per sportsbook.
--
-- Books disagree by a half point or so, and some cover games the others skip.
-- This model keeps every quote; `int_game_market` reduces them to a consensus.

with source as (

    select * from {{ source('raw', 'ncaa_betting_lines') }}

),

renamed as (

    select
        cast(game_id as varchar) as game_id,
        cast(season as integer) as season,
        provider,
        cast(spread as double) as home_spread,
        cast(over_under as double) as over_under,
        cast(home_moneyline as integer) as home_moneyline,
        cast(away_moneyline as integer) as away_moneyline,
        cast(extracted_at as timestamp) as extracted_at

    from source
    where spread is not null

)

select * from renamed
