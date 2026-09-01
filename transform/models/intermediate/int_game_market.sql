-- The market's view of each game, reduced to one row.
--
-- The median across books rather than the mean: a single stale or mistyped
-- quote should not move the consensus, and with a handful of books the median
-- is the standard way to say so.
--
-- The implied win probability uses a logistic on the spread. The scale factor
-- of 5.5 points is the usual fit for college basketball — a 5.5 point favourite
-- wins about 73% of the time — and it is stated here as a constant rather than
-- buried in a mart so that every consumer of "what did the market think"
-- agrees on the conversion.

{% set spread_to_probability_scale = 5.5 %}

with lines as (

    select * from {{ ref('stg_ncaa__betting_lines') }}

),

consensus as (

    select
        game_id,
        season,
        count(*) as book_count,
        median(home_spread) as consensus_home_spread,
        median(over_under) as consensus_over_under

    from lines
    group by 1, 2

),

final as (

    select
        *,

        -- A negative spread means the home team is laying points, so the sign
        -- flips to become a home win probability.
        1 / (1 + exp(consensus_home_spread / {{ spread_to_probability_scale }}))
            as market_home_win_probability,

        -consensus_home_spread as market_home_margin

    from consensus

)

select * from final
