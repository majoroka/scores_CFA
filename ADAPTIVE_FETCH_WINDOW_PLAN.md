# Adaptive Fetch Window Plan

## Implementation Status

### Already implemented

The following parts of this plan are already in place:

- `plan_fetchers.py` now computes:
  - `awaiting_window`
  - `result_chase`
  - `historical_backfill`
  - `missing_payload`
- the planner now emits:
  - `nextScheduledKickoff`
  - `firstResultFetchAt`
  - `lastMeaningfulFetchAt`
  - `nextRecommendedFetchAt`
  - `technicalState`
  - `technicalBackoffLevel`
  - `dueNow`
- the follow-up workflow now waits until `nextRecommendedFetchAt`
- the follow-up workflow no longer depends only on fixed retry waves
- historical polling now respects the `6h` recovery rhythm

### Still pending

The following parts are still not fully implemented:

- explicit technical error typing inside `run_fetchers.py`
  - `403`
  - `429`
  - `timeout`
  - `network_error`
- persistent technical failure memory between runs
- finer workflow summaries based on technical error class
- possible refinement of planner heuristics after observing real runs

## Goal

Make result polling more reliable and less noisy by separating:

1. result-chasing logic based on match date/time
2. technical backoff logic based on FPF failures or blocking

The target outcome is:

- fewer unnecessary requests to the FPF
- more predictable retries when results are still legitimately pending
- slower, safer retry cadence when the FPF is blocking or unstable


## Current Problem

The existing workflow retries based mainly on:

- selected competitions in the planner
- fixed retry waves
- degraded/failure outcomes

This works, but it mixes two different scenarios:

1. the score is not yet published, which is a normal business-state condition
2. the FPF is failing technically, which is an infrastructure condition

Those two cases should not share the same retry cadence.


## Proposed Model

Each competition should be evaluated with two independent dimensions:

1. **functional state**
2. **technical state**


## Functional State

### `idle`

No relevant pending matches in the active windows.

Behavior:

- do not run fetch


### `awaiting_window`

There are matches scheduled for today, but the expected result window has not started yet.

Behavior:

- no aggressive polling
- optional single lightweight verification of schedule integrity


### `result_chase`

At least one match is now old enough that a score is reasonably expected.

Definition:

- match date is today
- or match date is within the active recent window
- and current time is at least **2 hours after the scheduled kickoff**

Behavior:

1. perform the first real score fetch at `kickoff + 2h`
2. if all scores are available, stop
3. if scores are still missing:
   - retry every `15 minutes`
   - maximum `4` retry waves
4. if scores still remain missing after those four waves:
   - retry every `1 hour`
   - until local midnight


### `historical_backfill`

The match day has passed, but one or more historical matches still have missing scores.

Behavior:

- retry every `6 hours`
- stop when all pending historical scores are resolved
- apply a maximum historical lookback window, for example `14 days`


## Technical State

This state is independent from the functional state.

### `healthy`

The FPF responded normally and produced usable content.

Behavior:

- follow the functional cadence only


### `blocked`

The FPF returned:

- `403`
- `429`
- blocking page
- rate-limit behavior

Behavior:

- do not continue with aggressive retry cadence
- apply technical backoff:
  - after first block: retry in `10 minutes`
  - after second block: retry in `20 minutes`
  - after third or later block: retry in `40 minutes`


### `network_error`

Transport-level failure:

- timeout
- DNS
- connection reset
- incomplete response

Behavior:

- same technical backoff:
  - `10 minutes`
  - `20 minutes`
  - `40 minutes`


## Priority Rules

The scheduler should decide next execution time using these rules:

1. if all relevant matches have results:
   - stop
2. if technical state is `blocked` or `network_error`:
   - follow technical backoff
3. else if functional state is `result_chase`:
   - follow `15-minute` and then `hourly` schedule
4. else if functional state is `historical_backfill`:
   - follow `6-hour` schedule
5. else:
   - no fetch


## Match-Time Logic

For each competition, compute the earliest next useful polling moment from its scheduled matches.

For a match with kickoff `T0`:

- before `T0 + 2h`:
  - do not score-poll aggressively
- at `T0 + 2h`:
  - first meaningful fetch

If a competition has multiple matches on the same day:

- use the earliest unresolved match whose polling window is already open
- continue until all same-day unresolved matches are filled


## Suggested Data Model Additions

The planner should record, per competition:

- `nextScheduledKickoff`
- `firstResultFetchAt`
- `lastMeaningfulFetchAt`
- `lastTechnicalFailureAt`
- `technicalBackoffLevel`
- `lastKnownPendingMatchCount`
- `nextRecommendedFetchAt`

Optional but useful:

- `pendingPastMatches`
- `pendingTodayMatches`
- `pendingHistoricalMatches`


## Workflow Changes

### 1. Planning phase

`plan_fetchers.py` should evolve to compute:

- functional state
- technical state
- next recommended fetch time

It should stop thinking only in terms of:

- `active_pending`
- `historical_backfill`

and start computing actual timing windows.


### 2. Primary sync workflow

The main sync should:

- run when the planner says at least one competition is due now
- skip fetch entirely when nothing is due


### 3. Follow-up retry workflow

The follow-up workflow should:

- stop using a static global delay list as the only policy
- instead read the planner output
- only run fetchers whose `nextRecommendedFetchAt <= now`


### 4. Technical error propagation

`run_fetchers.py` and/or `competition_sync.py` should classify failures into:

- `blocked`
- `network_error`
- `fragment_missing`
- `partial_success`

That classification must be written into the fetch report so the planner can choose the right backoff.


## Recommended Retry Timeline

### For normal missing results

- `T0 + 2h`
- `+15m`
- `+30m`
- `+45m`
- `+60m`
- then `+1h` until `00:00`
- then `+6h` until resolved


### For technical blocking/error

- `+10m`
- `+20m`
- `+40m`
- then hold at `+40m` until the technical state clears


## Why This Is Better

This model:

- reduces unnecessary early polling
- avoids hammering the FPF during blocking periods
- keeps pressure on unresolved recent matches
- still allows slow historical recovery
- separates business latency from technical failure


## Recommended Implementation Order

1. extend planner output with match-window timing
2. classify technical failure types in fetch reports
3. teach follow-up workflow to honor `nextRecommendedFetchAt`
4. remove fixed retry-wave logic once the time-based planner is trusted
5. expose timing/debug fields in `status.json` or admin diagnostics if needed


## Success Criteria

The implementation is successful when:

1. competitions with no due matches are skipped entirely
2. same-day results begin polling only after `kickoff + 2h`
3. FPF blocking no longer triggers aggressive repeated retries
4. recent unresolved scores are still chased automatically
5. historical missing scores continue recovering in the background
6. the workflow history becomes more predictable and easier to interpret


## Immediate Next Steps

1. publish the current implementation
2. observe one or two real workflow cycles
3. if needed, refine technical error classification in `run_fetchers.py`:
   - `403`
   - `429`
   - `timeout`
   - `network_error`
