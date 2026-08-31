-- Conference standing per season: how deep a league is, not just how good its
-- best team is.
--
-- Depth is what actually predicts March performance. A conference with one
-- great team and thirteen bad ones sends one team and loses in the first
-- round; a conference where the median team is good sends eight.

with teams as (

    select * from {{ ref('mart_team_season') }}
    where conference_name is not null

),

aggregated as (

    select
        season,
        conference_name,
        count(*) as team_count,
        avg(adjusted_efficiency_margin) as avg_efficiency_margin,
        median(adjusted_efficiency_margin) as median_efficiency_margin,
        max(adjusted_efficiency_margin) as best_efficiency_margin,
        avg(elo_rating) as avg_elo,
        avg(adjusted_tempo) as avg_tempo,
        sum(wins) as total_wins,
        sum(losses) as total_losses,
        count(*) filter (where national_rank <= 25) as teams_in_top_25,
        count(*) filter (where national_rank <= 50) as teams_in_top_50,
        count(*) filter (where made_ncaa_tournament) as ncaa_bids,
        sum(ncaa_tournament_wins) as ncaa_tournament_wins,
        max(case when won_national_championship then 1 else 0 end) = 1 as won_championship,
        max_by(team_name, adjusted_efficiency_margin) as best_team

    from teams
    group by 1, 2

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['season', 'conference_name']) }}
            as conference_season_id,
        *,

        -- Non-conference games are the only ones that compare leagues, but
        -- every conference plays most of its schedule inside itself, so the
        -- median team's rating is the fairer depth measure.
        rank() over (partition by season order by median_efficiency_margin desc)
            as conference_rank,

        ncaa_tournament_wins * 1.0 / nullif(ncaa_bids, 0) as wins_per_bid

    from aggregated

)

select * from final
