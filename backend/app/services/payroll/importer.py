from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.services.payroll.team_slugs import payroll_source_url


_PLAYER_HEADER = ["Player", "Age", "Service Time", "Contract", "Info", "AAV"]
_DESCRIPTION_HEADER = "Description"
_LINK_RE = re.compile(r"\[([^]]+)]\([^)]*\)")
_OPTION_RE = re.compile(
    r"(?P<start>20\d{2})(?:-(?P<end>\d{2}|20\d{2}))?\s+"
    r"(?P<kind>club|player|mutual|vesting)\s+options?"
    r"(?P<exercised>\s+exercised)?",
    re.IGNORECASE,
)


class PayrollSourceBlockedError(RuntimeError):
    pass


def fetch_payroll_markdown(team_code: str, timeout: int = 90, attempts: int = 4) -> str:
    source_url = payroll_source_url(team_code)
    if not source_url:
        raise ValueError(f"Unknown team code: {team_code}")
    request = Request(
        f"https://r.jina.ai/{source_url}",
        headers={"User-Agent": "Petehub payroll snapshot importer/1.0"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                markdown = response.read().decode("utf-8")
                if is_payroll_source_blocked(markdown):
                    raise PayrollSourceBlockedError("FanGraphs is temporarily requiring browser security verification")
                return markdown
        except PayrollSourceBlockedError:
            raise
        except (HTTPError, URLError):
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)
    raise RuntimeError("Payroll fetch exhausted without a response")


def is_payroll_source_blocked(markdown: str) -> bool:
    normalized = markdown.casefold()
    return (
        "title: just a moment" in normalized
        or "performing security verification" in normalized
        or "requiring captcha" in normalized
    )


def parse_payroll_markdown(markdown: str, team_code: str, season: int) -> dict[str, object]:
    tables = _unique_tables(markdown)
    player_tables = [table for table in tables if table[0][:_PLAYER_HEADER.__len__()] == _PLAYER_HEADER]
    line_tables = [table for table in tables if table[0][0] == _DESCRIPTION_HEADER]

    groups: dict[str, list[dict[str, object]]] = {
        "guaranteed_players": [],
        "arbitration_players": [],
        "pre_arbitration_players": [],
        "off_roster_players": [],
    }
    pre_arbitration_other_estimate: str | None = None
    for index, table in enumerate(player_tables):
        rows, other_estimate = _parse_player_table(table)
        pre_arbitration_other_estimate = other_estimate or pre_arbitration_other_estimate
        values = " ".join(value for row in table[2:] for value in row)
        if index == 0:
            key = "guaranteed_players"
        elif "Pre-ARB" in values or other_estimate:
            key = "pre_arbitration_players"
        elif re.search(r"\bARB [1-4]\b", values):
            key = "arbitration_players"
        else:
            key = "off_roster_players"
        groups[key] = rows

    incentives: list[dict[str, object]] = []
    other_payments: list[dict[str, object]] = []
    luxury_tax_items: list[dict[str, object]] = []
    estimated_payroll_by_year: dict[str, str] = {}
    estimated_luxury_tax_payroll: dict[str, str] = {}
    for table in line_tables:
        rows = _parse_line_table(table)
        descriptions = {str(row["description"]) for row in rows}
        if "Estimated Luxury Tax Payroll" in descriptions:
            estimated_luxury_tax_payroll = _pop_total(rows, "Estimated Luxury Tax Payroll")
            luxury_tax_items = rows
        elif "Estimated Payroll" in descriptions:
            estimated_payroll_by_year = _pop_total(rows, "Estimated Payroll")
            other_payments = rows
        else:
            incentives = rows

    title_match = re.search(r"^Title:\s*\d{4}\s+(.+?)\s+Payroll\s+\|", markdown, re.MULTILINE)
    team_name = title_match.group(1).strip() if title_match else team_code.upper()
    current_payroll = estimated_payroll_by_year.get(str(season))
    return {
        "team_name": team_name,
        "source": "FanGraphs RosterResource public payroll page",
        "source_url": payroll_source_url(team_code),
        "source_updated_at": datetime.now(timezone.utc).isoformat(),
        "refresh_mode": "weekly_snapshot",
        "estimated_payroll": current_payroll,
        "prior_year_payroll": None,
        **groups,
        "pre_arbitration_other_estimate": pre_arbitration_other_estimate,
        "incentives": incentives,
        "other_payments": other_payments,
        "estimated_payroll_by_year": estimated_payroll_by_year,
        "luxury_tax_items": luxury_tax_items,
        "estimated_luxury_tax_payroll": estimated_luxury_tax_payroll,
    }


def write_payroll_snapshot(payload: dict[str, object], team_code: str, season: int, data_dir: Path) -> Path:
    output_dir = data_dir / f"MLB{season}" / "payroll"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{team_code.casefold()}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _unique_tables(markdown: str) -> list[list[list[str]]]:
    lines = markdown.splitlines()
    tables: list[list[list[str]]] = []
    index = 0
    while index < len(lines):
        if not lines[index].lstrip().startswith("|"):
            index += 1
            continue
        block: list[list[str]] = []
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            block.append(_split_row(lines[index]))
            index += 1
        if len(block) >= 2 and not any(block == existing for existing in tables):
            tables.append(block)
    return tables


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _parse_player_table(table: list[list[str]]) -> tuple[list[dict[str, object]], str | None]:
    headers = table[0]
    years = headers[6:]
    rows: list[dict[str, object]] = []
    other_estimate = None
    for cells in table[2:]:
        if not cells:
            continue
        name = _plain_text(cells[0])
        if name.startswith("Estimated salaries for other pre-arbitration players"):
            other_estimate = next((cell for cell in cells[1:] if cell), None)
            continue
        padded = cells + [""] * max(0, len(headers) - len(cells))
        salaries = {year: value for year, value in zip(years, padded[6:]) if value}
        contract = padded[3] or ""
        rows.append({
            "name": name,
            "age": _float_or_none(padded[1]),
            "service_time": padded[2] or None,
            "contract": contract,
            "aav": padded[5] or None,
            "salaries": salaries,
            "salary_statuses": derive_salary_statuses(contract, salaries),
        })
    return rows, other_estimate


def _parse_line_table(table: list[list[str]]) -> list[dict[str, object]]:
    years = table[0][1:]
    return [
        {
            "description": _plain_text(cells[0]),
            "amounts": {year: value for year, value in zip(years, cells[1:]) if value},
        }
        for cells in table[2:]
        if cells and cells[0]
    ]


def _pop_total(rows: list[dict[str, object]], description: str) -> dict[str, str]:
    for index, row in enumerate(rows):
        if row["description"] == description:
            return rows.pop(index)["amounts"]  # type: ignore[return-value]
    return {}


def _plain_text(value: str) -> str:
    return _LINK_RE.sub(r"\1", value).strip()


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def derive_salary_statuses(contract: str, salaries: dict[str, str]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for year, value in salaries.items():
        normalized = value.casefold()
        if "free agent" in normalized:
            statuses[year] = "free_agent"
        elif "pre-arb" in normalized:
            statuses[year] = "pre_arb"
        elif re.search(r"\barb\s*[1-4]?\b", normalized):
            statuses[year] = "arbitration"

    for match in _OPTION_RE.finditer(contract):
        start = int(match.group("start"))
        end_text = match.group("end")
        end = start if not end_text else int(end_text) if len(end_text) == 4 else (start // 100) * 100 + int(end_text)
        kind = f"{match.group('kind').casefold()}_option"
        if match.group("exercised"):
            kind = f"exercised_{kind}"
        for year in range(start, end + 1):
            year_label = str(year)
            if year_label in salaries:
                statuses[year_label] = kind
    return statuses
