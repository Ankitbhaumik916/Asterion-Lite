# Asterion Lite

An AI boss that learns how you play. Built for the Design of AI Products project: a three-lane
boss fight where an adaptive boss models the player's dodge habits and aims at their most likely
next move, compared against a scripted (and random) boss.

## Repository contents

| Path | Description |
|------|-------------|
| `asterion_lite/game.py` | Playable pygame prototype. Switch between scripted and adaptive boss live, toggle the 65% hit-rate governor, or let a bot test player play. |
| `asterion_lite/model.py` | Boss logic (scripted, random, adaptive learner) and the simulated test players. No pygame dependency. |
| `asterion_lite/simulate.py` | Experiment runner: 1000 sessions x 10 fights per boss, reports mean and 95% CI. `--csv` writes `results.csv`. |
| `asterion_lite/results.txt` | Latest experiment output (human readable). |
| `asterion_lite/results.csv` | Same results in CSV form. |
| `asterion_lite/requirements.txt` | Python dependencies (`pygame>=2.5`). |
| `asterion_lite/README.md` | Detailed setup, controls, and how the game works. |
| `asterion_sim.py` | Earlier standalone text simulation: scripted boss vs a first-order Markov adaptive boss. |
| `Asterion_Lite_Prototype.zip` | Packaged copy of the `asterion_lite/` prototype for submission. |

## Quick start

    cd asterion_lite
    pip install -r requirements.txt
    python game.py          # play it yourself
    python game.py --bot    # watch a test player vs the adaptive boss
    python simulate.py      # run the experiment

Python 3.9 or newer.

## Headline result

Against a habitual "left dodger" test player, the adaptive boss cuts the player win rate from
92.4% (scripted) to 58.4% and raises the boss hit rate from 34.9% to 49.7%. See
`asterion_lite/results.txt` for the full table.
