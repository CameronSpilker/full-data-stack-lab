-- A projected 64-team NCAA tournament field, built from the data.
--
-- Before Selection Sunday there is no official bracket, so this is
-- bracketology: 32 automatic bids to conference tournament champions, then the
-- best remaining teams at large, seeded S-curve style across four regions.
-- After Selection Sunday the real field is published and should replace this —
-- see the roadmap note on the NCAA bracket API.
--
-- The First Four is deliberately omitted. The real field is 68 with four
-- play-in games; modelling them changes a championship probability by less
-- than the simulation's own standard error, and it doubles the bracket logic.
--
-- The selection score is not the committee's process. The committee weighs
-- results the way a room of people weighs them. This weights the three things
-- that best predict what that room does: overall quality, wins above the
-- bubble, and wins against good teams.

-- At-large selection weights. These were 0.60 efficiency, 0.25 wins above
-- bubble, and 0.15 quality wins. Wins above bubble was a Barttorvik figure and
-- the rating source no longer publishes it, so its weight is redistributed in
-- the same proportion rather than left as a silent zero: efficiency and
-- quality wins keep their 4:1 ratio to each other.
{% set auto_bid_weight_efficiency = 0.80 %}
{% set auto_bid_weight_quality = 0.20 %}

with teams as (

    select * from {{ ref('mart_team_season') }}
    where season = (select max(season) from {{ ref('mart_team_season') }})
        and adjusted_efficiency_margin is not null
        and elo_rating is not null

),

team_games as (

    select * from {{ ref('int_team_games') }}

),

conference_tournament_games as (

    select
        team_games.season,
        team_games.game_id,
        team_games.game_date,
        team_games.team_id,
        team_games.is_win,
        teams.conference_name

    from team_games
    inner join teams
        on team_games.season = teams.season and team_games.team_id = teams.team_id
    where team_games.game_type = 'conference_tournament'
        and team_games.is_completed

),

conference_finals as (

    -- The last game a conference plays in its own tournament is its final.
    select distinct on (season, conference_name)
        season,
        conference_name,
        game_id
    from conference_tournament_games
    order by season, conference_name, game_date desc, game_id desc

),

auto_bids as (

    select
        games.season,
        games.team_id,
        games.conference_name
    from conference_tournament_games as games
    inner join conference_finals as finals
        on games.game_id = finals.game_id
        and games.conference_name = finals.conference_name
    where games.is_win

),

-- Standardised so the three components are on one scale before weighting.
-- Without this, efficiency margin (range ~30) would swamp wins over top-50
-- teams (range ~10) whatever the weights said.
scored as (

    select
        teams.*,
        auto_bids.team_id is not null as has_auto_bid,

        (teams.adjusted_efficiency_margin
            - avg(teams.adjusted_efficiency_margin) over ())
            / nullif(stddev_pop(teams.adjusted_efficiency_margin) over (), 0)
            as efficiency_z,

        (teams.wins_vs_top_50 - avg(teams.wins_vs_top_50) over ())
            / nullif(stddev_pop(teams.wins_vs_top_50) over (), 0)
            as quality_z

    from teams
    left join auto_bids
        on teams.season = auto_bids.season and teams.team_id = auto_bids.team_id

),

ranked as (

    select
        *,
        {{ auto_bid_weight_efficiency }} * coalesce(efficiency_z, 0)
            + {{ auto_bid_weight_quality }} * coalesce(quality_z, 0)
            as selection_score

    from scored

),

-- Automatic bids are in regardless of rating; at-large places go to the best
-- of everyone left, until the field reaches 64.
field as (

    select
        *,
        row_number() over (
            order by has_auto_bid desc, selection_score desc
        ) as bid_order
    from ranked

),

selected as (

    select
        *,
        row_number() over (order by selection_score desc) as overall_seed
    from field
    where has_auto_bid
        or bid_order <= 64

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['season', 'team_id']) }} as bracket_slot_id,
        season,
        team_id,
        team_name,
        conference_name,
        record,
        conference_record,
        has_auto_bid,
        case when has_auto_bid then 'automatic' else 'at large' end as bid_type,
        selection_score,
        overall_seed,

        cast(ceil(overall_seed / 4.0) as integer) as seed,

        -- The S-curve: seeds snake across the regions so the overall number
        -- one and the overall number five are not stacked in the same half.
        case
            when ceil(overall_seed / 4.0) % 2 = 1
                then cast((overall_seed - 1) % 4 + 1 as integer)
            else cast(4 - ((overall_seed - 1) % 4) as integer)
        end as region_number,

        adjusted_efficiency_margin,
        adjusted_offensive_efficiency,
        adjusted_defensive_efficiency,
        adjusted_tempo,
        elo_rating,
        national_rank,
        wins,
        losses

    from selected
    where overall_seed <= 64

)

select
    *,
    case region_number
        when 1 then 'East'
        when 2 then 'West'
        when 3 then 'South'
        else 'Midwest'
    end as region_name
from final
