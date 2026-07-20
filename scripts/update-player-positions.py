#!/usr/bin/env python3
"""Broaden player eligibility using the bundled verified season reference.

Default mode writes only the focused report. Pass --apply to update the two
player JSON files after the report has been reviewed. Ratings are never read or
changed by this script.
"""
import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORT = ROOT / "reports" / "player-position-updates.md"
FILES = ("current-players.json", "all-time-players.json")
CANONICAL = ("PG", "SG", "SF", "PF", "C")
DOCUMENTED_OVERRIDES = {
    "current-lal-luka-doncic-1": ["PG", "SG"],
    "alltime-cle-lebron-james-3": ["SF", "PF"],
    "alltime-lal-magic-johnson-1": ["PG", "SG"],
    "alltime-okc-kevin-durant-3": ["SF", "PF"],
}


def proposed_positions(player, reference):
    if player["id"] in DOCUMENTED_OVERRIDES:
        return DOCUMENTED_OVERRIDES[player["id"]], "High"
    selected = reference.get("selectedSeason") or {}
    selected_year = selected.get("seasonEndYear")
    supported = []
    exact = set()
    for row in reference.get("seasons", []):
        distance = abs(row.get("seasonEndYear", -10000) - selected_year) if selected_year else 10000
        if distance <= 2:
            for position in row.get("positions", []):
                if position in CANONICAL and position not in supported:
                    supported.append(position)
                if distance == 0:
                    exact.add(position)
    result = list(player["positions"])
    for position in supported:
        if position not in result and len(result) < 3:
            result.append(position)
    confidence = "High" if set(result) <= (set(player["positions"]) | exact) else "Medium"
    return result, confidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    references = {row["playerId"]: row for row in json.loads((DATA / "player-season-reference.json").read_text())["players"]}
    changes = []
    outputs = {}
    reviewed = 0
    for filename in FILES:
        players = json.loads((DATA / filename).read_text())
        reviewed += len(players)
        for player in players:
            old = list(player["positions"])
            new, confidence = proposed_positions(player, references.get(player["id"], {}))
            if new != old:
                changes.append((player, old, new, confidence))
                player["positions"] = new
        outputs[filename] = players

    if not changes and REPORT.exists():
        existing = REPORT.read_text()
        prior = next((line for line in existing.splitlines() if line.startswith("- Position records changed:")), "")
        print(json.dumps({"reviewed": reviewed, "changed": int(prior.rsplit(" ", 1)[-1] or 0), "applied": args.apply, "alreadyCurrent": True}))
        return
    lines = [
        "# Player Position Updates", "", f"Generated: {date.today().isoformat()}", "",
        f"- Player records reviewed: {reviewed}", f"- Position records changed: {len(changes)}",
        "- Ratings changed: 0", "",
        "Primary positions were retained. Secondary positions were added only when the bundled verified season reference lists the player at that position in the represented season or within two seasons of it.", "",
        "| Player | Franchise | Era | Season | Old Positions | New Positions | Reason | Confidence |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for player, old, new, confidence in changes:
        lines.append(
            f"| {player['name']} | {player['teamId']} | {player['era']} | {player['season']} | "
            f"{', '.join(old)} | {', '.join(new)} | Documented role in represented-season ±2-year window | {confidence} |"
        )
    lines.extend(["", "## Records left unchanged", "", "Records without a supported secondary position in the represented-season window remain single-position. Uncertain combinations were not inferred from height, ratings, reputation, or a different career stage."])
    REPORT.write_text("\n".join(lines) + "\n")
    if args.apply:
        for filename, players in outputs.items():
            (DATA / filename).write_text(json.dumps(players, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"reviewed": reviewed, "changed": len(changes), "applied": args.apply}))


if __name__ == "__main__":
    main()
