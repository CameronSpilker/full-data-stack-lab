"""Parser tests for the Barttorvik T-Rank extractor.

Barttorvik serves a CSV that has appeared both with and without a header row.
Both paths are exercised here, along with the guard that refuses a parse where
adjusted efficiency did not come through — the one failure mode that would
otherwise load a table of plausible-looking nulls into the rating that every
prediction depends on.
"""

from datetime import date

import pytest

from ingestion import torvik

SNAPSHOT = date(2026, 3, 1)

WITH_HEADER = """team,conf,G,W,L,AdjOE,AdjDE,Barthag,AdjT,EFG,EFGD,TOR,TORD,ORB,DRB,FTR,FTRD,WAB
Houston,B12,34,30,4,121.4,88.2,0.9712,63.1,52.1,45.0,15.2,19.8,33.4,72.1,29.0,26.5,7.4
Duke,ACC,33,28,5,124.0,91.5,0.9633,67.2,56.3,46.8,14.1,17.2,31.0,70.4,31.2,28.1,6.1
"""

# Assembled from parts rather than written as one string: the real export is a
# single very long line per team, and splitting it here keeps the column
# positions readable against POSITIONAL_COLUMNS in torvik.py.
WITHOUT_HEADER = "\n".join(
    [
        ",".join(
            [
                "Houston", "B12", "34", "30",          # team, conf, games, wins
                "121.4", "1", "88.2", "2", "0.9712",   # adj_oe, rank, adj_de, rank, barthag
                "52.1", "45.0", "29.0", "26.5",        # efg, efg allowed, ft rate, allowed
                "15.2", "19.8", "33.4", "72.1",        # turnovers, forced, o-reb, d-reb
                "54.0", "44.1", "36.2", "30.1",        # 2pt, 2pt allowed, 3pt, allowed
                "63.1", "5", "7.4",                    # tempo, rank, wab
            ]
        ),
        ",".join(
            [
                "Duke", "ACC", "33", "28",
                "124.0", "2", "91.5", "5", "0.9633",
                "56.3", "46.8", "31.2", "28.1",
                "14.1", "17.2", "31.0", "70.4",
                "57.1", "45.9", "38.0", "31.2",
                "67.2", "9", "6.1",
            ]
        ),
        "",
    ]
)


def test_parses_a_csv_with_a_header():
    rows = torvik.parse_ratings(WITH_HEADER, 2026, SNAPSHOT)

    assert len(rows) == 2
    houston = next(row for row in rows if row["team_name"] == "Houston")
    assert houston["adj_oe"] == 121.4
    assert houston["adj_de"] == 88.2
    assert houston["adj_tempo"] == 63.1
    assert houston["conference"] == "B12"
    assert houston["wins"] == 30
    assert houston["losses"] == 4
    assert houston["season"] == 2026
    assert houston["snapshot_date"] == SNAPSHOT


def test_parses_a_headerless_csv_positionally():
    rows = torvik.parse_ratings(WITHOUT_HEADER, 2026, SNAPSHOT)

    assert len(rows) == 2
    houston = next(row for row in rows if row["team_name"] == "Houston")
    assert houston["adj_oe"] == 121.4
    assert houston["adj_de"] == 88.2
    assert houston["conference"] == "B12"


def test_header_detection_distinguishes_the_two_layouts():
    assert torvik._looks_like_header(WITH_HEADER.splitlines()[0].split(","))
    assert not torvik._looks_like_header(WITHOUT_HEADER.splitlines()[0].split(","))


def test_a_combined_record_column_is_split():
    payload = "team,conf,AdjOE,AdjDE,Rec\nHouston,B12,121.4,88.2,30-4\n"

    row = torvik.parse_ratings(payload, 2026, SNAPSHOT)[0]

    assert row["wins"] == 30
    assert row["losses"] == 4


def test_a_layout_change_that_loses_efficiency_fails_the_run():
    # The failure mode this guards against: the CSV still parses, every team is
    # present, and the column the whole predictor rests on is empty.
    payload = "team,conf,somethingelse\nHouston,B12,1\nDuke,ACC,2\n"

    with pytest.raises(ValueError, match="adj_oe"):
        torvik.parse_ratings(payload, 2026, SNAPSHOT)


def test_an_empty_response_fails_rather_than_loading_nothing():
    with pytest.raises(ValueError, match="no rows"):
        torvik.parse_ratings("", 2026, SNAPSHOT)


def test_blank_lines_are_ignored():
    rows = torvik.parse_ratings(WITH_HEADER + "\n\n", 2026, SNAPSHOT)

    assert len(rows) == 2
