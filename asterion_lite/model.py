"""
Asterion Lite core: the player model, the bosses and a habit driven test player.

Nothing in this file needs pygame, so the game (game.py) and the headless
experiment runner (simulate.py) share exactly the same decision logic.

The model is small on purpose:
  1. a frequency model        how often the player ends a round in each lane
  2. a first order Markov     how likely each lane is, given the previous lane
     chain
  3. Laplace smoothing        no lane ever gets zero probability
  4. expected hit chance      the boss picks the attack with the best expected hit
Product additions:
  5. recency weighting        old counts decay, so the boss follows a changing player
  6. exploration              now and then the boss picks its second best attack
  7. difficulty governor      a cap on the boss hit rate inside a fight
"""
import random
from dataclasses import dataclass

# ---------------------------------------------------------------- game rules
LANES = ("LEFT", "CENTER", "RIGHT")
N = len(LANES)
ROUNDS_PER_FIGHT = 10          # attacks per fight
PLAYER_HP = 5                  # hits the player can take before losing
PLAYER_HEALS = 1               # heals available per fight

# seconds per phase of one round (used by the game and by the fight length metric)
T_WINDUP, T_TELL, T_IMPACT, T_REST = 1.10, 0.20, 0.45, 0.35
ROUND_SECONDS = T_WINDUP + T_TELL + T_IMPACT + T_REST

# Designer supplied hit table: HIT[attack][lane] = chance the attack hits a player in that lane.
# The defaults are one slam per lane. A studio can add wider attacks here.
ATTACK_NAMES = ("Left Slam", "Center Slam", "Right Slam")
HIT = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)


@dataclass
class Decision:
    attack: int                 # index into ATTACK_NAMES (also the lane it lands on)
    probs: list                 # model's probability for each player lane, or None
    confidence: float           # probability of the most likely lane, 0 if unknown
    note: str                   # short reason shown on screen
    adaptive: bool              # True if the model chose this, False for script or warm up


# ---------------------------------------------------------------- player model
class PlayerModel:
    def __init__(self, half_life_fights=5.0, smoothing=0.5, min_samples=6, trust=3.0):
        self.half_life = half_life_fights   # fights after which an old observation counts half
        self.alpha = smoothing              # Laplace smoothing constant
        self.min_samples = min_samples      # observations needed before the boss adapts
        self.trust = trust                  # how fast the Markov row is trusted over the overall counts
        self.clear()

    def clear(self):
        self.freq = [0.0] * N
        self.trans = [[0.0] * N for _ in range(N)]
        self.seen = 0

    def observe(self, prev_lane, lane):
        """Called after every round with the lane the player was in when the attack landed."""
        self.freq[lane] += 1
        if prev_lane is not None:
            self.trans[prev_lane][lane] += 1
        self.seen += 1

    def end_fight(self):
        """Recency weighting: every observation loses weight, halving after `half_life` fights."""
        d = 0.5 ** (1.0 / self.half_life)
        self.freq = [c * d for c in self.freq]
        self.trans = [[c * d for c in row] for row in self.trans]

    def ready(self):
        return self.seen >= self.min_samples

    def _normalise(self, counts):
        s = sum(counts) + self.alpha * N
        return [(c + self.alpha) / s for c in counts]

    def predict(self, prev_lane):
        """Probability of each lane for the next round."""
        overall = self._normalise(self.freq)
        if prev_lane is None:
            return overall
        row = self.trans[prev_lane]
        n = sum(row)
        w = n / (n + self.trust)            # trust the sequence model more as its row fills up
        seq = self._normalise(row)
        return [w * seq[i] + (1 - w) * overall[i] for i in range(N)]

    # profile store (a small local file; nothing leaves the device)
    def to_dict(self):
        return {"freq": self.freq, "trans": self.trans, "seen": self.seen}

    def load_dict(self, d):
        self.freq, self.trans, self.seen = d["freq"], d["trans"], d["seen"]


