-- One row per team per season: the table the whole dashboard hangs off.
--
-- Everything a team page needs without a further join — record, splits,
-- efficiency, tempo, four factors, Elo, schedule strength, and where the team
-- ranks nationally and inside its conference on each of them.

with inputs as (

    select * from {{ ref('int_team_prediction_inputs') }}

),

tournament as (

    -- What the team actually did in March, so past seasons can be read back.
    select
        season,
        team_id,
        count(*) as ncaa_tournament_games,
        sum(case when is_win then 1 else 0 end) as ncaa_tournament_wins,
        max(case when is_win and tournament_round = 'National Championship'
                 then 1 else 0 end) = 1 as won_national_championship
    from {{ ref('int_team_games') }}
    where game_type = 'ncaa_tournament' and is_completed
    group by 1, 2

),

final as (

    select
        inputs.*,

        coalesce(tournament.ncaa_tournament_games, 0) as ncaa_tournament_games,
        coalesce(tournament.ncaa_tournament_wins, 0) as ncaa_tournament_wins,
        coalesce(tournament.won_national_championship, false) as won_national_championship,
        tournament.season is not null as made_ncaa_tournament,

        concat(inputs.wins, '-', inputs.losses) as record,
        concat(inputs.conference_wins, '-', inputs.conference_losses) as conference_record,

        rank() over (
            partition by inputs.season order by inputs.adjusted_efficiency_margin desc
        ) as national_rank,

        rank() over (
            partition by inputs.season, inputs.conference_name
            order by inputs.adjusted_efficiency_margin desc
        ) as conference_rank,

        rank() over (
            partition by inputs.season order by inputs.adjusted_offensive_efficiency desc
        ) as offense_rank,

        -- Defensive efficiency is points allowed, so low is good.
        rank() over (
            partition by inputs.season order by inputs.adjusted_defensive_efficiency asc
        ) as defense_rank,

        rank() over (
            partition by inputs.season order by inputs.adjusted_tempo desc
        ) as tempo_rank,

        rank() over (
            partition by inputs.season order by inputs.strength_of_schedule desc
        ) as schedule_strength_rank

    from inputs
    left join tournament
        on inputs.season = tournament.season and inputs.team_id = tournament.team_id

)

select * from final
