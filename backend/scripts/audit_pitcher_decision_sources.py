"""Slice 1: reconcile official schedule/cached feeds with read-only Statcast sources."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import sys

import duckdb
import pandas as pd
import requests


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def schedule_rows(payload: dict) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for day in payload.get("dates", []):
        for game in day.get("games", []):
            if game.get("gameType") != "R":
                continue
            pk = int(game["gamePk"])
            status = game.get("status", {})
            # Cancelled games can also carry abstractGameState=Final.
            completed = status.get("detailedState") in {"Final", "Completed Early", "Game Over", "Final: Tied", "Forfeit"}
            candidate = {
                "game_pk": pk, "official_date": game.get("officialDate", day["date"]),
                "schedule_date": day["date"], "completed": completed,
                "state": status.get("detailedState"), "status_code": status.get("statusCode"),
                "away_id": game.get("teams", {}).get("away", {}).get("team", {}).get("id"),
                "home_id": game.get("teams", {}).get("home", {}).get("team", {}).get("id"),
                "away_score": game.get("teams", {}).get("away", {}).get("score"),
                "home_score": game.get("teams", {}).get("home", {}).get("score"),
                "double_header": game.get("doubleHeader"), "game_number": game.get("gameNumber"),
                "scheduled_innings": game.get("scheduledInnings"),
                "resume_date": game.get("resumeDate"), "resumed_from": game.get("resumedFrom"),
                "reschedule_date": game.get("rescheduleDate"), "rescheduled_from": game.get("rescheduledFrom"),
                "schedule_occurrences": 1,
            }
            old = rows.get(pk)
            if old:
                candidate["schedule_occurrences"] += old["schedule_occurrences"]
                if old["completed"] and not completed:
                    old["schedule_occurrences"] = candidate["schedule_occurrences"]
                    continue
            rows[pk] = candidate
    return rows


def fetch_schedule(year: int, output: Path, through: str) -> None:
    target = output / "sources" / f"schedule_{year}.json.gz"
    if target.exists():
        print(f"{year}: reuse saved schedule snapshot", flush=True)
        return
    params = {"sportId": 1, "season": year, "gameTypes": "R", "startDate": f"{year}-01-01",
              "endDate": min(f"{year}-12-31", through)}
    response = requests.get("https://statsapi.mlb.com/api/v1/schedule", params=params, timeout=(5, 20))
    response.raise_for_status()
    payload = response.json()
    normalized = schedule_rows(payload)
    if not normalized:
        raise ValueError(f"Empty schedule for {year}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gzip.compress(response.content, mtime=0))
    save_json(output / "sources" / f"schedule_{year}.manifest.json", {
        "url": response.url, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "http_status": response.status_code, "body_sha256": digest(response.content),
        "body_bytes": len(response.content), "authentication": "none; public GET; no API key or cookie",
        "response_date": response.headers.get("Date"), "etag": response.headers.get("ETag"),
        "unique_schedule_ids": len(normalized), "snapshot": str(target),
    })
    print(f"{year}: saved {len(normalized)} schedule IDs", flush=True)


def feed_observations(payload: dict) -> dict:
    pitches: set[tuple[int, int]] = set()
    numbered: set[tuple[int, int]] = set()
    complete: set[int] = set()
    zero_pitch: set[int] = set()
    event_types: Counter = Counter()
    plays = payload.get("liveData", {}).get("plays", {}).get("allPlays", [])
    for play in plays:
        ab = int(play["atBatIndex"]) + 1
        pitch_count = 0
        for event in play.get("playEvents", []):
            pn = event.get("pitchNumber")
            if pn is not None:
                numbered.add((ab, int(pn)))
            if event.get("isPitch") and pn is not None:
                pitches.add((ab, int(pn)))
                pitch_count += 1
            if event.get("type") == "action":
                event_types[event.get("details", {}).get("eventType", "unknown")] += 1
        if play.get("about", {}).get("isComplete"):
            complete.add(ab)
            if not pitch_count:
                zero_pitch.add(ab)
    linescore = payload.get("liveData", {}).get("linescore", {})
    return {"pitch_keys": pitches, "numbered_keys": numbered, "complete_plays": complete,
            "zero_pitch_plays": zero_pitch, "actions": event_types, "plays": len(plays),
            "home_score": linescore.get("teams", {}).get("home", {}).get("runs"),
            "away_score": linescore.get("teams", {}).get("away", {}).get("runs"),
            "timestamp": payload.get("metaData", {}).get("timeStamp"),
            "state": payload.get("gameData", {}).get("status", {}).get("detailedState")}


def audit_year(year: int, root: Path, output: Path) -> None:
    source = root / f"MLB{year}" / f"mlb_{year}.duckdb"
    stamp = {"size": source.stat().st_size, "mtime_ns": source.stat().st_mtime_ns}
    c = duckdb.connect(str(source), read_only=True, config={"threads": 1})
    records = c.execute("""SELECT game_pk,cast(game_date AS DATE),at_bat_number,pitch_number,
       events,description FROM pitches WHERE game_type='R' ORDER BY game_pk,at_bat_number,pitch_number""").fetchall()
    stats = c.execute("""SELECT game_pk,count(*) pitch_rows,
       arg_max(post_home_score,at_bat_number*1000+pitch_number) home_score,
       arg_max(post_away_score,at_bat_number*1000+pitch_number) away_score,
       max(inning) max_inning,count(DISTINCT at_bat_number) observed_plays,
       min(at_bat_number) first_ab,max(at_bat_number) last_ab,
       count(DISTINCT pitcher_team) fielding_teams
       FROM pitches WHERE game_type='R' GROUP BY game_pk""").fetchdf().set_index("game_pk").to_dict("index")
    c.close()
    local = defaultdict(lambda: {"keys": set(), "plays": set(), "terminal": set(), "dates": set(), "nonpitch_keys": set()})
    for pk, date, ab, pn, event, description in records:
        row = local[int(pk)]
        row["keys"].add((int(ab), int(pn)))
        row["plays"].add(int(ab))
        row["dates"].add(str(date))
        if event is not None:
            row["terminal"].add(int(ab))
        if description and ("automatic" in description.lower() or "intent" in description.lower()):
            row["nonpitch_keys"].add((int(ab), int(pn)))
    del records
    schedule = schedule_rows(json.loads(gzip.decompress((output/"sources"/f"schedule_{year}.json.gz").read_bytes())))
    feed_dir = root / "research/catcher_descriptive/slice1/raw_game_feeds" / str(year)
    issues = []
    games = []
    inventory = []
    all_actions: Counter = Counter()
    counts: Counter = Counter()

    def issue(pk: int, reason: str, priority: str, details: object) -> None:
        issues.append({"year": year, "game_pk": pk, "official_date": schedule.get(pk, {}).get("official_date"),
                       "reason": reason, "priority": priority, "details": json.dumps(details, ensure_ascii=False)})

    for i, pk in enumerate(sorted(set(local) | set(schedule)), 1):
        official = schedule.get(pk, {})
        loc = local.get(pk)
        path = feed_dir / f"{pk}.json.gz"
        game = {"year": year, "game_pk": pk, **official, "local_present": loc is not None,
                "local_pitch_rows": stats.get(pk, {}).get("pitch_rows", 0),
                "local_dates": ",".join(sorted(loc["dates"])) if loc else None,
                "feed_present": path.exists()}
        if official.get("completed"):
            counts["official_completed_games"] += 1
            if loc is None:
                issue(pk, "completed_game_missing_local", "backfill", official)
        elif loc is not None:
            issue(pk, "local_game_not_official_completed", "quarantine_review", official)
        if loc and official and official["official_date"] not in loc["dates"]:
            issue(pk, "official_date_differs", "date_review", {"local": sorted(loc["dates"]),
                  "official": official["official_date"], "resume_date": official.get("resume_date")})
        if loc and official.get("completed"):
            local_score = (stats[pk]["home_score"], stats[pk]["away_score"])
            official_score = (official.get("home_score"), official.get("away_score"))
            if local_score != official_score:
                issue(pk, "final_score_differs", "backfill_review", {"local": local_score, "official": official_score})
        if official.get("completed") or loc:
            if not path.exists():
                issue(pk, "official_feed_snapshot_missing", "snapshot_needed", {})
            else:
                try:
                    compressed = path.read_bytes()
                    payload = json.loads(gzip.decompress(compressed))
                    if int(payload.get("gamePk", -1)) != pk:
                        raise ValueError("feed gamePk mismatch")
                    feed = feed_observations(payload)
                    counts["readable_feed_games"] += 1
                    counts["official_pitch_events"] += len(feed["pitch_keys"])
                    counts["official_completed_plays"] += len(feed["complete_plays"])
                    counts["official_zero_pitch_completed_plays"] += len(feed["zero_pitch_plays"])
                    all_actions.update(feed["actions"])
                    inventory.append({"year": year, "game_pk": pk, "path": str(path),
                        "compressed_bytes": len(compressed), "compressed_sha256": digest(compressed),
                        "feed_timestamp": feed["timestamp"], "feed_state": feed["state"],
                        "snapshot_mtime_ns": path.stat().st_mtime_ns})
                    game.update({"feed_state": feed["state"], "feed_plays": feed["plays"],
                        "feed_pitch_events": len(feed["pitch_keys"]), "feed_zero_pitch_plays": len(feed["zero_pitch_plays"]),
                        "feed_pitching_substitutions": feed["actions"]["pitching_substitution"]})
                    if official.get("completed") and (feed["home_score"],feed["away_score"]) != (official.get("home_score"),official.get("away_score")):
                        issue(pk,"cached_feed_schedule_score_differs","snapshot_review",{"feed":[feed["home_score"],feed["away_score"]],"schedule":[official.get("home_score"),official.get("away_score")]})
                    if loc:
                        missing = feed["pitch_keys"] - loc["keys"]
                        unmatched = loc["keys"] - feed["numbered_keys"]
                        missing_plays = feed["complete_plays"] - loc["plays"]
                        no_terminal = loc["plays"] - loc["terminal"]
                        game.update({"official_pitch_keys_missing_local": len(missing),
                            "local_keys_not_in_feed_numbered_events": len(unmatched),
                            "official_completed_plays_without_local_rows": len(missing_plays),
                            "local_plays_without_terminal_event": len(no_terminal)})
                        counts["official_pitch_keys_missing_local"] += len(missing)
                        counts["local_keys_not_in_feed_numbered_events"] += len(unmatched)
                        counts["official_completed_plays_without_local_rows"] += len(missing_plays)
                        counts["local_plays_without_terminal_event"] += len(no_terminal)
                        if missing:
                            issue(pk,"official_pitch_keys_missing_local","tracking_or_backfill_review",sorted(missing))
                        if unmatched:
                            issue(pk,"local_keys_not_in_feed_numbered_events","key_semantics_review",sorted(unmatched))
                        if missing_plays:
                            issue(pk,"completed_plays_without_local_rows","zero_pitch_or_backfill_review",
                                  {"plays":sorted(missing_plays),"zero_pitch":sorted(missing_plays & feed["zero_pitch_plays"])})
                        if no_terminal:
                            issue(pk,"local_plays_without_terminal_event","event_semantics_review",sorted(no_terminal))
                except (OSError,ValueError,KeyError,TypeError) as exc:
                    issue(pk,"official_feed_unreadable","snapshot_needed",str(exc))
        games.append(game)
        if i % 100 == 0:
            print(f"{year}: compared {i}/{len(set(local)|set(schedule))} schedule IDs", flush=True)
    if stamp != {"size": source.stat().st_size, "mtime_ns": source.stat().st_mtime_ns}:
        raise RuntimeError("Source database changed during audit; rerun from a stable snapshot")
    output.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(games).to_parquet(output/f"games_{year}.parquet",index=False)
    pd.DataFrame(issues,columns=["year","game_pk","official_date","reason","priority","details"]).to_parquet(output/f"issues_{year}.parquet",index=False)
    pd.DataFrame(inventory).to_parquet(output/f"feed_inventory_{year}.parquet",index=False)
    summary={"year":year,"local_games":len(local),"local_pitches":sum(r["pitch_rows"] for r in stats.values()),
        **counts,"schedule_status_counts":dict(Counter(r["state"] for r in schedule.values())),
        "issue_counts":dict(Counter(r["reason"] for r in issues)),"official_action_counts":dict(all_actions),
        "source_db":{"path":str(source),**stamp},"feed_root":str(feed_dir),
        "unique_schedule_ids":len(schedule),"schedule_duplicate_occurrences":sum(r["schedule_occurrences"]-1 for r in schedule.values())}
    save_json(output/f"summary_{year}.json",summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


def finalize(root: Path, output: Path) -> None:
    summaries = [json.loads((output/f"summary_{y}.json").read_text(encoding="utf-8")) for y in range(2021,2027)]
    c = duckdb.connect(":memory:", config={"threads": 1})
    yearly = []
    dates = []
    backfill = []
    cancelled = []
    classifications = []
    checks = []
    score_reviews = []
    for row in summaries:
        year = row["year"]
        games = pd.read_parquet(output/f"games_{year}.parquet")
        issues = pd.read_parquet(output/f"issues_{year}.parquet")
        official = games[games["completed"].eq(True)]
        missing = official[~official["local_present"]]
        assert len(official) == row["official_completed_games"]
        assert len(missing) == row["issue_counts"].get("completed_game_missing_local", 0)
        assert len(games[games["local_present"]]) == row["local_games"]
        assert row["readable_feed_games"] == len(official)
        assert not row["issue_counts"].get("official_feed_unreadable", 0)
        assert not row["issue_counts"].get("cached_feed_schedule_score_differs", 0)
        assert len(games[games["local_present"] & ~games["completed"].eq(True)]) == 0
        for date, group in official.groupby("official_date"):
            missing_ids = group.loc[~group["local_present"],"game_pk"].astype(int).tolist()
            partial = group.loc[group["official_pitch_keys_missing_local"].fillna(0).gt(0),"game_pk"].astype(int).tolist()
            dates.append({"year":year,"date":date,"completed_games":len(group),"local_game_ids":int(group["local_present"].sum()),
                          "missing_game_ids":json.dumps(missing_ids),"pitch_key_review_games":json.dumps(partial)})
        for _, game in games[games["state"].eq("Cancelled")].iterrows():
            cancelled.append({"year":year,"game_pk":int(game["game_pk"]),"date":game["official_date"],"status":"Cancelled","count_as_missing":False})
        for _, issue_row in issues[issues["reason"].eq("official_pitch_keys_missing_local")].iterrows():
            keys = json.loads(issue_row["details"])
            pk = int(issue_row["game_pk"])
            game = games[games["game_pk"].eq(pk)].iloc[0]
            backfill.append({"year":year,"game_pk":pk,"date":issue_row["official_date"],"missing_official_pitch_keys":len(keys),
                "local_pitch_rows":int(game["local_pitch_rows"]),"official_pitch_events":int(game["feed_pitch_events"]),
                "classification":"partial_game" if len(keys)>10 else "source_revision_review",
                "action":"按 game ID 比對公開 Statcast 原始紀錄與已保存 feed；保存修訂差異，不直接以 feed 補造追蹤值。",
                "missing_keys":keys})
        for issue_row in issues[issues["reason"].eq("final_score_differs")].itertuples():
            pk = int(issue_row.game_pk)
            feed_path=root/"research/catcher_descriptive/slice1/raw_game_feeds"/str(year)/f"{pk}.json.gz"
            payload=json.loads(gzip.decompress(feed_path.read_bytes()))
            last_play=payload["liveData"]["plays"]["allPlays"][-1]
            event_type=last_play.get("result",{}).get("eventType")
            score_reviews.append({"year":year,"game_pk":pk,"last_event_type":event_type,
                "classification":"nonpitch_terminal_balk" if event_type=="balk" else "pitch_or_source_gap",
                "description":last_play.get("result",{}).get("description"),
                "scores":json.loads(issue_row.details)})
        unmatched = [(int(r.game_pk),*key) for r in issues[issues["reason"].eq("local_keys_not_in_feed_numbered_events")].itertuples()
                     for key in json.loads(r.details)]
        if unmatched:
            c.register("keys",pd.DataFrame(unmatched,columns=["game_pk","at_bat_number","pitch_number"]))
            db=(root/f"MLB{year}"/f"mlb_{year}.duckdb").as_posix()
            c.execute(f"ATTACH '{db}' AS season (READ_ONLY)")
            result=c.execute("""SELECT description,events,count(*) row_count,count(release_speed) with_speed
                FROM season.pitches JOIN keys USING(game_pk,at_bat_number,pitch_number)
                WHERE game_type='R' GROUP BY 1,2 ORDER BY 3 DESC""").fetchdf()
            result["year"]=year
            classifications.extend(json.loads(result.to_json(orient="records")))
            c.execute("DETACH season")
        yearly.append({"year":year,"completedGames":len(official),"localGames":row["local_games"],
                       "missingGames":len(missing),"cachedFeeds":row["readable_feed_games"],
                       "missingPitchKeys":row["official_pitch_keys_missing_local"],
                       "unmatchedLocalKeys":row["local_keys_not_in_feed_numbered_events"],
                       "completedPlaysWithoutLocalRows":row["official_completed_plays_without_local_rows"],
                       "localPlaysWithoutTerminal":row["local_plays_without_terminal_event"],
                       "officialPitchingSubstitutions":row["official_action_counts"].get("pitching_substitution",0),
                       "scoreReviewGames":row["issue_counts"].get("final_score_differs",0)})
        checks.append({"year":year,"official_vs_local_ids_reconciled":True,"cancelled_excluded":True,
                       "feed_scores_match_schedule":True,"all_completed_games_have_readable_cached_feed":True})
    pd.DataFrame(dates).to_csv(output/"date_coverage.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(classifications).to_csv(output/"unmatched_key_classification.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(yearly).to_csv(output/"yearly_summary.csv",index=False,encoding="utf-8-sig")
    total = {key:sum(r[key] for r in yearly) for key in yearly[0] if key!="year"}
    report = {"contract_version":"pitcher_decision_slice1_source_audit_v1", "audit_date":"2026-11-12",
        "scope":"2021–2026 MLB regular season; schedule snapshots and preexisting official feeds; source databases read-only",
        "years":yearly,"totals":total,"cancelled_games":cancelled,"pitch_backfill_queue":backfill,
        "missing_whole_dates":[r for r in dates if r["local_game_ids"]==0],
        "score_semantics_review":score_reviews,
        "fetch_estimate":{"new_official_feed_downloads":0,"statcast_game_ids_to_check":len(backfill),
            "physical_pitch_key_differences":sum(v["missing_official_pitch_keys"] for v in backfill),
            "note":"逐球鍵差異不保證皆能取得追蹤值；2024 單球需核對來源修訂，2026 是明確截斷。"},
        "provenance":{"schedule":"sources/schedule_YEAR.json.gz + per-year URL/UTC/SHA-256 manifests; public GET, no key/cookie",
            "cached_feeds":"feed_inventory_YEAR.parquet records existing compressed SHA-256, file mtime and feed timestamp",
            "local_sources":"summary_YEAR.json records read-only DuckDB size/mtime; start/end stability checked",
            "fresh_schedule_get_requests":6,"game_feed_download_requests":0},
        "limitations":["Cancelled 不能以 abstractGameState=Final 當作已完成，須檢查 detailedState。",
            "賽程 ID 齊全不等於逐球與事件齊全；此次只產出清單，沒有修復來源。",
            "完成 play 可能是零球保送、牽制或跑壘事件，不等於完成打者打席。",
            "來源 pitch_number 可能受自動壞球／好球與來源修訂影響；不能按不匹配數直接刪資料。",
            "完整官方 feed 可沿用，但仍須 Slice 3 建立換人與零球事件帳本。",
            "2026 賽程與早期研究資料均為回溯來源，不代表當時可取得的能力特徵。"],
        "checks":checks,"next_slice":"Slice 2 only after user instruction; use queue, reuse snapshots, preserve raw versions."}
    save_json(output/"report.json",report)
    # Small versioned evidence; full per-game inventories stay in ignored data/research.
    compact={k:v for k,v in report.items() if k not in {"pitch_backfill_queue"}}
    compact["pitch_backfill_queue"]=[{k:v for k,v in item.items() if k!="missing_keys"} for item in backfill]
    save_json(root/"sample/petehub_pitcher_decision_slice1_audit_v1.json",compact)
    print(json.dumps({"totals":total,"backfill_games":[(r["year"],r["game_pk"],r["missing_official_pitch_keys"]) for r in backfill],
                      "cancelled_games":cancelled,"checks":"6 years passed"},ensure_ascii=False),flush=True)


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser()
    parser.add_argument("--year",type=int,choices=range(2021,2027))
    parser.add_argument("--data-dir",type=Path,default=Path(__file__).resolve().parents[2]/"data")
    parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[2]/"data/research/decision_support_slice1_20261112")
    parser.add_argument("--through",default="2026-11-12")
    parser.add_argument("--fetch-schedule",action="store_true")
    parser.add_argument("--finalize",action="store_true")
    args=parser.parse_args()
    if args.finalize:finalize(args.data_dir,args.output)
    elif args.year is None:parser.error("--year is required unless --finalize is used")
    elif args.fetch_schedule:fetch_schedule(args.year,args.output,args.through)
    else:audit_year(args.year,args.data_dir,args.output)
