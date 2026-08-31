-- Team box score lines, with the shooting rates the four factors need.

with source as (

    select * from {{ source('raw', 'ncaa_team_box') }}

),

renamed as (

    select
        cast(game_id as varchar) as game_id,
        cast(season as integer) as season,
        cast(team_id as varchar) as team_id,
        team_name,

        cast(field_goals_made as integer) as field_goals_made,
        cast(field_goals_attempted as integer) as field_goals_attempted,
        cast(three_pointers_made as integer) as three_pointers_made,
        cast(three_pointers_attempted as integer) as three_pointers_attempted,
        cast(free_throws_made as integer) as free_throws_made,
        cast(free_throws_attempted as integer) as free_throws_attempted,
        cast(rebounds as integer) as rebounds,
        cast(offensive_rebounds as integer) as offensive_rebounds,
        cast(defensive_rebounds as integer) as defensive_rebounds,
        cast(assists as integer) as assists,
        cast(steals as integer) as steals,
        cast(blocks as integer) as blocks,
        cast(turnovers as integer) as turnovers,
        cast(fouls as integer) as fouls,
        cast(extracted_at as timestamp) as extracted_at

    from source

),

derived as (

    select
        *,

        -- Effective field goal percentage: a three is worth 1.5 twos, so a
        -- raw FG% understates a team that shoots well from distance.
        case
            when field_goals_attempted > 0
                then (field_goals_made + 0.5 * three_pointers_made) * 1.0
                     / field_goals_attempted
        end as effective_fg_pct,

        case
            when field_goals_attempted > 0
                then free_throws_attempted * 1.0 / field_goals_attempted
        end as free_throw_rate,

        -- The standard possession estimate. Free throws are worth ~0.475 of a
        -- possession because most trips are two shots and only the last ends it.
        field_goals_attempted
            - offensive_rebounds
            + turnovers
            + 0.475 * free_throws_attempted as estimated_possessions

    from renamed

)

select * from derived
