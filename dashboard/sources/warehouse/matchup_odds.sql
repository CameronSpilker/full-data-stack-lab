-- Every pair is stored once, in team_id order, because a grid holding each
-- matchup both ways is twice the rows for none of the information. A page
-- reading it from one team's point of view has to put the mirror back, which
-- is what the matchup page's `oriented` query does.
--
-- The efficiency-only and Elo-only columns are the two halves of the blend
-- the model ships, unweighted. They are not alternative predictions: the
-- blend is the prediction, and these say where it came from.
select
    matchup_id,
    season,
    team_id,
    team_name,
    conference_name,
    opponent_team_id,
    opponent_name,
    opponent_conference,
    predicted_margin_neutral,
    predicted_margin_at_home,
    predicted_margin_efficiency_only,
    predicted_margin_elo_only,
    win_probability_neutral,
    win_probability_at_home,
    win_probability_efficiency_only,
    win_probability_elo_only
from marts.mart_matchup_odds
