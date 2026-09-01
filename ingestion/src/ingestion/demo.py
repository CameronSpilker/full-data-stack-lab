"""Deterministic synthetic seasons, for development and CI.

The real extractors need network access to ESPN and Barttorvik. This module
fabricates the same table shapes so `dbt build`, the Dagster graph, and the
Evidence dashboard all run end to end on a clean checkout with no network.

It is a season simulator rather than a random number generator: every team has
a latent offensive and defensive strength, games are scored from those
strengths over a possession estimate, and the published ratings are those
strengths observed with noise. That matters because the marts backtest a
predictor. If scores and ratings were drawn independently, the model would
score no better than chance on synthetic data and a genuine modelling
regression would be indistinguishable from the fixture.

The teams here are INVENTED, deliberately. Fabricated tournament odds attached
to real school names are the kind of thing that gets screenshotted and
believed, so nothing in this module shares a name with a real program.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, date, datetime, timedelta
from typing import Any

from .config import Season, utc_today

SEED = 20260830

# Division I averages, roughly. Efficiency is points per 100 possessions.
LEAGUE_EFFICIENCY = 104.0
LEAGUE_TEMPO = 68.0
HOME_ADVANTAGE_POINTS = 1.75
SCORE_NOISE = 7.0

FIRST_NAMES = [
    "Ashford", "Belmont", "Cedar", "Dunmore", "Eastvale", "Fairhaven", "Glenrock",
    "Harlow", "Ironwood", "Juniper", "Kestrel", "Lakemont", "Marchfield", "Northgate",
    "Oakhurst", "Pinecrest", "Quarry", "Redbluff", "Stonebridge", "Thornton",
    "Umberly", "Vantage", "Westmoor", "Yarrow", "Alderton", "Brightwater",
    "Cliffside", "Draymoor", "Elmridge", "Foxbury", "Granbury", "Havenport",
]
PREFIXES = ["", "", "North", "South", "East", "West", "Port", "New"]
SUFFIXES = ["State", "University", "College", "Tech", "A&M", "Institute", ""]
MASCOTS = [
    "Wolves", "Ravens", "Foxes", "Pioneers", "Mariners", "Cardinals", "Bobcats",
    "Otters", "Falcons", "Miners", "Sentinels", "Grizzlies", "Herons", "Comets",
]

# 32 conferences, matching D1's real shape: a handful of deep leagues, a long
# tail of one-bid ones. `tier` drives average team quality.
CONFERENCE_TIERS = (
    [("major", 16, 5.5)] * 6      # 6 conferences of 16 teams, strong
    + [("mid", 12, 0.0)] * 10     # 10 of 12, average
    + [("low", 10, -4.5)] * 16    # 16 of 10, weak
)


class TeamSpec:
    """A synthetic program and its latent, unobservable true strength."""

    def __init__(
        self,
        team_id: str,
        name: str,
        mascot: str,
        conference: str,
        conference_id: str,
        offense: float,
        defense: float,
        tempo: float,
    ) -> None:
        self.team_id = team_id
        self.name = name
        self.mascot = mascot
        self.conference = conference
        self.conference_id = conference_id
        self.offense = offense  # points per 100 above league average
        self.defense = defense  # points per 100 allowed below league average
        self.tempo = tempo

    @property
    def strength(self) -> float:
        return self.offense + self.defense


def _conference_names(rng: random.Random) -> list[tuple[str, str, int, float]]:
    regions = [
        "Atlantic", "Great Lakes", "Frontier", "Coastal", "Summit", "Heartland",
        "Cascade", "Piedmont", "Gulf", "Highland", "Prairie", "Northern",
        "Southern", "Valley", "Metro", "Empire", "Cardinal", "Granite",
        "Riverlands", "Bayou", "Sierra", "Colonial", "Badlands", "Meridian",
        "Ozark", "Puget", "Chesapeake", "Sandhills", "Tidewater", "Blue Ridge",
        "Foothills", "Crossroads",
    ]
    rng.shuffle(regions)
    return [
        (f"{regions[index]} Conference", f"C{index:02d}", size, tier_strength)
        for index, (_, size, tier_strength) in enumerate(CONFERENCE_TIERS)
    ]


def _build_teams(rng: random.Random) -> list[TeamSpec]:
    teams: list[TeamSpec] = []
    used_names: set[str] = set()
    team_number = 1000

    for conference, conference_id, size, tier_strength in _conference_names(rng):
        for _ in range(size):
            # 8 x 32 x 7 combinations against 376 teams, so collisions are
            # common and exhaustion is not. The counter is a backstop: a name
            # pool that cannot cover the field must never spin forever.
            for _ in range(200):
                name = " ".join(
                    part
                    for part in (
                        rng.choice(PREFIXES),
                        rng.choice(FIRST_NAMES),
                        rng.choice(SUFFIXES),
                    )
                    if part
                )
                if name not in used_names:
                    break
            else:
                name = f"{rng.choice(FIRST_NAMES)} {team_number}"
            used_names.add(name)

            # Strength splits into offense and defense so the two efficiency
            # numbers are correlated but not identical, as they are in reality.
            strength = rng.gauss(tier_strength, 5.0)
            split = rng.uniform(0.3, 0.7)
            team_number += 1
            teams.append(
                TeamSpec(
                    team_id=str(team_number),
                    name=name,
                    mascot=rng.choice(MASCOTS),
                    conference=conference,
                    conference_id=conference_id,
                    offense=strength * split,
                    defense=strength * (1 - split),
                    tempo=rng.gauss(LEAGUE_TEMPO, 3.5),
                )
            )
    return teams


def _reseed(teams: list[TeamSpec], rng: random.Random, season_year: int) -> list[TeamSpec]:
    """Drift every team's strength between seasons.

    Rosters turn over, so a team's rating regresses toward its conference's
    mean and picks up new noise. Without this, five seasons of history would
    be five copies of the same standings.
    """
    by_conference: dict[str, list[float]] = {}
    for team in teams:
        by_conference.setdefault(team.conference_id, []).append(team.strength)
    means = {key: sum(values) / len(values) for key, values in by_conference.items()}

    drifted = []
    for team in teams:
        mean = means[team.conference_id]
        strength = 0.65 * team.strength + 0.35 * mean + rng.gauss(0, 3.0)
        split = rng.uniform(0.3, 0.7)
        drifted.append(
            TeamSpec(
                team_id=team.team_id,
                name=team.name,
                mascot=team.mascot,
                conference=team.conference,
                conference_id=team.conference_id,
                offense=strength * split,
                defense=strength * (1 - split),
                tempo=team.tempo + rng.gauss(0, 1.0),
            )
        )
    _ = season_year
    return drifted


def _expected_margin(home: TeamSpec, away: TeamSpec, neutral: bool) -> float:
    """The home team's margin before any luck — what a perfect model would say."""
    possessions = home.tempo * away.tempo / LEAGUE_TEMPO
    edge = 0.0 if neutral else HOME_ADVANTAGE_POINTS
    home_points = possessions * (LEAGUE_EFFICIENCY + home.offense - away.defense) / 100
    away_points = possessions * (LEAGUE_EFFICIENCY + away.offense - home.defense) / 100
    return home_points - away_points + 2 * edge