# ---------------------------------------------------------------- bosses
class ScriptedBoss:
    """A traditional boss: the same fixed pattern every fight."""
    name = "SCRIPTED"
    SCRIPT = (0, 2, 1, 0, 2, 1, 0, 2, 1, 0)       # lane of each attack, repeats every fight

    def begin_fight(self):
        self.i = 0

    def choose(self, prev_lane):
        a = self.SCRIPT[self.i % len(self.SCRIPT)]
        self.i += 1
        return Decision(a, None, 0.0, "fixed script", False)

    def record_attack(self, hit):
        pass


class RandomBoss:
    """Baseline for the experiments: a boss that picks a lane at random."""
    name = "RANDOM"

    def __init__(self, rng):
        self.rng = rng

    def begin_fight(self):
        pass

    def choose(self, prev_lane):
        return Decision(self.rng.randrange(N), None, 0.0, "random", False)

    def record_attack(self, hit):
        pass


class AdaptiveBoss:
    name = "ADAPTIVE"

    def __init__(self, model, rng, exploration=0.10, cap=0.65, min_rounds_for_cap=3):
        self.model = model
        self.rng = rng
        self.exploration = exploration      # chance of picking the second best attack
        self.cap = cap                      # governor: maximum hit rate inside a fight (None = off)
        self.min_rounds_for_cap = min_rounds_for_cap
        self.warmup = ScriptedBoss()
        self.begin_fight()

    def begin_fight(self):
        self.warmup.begin_fight()
        self.rounds = 0
        self.hits = 0

    def expected_hits(self, probs):
        return [sum(probs[l] * HIT[a][l] for l in range(N)) for a in range(len(HIT))]

    def choose(self, prev_lane):
        if not self.model.ready():                     # cold start: follow the script
            d = self.warmup.choose(prev_lane)
            return Decision(d.attack, None, 0.0, "warming up: following the script", False)
        probs = self.model.predict(prev_lane)
        ev = self.expected_hits(probs)
        order = sorted(range(len(ev)), key=lambda a: -ev[a])
        conf = max(probs)
        likely = probs.index(conf)
        governed = (self.cap is not None and self.rounds >= self.min_rounds_for_cap
                    and self.hits / self.rounds > self.cap)
        if governed:
            return Decision(order[-1], probs, conf, "governor: easing off", True)
        if self.rng.random() < self.exploration:
            return Decision(order[1], probs, conf, "exploring: second best attack", True)
        return Decision(order[0], probs, conf, f"predicts {LANES[likely]} dodge", True)

    def observe(self, prev_lane, lane):
        self.model.observe(prev_lane, lane)

    def record_attack(self, hit):
        self.rounds += 1
        self.hits += 1 if hit else 0


# ---------------------------------------------------------------- test player
class HabitBot:
    """A habit driven test player. It never sees the boss's choice."""
    PROFILES = {
        # always drifts toward the left lane
        "left dodger": ((0.60, 0.25, 0.15), (0.60, 0.25, 0.15), (0.60, 0.25, 0.15)),
        # tends to step through the lanes in order: left, centre, right, left ...
        "cycler": ((0.15, 0.70, 0.15), (0.15, 0.15, 0.70), (0.70, 0.15, 0.15)),
    }

    def __init__(self, rng, habit="left dodger"):
        self.rng = rng
        self.habit = habit
        self.last = 1

    def act(self, hp, heals):
        """One round of play. Returns (lane, healed). Healing uses the round, so the lane stays put."""
        if hp <= 2 and heals > 0 and self.rng.random() < 0.5:
            return self.last, True
        return self.pick(), False

    def pick(self):
        row = self.PROFILES[self.habit][self.last]
        r, acc = self.rng.random(), 0.0
        for lane, p in enumerate(row):
            acc += p
            if r <= acc:
                self.last = lane
                return lane
        self.last = N - 1
        return self.last
