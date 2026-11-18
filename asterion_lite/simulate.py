"""
Headless experiment runner for Asterion Lite.

Plays many sessions of fights between a habit driven test player and each boss, then
prints the mean and a 95% confidence interval across sessions for every metric.
It uses the same boss code as the game (model.py).

    python simulate.py                       # 1000 sessions x 10 fights, both habits
    python simulate.py --habit "left dodger" --sessions 2000
    python simulate.py --no-governor         # see what the boss does without the cap
    python simulate.py --csv results.csv
"""
import argparse
import csv
import math
import random
import statistics

from model import (AdaptiveBoss, HabitBot, PlayerModel, RandomBoss, ScriptedBoss,
                   PLAYER_HP, PLAYER_HEALS, ROUNDS_PER_FIGHT, ROUND_SECONDS)


def play_fight(boss, bot, model=None):
    """One fight. Returns (player_won, hits_taken, rounds_played)."""
    boss.begin_fight()
    hp, heals, hits, prev = PLAYER_HP, PLAYER_HEALS, 0, None
    for r in range(1, ROUNDS_PER_FIGHT + 1):
        decision = boss.choose(prev)            # the boss only sees past rounds
        lane, healed = bot.act(hp, heals)
        if healed:
            hp, heals = hp + 1, heals - 1
        hit = decision.attack == lane
        boss.record_attack(hit)
        if model is not None:
            model.observe(prev, lane)
        prev = lane
        if hit:
            hits += 1
            hp -= 1
            if hp <= 0:
                return False, hits, r
    return True, hits, ROUNDS_PER_FIGHT


def run_session(kind, habit, fights, rng, cap):
    bot = HabitBot(rng, habit)
    if kind == "scripted":
        boss, model = ScriptedBoss(), None
    elif kind == "random":
        boss, model = RandomBoss(rng), None
    else:
        model = PlayerModel()
        boss = AdaptiveBoss(model, rng, cap=cap)
    wins = hits = rounds = 0
    for _ in range(fights):
        won, h, r = play_fight(boss, bot, model)
        wins += won
        hits += h
        rounds += r
        if model is not None:
            model.end_fight()
    return {
        "win_rate": 100.0 * wins / fights,
        "hits_per_fight": hits / fights,
        "boss_hit_rate": 100.0 * hits / rounds,
        "fight_seconds": rounds * ROUND_SECONDS / fights,
    }


def summarise(values):
    m = statistics.fmean(values)
    ci = 1.96 * statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return m, ci


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=1000)
    ap.add_argument("--fights", type=int, default=10)
    ap.add_argument("--habit", choices=list(HabitBot.PROFILES) + ["both"], default="both")
    ap.add_argument("--cap", type=float, default=0.65, help="governor cap on boss hit rate")
    ap.add_argument("--no-governor", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--csv", help="write the summary to a CSV file")
    a = ap.parse_args()

    cap = None if a.no_governor else a.cap
    habits = list(HabitBot.PROFILES) if a.habit == "both" else [a.habit]
    rows = []
    print(f"{a.sessions} sessions x {a.fights} fights. Mean and 95% CI across sessions. "
          f"Governor cap: {'off' if cap is None else cap}\n")
    for habit in habits:
        print(f"Test player habit: {habit}")
        print(f"{'boss':<10}{'player win %':>16}{'boss hit %':>16}{'hits taken':>16}{'fight length s':>18}")
        for kind in ("scripted", "random", "adaptive"):
            rng = random.Random(a.seed)
            res = [run_session(kind, habit, a.fights, rng, cap) for _ in range(a.sessions)]
            cells, rec = [], {"habit": habit, "boss": kind}
            for key in ("win_rate", "boss_hit_rate", "hits_per_fight", "fight_seconds"):
                m, ci = summarise([r[key] for r in res])
                cells.append(f"{m:8.1f} +/-{ci:4.1f}")
                rec[key], rec[key + "_ci"] = round(m, 2), round(ci, 2)
            rows.append(rec)
            print(f"{kind:<10}" + "".join(f"{c:>16}" if i < 3 else f"{c:>18}" for i, c in enumerate(cells)))
        print()
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print("wrote", a.csv)


if __name__ == "__main__":
    main()
