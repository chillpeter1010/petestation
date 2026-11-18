"""Small on-demand current bio cache; never rewrite historical pitch data."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from uuid import uuid4

import requests

from app.api.schemas.player_bio import PlayerBio
from app.core.config import settings

BIO_TTL_SECONDS = 7 * 86400
BIO_RETRY_SECONDS = 15 * 60


def _fetch(url: str, timeout: int) -> dict:
    response = requests.get(url, timeout=(3, timeout))
    response.raise_for_status()
    return response.json()


def _weight(value: object) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) and 0 < number < 1500 else None
    except (ValueError, TypeError):
        return None


def normalize_person(person: dict, retrieved_at: str) -> PlayerBio:
    raw = person.get("height")
    match = re.fullmatch(r"\s*(\d)\s*'\s*(\d{1,2})\s*\"?\s*", str(raw or ""))
    inches = int(match[1]) * 12 + int(match[2]) if match and int(match[2]) < 12 else None
    if inches is not None and not 36 <= inches <= 108:
        inches = None
    pounds = _weight(person.get("weight"))
    bats = (person.get("batSide") or {}).get("code")
    throws = (person.get("pitchHand") or {}).get("code")
    return PlayerBio(
        player_id=int(person["id"]), name=person.get("fullName"),
        source_url=f"https://statsapi.mlb.com/api/v1/people/{int(person['id'])}",
        height_raw=str(raw) if raw is not None else None, height_inches=inches,
        height_m=round(inches * .0254, 6) if inches is not None else None,
        weight_lb=pounds, weight_kg=round(pounds * .45359237, 4) if pounds is not None else None,
        bats=bats if bats in {"R", "L", "S"} else None,
        throws=throws if throws in {"R", "L", "S"} else None,
        retrieved_at=retrieved_at, last_attempt_at=retrieved_at, freshness="fresh",
    )


def _age(value: str | None, now: datetime) -> float:
    try:
        stamp = datetime.fromisoformat(value or "")
        return max(0, (now - stamp.replace(tzinfo=stamp.tzinfo or timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return float("inf")


def get_player_bios(
    player_ids: list[int] | tuple[int, ...], *, data_dir: Path | None = None,
    now: datetime | None = None, fetcher: Callable = _fetch,
) -> dict[int, PlayerBio]:
    ids = sorted({int(i) for i in player_ids if int(i) > 0})
    if len(ids) > 50:
        raise ValueError("Bio lookup is limited to 50 players per request.")
    current = now or datetime.now(timezone.utc)
    current = current.replace(tzinfo=current.tzinfo or timezone.utc)
    stamp = current.isoformat()
    root = Path(data_dir or settings.data_dir) / "player_bios_v1"
    result, pending = {}, []
    for player_id in ids:
        bio = None
        try:
            bio = PlayerBio.model_validate_json((root / f"{player_id}.json").read_text(encoding="utf-8"))
            if bio.player_id != player_id:
                bio = None
        except (OSError, ValueError):
            pass
        if bio is None:
            bio = PlayerBio(player_id=player_id, source_url=f"https://statsapi.mlb.com/api/v1/people/{player_id}")
        bio.freshness = "fresh" if _age(bio.retrieved_at, current) < BIO_TTL_SECONDS else "stale" if bio.retrieved_at else "unavailable"
        result[player_id] = bio
        if bio.freshness != "fresh" and _age(bio.last_attempt_at, current) >= BIO_RETRY_SECONDS:
            pending.append(player_id)
    if not pending:
        return result
    query = urlencode({"personIds": ",".join(map(str, pending)), "fields": "people,id,fullName,height,weight,batSide,code,pitchHand"})
    warning = None
    received = {}
    try:
        payload = fetcher(f"https://statsapi.mlb.com/api/v1/people?{query}", timeout=6)
        if not isinstance(payload, dict) or not isinstance(payload.get("people"), list):
            raise ValueError("People response is missing its player list.")
        for person in payload["people"]:
            # Reject unrelated IDs; malformed one-player bio must not drop the others.
            try:
                if int(person["id"]) in pending:
                    received[int(person["id"])] = normalize_person(person, stamp)
            except (TypeError, ValueError, KeyError):
                continue
    except (requests.RequestException, ValueError, TypeError) as exc:
        warning = f"Bio refresh unavailable: {type(exc).__name__}."
    for player_id in pending:
        bio = received.get(player_id, result[player_id])
        bio.last_attempt_at = stamp
        bio.warning = None if player_id in received else warning or "Player omitted from People response; keeping any prior bio."
        result[player_id] = bio
        # Cache errors never block replay; unique temporary names permit concurrent requests.
        temp = root / f"{player_id}.{uuid4().hex}.tmp"
        try:
            root.mkdir(parents=True, exist_ok=True)
            temp.write_text(bio.model_dump_json(indent=2), encoding="utf-8")
            temp.replace(root / f"{player_id}.json")
        except OSError:
            bio.warning = "Bio cache could not be saved; this response remains usable."
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
    return result
