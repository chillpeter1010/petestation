import pandas as pd

from app.services.personal_service import build_pitch_type_distribution


def test_build_pitch_type_distribution_counts_pitch_names():
    frame = pd.DataFrame(
        [
            {"pitch_name": "Sinker"},
            {"pitch_name": "Sinker"},
            {"pitch_name": "Slider"},
        ]
    )

    distribution = build_pitch_type_distribution(frame)

    assert distribution[0]["pitch"] == "Sinker"
    assert distribution[0]["count"] == 2
    assert distribution[0]["rate"] == 2 / 3
