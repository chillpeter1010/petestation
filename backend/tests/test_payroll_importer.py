from app.services.payroll.importer import derive_salary_statuses, is_payroll_source_blocked, parse_payroll_markdown


def test_parse_payroll_markdown_groups_tables_and_totals():
    markdown = """Title: 2026 Arizona Diamondbacks Payroll | RosterResource
| Player | Age | Service Time | Contract | Info | AAV | 2026 | 2027 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [Starter](https://example.com) | 30.5 | 6.000 | 2 yr, $20M | | $10M | $10M | $10M |

| Player | Age | Service Time | Contract | Info | AAV | 2026 | 2027 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Arb Player | 28.0 | 3.000 | 1 yr | | | $3M | ARB 2 |

| Player | Age | Service Time | Contract | Info | AAV | 2026 | 2027 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Young Player | 24.0 | 1.000 | 1 yr | | | $800k | Pre-ARB |
| Estimated salaries for other pre-arbitration players | $780k | | | | | | |

| Description | 2026 | 2027 |
| --- | --- | --- |
| Incentives earned by Starter | $1M | |

| Description | 2026 | 2027 |
| --- | --- | --- |
| Buyout | $1M | |
| Estimated Payroll | $100M | $80M |

| Description | 2026 | 2027 |
| --- | --- | --- |
| Guaranteed AAV | $90M | $70M |
| Estimated Luxury Tax Payroll | $120M | $95M |
"""

    result = parse_payroll_markdown(markdown, "AZ", 2026)

    assert result["team_name"] == "Arizona Diamondbacks"
    assert result["guaranteed_players"][0]["name"] == "Starter"
    assert result["arbitration_players"][0]["name"] == "Arb Player"
    assert result["pre_arbitration_players"][0]["name"] == "Young Player"
    assert result["pre_arbitration_other_estimate"] == "$780k"
    assert result["estimated_payroll"] == "$100M"
    assert result["estimated_luxury_tax_payroll"]["2026"] == "$120M"


def test_derive_salary_statuses_handles_ranges_and_exercised_options():
    statuses = derive_salary_statuses(
        "4 yr, $80M (2024-27), 2028-29 player options; 2030 club option; 2026 club option exercised",
        {"2026": "$10M", "2027": "$15M", "2028": "$20M", "2029": "$21M", "2030": "$22M", "2031": "FREE AGENT"},
    )

    assert statuses == {
        "2026": "exercised_club_option",
        "2028": "player_option",
        "2029": "player_option",
        "2030": "club_option",
        "2031": "free_agent",
    }


def test_detects_fangraphs_security_challenge():
    assert is_payroll_source_blocked("Title: Just a moment...\n## Performing security verification")
    assert not is_payroll_source_blocked("Title: 2026 Athletics Payroll | RosterResource")
