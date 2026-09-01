-- Elo must be conserved: whatever the winner gains, the loser loses.
--
-- A rating system that creates or destroys points drifts, and every downstream
-- probability drifts with it. Because the update is applied twice — once with
-- each sign — a bug in that symmetry is exactly the kind that produces
-- plausible-looking numbers, so it is asserted rather than assumed.

select
    game_id,
    sum(elo_change) as net_change

from {{ ref('int_team_elo') }}
group by 1
having abs(sum(elo_change)) > 0.0001
