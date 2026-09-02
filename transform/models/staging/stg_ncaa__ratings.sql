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

),

-- The source's historical ratings are not all real. Pittsburgh's 2023 season
-- is published at a 160.4 offensive efficiency, Northwestern's at a 158.1
-- defensive one, and five teams in 2022 and 2023 carry tempos in the thirties
-- and forties. Nothing in basketball produces those numbers, so they are not
-- worth modelling and they are not worth silently rounding into range either.
-- Out-of-band values become null and `has_plausible_rating` says the row was
-- screened, which turns a wrong prediction into a missing one.
screened as (

    select
        * exclude (
            adjusted_offensive_efficiency,
            adjusted_defensive_efficiency,
            adjusted_efficiency_margin,
            adjusted_tempo
        ),

        case when adjusted_offensive_efficiency
                between {{ var('plausible_efficiency_min') }}
                    and {{ var('plausible_efficiency_max') }}
            then adjusted_offensive_efficiency
        end as adjusted_offensive_efficiency,

        case when adjusted_defensive_efficiency
                between {{ var('plausible_efficiency_min') }}
                    and {{ var('plausible_efficiency_max') }}
            then adjusted_defensive_efficiency
        end as adjusted_defensive_efficiency,

        -- The margin is the difference of the two, so a bad component makes it
        -- bad as well, whatever it reads on its own.
        case when adjusted_offensive_efficiency
                between {{ var('plausible_efficiency_min') }}
                    and {{ var('plausible_efficiency_max') }}
            and adjusted_defensive_efficiency
                between {{ var('plausible_efficiency_min') }}
                    and {{ var('plausible_efficiency_max') }}
            then adjusted_efficiency_margin
        end as adjusted_efficiency_margin,

        case when adjusted_tempo
                between {{ var('plausible_tempo_min') }}
                    and {{ var('plausible_tempo_max') }}
            then adjusted_tempo
        end as adjusted_tempo,

        -- What the source said, kept so the warning that reports a screened
        -- row can print the number that got it screened.
        adjusted_offensive_efficiency as source_adjusted_offensive_efficiency,
        adjusted_defensive_efficiency as source_adjusted_defensive_efficiency,
        adjusted_tempo as source_adjusted_tempo,

        -- A missing rating is not a screened one, so the coalesce keeps the
        -- flag about this check rather than about coverage.
        coalesce(
            adjusted_offensive_efficiency
                between {{ var('plausible_efficiency_min') }}
                    and {{ var('plausible_efficiency_max') }}
            and adjusted_defensive_efficiency
                between {{ var('plausible_efficiency_min') }}
                    and {{ var('plausible_efficiency_max') }}
            and adjusted_tempo
                between {{ var('plausible_tempo_min') }}
                    and {{ var('plausible_tempo_max') }},
            true
        ) as has_plausible_rating

    from renamed

)

select * from screened
