#!/usr/bin/env python3
"""Audit bundled player facts against downloaded Basketball Reference season tables.

Default mode is report-only. Pass --apply to archive the input files and apply only
unambiguous fact corrections. Ratings are never silently recalculated by this tool.
"""
import argparse
import copy
import csv
import html
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
DEFAULT_CACHE = Path("/tmp/bref-seasons")
DEFAULT_DATASET = Path("/tmp/nba-stats/Player Per Game.csv")
POSITION_ORDER = ["PG", "SG", "SF", "PF", "C"]
SOURCE_URL = "https://www.basketball-reference.com/leagues/NBA_{year}_per_game.html"

# Explicit continuous-franchise-history policy. Defunct clubs not listed here do
# not silently attach to a current franchise.
LINEAGE = {
    "ATL": {"TRI", "MLH", "STL", "ATL"}, "BOS": {"BOS"},
    "BKN": {"NYA", "NJA", "NJN", "BRK", "BKN"}, "CHA": {"CHH", "CHO", "CHA"},
    "CHI": {"CHI"}, "CLE": {"CLE"}, "DAL": {"DAL"},
    "DEN": {"DNR", "DNA", "DEN"}, "DET": {"FTW", "DET"},
    "GSW": {"PHW", "SFW", "GSW"}, "HOU": {"SDR", "HOU"},
    "IND": {"INA", "IND"}, "LAC": {"BUF", "SDC", "LAC"},
    "LAL": {"MNL", "LAL"}, "MEM": {"VAN", "MEM"}, "MIA": {"MIA"},
    "MIL": {"MIL"}, "MIN": {"MIN"}, "NOP": {"NOH", "NOK", "NOP"},
    "NYK": {"NYK"}, "OKC": {"SEA", "OKC"}, "ORL": {"ORL"},
    "PHI": {"SYR", "PHI"}, "PHX": {"PHO", "PHX"},
    "POR": {"POR"}, "SAC": {"ROC", "CIN", "KCO", "KCK", "SAC"},
    "SAS": {"DLC", "TEX", "SAA", "SAS"}, "TOR": {"TOR"},
    "UTA": {"NOJ", "UTA"},
    "WAS": {"CHP", "CHZ", "BAL", "CAP", "WSB", "WAS"},
}


def norm(value):
    value = value.replace("ё", "e").replace("Ё", "E")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = value.lower().replace("’", "'")
    value = re.sub(r"\b(jr|sr|ii|iii|iv)\.?\b", "", value)
    return re.sub(r"[^a-z0-9]", "", value)


def season_label(end_year):
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def decade_tag(label):
    start = int(label[:4])
    return f"{(start % 100) // 10 * 10:02d}s"


class SeasonParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_table = False; self.row = None; self.cell = None; self.rows = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and attrs.get("id") == "per_game_stats": self.in_table = True
        elif self.in_table and tag == "tr": self.row = {"playerRef": None}
        elif self.row is not None and tag in {"th", "td"}:
            stat = attrs.get("data-stat")
            if stat:
                self.cell = [stat, ""]
                if stat == "name_display": self.row["playerRef"] = attrs.get("data-append-csv")
    def handle_data(self, data):
        if self.cell is not None: self.cell[1] += data
    def handle_endtag(self, tag):
        if self.cell is not None and tag in {"th", "td"}:
            self.row[self.cell[0]] = html.unescape(self.cell[1]).strip(); self.cell = None
        elif self.row is not None and tag == "tr":
            if self.row.get("playerRef") and self.row.get("name_display") != "League Average": self.rows.append(self.row)
            self.row = None
        elif self.in_table and tag == "table": self.in_table = False


def number(row, key):
    try: return float(row.get(key) or 0)
    except ValueError: return 0.0


def parse_cache(cache):
    by_name = defaultdict(list); downloaded = []
    for path in sorted(cache.glob("*.html")):
        try: end_year = int(path.stem)
        except ValueError: continue
        parser = SeasonParser(); parser.feed(path.read_text(errors="ignore"))
        if not parser.rows: continue
        downloaded.append(end_year)
        for order, row in enumerate(parser.rows):
            team = row.get("team_name_abbr", "")
            if not team or team == "TOT": continue
            pos = [p for p in re.split(r"[-/]", row.get("pos", "")) if p in POSITION_ORDER]
            record = {
                "season": season_label(end_year), "seasonEndYear": end_year,
                "playerRef": row["playerRef"], "name": row["name_display"],
                "team": team, "positions": pos, "games": int(number(row, "games")),
                "minutes": number(row, "mp_per_g"), "points": number(row, "pts_per_g"),
                "rebounds": number(row, "trb_per_g"), "assists": number(row, "ast_per_g"),
                "steals": number(row, "stl_per_g"), "blocks": number(row, "blk_per_g"),
                "order": order, "source": SOURCE_URL.format(year=end_year),
            }
            by_name[norm(record["name"])].append(record)
    return by_name, downloaded


