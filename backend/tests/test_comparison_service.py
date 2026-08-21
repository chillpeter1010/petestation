import pandas as pd

from app.core.config import settings
from app.services import comparison_service


def test_comparison_options_and_overview_build_percentile_cards(tmp_path, monkeypatch):
    data = pd.DataFrame(
        [
            {
                "year": 2026,
                "player_id": 1,
                "display_name": "Ace One",
                "team": "AAA",
                "role": "SP",
                "fip": 2.50,
                "xfip": 3.00,
                "xba": 0.210,
                "fastball_avg_speed": 96.0,
            },
            {
                "year": 2026,
                "player_id": 2,
                "display_name": "Ace Two",
                "team": "BBB",
                "role": "SP",
                "fip": 4.50,
                "xfip": 4.00,
                "xba": 0.260,
                "fastball_avg_speed": 92.0,
            },
        ]
    )
    data.to_csv(tmp_path / "2026_pitcher_comparison.csv", index=False)

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    comparison_service.load_comparison_pool.cache_clear()

    options = comparison_service.get_comparison_options(2026)
    assert [pitcher.player_id for pitcher in options.pitchers] == [1, 2]
    assert options.years == [2026]

    overview = comparison_service.get_comparison_overview(2026, 2026, 1, 2)
    left_metrics = {metric.key: metric for metric in overview.percentile_cards["left"]}
    right_metrics = {metric.key: metric for metric in overview.percentile_cards["right"]}

    assert overview.players["left"].display_label == "Ace One (AAA, SP)"
    assert left_metrics["fip"].formatted_value == "2.50"
    assert left_metrics["fip"].percentile == 100
    assert right_metrics["fastball_velo"].formatted_value == "92.0"
    assert right_metrics["fastball_velo"].percentile == 50
    assert overview.tables["metric_comparison"].rows
    assert overview.charts["advantages"]["left"]


