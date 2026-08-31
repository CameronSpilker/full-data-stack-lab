-- The simulated bracket must obey the arithmetic of a bracket.
--
-- Exactly one team wins, four reach the Final Four, sixteen reach the Sweet 16.
-- These hold no matter which team is better, so any deviation is a bug in the
-- simulation rather than a surprising result. The tolerance absorbs floating
-- point only, not a missing or duplicated team.

with totals as (

    select
        sum(won_championship) as champions,
        sum(reached_championship_game) as finalists,
        sum(reached_final_four) as final_four,
        sum(reached_elite_eight) as elite_eight,
        sum(reached_sweet_16) as sweet_16,
        sum(reached_round_of_32) as round_of_32
    from {{ ref('mart_tournament_odds') }}

)

select *
from totals
where abs(champions - 1) > 0.001
    or abs(finalists - 2) > 0.001
    or abs(final_four - 4) > 0.001
    or abs(elite_eight - 8) > 0.001
    or abs(sweet_16 - 16) > 0.001
    or abs(round_of_32 - 32) > 0.001
