"""Asterion Lite: scripted boss vs adaptive boss, simulated test player.

Each turn the boss attacks one lane (LEFT, RIGHT, BACK) and the player dodges
into one lane. If the boss aimed where the player dodged, the player is hit.
The test player has human-like habits: a preferred dodge and a tendency to
repeat their last move. The adaptive boss learns a first order Markov model of
the player's dodges and aims at the most likely next move. The model persists
across fights, like a boss that remembers past battles.
"""
import random

MOVES = ["LEFT", "RIGHT", "BACK"]
BASE = [0.55, 0.28, 0.17]      # preferred dodge habits
REPEAT = 0.35                  # chance to repeat the last dodge
PLAYER_HP, BOSS_HP = 12, 10
PLAYER_HIT_CHANCE = 0.5        # player lands a hit on the boss per turn
SECONDS_PER_TURN = 1.5


def player_move(last, rng):
    if last is not None and rng.random() < REPEAT:
        return last
    return rng.choices(range(3), weights=BASE)[0]


class ScriptedBoss:
    def __init__(self):
        self.t = 0

    def aim(self, last):
        a = self.t % 3
        self.t += 1
        return a

    def observe(self, prev, move):
        pass


class AdaptiveBoss:
    def __init__(self):
        # counts[prev][next], prev index 3 means "start of fight"
        self.counts = [[1, 1, 1] for _ in range(4)]

    def aim(self, last):
        row = self.counts[3 if last is None else last]
        return max(range(3), key=lambda i: row[i])

    def observe(self, prev, move):
        self.counts[3 if prev is None else prev][move] += 1


def fight(boss, rng):
    php, bhp, last, turns, hits = PLAYER_HP, BOSS_HP, None, 0, 0
    while php > 0 and bhp > 0:
        turns += 1
        aim = boss.aim(last)
        move = player_move(last, rng)
        if aim == move:
            php -= 1
            hits += 1
        if rng.random() < PLAYER_HIT_CHANCE:
            bhp -= 1
        boss.observe(last, move)
        last = move
    return bhp <= 0, hits, turns * SECONDS_PER_TURN


def session(boss_cls, rng, fights=10):
    boss = boss_cls()
    return [fight(boss, rng) for _ in range(fights)]


def summarize(boss_cls, sessions=1000, seed=7):
    rng = random.Random(seed)
    wins = hits = secs = n = 0
    for _ in range(sessions):
        for w, h, s in session(boss_cls, rng):
            wins += w; hits += h; secs += s; n += 1
    return 100 * wins / n, hits / n, secs / n


if __name__ == "__main__":
    for name, cls in [("Scripted", ScriptedBoss), ("Adaptive", AdaptiveBoss)]:
        w, h, s = summarize(cls)
        print(f"{name:9s} win rate {w:5.1f}%  hits taken {h:4.2f}  fight length {s:5.1f}s")


def accuracy_curve(boss_cls, sessions=1000, seed=11):
    """Boss hit accuracy (hits per attack) for fight 1..10 of a session."""
    rng = random.Random(seed)
    tot = [[0, 0] for _ in range(10)]
    for _ in range(sessions):
        for i, (w, h, s) in enumerate(session(boss_cls, rng)):
            tot[i][0] += h; tot[i][1] += s / SECONDS_PER_TURN
    return [round(100 * a / b, 1) for a, b in tot]


if __name__ == "__main__":
    print("Scripted accuracy by fight:", accuracy_curve(ScriptedBoss))
    print("Adaptive accuracy by fight:", accuracy_curve(AdaptiveBoss))