def _play(
    rng: random.Random, home: TeamSpec, away: TeamSpec, neutral: bool
) -> tuple[int, int]:
    """Score one game from both teams' latent strengths."""
    possessions = home.tempo * away.tempo / LEAGUE_TEMPO
    edge = 0.0 if neutral else HOME_ADVANTAGE_POINTS

    home_points = (
        possessions * (LEAGUE_EFFICIENCY + home.offense - away.defense) / 100
        + edge
        + rng.gauss(0, SCORE_NOISE)
    )
    away_points = (
        possessions * (LEAGUE_EFFICIENCY + away.offense - home.defense) / 100
        - edge
        + rng.gauss(0, SCORE_NOISE)
    )

    home_score, away_score = max(int(home_points), 40), max(int(away_points), 40)
    while home_score == away_score:  # overtime
        home_score += rng.randint(0, 12)
        away_score += rng.randint(0, 12)
    return home_score, away_score


class _GameLog:
    """Accumulates game rows and hands out unique ids."""

    def __init__(self, season: Season) -> None:
        self.season = season
        self.rows: list[dict[str, Any]] = []
        self.expected_margin: dict[str, float] = {}

    def add(
        self,
        rng: random.Random,
        home: TeamSpec,
        away: TeamSpec,
        day: date,
        *,
        neutral: bool = False,
        note: str | None = None,
        season_type: int = 2,
    ) -> tuple[int, int]:
        home_score, away_score = _play(rng, home, away, neutral)
        index = len(self.rows) + 1
        game_id = f"{self.season.year}{index:05d}"
        self.expected_margin[game_id] = _expected_margin(home, away, neutral)
        tipoff = datetime(day.year, day.month, day.day, 23, 0, tzinfo=UTC)

        self.rows.append(
            {
                "season": self.season.year,
                "season_type": season_type,
                "game_id": game_id,
                "game_date": day.isoformat(),
                "tipoff_at": tipoff.isoformat().replace("+00:00", "Z"),
                "is_neutral_site": neutral,
                "is_conference_game": home.conference_id == away.conference_id,
                "is_completed": True,
                "status_state": "post",
                "attendance": rng.randint(1_500, 21_000),
                "venue_name": f"{home.name} Arena" if not neutral else "Neutral Site Arena",
                "tournament_note": note,
                "home_team_id": home.team_id,
                "home_team_name": f"{home.name} {home.mascot}",
                "home_team_abbreviation": home.name[:4].upper(),
                "home_conference_id": home.conference_id,
                "home_score": home_score,
                "home_ap_rank": None,
                "home_record": None,
                "away_team_id": away.team_id,
                "away_team_name": f"{away.name} {away.mascot}",
                "away_team_abbreviation": away.name[:4].upper(),
                "away_conference_id": away.conference_id,
                "away_score": away_score,
                "away_ap_rank": None,
                "away_record": None,
                "extracted_at": datetime.now(UTC),
            }
        )
        return home_score, away_score


