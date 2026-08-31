select
    team_id,
    season,
    team_name,
    conference_name,
    seed,
    region_name,
    region_number,
    overall_seed,
    bid_type,
    has_auto_bid,
    record,
    selection_score,
    adjusted_efficiency_margin,
    elo_rating,
    national_rank
from marts.mart_bracket
