-- A forecast is only a forecast if the game has not happened.
--
-- Every other model in this project is graded against a result. This one
-- cannot be, so the guard has to be on the input instead: nothing in
-- `mart_upcoming_games` may be a game the warehouse already holds a score
-- for. The failure this catches is a scheduled row that keeps its slot after
-- the game is played, which would publish a "prediction" of a finished game
-- and quietly flatter every number on the page.

select
    upcoming.game_id,
    upcoming.game_date,
    games.scoring_status,
    games.home_score,
    games.away_score

from {{ ref('mart_upcoming_games') }} as upcoming
join {{ ref('stg_ncaa__games') }} as games
    on upcoming.game_id = games.game_id

where games.is_completed
    or games.home_score is not null
    or games.away_score is not null
    or upcoming.game_date < upcoming.as_of_date
