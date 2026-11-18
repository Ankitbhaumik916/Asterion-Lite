"""
Asterion Lite: an AI boss that learns how you play.   (visual prototype)

Each round the boss winds up, then slams one of three lanes. You stand in a lane when it lands.
The lane is only shown for a split second before impact, so you have to guess, and a player with
a habit gets caught.  Switch the boss between SCRIPTED and ADAPTIVE at any time and watch the
right hand panel: it shows what the adaptive boss currently believes about you.

    python game.py            play yourself
    python game.py --bot      start with the habit driven test player
    python game.py --help

Keys
    LEFT / RIGHT or A / D   move lane            H   heal (one per fight, you cannot move that round)
    M or TAB                switch SCRIPTED / ADAPTIVE   G   governor cap on / off
    B                       test player: off, left dodger, cycler        F   speed 1x, 4x, 12x
    C                       forget the learned profile    R   reset the stats
    SPACE                   pause      ESC   quit
"""
import argparse
import json
import os
import random
import sys

import pygame

from model import (ATTACK_NAMES, LANES, N, PLAYER_HEALS, PLAYER_HP, ROUNDS_PER_FIGHT,
                   T_IMPACT, T_REST, T_TELL, T_WINDUP, AdaptiveBoss, HabitBot, PlayerModel,
                   ScriptedBoss)

# ------------------------------------------------------------------ look
W, H = 1000, 660
ARENA = pygame.Rect(20, 78, 630, 470)
PANEL_X = 672
BG, PANEL = (14, 18, 28), (22, 28, 42)
INK, MUTED = (232, 236, 244), (140, 150, 170)
TEAL, AMBER, RED, GREEN, BLUE = (62, 190, 190), (240, 170, 50), (235, 70, 70), (80, 205, 120), (90, 150, 240)
LANE_COL = ((26, 34, 52), (30, 40, 60), (26, 34, 52))
PROFILE_FILE = "asterion_profile.json"
FIGHT_OVER_PAUSE = 2.4


def lane_rect(i):
    w = ARENA.w // N
    return pygame.Rect(ARENA.x + i * w, ARENA.y, w, ARENA.h)


def lane_cx(i):
    return lane_rect(i).centerx


