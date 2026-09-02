-- Adjusted efficiency, reduced to the latest snapshot per season.
--
-- Ratings are recomputed after every game, so a season accumulates many
-- snapshots. Only the most recent describes the team as it stands now, which
-- is what a prediction should use.
--
-- The source is collegebasketballdata.com, which keys ratings on the same
-- team id as every other table here. It replaced Barttorvik, whose CDN refuses
-- requests from data centres, so the scheduled pipeline could never read it.

with source as (

    select * from {{ source('raw', 'ncaa_ratings') }}

),

latest as (

    select *
    from source
    qualify
        row_number() over (
            partition by season, team_id order by snapshot_date desc
        ) = 1

),

renamed as (

    select
        cast(season as integer) as season,
        cast(team_id as varchar) as team_id,
        team_name as rating_team_name,
        conference as rating_conference,

        cast(wins as integer) as wins,
        cast(losses as integer) as losses,

        adj_oe as adjusted_offensive_efficiency,
        adj_de as adjusted_defensive_efficiency,
        adj_margin as adjusted_efficiency_margin,
        adj_tempo as adjusted_tempo,

        efg_pct as effective_fg_pct,
        efg_pct_allowed as effective_fg_pct_allowed,
        turnover_pct,
        turnover_pct_forced,
        off_reb_pct as offensive_rebound_pct,
        -- A team's defensive rebound share is what its opponents did not get
        -- on the offensive glass.
        100 - off_reb_pct_allowed as defensive_rebound_pct,
        ft_rate as free_throw_rate,
        ft_rate_allowed as free_throw_rate_allowed,
        two_pt_pct as two_point_pct,
        two_pt_pct_allowed as two_point_pct_allowed,
        three_pt_pct as three_point_pct,
        three_pt_pct_allowed as three_point_pct_allowed,

        cast(snapshot_date as date) as snapshot_date,
        cast(extracted_at as timestamp) as extracted_at

    from latest

)

select * from renamed
