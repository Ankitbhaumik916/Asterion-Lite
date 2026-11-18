# Asterion Lite: an AI boss that learns how you play

Visual prototype and experiment runner for the Design of AI Products project.

## Setup and run

    pip install -r requirements.txt
    python game.py              # play it yourself (starts with the scripted boss)
    python game.py --bot        # test player at 12x speed, adaptive boss
    python simulate.py          # 1000 sessions x 10 fights, mean and 95% CI, writes nothing unless --csv

Python 3.9 or newer. `model.py` has no pygame dependency, so `simulate.py` runs anywhere.

## How the game works

Each round the boss winds up, then slams one of three lanes (LEFT, CENTER, RIGHT). You are in
one lane when it lands. The target lane is only shown for 0.2 seconds before impact, which is
less than a normal reaction time, so you cannot simply dodge what you see. You have to guess,
and a player with a habit gets caught. A fight is 10 attacks. You lose if you take 5 hits
(one heal per fight, bound to H, uses up that round).

The boss decides at the end of the wind up using only what it saw in earlier rounds. It never
reads your current lane. Events reach the model after impact.

## Keys

    LEFT / RIGHT or A / D   move lane          H   heal
    M or TAB                scripted / adaptive boss (live, applies from the next round)
    G                       governor cap on / off (cap is 65% hit rate)
    B                       test player: off, left dodger, cycler
    F                       speed 1x, 4x, 12x
    C                       make the boss forget what it learned
    R                       reset the stats       SPACE pause       ESC quit

## Suggested demo for the video (about 90 seconds)

1. Start `python game.py`. Stay in scripted mode and play about 20 seconds. Point at the fixed
   pattern in the right panel. Dodge on cue.
2. Press M for the adaptive boss. Dodge left most of the time. Watch "What the boss believes
   about you" turn into a clear lean to the left, and the boss start hitting you.
3. Optional: press B then F to let the test player play at speed and watch the results table
   fill in. Press G to show the governor cap, and C to wipe what the boss has learned.

## What maps to the report

| Report                         | Code                                               |
|--------------------------------|----------------------------------------------------|
| Frequency model                | `PlayerModel.freq`                                 |
| First order Markov chain       | `PlayerModel.trans`, blended in `predict`          |
| Laplace smoothing              | `PlayerModel.alpha`                                |
| Counter selection              | `AdaptiveBoss.choose` and the `HIT` table          |
| Recency weighting              | `PlayerModel.end_fight` (half life in fights)      |
| Exploration rate               | `AdaptiveBoss.exploration`                         |
| Difficulty governor            | `AdaptiveBoss.cap`                                 |
| Cold start fallback            | `PlayerModel.min_samples`, boss follows the script |
| Profile Store (local file)     | `python game.py --profile` saves asterion_profile.json |
| Scripted, random baselines     | `ScriptedBoss`, `RandomBoss`                       |
| Confidence intervals           | `simulate.py`                                      |

## Be honest about these in your submission

* The numbers in the old slides (98% to 57%, 6.7 to 10.4 hits) came from your earlier code.
  This is a new implementation. Run `python simulate.py` and use the numbers it prints for
  whatever you show alongside this code.
* This prototype does not model distance. The report mentions distance as context for the
  frequency model. Either reword that line or add a near and far row to the game.
* The "reaction delay" option from the report is represented by the 0.2 second tell.
* The test player is synthetic with fixed habits. Results show the learning works, not how
  real people will respond.
* The prototype is Python and Pygame. The product core in the report is C++ or Rust.
