# Basketball Legends

Basketball Legends is a zero-build browser draft, 82-game season, and playoff simulator. One to eight people spin franchise and era wheels, browse complete franchise-era player pools, then drag a player into an eligible roster position. Those teams join all 30 NBA franchises for a complete regular season and optional postseason.

Player eligibility now follows the verified season-table position rather than synthetic multi-position assignments. The validator warns when a small ten-player franchise pool lacks a position; it does not invent eligibility to silence the warning. Historically impossible pre-expansion combinations remain visible but cannot be selected.

## Implementation plan

1. **Foundation:** semantic application shell, responsive CSS, JSON loading and validation, central state, persistence, internally keyed randomness, and phase-safe navigation.
2. **Draft and lineup:** setup forms, accessible animated wheels, searchable player pools, duplicate rules, five unrestricted picks, eligible-position assignment, and in-draft lineup movement.
3. **League:** position-aware custom ratings, alternating conference assignment, deterministic 82-game schedule generation, and strict validation.
4. **Season:** deterministic per-game score simulation, overtime, live standings and streaks, game/day/full-season controls, speed and pause support.
5. **Playoffs:** top-eight qualification, shared fixed bracket, best-of-seven series, round controls, Finals, and champion presentation.
6. **Results and quality:** regular-season and playoff reports, copy and restart actions, Python data tooling, browser tests, responsive and reduced-motion checks.

## Features

- One to eight custom expansion teams and a deterministic position-valid draft
- In-draft drag-and-swap lineup controls for every custom team
- Eligible-position swaps with drag and drop or keyboard-accessible position controls
- Atomic swap validation, undo, reset to drafted positions, and pre-season editing
- Lineups lock when the regular season begins
- Complete 82-game regular season with live conference standings
- Top-eight playoff qualification in each conference
- Optional postseason entry and one shared league bracket
- Conference First Round, Semifinals, Conference Finals, and NBA Finals
- Best-of-seven series with game-by-game results and `2-2-1-1-1` home court
- One current-round button per active custom team; the selected team becomes the presentation focus while the entire shared round resolves once
- Conference champions, NBA champion, and championship featured player for custom champions
- Regular-season and playoff save/resume, including safe per-game playoff checkpoints

## Game flow

```text
Welcome → User setup → Spin franchise and era → Choose any player
→ Assign an eligible open position → Repeat for five picks
→ Next user drafts → Review all teams → 82-game regular season
→ Postseason qualification → Optional playoff entry → First Round
→ Conference Semifinals → Conference Finals → NBA Finals
→ Champion and final results
```

## Run locally

JSON is loaded with `fetch`, so do not open `index.html` with `file://`.

```bash
cd basketball-legends
python -m http.server 8000
```

Open `http://localhost:8000`. No package manager, build tool, framework, backend, or internet connection is needed.

## Run tests

With the local server running, open `http://localhost:8000/tests/test-runner.html`. The page reports passed and failed assertions. Run the data validator and audit regression suite with:

```bash
python scripts/validate-data.py
python -m unittest tests/test_player_audit.py
```

## Project structure

- `index.html` – semantic application shell
- `css/` – reset, tokens, layout, components, and responsive rules
- `js/` – isolated state, draft and lineup validation/UI, ratings, scheduling, regular-season simulation, playoff qualification/bracket/series/UI/results, audio, and persistence modules
- `data/` – 30 franchises and 600 local player records (300 current and 300 all-time)
- `scripts/` – data validation and position-aware rating generation
- `tests/` – package-free browser test runner

## Data maintenance

### Add a team

Add a unique record to `data/teams.json` with `id`, `name`, `city`, `conference` (`East` or `West`), `division`, integer `baseOverall`, `baseOffense`, `baseDefense`, and `pace` ratings from 40–99, `active`, and a `theme` containing accessible primary and secondary colours. Version 1 intentionally requires exactly 30 active base teams.

### Add a current or all-time player

Add the record to the matching file. Required schema:

