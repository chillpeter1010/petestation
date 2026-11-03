from __future__ import annotations


MLB_TEAM_ID_TO_CODE: dict[int, str] = {
    108: "LAA", 109: "AZ", 110: "BAL", 111: "BOS", 112: "CHC", 113: "CIN",
    114: "CLE", 115: "COL", 116: "DET", 117: "HOU", 118: "KC", 119: "LAD",
    120: "WSH", 121: "NYM", 133: "ATH", 134: "PIT", 135: "SD", 136: "SEA",
    137: "SF", 138: "STL", 139: "TB", 140: "TEX", 141: "TOR", 142: "MIN",
    143: "PHI", 144: "ATL", 145: "CWS", 146: "MIA", 147: "NYY", 158: "MIL",
}
MLB_TEAM_CODE_TO_ID: dict[str, int] = {code: team_id for team_id, code in MLB_TEAM_ID_TO_CODE.items()}


def validate_mlb_team_id(team_id: int | None) -> int | None:
    if team_id is None:
        return None
    if team_id not in MLB_TEAM_ID_TO_CODE:
        raise ValueError("Unsupported MLB team.")
    return team_id
