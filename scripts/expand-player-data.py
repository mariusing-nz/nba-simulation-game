#!/usr/bin/env python3
"""Expand the production database to 400 current and 400 all-time records.

New records are selected deterministically from the bundled Basketball Reference
CSV mirror. Position eligibility is limited to positions explicitly listed in a
player's recorded career, with the represented-season primary position first.
"""
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CSV = Path("/tmp/nba-stats/Player Per Game.csv")
ORDER = ["PG", "SG", "SF", "PF", "C"]

spec = importlib.util.spec_from_file_location("audit_player_data", ROOT / "scripts" / "audit-player-data.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def clamp(value, low=40, high=99):
    return max(low, min(high, round(value)))


def slug(value):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def score(row):
    return row["points"] + row["rebounds"] + row["assists"] + row["steals"] + row["blocks"]


def career_positions(rows, primary):
    seen = {position for row in rows for position in row["positions"] if position in ORDER}
    positions = [primary] if primary in ORDER else []
    for distance in (1, 2, 3, 4):
        for position in ORDER:
            if position in seen and position not in positions and positions and abs(ORDER.index(position) - ORDER.index(primary)) == distance:
                positions.append(position)
                if len(positions) == 3:
                    return positions
    return positions or ["SF"]


def ratings(row):
    overall = clamp(67 + score(row) * .36, 67, 94)
    return {
        "overall": overall,
        "offense": clamp(64 + row["points"] * .75 + row["assists"] * .35, 60, 97),
        "defense": clamp(65 + row["rebounds"] * .8 + row["steals"] * 3 + row["blocks"] * 3, 58, 96),
        "shooting": clamp(63 + row["points"] * .75, 55, 96),
        "playmaking": clamp(62 + row["assists"] * 3.2, 52, 97),
        "rebounding": clamp(61 + row["rebounds"] * 3.1, 50, 98),
        "athleticism": clamp(68 + row["minutes"] * .45, 60, 94),
    }


def make_player(era, team, row, rows, index):
    primary = row["positions"][0] if row["positions"] else "SF"
    years = [item["seasonEndYear"] for item in rows]
    current = any(year == 2026 for year in years)
    result = {
        "id": f"{era.replace('-', '')}-{team.lower()}-{slug(row['name'])}-{index}",
        "name": row["name"], "teamId": team, "era": era, "season": row["season"],
        "decadeTags": [] if era == "current" else [f"{(row['seasonEndYear'] - 1) % 100 // 10 * 10:02d}s"],
        "positions": career_positions(rows, primary), **ratings(row),
        "ratingMethod": "statistical-formula-manual-review", "ratingConfidence": "low", "active": True,
        "playingStatus": "active" if current else "historical", "careerStartYear": min(years) - 1,
        "careerEndYear": None if current else max(years),
        "factVerification": {"status": "verified-secondary", "sourceType": "secondary-statistical",
            "source": row["source"], "verifiedFields": ["name", "teamId", "season", "positions"], "notes": []},
    }
    return result


def quotas():
    teams = list(audit.LINEAGE)
    return {team: 4 if index < 10 else 3 for index, team in enumerate(teams)}


def choose_current(by_name, existing):
    output = []
    for team, needed in quotas().items():
        used = {audit.norm(p["name"]) for p in existing if p["teamId"] == team}
        candidates = []
        for rows in by_name.values():
            season = [r for r in rows if r["seasonEndYear"] == 2026 and r["team"] in audit.LINEAGE[team]]
            if season and audit.norm(season[0]["name"]) not in used:
                selected = max(season, key=lambda r: (r["games"], r["minutes"], score(r)))
                candidates.append((selected, rows))
        candidates.sort(key=lambda item: (item[0]["games"], item[0]["minutes"], score(item[0]), item[0]["name"]), reverse=True)
        if len(candidates) < needed:
            raise RuntimeError(f"Not enough current candidates for {team}: {len(candidates)}")
        for offset, (selected, rows) in enumerate(candidates[:needed], 11):
            output.append(make_player("current", team, selected, rows, offset))
    return output


def choose_alltime(by_name, existing):
    output = []
    for team, needed in quotas().items():
        used = {audit.norm(p["name"]) for p in existing if p["teamId"] == team}
        candidates = []
        for rows in by_name.values():
            lineage = [r for r in rows if r["team"] in audit.LINEAGE[team]]
            if not lineage or audit.norm(lineage[0]["name"]) in used:
                continue
            selected = max(lineage, key=lambda r: (score(r), r["minutes"], r["games"], r["seasonEndYear"]))
            positions = career_positions(rows, selected["positions"][0] if selected["positions"] else "SF")
            if len(positions) > 1:
                candidates.append((selected, rows))
        candidates.sort(key=lambda item: (score(item[0]), item[0]["minutes"], item[0]["games"], item[0]["name"]), reverse=True)
        if len(candidates) < needed:
            raise RuntimeError(f"Not enough all-time multi-position candidates for {team}: {len(candidates)}")
        for offset, (selected, rows) in enumerate(candidates[:needed], 11):
            output.append(make_player("all-time", team, selected, rows, offset))
    return output


def reference_row(player, rows):
    selected = next(r for r in rows if r["name"] == player["name"] and r["season"] == player["season"] and r["team"] in audit.LINEAGE[player["teamId"]])
    return {"playerId": player["id"], "matchedName": selected["name"], "playerRef": selected["playerRef"],
            "selectedSeason": selected, "seasons": rows}


def meet_secondary_target(players, by_name, target=320):
    """Add only career-recorded secondary positions until the 40% floor is met."""
    multi = sum(len(player["positions"]) > 1 for player in players)
    for player in players:
        if multi >= target:
            break
        if len(player["positions"]) > 1:
            continue
        rows = by_name.get(audit.norm(player["name"]), [])
        proposed = career_positions(rows, player["positions"][0])
        if len(proposed) > 1:
            player["positions"] = proposed
            multi += 1
    return multi


def main():
    if not CSV.exists():
        raise SystemExit(f"Missing audited source dataset: {CSV}")
    by_name, years = audit.parse_csv_dataset(CSV)
    current = json.loads((DATA / "current-players.json").read_text())
    alltime = json.loads((DATA / "all-time-players.json").read_text())
    if len(current) == 300:
        current.extend(choose_current(by_name, current))
    if len(alltime) == 300:
        alltime.extend(choose_alltime(by_name, alltime))
    if (len(current), len(alltime)) != (400, 400):
        raise RuntimeError(f"Expected 400/400 records, got {len(current)}/{len(alltime)}")
    multi = meet_secondary_target(current + alltime, by_name)
    references = json.loads((DATA / "player-season-reference.json").read_text())
    known = {row["playerId"] for row in references["players"]}
    for player in current + alltime:
        if player["id"] not in known:
            references["players"].append(reference_row(player, by_name[audit.norm(player["name"])]))
    references["downloadedSeasonEndYears"] = years
    references["generated"] = "2026-07-21"
    (DATA / "current-players.json").write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n")
    (DATA / "all-time-players.json").write_text(json.dumps(alltime, indent=2, ensure_ascii=False) + "\n")
    (DATA / "player-season-reference.json").write_text(json.dumps(references, indent=2, ensure_ascii=False) + "\n")
    total = current + alltime
    if multi < 320:
        raise RuntimeError(f"Secondary-position target missed: {multi}/800")
    print(json.dumps({"current": len(current), "allTime": len(alltime), "multiPosition": multi, "percentage": multi / 8}, indent=2))


if __name__ == "__main__":
    main()