```json
{
  "id": "current-den-nikola-jokic",
  "name": "Nikola Jokic",
  "teamId": "DEN",
  "era": "current",
  "season": "2025-26",
  "positions": ["C"],
  "overall": 98,
  "offense": 99,
  "defense": 88,
  "shooting": 91,
  "playmaking": 99,
  "rebounding": 96,
  "athleticism": 76,
  "ratingMethod": "legacy-prototype-manual-review",
  "ratingConfidence": "low",
  "playingStatus": "active",
  "careerStartYear": 2015,
  "careerEndYear": null,
  "factVerification": {
    "status": "verified-secondary",
    "sourceType": "secondary-statistical",
    "source": "https://www.basketball-reference.com/leagues/NBA_2026_per_game.html",
    "verifiedFields": ["name", "teamId", "season", "positions"],
    "notes": []
  },
  "active": true
}
```

IDs must be globally unique. Ratings are custom—not official game ratings—and must be integers from 40–99. The bundled legacy rating numbers are preserved for game compatibility but are explicitly low-confidence and queued for expert review; the audit does not claim they are official or statistically verified.

### Rating generation and overrides

`scripts/generate-ratings.py INPUT OUTPUT [--config FILE] [--overrides FILE] [--report FILE]` consumes normalized statistics, standardizes position/season cohorts, and uses the checked-in weights in `scripts/config/rating-weights.json`. Overrides require fields, a reason, and a source. Missing required statistics are reported, never invented.

### Fact audit and provenance

The production files contain 300 current and 300 all-time records. `scripts/audit-player-data.py` is report-only by default; `--apply` archives the pre-audit files, applies only unambiguous season-table corrections, writes `data/player-season-reference.json`, and regenerates the reports in `reports/`. The reference covers 1947–2026 NBA/BAA records and relevant ABA predecessor seasons. Current means 2025–26 regular-season participation. A player absent for the full season or listed for a different team is retained only as `manual-review-required`, never silently declared verified.

The all-time representative season is the highest season within that franchise lineage by a documented per-game productivity sum (points + rebounds + assists + steals + blocks), then minutes, games, and recency. This is a reproducible representative-season rule, not a claim that the selected year is an official “peak season.” Franchise lineage is explicit in the audit script. Examples include Seattle → Oklahoma City, New Jersey → Brooklyn, and Minneapolis → Los Angeles.

Source hierarchy: official NBA statistics are preferred; Basketball Reference season tables are the statistical reference used for this pass. Common-name aliases are documented with source and reason in `scripts/config/player-fact-overrides.json`. Facts lacking a unique match remain in `reports/manual-review-required.md`.

## Position and lineup rules

Every custom team always finishes with exactly one PG, SG, SF, PF, and C, but those slots may be filled in any order. For each pick, spin a franchise and era, then view all matching available players regardless of position. Drafting is a two-click action: click or tap anywhere on a player card, then click a highlighted eligible empty position in the right-hand lineup. The position click immediately places the player and begins the next pick. There is no separate Select button, Confirm Pick button, pop-up, or confirmation dialog. Search, alphabetical/overall sorting, and an optional position filter remain available.

Position arrays contain the primary position first and credible secondary positions where the represented season supports them. Many combo guards, swingmen, forwards, and mobile bigs can fill two positions, while traditional specialists remain restricted to one. A small number of unusual players have three positions. Eligibility comes only from the stored position list and may differ between franchise-season versions of the same player. The focused audit and every change are recorded in `reports/player-position-updates.md`.

Players with no currently open eligible position remain visible but unavailable until the lineup is rearranged. While choosing a new player, occupied and ineligible slots are dimmed and cannot receive that player. Clicking an invalid slot leaves the selection intact. After placement, drafted players can still be dragged to an eligible empty slot or dropped onto an occupied slot to request an atomic swap. The swap succeeds only when both players are eligible for their new positions, and an invalid swap changes neither player. Native position selectors and Move controls provide the same behavior for keyboard, touch, and assistive technology.

Roster entries store `draftPickNumber`, `initialAssignedPosition`, and the current `assignedPosition` separately. Selection order never affects ratings; only the final assigned lineup does. The draft completes only after exactly five unique players legally occupy PG, SG, SF, PF, and C. Version 1 has no bench players.