class Game:
    def __init__(self, args):
        pygame.init()
        pygame.display.set_caption("Asterion Lite: an AI boss that learns how you play")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        names = "dejavusans,arial,helvetica,liberationsans"
        self.f = {s: pygame.font.SysFont(names, s) for s in (13, 15, 17, 20, 26, 34, 52)}
        self.fb = {s: pygame.font.SysFont(names, s, bold=True) for s in (13, 15, 17, 20, 26, 34, 52)}

        self.rng = random.Random(args.seed)
        self.model = PlayerModel()
        if args.profile and os.path.exists(PROFILE_FILE):
            with open(PROFILE_FILE) as fh:
                self.model.load_dict(json.load(fh))
        self.profile_on = args.profile
        self.cap_on = True
        self.scripted = ScriptedBoss()
        self.adaptive = AdaptiveBoss(self.model, self.rng)
        self.mode = "ADAPTIVE" if args.adaptive else "SCRIPTED"
        self.bot_kinds = [None] + list(HabitBot.PROFILES)
        self.bot_i = 1 if args.bot else 0
        self.bot = HabitBot(self.rng, self.bot_kinds[self.bot_i] or "left dodger")
        self.speed_i = 2 if args.bot else 0
        self.speeds = (1, 4, 12)
        self.paused = False
        self.reset_stats()
        self.start_fight()

    # ------------------------------------------------------------ state
    def reset_stats(self):
        self.stats = {m: {"fights": 0, "wins": 0, "rounds": 0, "hits": 0} for m in ("SCRIPTED", "ADAPTIVE")}
        self.fight_no = 0

    def start_fight(self):
        self.fight_no += 1
        self.round = 0
        self.hp = PLAYER_HP
        self.heals = PLAYER_HEALS
        self.lane = 1
        self.prev_lane = None
        self.pips = []                    # one entry per finished round: True = hit
        self.log = self.log if hasattr(self, "log") else []
        self.scripted.begin_fight()
        self.adaptive.begin_fight()
        self.phase, self.t = "READY", 0.0
        self.decision = None
        self.round_boss = None
        self.fight_over = None
        self.flash = 0.0
        self.flash_col = RED
        self.msg, self.msg_t = "", 0.0
        self.healed_this_round = False
        self.fight_time = 0.0

    def start_round(self):
        self.round += 1
        self.phase, self.t = "WINDUP", 0.0
        self.round_boss = self.adaptive if self.mode == "ADAPTIVE" else self.scripted
        self.decision = None
        self.healed_this_round = False
        self.bot_pick_at = self.rng.uniform(0.15, 0.80) * T_WINDUP
        self.bot_done = False

    # ------------------------------------------------------------ input
    def move(self, d):
        if self.phase in ("READY", "WINDUP", "TELL") and not self.healed_this_round:
            self.lane = max(0, min(N - 1, self.lane + d))

    def heal(self):
        if self.phase == "WINDUP" and self.heals > 0 and self.hp < PLAYER_HP:
            self.hp += 1
            self.heals -= 1
            self.healed_this_round = True
            self.say("HEALED +1", GREEN)

    def say(self, text, col):
        self.msg, self.msg_col, self.msg_t = text, col, 1.0

    def handle(self, e):
        k = e.key
        if k == pygame.K_ESCAPE:
            self.quit()
        elif k in (pygame.K_LEFT, pygame.K_a):
            self.move(-1)
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.move(1)
        elif k == pygame.K_h:
            self.heal()
        elif k in (pygame.K_m, pygame.K_TAB):
            self.mode = "ADAPTIVE" if self.mode == "SCRIPTED" else "SCRIPTED"
        elif k == pygame.K_g:
            self.cap_on = not self.cap_on
            self.adaptive.cap = 0.65 if self.cap_on else None
        elif k == pygame.K_b:
            self.bot_i = (self.bot_i + 1) % len(self.bot_kinds)
            if self.bot_kinds[self.bot_i]:
                self.bot.habit = self.bot_kinds[self.bot_i]
        elif k == pygame.K_f:
            self.speed_i = (self.speed_i + 1) % len(self.speeds)
        elif k == pygame.K_c:
            self.model.clear()
        elif k == pygame.K_r:
            self.reset_stats()
            self.start_fight()
        elif k == pygame.K_SPACE:
            self.paused = not self.paused

    # ------------------------------------------------------------ update
    def update(self, dt):
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        self.msg_t = max(0.0, self.msg_t - dt)
        if self.phase in ("WINDUP", "TELL", "IMPACT", "REST"):
            self.fight_time += dt
        bot_on = self.bot_kinds[self.bot_i] is not None

        if self.phase == "READY":
            if self.t >= 0.9:
                self.start_round()

        elif self.phase == "WINDUP":
            if bot_on and not self.bot_done and self.t >= self.bot_pick_at and not self.healed_this_round:
                self.bot_done = True
                lane, healed = self.bot.act(self.hp, self.heals)
                if healed:
                    self.heal()
                else:
                    self.lane = lane
            if self.t >= T_WINDUP:
                # The boss decides now, using only what it saw in earlier rounds.
                self.decision = self.round_boss.choose(self.prev_lane)
                self.phase, self.t = "TELL", 0.0

        elif self.phase == "TELL":
            if self.t >= T_TELL:
                self.resolve()

        elif self.phase == "IMPACT":
            if self.t >= T_IMPACT:
                self.phase, self.t = "REST", 0.0

        elif self.phase == "REST":
            if self.t >= T_REST:
                if self.hp <= 0 or self.round >= ROUNDS_PER_FIGHT:
                    self.finish_fight()
                else:
                    self.start_round()

        elif self.phase == "OVER":
            if self.t >= FIGHT_OVER_PAUSE:
                self.model.end_fight()          # recency weighting: old counts fade a little
                self.start_fight()

    def resolve(self):
        d = self.decision
        hit = d.attack == self.lane
        st = self.stats[self.round_boss.name]
        st["rounds"] += 1
        if hit:
            st["hits"] += 1
            self.hp -= 1
            self.flash, self.flash_col = 0.35, RED
            self.say("HIT  -1", RED)
        else:
            self.say("DODGED", GREEN)
        # events are sent after they happen: the model never sees the lane before impact
        self.adaptive.observe(self.prev_lane, self.lane)
        if self.round_boss is self.adaptive:
            self.adaptive.record_attack(hit)
        self.pips.append(hit)
        self.log.append((self.round, self.round_boss.name[0], d.attack, self.lane, hit, self.healed_this_round))
        self.log = self.log[-6:]
        self.prev_lane = self.lane
        self.phase, self.t = "IMPACT", 0.0

    def finish_fight(self):
        won = self.hp > 0
        st = self.stats[self.round_boss.name]
        st["fights"] += 1
        st["wins"] += 1 if won else 0
        self.fight_over = won
        self.phase, self.t = "OVER", 0.0

    # ------------------------------------------------------------ drawing
    def text(self, s, size, col, pos, bold=False, anchor="topleft"):
        img = (self.fb if bold else self.f)[size].render(s, True, col)
        r = img.get_rect(**{anchor: pos})
        self.screen.blit(img, r)
        return r

    def overlay(self, rect, col, alpha):
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        s.fill((*col, alpha))
        self.screen.blit(s, rect.topleft)

    def draw(self):
        scr = self.screen
        scr.fill(BG)
        self.draw_header()
        self.draw_arena()
        self.draw_panel()
        self.draw_footer()
        pygame.display.flip()

    def draw_header(self):
        self.text("ASTERION LITE", 26, INK, (20, 14), bold=True)
        self.text("an AI boss that learns how you play", 15, MUTED, (222, 24))
        x0 = ARENA.x
        self.text(f"FIGHT {self.fight_no}", 15, MUTED, (x0, 54), bold=True)
        for i in range(ROUNDS_PER_FIGHT):
            r = pygame.Rect(x0 + 92 + i * 30, 54, 24, 14)
            col = (50, 58, 78)
            if i < len(self.pips):
                col = RED if self.pips[i] else GREEN
            pygame.draw.rect(self.screen, col, r, border_radius=4)
        hp_x = x0 + 92 + ROUNDS_PER_FIGHT * 30 + 24
        self.text("HP", 15, MUTED, (hp_x, 54), bold=True)
        for i in range(PLAYER_HP):
            c = (hp_x + 32 + i * 20, 61)
            pygame.draw.circle(self.screen, RED if i < self.hp else (60, 40, 46), c, 7)
        if self.heals:
            self.text("H: heal ready", 13, GREEN, (hp_x + 32 + PLAYER_HP * 20 + 6, 54))

    def draw_arena(self):
        scr = self.screen
        for i in range(N):
            pygame.draw.rect(scr, LANE_COL[i], lane_rect(i))
            pygame.draw.line(scr, (50, 60, 84), lane_rect(i).topleft, lane_rect(i).bottomleft, 2)
            self.text(LANES[i], 13, (90, 102, 130), (lane_cx(i), ARENA.bottom - 14), anchor="center")
        pygame.draw.line(scr, (50, 60, 84), ARENA.topright, ARENA.bottomright, 2)

        # target lane highlight
        if self.decision is not None and self.phase in ("TELL", "IMPACT"):
            r = lane_rect(self.decision.attack)
            if self.phase == "TELL":
                self.overlay(r, RED, 70)
                pygame.draw.rect(scr, RED, r, 3)
                self.text("!", 52, RED, (r.centerx, r.centery - 10), bold=True, anchor="center")
            else:
                k = 1.0 - self.t / T_IMPACT
                self.overlay(r, RED, int(40 + 150 * k))
        self.draw_boss()
        self.draw_player()
        if self.msg_t > 0:
            col = getattr(self, "msg_col", INK)
            self.text(self.msg, 34, col, (ARENA.centerx, ARENA.y + 250), bold=True, anchor="center")
        if self.phase == "READY":
            self.text(f"FIGHT {self.fight_no}", 52, INK, (ARENA.centerx, ARENA.centery - 20), bold=True, anchor="center")
            self.text("get ready", 20, MUTED, (ARENA.centerx, ARENA.centery + 24), anchor="center")
        if self.phase == "OVER":
            self.overlay(ARENA, (8, 10, 16), 170)
            word, col = ("VICTORY", GREEN) if self.fight_over else ("DEFEAT", RED)
            self.text(word, 52, col, (ARENA.centerx, ARENA.centery - 20), bold=True, anchor="center")
            self.text(f"{sum(self.pips)} hits taken in {len(self.pips)} rounds",
                      20, INK, (ARENA.centerx, ARENA.centery + 26), anchor="center")

    def draw_boss(self):
        scr = self.screen
        cx, cy = ARENA.centerx, ARENA.y + 80
        body = (120, 70, 150) if self.mode == "ADAPTIVE" else (110, 110, 120)
        if self.phase == "TELL":
            body = (170, 60, 70)
        pygame.draw.polygon(scr, body, [(cx - 52, cy - 30), (cx - 34, cy - 76), (cx - 16, cy - 40)])
        pygame.draw.polygon(scr, body, [(cx + 52, cy - 30), (cx + 34, cy - 76), (cx + 16, cy - 40)])
        pygame.draw.circle(scr, body, (cx, cy), 56)
        pygame.draw.circle(scr, (20, 20, 30), (cx, cy), 56, 3)
        look = 0
        if self.decision is not None and self.phase in ("TELL", "IMPACT"):
            look = (self.decision.attack - 1) * 7
        for ex in (-20, 20):
            pygame.draw.ellipse(scr, (240, 240, 245), (cx + ex - 13, cy - 16, 26, 22))
            pygame.draw.circle(scr, (20, 20, 30), (cx + ex + look, cy - 3), 6)
        mouth_open = 8 if self.phase in ("TELL", "IMPACT") else 2
        pygame.draw.rect(scr, (20, 20, 30), (cx - 20, cy + 26, 40, mouth_open + 2), border_radius=4)
        # charge bar
        bar = pygame.Rect(cx - 90, cy + 70, 180, 10)
        pygame.draw.rect(scr, (40, 46, 64), bar, border_radius=5)
        if self.phase == "WINDUP":
            frac = min(1.0, self.t / T_WINDUP)
        else:
            frac = 1.0 if self.phase in ("TELL", "IMPACT") else 0.0
        if frac > 0:
            col = AMBER if frac < 0.85 else RED
            pygame.draw.rect(scr, col, (bar.x, bar.y, int(bar.w * frac), bar.h), border_radius=5)
        label = {"SCRIPTED": "scripted boss", "ADAPTIVE": "adaptive boss"}[self.mode]
        self.text(label, 13, MUTED, (cx, cy + 92), anchor="center")

    def draw_player(self):
        scr = self.screen
        x, y = lane_cx(self.lane), ARENA.bottom - 78
        col = TEAL
        if self.flash > 0:
            col = RED
        elif self.healed_this_round:
            col = GREEN
        pygame.draw.circle(scr, (10, 14, 22), (x, y + 4), 30)
        pygame.draw.circle(scr, col, (x, y), 26)
        pygame.draw.circle(scr, (240, 248, 250), (x, y), 26, 3)
        pygame.draw.polygon(scr, (10, 14, 22), [(x, y - 12), (x - 9, y + 8), (x + 9, y + 8)])

    def draw_panel(self):
        scr = self.screen
        px, pw = PANEL_X, W - PANEL_X - 18
        pygame.draw.rect(scr, PANEL, (px, 78, pw, 470), border_radius=10)
        x = px + 16
        # mode badge
        adaptive = self.mode == "ADAPTIVE"
        badge = pygame.Rect(x, 92, pw - 32, 40)
        pygame.draw.rect(scr, (92, 60, 130) if adaptive else (80, 84, 98), badge, border_radius=8)
        self.text(f"{self.mode} BOSS", 20, INK, badge.center, bold=True, anchor="center")

        if adaptive:
            self.draw_belief(x, pw)
        else:
            self.draw_script(x, pw)
        self.draw_stats(x, pw)
        self.draw_log(x, pw)

    def draw_belief(self, x, pw):
        scr = self.screen
        m = self.model
        self.text("WHAT THE BOSS BELIEVES ABOUT YOU", 13, MUTED, (x, 144), bold=True)
        probs = m.predict(self.prev_lane)
        locked = self.decision.attack if (self.decision and self.phase in ("TELL", "IMPACT")
                                          and self.round_boss is self.adaptive) else None
        best = probs.index(max(probs))
        for i in range(N):
            y = 168 + i * 30
            self.text(LANES[i][:1] + LANES[i][1:].lower(), 15, INK, (x, y))
            bar = pygame.Rect(x + 68, y + 2, pw - 32 - 68 - 52, 16)
            pygame.draw.rect(scr, (40, 46, 64), bar, border_radius=4)
            fill = pygame.Rect(bar.x, bar.y, int(bar.w * probs[i]), bar.h)
            col = AMBER if i == best else BLUE
            if m.ready():
                pygame.draw.rect(scr, col, fill, border_radius=4)
            self.text(f"{probs[i] * 100:3.0f}%" if m.ready() else " ?", 15, INK, (bar.right + 8, y), bold=(i == best))
            if locked == i:
                pygame.draw.rect(scr, RED, bar.inflate(6, 6), 2, border_radius=6)
        if m.ready():
            c = max(probs)
            txt = f"Predicts {LANES[best].lower()} dodge, {c * 100:.0f}% sure"
            self.text(txt, 15, AMBER, (x, 262), bold=True)
        else:
            self.text(f"Warming up: {m.seen} of {m.min_samples} rounds seen", 15, AMBER, (x, 262), bold=True)
        note = self.decision.note if (self.decision and self.round_boss is self.adaptive and self.phase != "WINDUP") else ""
        self.text(note, 13, MUTED, (x, 284))
        gov = f"governor cap {int(self.adaptive.cap * 100)}%" if self.adaptive.cap else "governor OFF"
        self.text(f"{gov}   |   learned from {m.seen} rounds", 13, MUTED, (x, 304))

    def draw_script(self, x, pw):
        self.text("FIXED ATTACK PATTERN", 13, MUTED, (x, 144), bold=True)
        s = ScriptedBoss.SCRIPT
        for i, a in enumerate(s):
            r = pygame.Rect(x + (i % 5) * 52, 170 + (i // 5) * 40, 46, 32)
            cur = (i == self.scripted.i - 1) and self.round_boss is self.scripted and self.phase != "WINDUP"
            pygame.draw.rect(self.screen, AMBER if cur else (46, 54, 76), r, border_radius=6)
            self.text(LANES[a][0], 17, BG if cur else INK, r.center, bold=True, anchor="center")
        self.text("Same order every fight.", 15, AMBER, (x, 262), bold=True)
        self.text("Once you spot it, you can dodge on cue.", 13, MUTED, (x, 284))
        self.text("The adaptive model keeps learning quietly.", 13, MUTED, (x, 304))

    def draw_stats(self, x, pw):
        scr = self.screen
        y0 = 336
        self.text("RESULTS SO FAR", 13, MUTED, (x, y0), bold=True)
        cols = (x + 78, x + 140, x + 186)
        for c, h in zip(cols, ("Fights", "Win %", "Hit %")):
            self.text(h, 13, MUTED, (c, y0 + 22))
        for j, name in enumerate(("SCRIPTED", "ADAPTIVE")):
            s = self.stats[name]
            y = y0 + 44 + j * 24
            self.text(name.title(), 15, INK, (x, y), bold=(name == self.mode))
            self.text(str(s["fights"]), 15, INK, (cols[0] + 6, y))
            win = f"{100 * s['wins'] / s['fights']:.0f}%" if s["fights"] else "n/a"
            hit = f"{100 * s['hits'] / s['rounds']:.0f}%" if s["rounds"] else "n/a"
            self.text(win, 15, GREEN if name == "ADAPTIVE" else INK, (cols[1], y), bold=True)
            self.text(hit, 15, RED if name == "ADAPTIVE" else INK, (cols[2], y), bold=True)

    def draw_log(self, x, pw):
        self.text("BOSS ATTACK LOG", 13, MUTED, (x, 438), bold=True)
        for i, (rn, who, atk, lane, hit, healed) in enumerate(reversed(self.log[-4:])):
            y = 460 + i * 20
            res = "HIT" if hit else "dodged"
            self.text(f"R{rn} {who}  boss {LANES[atk][:1]}  you {LANES[lane][:1]}", 13, INK, (x, y))
            self.text(res, 13, RED if hit else GREEN, (x + 168, y), bold=True)

    def draw_footer(self):
        bot = self.bot_kinds[self.bot_i]
        bot_txt = f"TEST PLAYER: {bot.upper()}" if bot else "YOU ARE PLAYING"
        self.text(bot_txt, 15, AMBER if bot else TEAL, (20, 562), bold=True)
        self.text(f"speed {self.speeds[self.speed_i]}x", 15, MUTED, (260, 562))
        if self.paused:
            self.text("PAUSED", 15, RED, (340, 562), bold=True)
        keys = ("Move: arrows or A D     H: heal     M: switch boss     G: governor     "
                "B: test player     F: speed     C: forget     R: reset     SPACE: pause")
        self.text(keys, 13, MUTED, (20, 590))
        self.text("The lane is only shown for a split second before impact, so you have to guess.", 13, MUTED, (20, 612))

    # ------------------------------------------------------------ main loop
    def quit(self):
        if self.profile_on:
            with open(PROFILE_FILE, "w") as fh:
                json.dump(self.model.to_dict(), fh)
        pygame.quit()
        sys.exit(0)

    def run(self, shot=None, frames=0):
        n = 0
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.quit()
                if e.type == pygame.KEYDOWN:
                    self.handle(e)
            if not self.paused:
                for _ in range(self.speeds[self.speed_i]):
                    self.update(1 / 60)
            self.draw()
            self.clock.tick(60)
            n += 1
            if shot and n >= frames:
                pygame.image.save(self.screen, shot)
                return


def main():
    ap = argparse.ArgumentParser(description="Asterion Lite visual prototype")
    ap.add_argument("--bot", action="store_true", help="start with the habit driven test player at 12x speed")
    ap.add_argument("--adaptive", action="store_true", help="start with the adaptive boss")
    ap.add_argument("--profile", action="store_true", help="load and save the learned profile between runs")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--shot", help="save a screenshot after --frames frames and exit (for testing)")
    ap.add_argument("--frames", type=int, default=600)
    a = ap.parse_args()
    Game(a).run(a.shot, a.frames)


if __name__ == "__main__":
    main()