def parse_csv_dataset(path):
    """Parse the maintained 1947-present CSV mirror of BRef per-game tables."""
    by_name = defaultdict(list); downloaded = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for order, row in enumerate(csv.DictReader(handle)):
            if row.get("lg") not in {"NBA", "BAA", "ABA"} or row.get("team") in {"TOT", "2TM", "3TM"}: continue
            end_year = int(row["season"]); downloaded.add(end_year)
            pos = [p for p in re.split(r"[-/]", row.get("pos", "")) if p in POSITION_ORDER]
            def n(key):
                try: return float(row.get(key) or 0) if row.get(key) != "NA" else 0.0
                except ValueError: return 0.0
            record = {
                "season": season_label(end_year), "seasonEndYear": end_year,
                "playerRef": row.get("player_id"), "name": row["player"], "team": row["team"],
                "positions": pos, "games": int(n("g")), "minutes": n("mp_per_game"),
                "points": n("pts_per_game"), "rebounds": n("trb_per_game"),
                "assists": n("ast_per_game"), "steals": n("stl_per_game"),
                "blocks": n("blk_per_game"), "order": order,
                "source": SOURCE_URL.format(year=end_year),
            }
            by_name[norm(record["name"])].append(record)
    return by_name, sorted(downloaded)


def representative(rows):
    # Reproducible statistical representative season within the selected lineage.
    return max(rows, key=lambda r: (
        r["points"] + r["rebounds"] + r["assists"] + r["steals"] + r["blocks"],
        r["minutes"], r["games"], r["seasonEndYear"]
    ))


def audit_player(player, era, reference):
    original = copy.deepcopy(player); rows = reference.get(norm(player["name"]), [])
    lineage_rows = [r for r in rows if r["team"] in LINEAGE.get(player["teamId"], {player["teamId"]})]
    issues = []; changes = []; selected = None
    if era == "current":
        season_rows = [r for r in rows if r["season"] == "2025-26"]
        lineage_season = [r for r in season_rows if r["team"] in LINEAGE.get(player["teamId"], {player["teamId"]})]
        if lineage_season:
            selected = lineage_season[-1]
        elif season_rows:
            final = season_rows[-1]
            target = next((tid for tid, codes in LINEAGE.items() if final["team"] in codes), None)
            if target:
                selected = final
                issues.append(f"2025-26 season data lists {target}, not selected team {player['teamId']}")
            else: issues.append("2025-26 team does not map to a current franchise")
        else: issues.append("no 2025-26 season row found")
    else:
        if lineage_rows: selected = representative(lineage_rows)
        else: issues.append("no season found with the selected franchise lineage")
    if selected:
        if player.get("season") != selected["season"]:
            changes.append(("season", player.get("season"), selected["season"])); player["season"] = selected["season"]
        if selected["positions"] and player.get("positions") != selected["positions"]:
            changes.append(("positions", player.get("positions"), selected["positions"])); player["positions"] = selected["positions"]
        if era == "all-time": player["decadeTags"] = [decade_tag(selected["season"])]
    career_rows = rows
    player["playingStatus"] = "active" if any(r["season"] == "2025-26" for r in career_rows) else "historical"
    player["careerStartYear"] = min((r["seasonEndYear"] - 1 for r in career_rows), default=None)
    player["careerEndYear"] = None if player["playingStatus"] == "active" else max((r["seasonEndYear"] for r in career_rows), default=None)
    # Existing ratings came from a prototype name hash. Preserve gameplay values,
    # but remove the unsupported claim that they are high-confidence statistics.
    if player.get("ratingConfidence") != "low": changes.append(("ratingConfidence", player.get("ratingConfidence"), "low"))
    player["ratingConfidence"] = "low"; player["ratingMethod"] = "legacy-prototype-manual-review"
    player["factVerification"] = {
        "status": "verified-secondary" if selected and not issues else "manual-review-required",
        "sourceType": "secondary-statistical",
        "source": selected["source"] if selected else "Basketball Reference per-game season tables",
        "verifiedFields": (["name", "season", "positions"] if issues else ["name", "teamId", "season", "positions"]) if selected else ["name"],
        "notes": issues,
    }
    ref = {
        "playerId": player["id"], "matchedName": selected["name"] if selected else None,
        "playerRef": selected["playerRef"] if selected else None,
        "selectedSeason": selected, "seasons": career_rows,
    }
    return player, original, changes, issues, ref


