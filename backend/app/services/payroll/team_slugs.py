TEAM_PAYROLL_SLUGS: dict[str, str] = {
    "AZ": "diamondbacks", "ATH": "athletics", "ATL": "braves", "BAL": "orioles",
    "BOS": "red-sox", "CHC": "cubs", "CWS": "white-sox", "CIN": "reds",
    "CLE": "guardians", "COL": "rockies", "DET": "tigers", "HOU": "astros",
    "KC": "royals", "LAA": "angels", "LAD": "dodgers", "MIA": "marlins",
    "MIL": "brewers", "MIN": "twins", "NYM": "mets", "NYY": "yankees",
    "PHI": "phillies", "PIT": "pirates", "SD": "padres", "SEA": "mariners",
    "SF": "giants", "STL": "cardinals", "TB": "rays", "TEX": "rangers",
    "TOR": "blue-jays", "WSH": "nationals",
}


def payroll_source_url(team_code: str) -> str | None:
    slug = TEAM_PAYROLL_SLUGS.get(team_code.strip().upper())
    return f"https://www.fangraphs.com/roster-resource/payroll/{slug}" if slug else None
