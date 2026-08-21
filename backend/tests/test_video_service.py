import duckdb
import pandas as pd

from app.services import video_service


def test_build_playbyplay_pitch_map_from_statsapi_payload():
    payload = {
        "allPlays": [
            {
                "about": {"atBatIndex": 0},
                "matchup": {"pitcher": {"id": 11}, "batter": {"id": 22}},
                "playEvents": [
                    {"isPitch": True, "pitchNumber": 1, "playId": "abc"},
                    {"isPitch": False, "pitchNumber": 2, "playId": "ignored"},
                    {"isPitch": True, "pitchNumber": 2, "playId": "def"},
                ],
            }
        ]
    }

    mapped = video_service.build_playbyplay_pitch_map(123, payload=payload)

    assert mapped.to_dict("records") == [
        {
            "game_pk": 123,
            "at_bat_number": 1,
            "pitch_number": 1,
            "play_id": "abc",
            "video_url": f"{video_service.SPORTY_VIDEO_BASE}abc",
            "pitcher": 11,
            "batter": 22,
        },
        {
            "game_pk": 123,
            "at_bat_number": 1,
            "pitch_number": 2,
            "play_id": "def",
            "video_url": f"{video_service.SPORTY_VIDEO_BASE}def",
            "pitcher": 11,
            "batter": 22,
        },
    ]


def test_normalize_pitch_lookup_dedupes_pitch_keys():
    lookup = pd.DataFrame(
        [
            {"game_pk": "1", "at_bat_number": "2", "pitch_number": "3", "play_id": "old", "video_url": "old"},
            {"game_pk": "1", "at_bat_number": "2", "pitch_number": "3", "play_id": "new", "video_url": "new"},
        ]
    )

    normalized = video_service.normalize_pitch_lookup(lookup)

    assert len(normalized) == 1
    assert normalized.iloc[0]["play_id"] == "new"


def test_sync_official_player_names_repairs_unknown_batter():
    with duckdb.connect(":memory:") as conn:
        conn.execute(
            """
            CREATE TABLE player_master (
                player_id BIGINT, player_name VARCHAR, name_source VARCHAR
            );
            INSERT INTO player_master VALUES (682988, 'Unknown', 'unknown_batter');
            CREATE TABLE game_player_lookup (
                game_pk BIGINT, player_id BIGINT, player_name VARCHAR, role VARCHAR
            );
            INSERT INTO game_player_lookup VALUES (1, 682988, 'Tyler Locklear', 'batter');
            """
        )

        repaired = video_service.sync_official_player_names(conn)
        row = conn.execute("SELECT player_name, name_source FROM player_master").fetchone()

    assert repaired == 1
    assert row == ("Tyler Locklear", "game_player_lookup")