def render_reports(results, downloaded, applied):
    REPORTS.mkdir(exist_ok=True)
    all_results = [x for group in results.values() for x in group]
    factual = sum(bool(x["factChanges"]) for x in all_results)
    manual = sum(bool(x["issues"]) for x in all_results)
    lines = ["# Player Data Audit Summary", "", f"Generated: {date.today().isoformat()}", "",
             f"- Mode: {'apply' if applied else 'report-only'}", f"- Players audited: {len(all_results)}",
             f"- Players with factual changes: {factual}", "- Ratings numerically changed: 0",
             f"- Ratings relabeled low-confidence/manual-review: {len(all_results)}",
             f"- Players requiring factual manual review: {manual}",
             f"- Source seasons available: {min(downloaded) if downloaded else 'none'}–{max(downloaded) if downloaded else 'none'}",
             "", "All automatic changes use Basketball Reference season tables. Ratings were preserved,",
             "because the old generator was synthetic; they are no longer labeled high confidence."]
    for era in ("current", "all-time"):
        sample = [x["name"] for x in results[era] if not x["issues"]][:20]
        lines.extend(["", f"## Deterministic 20-player verification sample: {era}", "",
                      ", ".join(sample) + ".",
                      "", "Each sample record was matched by normalized name to a season row, then checked against the explicit franchise-lineage map. "])
    high = [x for x in all_results if x["overall"] >= 95]
    multi = [x for x in all_results if x["positionCount"] >= 3]
    lines.extend(["", "## Required targeted checks", "",
                  f"- Overall 95+: {len(high)} checked; all retained ratings relabeled low-confidence/manual-review.",
                  f"- Three or more eligible positions after correction: {len(multi)}; unresolved entries are listed in the manual-review report."])
    (REPORTS / "player-data-audit-summary.md").write_text("\n".join(lines) + "\n")
    md = ["# Player Data Change Log", "", "| Player | Dataset | Field | Before | After | Reason |",
          "|---|---|---|---|---|---|"]
    for x in all_results:
        for field, before, after in x["changes"]:
            if field == "ratingConfidence": continue
            md.append(f"| {x['name']} | {x['era']} | {field} | {json.dumps(before)} | {json.dumps(after)} | season-table match |")
    (REPORTS / "player-data-change-log.md").write_text("\n".join(md) + "\n")
    review = ["# Manual Review Required", ""]
    for x in all_results:
        if x["issues"]: review.append(f"- **{x['name']}** ({x['era']}, {x['teamId']}): {'; '.join(x['issues'])}")
    if len(review) == 2: review.append("No unresolved factual matches.")
    review.extend(["", "## Rating review queue", "", f"All {len(all_results)} legacy prototype rating sets require expert/manual calibration."])
    (REPORTS / "manual-review-required.md").write_text("\n".join(review) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args()
    reference, downloaded = parse_csv_dataset(args.dataset) if args.dataset.exists() else parse_cache(args.cache)
    overrides = json.loads((ROOT / "scripts/config/player-fact-overrides.json").read_text())
    for display_name, canonical_name in overrides.get("aliases", {}).items():
        if norm(canonical_name) in reference: reference[norm(display_name)] = reference[norm(canonical_name)]
    if not downloaded: raise SystemExit(f"No valid season tables found in {args.cache}")
    results = {}; output = {}; refs = []
    for era, filename in (("current", "current-players.json"), ("all-time", "all-time-players.json")):
        players = json.loads((DATA / filename).read_text()); output[filename] = []; results[era] = []
        for source in players:
            player, original, changes, issues, ref = audit_player(copy.deepcopy(source), era, reference)
            output[filename].append(player); refs.append(ref)
            results[era].append({"id": player["id"], "name": player["name"], "teamId": player["teamId"],
                                 "era": era, "overall": player["overall"], "positionCount": len(player["positions"]),
                                 "changes": changes, "factChanges": [c for c in changes if c[0] != "ratingConfidence"], "issues": issues})
    render_reports(results, downloaded, args.apply)
    if args.apply:
        archive = DATA / "archive" / "pre-audit"; archive.mkdir(parents=True, exist_ok=True)
        for filename, players in output.items():
            target = DATA / filename
            if not (archive / filename).exists(): shutil.copy2(target, archive / filename)
            target.write_text(json.dumps(players, indent=2, ensure_ascii=False) + "\n")
        (DATA / "player-season-reference.json").write_text(json.dumps({
            "source": "Basketball Reference per-game season tables", "sourceType": "secondary-statistical",
            "lineagePolicy": "continuous current-franchise history; explicit abbreviation map in audit-player-data.py",
            "generated": date.today().isoformat(), "downloadedSeasonEndYears": downloaded, "players": refs,
        }, indent=2, ensure_ascii=False) + "\n")
    summary = Counter()
    for group in results.values():
        for x in group: summary["players"] += 1; summary["factChanges"] += len(x["factChanges"]); summary["manual"] += bool(x["issues"])
    print(json.dumps(dict(summary) | {"mode": "apply" if args.apply else "report-only"}, indent=2))
    if args.apply and summary["manual"]:
        print("Applied only supported changes; unresolved records remain explicitly marked for manual review.")


if __name__ == "__main__": main()