## Saves

The app autosaves in-progress franchise, era, and player selections, every confirmed pick, every successful move or swap, completed lineups, schedule creation, simulation batches, postseason qualification, playoff entry, every playoff game, completed series and rounds, and the champion in browser `localStorage`. Schema `5.0.0` stores pick order, initial assignment, current assignment, and the private internal `gameId`. Older `draftedForPosition` records migrate to `initialAssignedPosition`, while an existing `assignedPosition` is preserved. Completed games and rounds cannot be regenerated, and a mid-round resume continues from the next unplayed game. Corrupt saves are ignored safely. Save data stays on the current device/browser.

Every **Start New Game** creates a fresh `gameId` with `crypto.randomUUID()` when available. The identifier is never shown or managed by players. It derives stable event keys for draft spins, schedule generation, each regular-season game, each playoff game, overtime, and random standings tiebreakers. This makes every new game newly random while ensuring reloads, animation speed, re-rendering, save/resume timing, and the selected playoff presentation button cannot change an outcome. **Restart Season With Same Draft** retains the drafted teams but creates a new `gameId` and a newly random schedule and season. **Resume Saved Game** retains the saved `gameId`.

## Playoff rules

The top eight teams in each conference qualify directly; Version 1 has no Play-In Tournament. First-round matchups are 1–8, 4–5, 2–7, and 3–6. Winners follow a fixed bracket with no reseeding: 1/8 meets 4/5, and 2/7 meets 3/6.

Every series is best-of-seven and stops immediately when a team reaches four wins. The higher seed hosts Games 1, 2, 5, and 7; the lower seed hosts Games 3, 4, and 6. In the Finals, better regular-season record determines home court, followed by the deterministic existing seed/tiebreak ordering.

Each active custom team receives a button for the current round. Clicking one button features that team’s series, but resolves every series in the shared round to preserve bracket integrity. The round is simulated only once; all other custom-team cards update to advanced, eliminated, or round complete automatically.

Playoff games reuse the regular game engine with named form, home-court, score, and rating-impact settings. Rating gaps are intentionally compressed during the postseason so elite teams remain favorites without making seven-game upsets vanishingly rare. Every playoff match has its own key derived from the internal `gameId`, series ID, and game number, so button choice, animation speed, and save/resume timing cannot alter results.

## Playoff testing

The browser runner covers qualification, 1–8/4–5/2–7/3–6 pairings, fixed advancement, best-of-seven stopping, home-court order, shared-round protection, deterministic reproduction, and storage migration. Open `tests/test-runner.html` through the local server.

## Lineup testing and accessibility

The test runner covers unrestricted pick orders, card selection and confirmation, one-to-three-position validation, all-position pools, filtering, disabled no-fit players, five-position validation, missing and duplicate positions, valid and invalid atomic swaps, empty-slot moves, separate initial/assigned positions, rating recalculation, save migration, and lineup locking. Available-player cards are semantic buttons for mouse, keyboard, and touch use; only drafted lineup entries are draggable. Native position selectors and buttons provide the same lineup-movement workflow for keyboard-only, touch, and assistive-technology users, with results announced through an `aria-live` status region.

## Version 1 limitations

The game has ten current and ten all-time records per franchise rather than complete rosters. The 2025–26 current snapshot includes explicit manual-review records for season-long absences and team conflicts. Narrow pools can lack a verified eligible position; warnings are preferable to fabricated multi-position labels. Base franchises use team-level ratings. Playoffs have no Play-In Tournament, injuries, fatigue, bench rotations, individual box scores, player-level Finals MVP statistics, or reseeding. The game also omits trades, salary caps, accounts, online multiplayer, official logos/photos, and official 2K ratings. Audio uses generated Web Audio tones and may require a first interaction.

The module boundaries and data schemas leave room for Play-In qualification, benches, injuries, and richer player attributes without replacing the draft, schedule, or simulation engines.

## Future ideas

Play-In Tournament, player playoff statistics, injuries and fatigue, bench rotations, series momentum, advanced home-court modelling, playoff history, shareable bracket exports, season awards, and optional shared multiplayer rooms.
