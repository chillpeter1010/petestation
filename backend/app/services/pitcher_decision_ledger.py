"""Chronological official event ledger, independent of frozen Stamina models.

Outcome fields live on play rows only. Candidate and workload features must not
read those outcome columns. Dates/timestamps refer to the original event feed.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from typing import Any

NON_BF = {"balk", "caught_stealing_2b", "caught_stealing_3b", "caught_stealing_home",
          "other_out", "passed_ball", "pickoff_1b", "pickoff_2b", "pickoff_3b",
          "pickoff_caught_stealing_2b", "pickoff_caught_stealing_3b", "pickoff_caught_stealing_home",
          "pickoff_error_1b", "pickoff_error_2b", "pickoff_error_3b", "pickoff_error_home",
          "stolen_base_2b", "stolen_base_3b", "stolen_base_home", "wild_pitch", "game_advisory", "runner_double_play", "defensive_indiff", "forced_balk"}
PITCH_CHANGES = {"pitching_substitution", "pitcher_switch"}


def integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def is_pitch_change(event: dict) -> bool:
    kind = event.get("details", {}).get("eventType")
    return kind in PITCH_CHANGES or (kind == "defensive_switch" and str((event.get("position") or {}).get("code")) == "1")


def statutory_change_status(batters_faced: int, previous_half_ended: bool, initial: bool) -> str:
    if initial:
        return "initial_start"
    return "allowed" if previous_half_ended or batters_faced >= 3 else "minimum_batters_not_met"


def parse_game(year: int, payload: dict, local_pa: dict[int, dict] | None = None) -> dict[str, list[dict]]:
    pk = int(payload["gamePk"])
    local_pa = local_pa or {}
    result: dict[str, list[dict]] = {k: [] for k in ["events", "plays", "decisions", "appearances", "roster", "runners"]}
    data = payload.get("gameData", {})
    official_date = data.get("datetime", {}).get("officialDate") or data.get("datetime", {}).get("originalDate")
    scheduled = integer(payload.get("liveData", {}).get("linescore", {}).get("scheduledInnings")) or integer(data.get("game", {}).get("scheduledInnings")) or 9
    teams = payload.get("liveData", {}).get("boxscore", {}).get("teams", {})
    active: dict[str, int | None] = {}
    team_ids = {}
    removed: dict[str, set[int]] = {"home": set(), "away": set()}
    used: dict[str, set[int]] = {"home": set(), "away": set()}
    switched: dict[str, set[int]] = {"home": set(), "away": set()}
    current: dict[str, dict | None] = {"home": None, "away": None}
    last_outs = {"home": 3, "away": 3}
    has_pitched = {"home": False, "away": False}
    serial = {"home": 0, "away": 0}
    for side in ["home", "away"]:
        box = teams.get(side, {})
        team_ids[side] = integer(box.get("team", {}).get("id") or data.get("teams", {}).get(side, {}).get("id"))
        active[side] = integer((box.get("pitchers") or [None])[0])
        # Use every named roster member, not just the retrospective used-pitcher list.
        for person in box.get("players", {}).values():
            pid = integer(person.get("person", {}).get("id"))
            if pid is None:
                continue
            result["roster"].append({"year": year, "game_pk": pk, "official_date": official_date,
                "team_id": team_ids[side], "side": side, "player_id": pid,
                "name": person.get("person", {}).get("fullName"), "position_code": str(person.get("position", {}).get("code") or ""),
                "status_code": person.get("status", {}).get("code"),
                "basis": "retrospective_full_game_roster_not_usage_list"})

    def enter(side: str, pid: int | None, time: str | None, ab: int, index: int, inning: int, half: str, initial: bool = False) -> dict:
        previous = current[side]
        if previous and previous["pitcher_id"] == pid:
            return previous
        if previous:
            previous["exit_time"] = time
            previous["exit_ab"] = ab
            previous["exit_event_index"] = index
        serial[side] += 1
        item = {"year": year, "game_pk": pk, "official_date": official_date, "team_id": team_ids[side],
                "pitcher_id": pid, "appearance_id": f"{pk}:{side}:{serial[side]}",
                "role": "SP" if initial and serial[side] == 1 else "RP", "entry_time": time,
                "exit_time": None, "entry_ab": ab, "entry_event_index": index,
                "exit_ab": None, "exit_event_index": None, "first_pitch_time": None, "last_pitch_time": None,
                "pitches": 0, "bf": 0, "outs": 0, "entry_inning": inning, "entry_half": half,
                "last_inning": inning, "zero_pitch": True}
        result["appearances"].append(item)
        current[side] = item
        active[side] = pid
        if pid is not None:
            used[side].add(pid)
        return item

    home_score = away_score = 0
    bases: dict[int, int] = {}
    outs = 0
    half_key = None
    base_state_known = True
    plays = payload.get("liveData", {}).get("plays", {}).get("allPlays", [])
    def base_value() -> int | None:
        values=list(bases.values())
        return sum(values) if len(values)==len(set(values)) else None
    for play in plays:
        about = play.get("about", {})
        ab = int(play["atBatIndex"]) + 1
        inning = int(about.get("inning") or 1)
        half = "top" if about.get("isTopInning") else "bottom"
        side = "home" if half == "top" else "away"
        offense = "away" if side == "home" else "home"
        if half_key != (inning, half):
            half_key = (inning, half)
            bases = {}
            outs = 0
            base_state_known = True
        outcome = play.get("result", {})
        event_type = outcome.get("eventType", "unknown")
        bf = int(outcome.get("type") == "atBat" and event_type not in NON_BF and about.get("isComplete", False))
        physical = [e for e in play.get("playEvents", []) if e.get("isPitch")]
        events = sorted(play.get("playEvents", []), key=lambda e: int(e.get("index", 0)))
        first_pitch_index = min((int(e.get("index", 0)) for e in physical), default=10**6)
        changes = [e for e in events if is_pitch_change(e)]
        pre_changes = [e for e in changes if int(e.get("index", 0)) < first_pitch_index]
        decision_index = int(pre_changes[0].get("index", 0)) if pre_changes else first_pitch_index
        if decision_index == 10**6:
            decision_index = int(events[0].get("index", 0)) if events else -1
        match = play.get("matchup", {})
        batter = integer(match.get("batter", {}).get("id"))
        offensive_changes = [e for e in events if e.get("details", {}).get("eventType") == "offensive_substitution"]
        # Rewind only the actual batter's substitution chain. A pinch-runner is
        # also an offensive_substitution but must never become the batter.
        for change in reversed(offensive_changes):
            if integer(change.get('player',{}).get('id')) == batter and change.get('position',{}).get('abbreviation')!='PR':
                batter = integer(change.get('replacedPlayer',{}).get('id')) or batter
        initial_side = not has_pitched[side]
        if current[side] is None:
            starter = active[side] or integer(match.get("pitcher", {}).get("id"))
            enter(side, starter, iso(about.get("startTime")), ab, -1, inning, half, initial=True)
        start_pitcher = active[side]
        prefix_home, prefix_away, prefix_outs, prefix_bases = home_score, away_score, outs, base_value()
        balls = strikes = 0
        observed_injury = False
        decision = None
        runner_by_index: dict[int, list[dict]] = defaultdict(list)
        for runner in play.get("runners", []):
            idx = integer(runner.get("details", {}).get("playIndex"))
            runner_by_index[idx if idx is not None else -1].append(runner)

        def make_decision(index: int, time: str | None, basis: str = "play_start_fallback") -> dict:
            cur = current[side]
            chosen = integer(pre_changes[0].get("player", {}).get("id")) if pre_changes else active[side]
            return {"year": year, "game_pk": pk, "official_date": official_date, "at_bat_number": ab,
                "decision_id": f"{pk}:{ab}:boundary", "event_index": index, "decision_time": time,"time_basis":basis,
                "team_id": team_ids[side], "outgoing_pitcher_id": active[side], "incoming_pitcher_id": chosen,
                "appearance_id": cur["appearance_id"], "batter_id": batter, "inning": inning, "half": half,
                "home_score": home_score, "away_score": away_score, "outs": outs, "base_state": base_value(),
                "balls": balls, "strikes": strikes, "is_initial_start": initial_side,
                "base_state_known": base_state_known and base_value() is not None and not (inning > scheduled and outs == 0 and not bases),
                "observed_change": bool(pre_changes), "statutory_status": statutory_change_status(cur["bf"], last_outs[side] >= 3, initial_side),
                "current_pitches": cur["pitches"], "current_bf": cur["bf"], "injury_observed_before": observed_injury,
                "mandatory_removed_pitcher": active[side] in removed[side],
                "compound_prelude": len(pre_changes) > 1 or any(int(e.get("index",0)) > index for e in offensive_changes),
                "completed_batter_play": bool(bf), "used_pitcher_ids": json.dumps(sorted(used[side])),
                "removed_player_ids": json.dumps(sorted(removed[side])), "unsupported_switch_ids": json.dumps(sorted(switched[side])),
                "warmup_status": "unknown", "body_status": "unknown", "outcome_key": f"{pk}:{ab}"}

        for event in events:
            index = int(event.get("index", 0))
            time = iso(event.get("startTime") or event.get("endTime") or about.get("startTime"))
            time_basis = "event_start" if event.get("startTime") else "event_end" if event.get("endTime") else "play_start_fallback"
            details = event.get("details", {})
            kind = details.get("eventType") or event.get("type") or "unknown"
            if index == decision_index:
                decision = make_decision(index, time, time_basis)
            before_pitcher = active[side]
            before_bases = base_value()
            before_outs = outs
            if kind == "injury":
                observed_injury = True
            player = integer(event.get("player", {}).get("id"))
            replaced = integer(event.get("replacedPlayer", {}).get("id"))
            if is_pitch_change(event) and player is not None:
                enter(side, player, time, ab, index, inning, half)
                if kind != "pitching_substitution":
                    switched[side].add(player)
            elif kind in {"offensive_substitution", "defensive_substitution"} and replaced is not None:
                affected = offense if kind == "offensive_substitution" else side
                removed[affected].add(replaced)
            elif kind == "defensive_switch" and player is not None:
                switched[side].add(player)
            if kind == "offensive_substitution" and replaced == batter and player is not None:
                batter = player
            if kind == "offensive_substitution" and replaced in bases and player is not None:
                bases[player] = bases.pop(replaced)
            physical_pitch = bool(event.get("isPitch"))
            cur = current[side]
            if physical_pitch:
                cur["pitches"] += 1
                cur["zero_pitch"] = False
                cur["first_pitch_time"] = cur["first_pitch_time"] or time
                cur["last_pitch_time"] = time
                cur["last_inning"] = inning
                has_pitched[side] = True
            # Runner placements and movements are applied only at their event index.
            if kind == "runner_placed" and player is not None:
                base = str(event.get("base") or "2B")
                bases[player] = {"1B": 1, "2B": 2, "3B": 4}.get(base, 2)
            movements = runner_by_index.get(index, [])
            for runner in movements:
                move, rd = runner.get("movement", {}), runner.get("details", {})
                rid = integer(rd.get("runner", {}).get("id"))
                if rid is not None:
                    bases.pop(rid, None)
                    end = move.get("end")
                    if not move.get("isOut") and end in {"1B", "2B", "3B"}:
                        bases[rid] = {"1B": 1, "2B": 2, "3B": 4}[end]
                if rd.get("isScoringEvent"):
                    if offense == "home": home_score += 1
                    else: away_score += 1
                if move.get("isOut") and move.get("outNumber") is not None:
                    outs = max(outs, int(move["outNumber"]))
                result["runners"].append({"year": year, "game_pk": pk, "at_bat_number": ab, "event_index": index,
                    "runner_id": rid, "start_base": move.get("start"), "end_base": move.get("end"),
                    "is_out": bool(move.get("isOut")), "is_scoring": bool(rd.get("isScoringEvent")),
                    "responsible_pitcher_id": integer((rd.get("responsiblePitcher") or {}).get("id")),
                    "attribution": "official_outcome_only"})
            cur["outs"] += max(0, outs - before_outs)
            result["events"].append({"year": year, "game_pk": pk, "official_date": official_date,
                "at_bat_number": ab, "event_index": index, "event_id": f"{pk}:{ab}:{index}",
                "event_time": time,"time_basis":time_basis, "end_time": iso(event.get("endTime")), "event_type": kind,
                "is_pitch": physical_pitch, "pitch_number": integer(event.get("pitchNumber")),
                "play_id": event.get("playId"), "team_id": team_ids[side], "pitcher_id": active[side],
                "previous_pitcher_id": before_pitcher, "player_id": player, "replaced_player_id": replaced,
                "batter_id": batter, "appearance_id": cur["appearance_id"], "inning": inning, "half": half,
                "balls_before": balls, "strikes_before": strikes, "outs_before": before_outs,
                "base_state_before": before_bases, "home_score_after": home_score, "away_score_after": away_score,
                "is_pitch_change": is_pitch_change(event), "description": details.get("description")})
            count = event.get("count", {})
            balls = integer(count.get("balls")) if count.get("balls") is not None else balls
            strikes = integer(count.get("strikes")) if count.get("strikes") is not None else strikes
        if decision is None:
            decision = make_decision(-1, iso(about.get("startTime")))
        result["decisions"].append(decision)
        cur = current[side]
        cur["bf"] += bf
        if bf:
            has_pitched[side] = True
        if runner_by_index.get(-1):
            base_state_known = False
        post_outs = integer(play.get("count", {}).get("outs"))
        cur["outs"] += max(0, (post_outs if post_outs is not None else outs) - outs)
        outs = post_outs if post_outs is not None else outs
        # End-of-play official totals are outcomes; never copied into decision features.
        home_score = integer(outcome.get("homeScore")) if outcome.get("homeScore") is not None else home_score
        away_score = integer(outcome.get("awayScore")) if outcome.get("awayScore") is not None else away_score
        last_outs[side] = outs
        loc = local_pa.get(ab, {})
        result["plays"].append({"year": year, "game_pk": pk, "official_date": official_date,
            "at_bat_number": ab, "outcome_key": f"{pk}:{ab}", "team_id": team_ids[side], "inning": inning, "half": half,
            "start_time": iso(about.get("startTime")), "end_time": iso(about.get("endTime")),
            "initial_pitcher_id": start_pitcher, "terminal_pitcher_id": active[side], "batter_id": integer(match.get("batter", {}).get("id")),
            "is_complete": bool(about.get("isComplete")), "is_batter_faced": bool(bf), "event_type": event_type,
            "pitch_count": len(physical), "zero_pitch": not physical, "mid_pa_change": any(int(e.get("index",0)) >= first_pitch_index for e in changes),
            "home_score_before": prefix_home, "away_score_before": prefix_away,
            "home_score_after": home_score, "away_score_after": away_score,
            "outs_before": prefix_outs, "outs_after": outs, "base_state_before": prefix_bases,
            "base_state_after": base_value(), "pre_home_we": loc.get("pre_home_we"),
            "source_re24": loc.get("source_re24"), "runner_index_missing": bool(runner_by_index.get(-1)),
            "scheduled_innings": scheduled})
    # WPA is stored once per play, only for directly available adjacent boundaries.
    for index, play in enumerate(result["plays"]):
        pre = play["pre_home_we"]
        if index + 1 < len(result["plays"]):
            post = result["plays"][index+1]["pre_home_we"]
        else:
            post = 1.0 if home_score > away_score else 0.0 if home_score < away_score else None
        play["raw_home_wpa"] = post-pre if pre is not None and post is not None else None
        play["wpa_status"] = "adjacent_boundary" if play["raw_home_wpa"] is not None else "unpriced_boundary"
    end = iso(plays[-1].get("about", {}).get("endTime")) if plays else None
    for item in result["appearances"]:
        if item["exit_time"] is None:
            item["exit_time"] = end
    return result