def _regular_season(rng: random.Random, teams: list[TeamSpec], log: _GameLog) -> None:
    """Non-conference games in November and December, conference play after."""
    season = log.season
    by_conference: dict[str, list[TeamSpec]] = {}
    for team in teams:
        by_conference.setdefault(team.conference_id, []).append(team)

    # Non-conference: 11 games each, paired at random across conferences.
    non_conference_end = date(season.year - 1, 12, 31)
    span = (non_conference_end - season.start).days
    for _ in range(6):
        pool = teams[:]
        rng.shuffle(pool)
        for home, away in zip(pool[::2], pool[1::2], strict=False):
            if home.conference_id == away.conference_id:
                continue
            day = season.start + timedelta(days=rng.randint(0, max(span, 1)))
            log.add(rng, home, away, day)

    # Conference play: a double round robin, January through early March.
    conference_start = date(season.year, 1, 2)
    conference_end = date(season.year, 3, 8)
    conference_span = (conference_end - conference_start).days

    for members in by_conference.values():
        for index, home in enumerate(members):
            for away in members[index + 1 :]:
                for first, second in ((home, away), (away, home)):
                    day = conference_start + timedelta(days=rng.randint(0, conference_span))
                    log.add(rng, first, second, day)


def _bracket_round(
    rng: random.Random,
    log: _GameLog,
    field: list[TeamSpec],
    day: date,
    note: str,
    season_type: int = 3,
) -> list[TeamSpec]:
    """Play one single-elimination round, highest seed against lowest."""
    winners: list[TeamSpec] = []
    for high, low in zip(field[: len(field) // 2], field[len(field) // 2 :][::-1], strict=False):
        home_score, away_score = log.add(
            rng, high, low, day, neutral=True, note=note, season_type=season_type
        )
        winners.append(high if home_score > away_score else low)
    return winners


def _conference_tournaments(
    rng: random.Random, teams: list[TeamSpec], log: _GameLog, standings: dict[str, int]
) -> list[TeamSpec]:
    """An eight-team tournament in every conference. Winners take the auto-bid."""
    by_conference: dict[str, list[TeamSpec]] = {}
    for team in teams:
        by_conference.setdefault(team.conference_id, []).append(team)

    champions: list[TeamSpec] = []
    day = date(log.season.year, 3, 12)

    for members in by_conference.values():
        field = sorted(members, key=lambda team: -standings.get(team.team_id, 0))[:8]
        note = f"{members[0].conference} Tournament"
        while len(field) > 1:
            field = _bracket_round(rng, log, field, day, note)
            day += timedelta(days=1)
        champions.append(field[0])
        day = date(log.season.year, 3, 12)

    return champions


def _ncaa_tournament(
    rng: random.Random,
    teams: list[TeamSpec],
    log: _GameLog,
    champions: list[TeamSpec],
    standings: dict[str, int],
) -> None:
    """A 64-team bracket: 32 auto-bids plus the best 32 at-large records."""
    auto_bids = {team.team_id for team in champions}
    at_large = [
        team
        for team in sorted(teams, key=lambda team: -standings.get(team.team_id, 0))
        if team.team_id not in auto_bids
    ][:32]

    field = sorted(
        champions + at_large, key=lambda team: -standings.get(team.team_id, 0)
    )
    rounds = [
        ("NCAA Tournament - First Round", 64),
        ("NCAA Tournament - Second Round", 32),
        ("NCAA Tournament - Sweet 16", 16),
        ("NCAA Tournament - Elite Eight", 8),
        ("NCAA Tournament - Final Four", 4),
        ("NCAA Tournament - National Championship", 2),
    ]
    day = date(log.season.year, 3, 19)

    for note, size in rounds:
        if len(field) < size:
            break
        field = _bracket_round(rng, log, field[:size], day, note)
        day += timedelta(days=3)


def _ratings(
    rng: random.Random, teams: list[TeamSpec], season: Season, snapshot: date,
    standings: dict[str, int], played: dict[str, int],
) -> list[dict[str, Any]]:
    """Published ratings: the latent strengths, observed imperfectly.

    A real rating system sees the same games this simulator generated and
    recovers strength approximately. The noise term is what stops the
    predictor from being handed the exact truth it is supposed to estimate.
    """
    extracted_at = datetime.now(UTC)
    rows = []
    for team in teams:
        adj_oe = LEAGUE_EFFICIENCY + team.offense + rng.gauss(0, 0.8)
        adj_de = LEAGUE_EFFICIENCY - team.defense + rng.gauss(0, 0.8)
        wins = standings.get(team.team_id, 0)
        games = played.get(team.team_id, 0)

        # Barthag is a win probability against an average team, which the
        # Pythagorean form of the efficiency margin approximates well.
        margin = adj_oe - adj_de
        barthag = 1 / (1 + math.exp(-margin / 9.0))

        rows.append(
            {
                "snapshot_date": snapshot,
                "season": season.year,
                "team_name": team.name,
                "conference": team.conference,
                "wins": float(wins),
                "losses": float(games - wins),
                "games": float(games),
                "adj_oe": round(adj_oe, 2),
                "adj_de": round(adj_de, 2),
                "barthag": round(barthag, 4),
                "adj_tempo": round(team.tempo + rng.gauss(0, 0.5), 1),
                "efg_pct": round(50.0 + team.offense * 0.55 + rng.gauss(0, 1.0), 1),
                "efg_pct_allowed": round(50.0 - team.defense * 0.55 + rng.gauss(0, 1.0), 1),
                "turnover_pct": round(17.5 - team.offense * 0.12 + rng.gauss(0, 0.8), 1),
                "turnover_pct_forced": round(17.5 + team.defense * 0.12 + rng.gauss(0, 0.8), 1),
                "off_reb_pct": round(29.5 + team.offense * 0.3 + rng.gauss(0, 1.5), 1),
                "def_reb_pct": round(70.5 + team.defense * 0.3 + rng.gauss(0, 1.5), 1),
                "ft_rate": round(32.0 + rng.gauss(0, 3.0), 1),
                "ft_rate_allowed": round(32.0 + rng.gauss(0, 3.0), 1),
                "two_pt_pct": round(50.5 + team.offense * 0.4 + rng.gauss(0, 1.2), 1),
                "two_pt_pct_allowed": round(50.5 - team.defense * 0.4 + rng.gauss(0, 1.2), 1),
                "three_pt_pct": round(34.0 + team.offense * 0.18 + rng.gauss(0, 1.0), 1),
                "three_pt_pct_allowed": round(34.0 - team.defense * 0.18 + rng.gauss(0, 1.0), 1),
                "wab": round(team.strength * 0.6 + rng.gauss(0, 1.0), 1),
                "seed": None,
                "extracted_at": extracted_at,
            }
        )
    return rows


def _box_scores(rng: random.Random, games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Box score lines consistent with the final score of each game."""
    extracted_at = datetime.now(UTC)
    rows = []

    for game in games:
        for side in ("home", "away"):
            points = game[f"{side}_score"]
            threes = max(int(points * rng.uniform(0.10, 0.22)), 0)
            free_throws = max(int(points * rng.uniform(0.08, 0.20)), 0)
            twos = max(int((points - 3 * threes - free_throws) / 2), 0)

            rows.append(
                {
                    "season": game["season"],
                    "game_id": game["game_id"],
                    "team_id": game[f"{side}_team_id"],
                    "team_name": game[f"{side}_team_name"],
                    "field_goals_made": twos + threes,
                    "field_goals_attempted": int((twos + threes) / rng.uniform(0.39, 0.52)),
                    "three_pointers_made": threes,
                    "three_pointers_attempted": int(threes / rng.uniform(0.28, 0.42)) + 1,
                    "free_throws_made": free_throws,
                    "free_throws_attempted": int(free_throws / rng.uniform(0.62, 0.82)) + 1,
                    "rebounds": rng.randint(24, 46),
                    "offensive_rebounds": rng.randint(5, 16),
                    "defensive_rebounds": rng.randint(18, 32),
                    "assists": rng.randint(7, 22),
                    "steals": rng.randint(2, 12),
                    "blocks": rng.randint(0, 8),
                    "turnovers": rng.randint(6, 20),
                    "fouls": rng.randint(10, 24),
                    "extracted_at": extracted_at,
                }
            )
    return rows


def _betting_lines(
    rng: random.Random, games: list[dict[str, Any]], expected: dict[str, float]
) -> list[dict[str, Any]]:
    """A synthetic betting market, priced off the true expected margin.

    The market is deliberately sharp — it sees the real expectation plus a
    little noise — because that is what makes it a hard benchmark. A model
    that beats this line is genuinely extracting something; a model that beats
    a sloppy line has only found the sloppiness. Spreads are quoted from the
    home team's perspective, so a negative number means the home side is
    favoured, and rounded to the half point books actually post.
    """
    extracted_at = datetime.now(UTC)
    rows = []

    for game in games:
        margin = expected.get(game["game_id"])
        if margin is None:
            continue
        spread = -round((margin + rng.gauss(0, 1.2)) * 2) / 2
        total = round((141.0 + rng.gauss(0, 6.0)) * 2) / 2

        # Converting a spread to a moneyline is a rough logistic; books add
        # vig on top, which is why both sides here are worse than fair odds.
        probability = 1 / (1 + math.exp(spread / 5.5))
        rows.append(
            {
                "season": game["season"],
                "game_id": game["game_id"],
                "provider": "synthetic",
                "spread": spread,
                "over_under": total,
                "home_moneyline": _moneyline(probability),
                "away_moneyline": _moneyline(1 - probability),
                "extracted_at": extracted_at,
            }
        )
    return rows


def _moneyline(probability: float) -> int:
    """American odds for a probability, with a 2% hold baked into each side."""
    priced = min(max(probability * 1.02, 0.01), 0.99)
    if priced >= 0.5:
        return round(-100 * priced / (1 - priced))
    return round(100 * (1 - priced) / priced)


def extract(
    seasons: list[Season], snapshot: date | None = None, current: Season | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Generate a full synthetic history across every requested season."""
    snapshot = snapshot or utc_today()
    rng = random.Random(SEED)
    current = current or seasons[-1]

    teams = _build_teams(rng)
    games: list[dict[str, Any]] = []
    ratings: list[dict[str, Any]] = []
    expected_margin: dict[str, float] = {}

    for season in seasons:
        if season.year != seasons[0].year:
            teams = _reseed(teams, rng, season.year)

        log = _GameLog(season)
        _regular_season(rng, teams, log)

        standings: dict[str, int] = {}
        played: dict[str, int] = {}
        for game in log.rows:
            for side, other in (("home", "away"), ("away", "home")):
                team_id = game[f"{side}_team_id"]
                played[team_id] = played.get(team_id, 0) + 1
                if game[f"{side}_score"] > game[f"{other}_score"]:
                    standings[team_id] = standings.get(team_id, 0) + 1

        champions = _conference_tournaments(rng, teams, log, standings)
        _ncaa_tournament(rng, teams, log, champions, standings)

        games.extend(log.rows)
        expected_margin.update(log.expected_margin)
        ratings.extend(_ratings(rng, teams, season, snapshot, standings, played))

    team_rows = [
        {
            "snapshot_date": snapshot,
            "team_id": team.team_id,
            "team_slug": team.name.lower().replace(" ", "-").replace("&", "and"),
            "location": team.name,
            "mascot": team.mascot,
            "display_name": f"{team.name} {team.mascot}",
            "short_name": team.name,
            "abbreviation": team.name[:4].upper(),
            "conference_id": team.conference_id,
            "conference_name": team.conference,
            "venue_name": f"{team.name} Arena",
            "venue_city": None,
            "venue_state": None,
            "color": None,
            "is_active": True,
            "extracted_at": datetime.now(UTC),
        }
        for team in teams
    ]

    # Box scores only for the current season: they add nothing the ratings do
    # not already carry for past seasons, and they double the row count.
    current_games = [game for game in games if game["season"] == current.year]

    return {
        "ncaa_teams": team_rows,
        "ncaa_games": games,
        "ncaa_ratings": ratings,
        "ncaa_team_box": _box_scores(rng, current_games),
        "ncaa_betting_lines": _betting_lines(rng, games, expected_margin),
    }