def test_period_comparison_overview_builds_metrics_from_pitch_rows(tmp_path, monkeypatch):
    data = pd.DataFrame(
        [
            {
                "year": 2026,
                "player_id": 7,
                "display_name": "Period Arm",
                "team": "AAA",
                "role": "SP",
                "xba": 0.250,
                "fastball_avg_speed": 95.0,
                "exit_velocity_avg": 88.0,
                "oz_swing_percent": 30.0,
                "whiff_percent": 25.0,
                "k_percent": 20.0,
                "bb_percent": 8.0,
                "barrel_batted_rate": 7.0,
                "hard_hit_percent": 40.0,
                "groundballs_percent": 45.0,
            },
            {
                "year": 2026,
                "player_id": 8,
                "display_name": "Pool Arm",
                "team": "BBB",
                "role": "RP",
                "xba": 0.300,
                "fastball_avg_speed": 91.0,
                "exit_velocity_avg": 90.0,
                "oz_swing_percent": 20.0,
                "whiff_percent": 15.0,
                "k_percent": 10.0,
                "bb_percent": 12.0,
                "barrel_batted_rate": 10.0,
                "hard_hit_percent": 50.0,
                "groundballs_percent": 30.0,
            },
        ]
    )
    data.to_csv(tmp_path / "2026_pitcher_comparison.csv", index=False)

    pitch_rows = pd.DataFrame(
        [
            {
                "game_pk": 1,
                "at_bat_number": 1,
                "pitch_number": 1,
                "pitch_name": "Four-Seam",
                "release_speed": 96.0,
                "description": "called_strike",
                "zone": 5,
                "events": "",
                "balls": 0,
                "strikes": 0,
                "plate_x": 0.1,
                "plate_z": 2.5,
                "pfx_x": -0.5,
                "pfx_z": 1.4,
                "p_throws": "L",
                "play_id": "abc",
            },
            {
                "game_pk": 1,
                "at_bat_number": 1,
                "pitch_number": 2,
                "pitch_name": "Four-Seam",
                "release_speed": 97.0,
                "description": "swinging_strike",
                "zone": 11,
                "events": "strikeout",
                "balls": 0,
                "strikes": 1,
                "estimated_ba_using_speedangle": 0.2,
                "plate_x": -0.3,
                "plate_z": 3.1,
                "pfx_x": -0.6,
                "pfx_z": 1.5,
                "p_throws": "L",
                "play_id": "def",
            },
            {
                "game_pk": 1,
                "at_bat_number": 2,
                "pitch_number": 1,
                "pitch_name": "Sinker",
                "release_speed": 94.0,
                "description": "hit_into_play",
                "zone": 6,
                "events": "field_out",
                "balls": 1,
                "strikes": 0,
                "launch_speed": 90.0,
                "launch_speed_angle": 6,
                "bb_type": "ground_ball",
                "estimated_ba_using_speedangle": 0.3,
                "plate_x": 0.4,
                "plate_z": 1.9,
                "pfx_x": -0.9,
                "pfx_z": 1.1,
                "p_throws": "L",
            },
        ]
    )

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(comparison_service, "load_pitcher_cached_season", lambda *args, **kwargs: pitch_rows)
    comparison_service.load_comparison_pool.cache_clear()

    overview = comparison_service.get_period_comparison_overview(
        pitcher_id=7,
        left_year=2026,
        right_year=2026,
        left_start="2026-03-01",
        left_end="2026-04-01",
        right_start="2026-04-02",
        right_end="2026-05-01",
    )

    left_metrics = {metric.key: metric for metric in overview.percentile_cards["left"]}
    assert overview.players["left"].display_name == "Period Arm"
    assert left_metrics["fastball_velo"].formatted_value == "95.7"
    assert overview.tables["metric_comparison"].rows
    assert overview.charts["period_counts"] == {"left": 3, "right": 3}
    assert len(overview.charts["period_locations"]["left"]) == 3
    assert overview.charts["period_locations"]["left"][0]["plate_x"] == 0.1
    assert len(overview.charts["period_movement"]["left"]["scatter"]) == 3
    assert overview.charts["period_movement"]["left"]["summary"][0]["pitch_name"] == "Four-Seam"
    assert overview.charts["period_movement"]["left"]["pitcher_hand"] == "L"
    assert "league" in overview.charts["period_movement"]["left"]
    assert overview.charts["period_pitch_mix"]["left"]["total"] == 3
    assert overview.charts["period_pitch_mix"]["left"]["rows"][0]["pitch"] == "Four-Seam"
    assert overview.charts["period_discipline"]["left"]["panel_groups"]["result"]["pitch_result"][0]["pitches"] == 1
    assert overview.charts["period_discipline"]["left"]["panel_groups"]["result"]["batted_ball"][0]["pitches"] == 1
    assert overview.charts["period_videos"]["left"]["total"] == 2
    assert overview.charts["period_videos"]["left"]["rows"][0]["video_url"].endswith("abc")


def test_period_date_range_uses_pitcher_season_bounds(monkeypatch):
    monkeypatch.setattr(
        comparison_service,
        "load_pitcher_season_date_range",
        lambda year, pitcher_id, data_dir: {"start_date": "2026-03-27", "end_date": "2026-07-09", "pitches": 1234},
    )

    payload = comparison_service.get_period_date_range(2026, 99)

    assert payload == {
        "year": 2026,
        "pitcher_id": 99,
        "start_date": "2026-03-27",
        "end_date": "2026-07-09",
        "pitches": 1234,
    }


def test_period_video_payload_does_not_truncate_by_default():
    rows = [
        {
            "game_date": "2026-04-01",
            "pitch_name": "4-Seam",
            "description": "called_strike",
            "balls": 0,
            "strikes": 0,
            "video_url": f"https://example.com/{index}",
            "play_id": f"play-{index}",
        }
        for index in range(120)
    ]

    payload = comparison_service.build_period_video_payload(pd.DataFrame(rows))
    limited_payload = comparison_service.build_period_video_payload(pd.DataFrame(rows), limit=80)

    assert payload["total"] == 120
    assert len(payload["rows"]) == 120
    assert limited_payload["total"] == 120
    assert len(limited_payload["rows"]) == 80
