import math
import random
import pygame


def _screen_size():
    surf = pygame.display.get_surface()
    return surf.get_size() if surf else (800, 700)


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


_SPRITES = {}


def _load_sprite(kind, w, h, color, path="assets/images/enemy.png", tint=True):
    """Loads `path` (tinted per type unless tint=False) when it exists, else None."""
    key = (kind, w, h, path)
    if key in _SPRITES:
        return _SPRITES[key]
    result = None
    try:
        img = pygame.image.load(path).convert_alpha()
        img = pygame.transform.smoothscale(img, (w, h))
        if tint:
            tint_c = tuple(int(c * 0.5 + 127) for c in color)
            img.fill(tint_c + (255,), special_flags=pygame.BLEND_RGBA_MULT)
        flash = img.copy()
        flash.fill((110, 110, 110, 0), special_flags=pygame.BLEND_RGB_ADD)
        result = (img, flash)
    except (pygame.error, FileNotFoundError):
        result = None
    _SPRITES[key] = result
    return result


class EnemyBullet:
    """Enemy projectile. kind: 'orb' (round) or 'laser' (long, fast, 2 damage)."""

    def __init__(self, x, y, vx=0.0, vy=5.0, damage=1, color=(255, 90, 90), radius=5, kind="orb"):
        self.x = float(x)
        self.y = float(y)
        self.vx = vx
        self.vy = vy
        self.damage = damage
        self.color = color
        self.radius = radius
        self.kind = kind
        self.is_active = True
        self.age = 0
        self.screen_w, self.screen_h = _screen_size()

    def update(self):
        self.age += 1
        self.x += self.vx
        self.y += self.vy
        if (self.y > self.screen_h + 40 or self.y < -60 or
                self.x < -50 or self.x > self.screen_w + 50):
            self.is_active = False

    def get_rect(self):
        if self.kind == "laser":
            return pygame.Rect(int(self.x - 3), int(self.y - 18), 6, 36)
        r = self.radius
        return pygame.Rect(int(self.x - r + 2), int(self.y - r + 2), 2 * r - 4, 2 * r - 4)

    def draw(self, screen):
        if self.kind == "laser":
            rect = pygame.Rect(int(self.x - 4), int(self.y - 20), 8, 40)
            pygame.draw.rect(screen, _shade(self.color, 0.5), rect, border_radius=4)
            pygame.draw.rect(screen, self.color, rect.inflate(-3, 0), border_radius=3)
            pygame.draw.rect(screen, (255, 255, 255), rect.inflate(-6, -8), border_radius=2)
            return
        c = (int(self.x), int(self.y))
        pygame.draw.circle(screen, _shade(self.color, 0.45), c, self.radius + 3)
        pygame.draw.circle(screen, self.color, c, self.radius)
        pygame.draw.circle(screen, (255, 245, 235), c, max(1, self.radius // 2))


# ---------------------------------------------------------------------------
TYPES = {
    #            hp  score  w   h   formation-speed dive-speed colour
    "normal": dict(hp=2, score=100, w=70, h=62, speed=2.2, dive=4.2, color=(205, 75, 90)),
    "scout": dict(hp=1, score=80, w=54, h=50, speed=3.0, dive=6.5, color=(240, 170, 60)),
    "power": dict(hp=3, score=200, w=80, h=72, speed=2.0, dive=4.0, color=(170, 100, 215)),
    "tank": dict(hp=6, score=300, w=92, h=76, speed=1.4, dive=2.8, color=(90, 135, 175)),
    "sniper": dict(hp=2, score=250, w=64, h=70, speed=2.0, dive=3.6, color=(80, 200, 140)),
    "boss": dict(hp=40, score=1000, w=220, h=160, speed=2.0, dive=0.0, color=(220, 60, 80)),
}
BOSS_COLORS = [(220, 60, 80), (150, 90, 220), (235, 150, 50)]

SHAPES = {
    "normal": [(.5, 1), (0, .4), (.2, 0), (.8, 0), (1, .4)],
    "scout": [(.5, 1), (0, .1), (.5, .38), (1, .1)],
    "power": [(.5, 1), (.1, .75), (0, .3), (.3, 0), (.7, 0), (1, .3), (.9, .75)],
    "tank": [(.5, 1), (.05, .8), (0, .2), (.15, 0), (.85, 0), (1, .2), (.95, .8)],
    "sniper": [(.5, 1), (.25, .55), (.36, 0), (.64, 0), (.75, .55)],
}


class Enemy:
    """Formation enemy or boss.

    States: entering -> waiting -> diving -> offscreen -> entering ...
    Boss states: entering -> waiting (fights from the top of the screen).

    Bullet volume scales with the wave: fewer and slower-firing shots in early
    waves, ramping up to full patterns around wave 8 (see `intensity`).
    """

    def __init__(self, index, count, screen_width, kind="normal"):
        spec = TYPES.get(kind, TYPES["normal"])
        self.enemy_type = kind
        self.width, self.height = spec["w"], spec["h"]
        self.max_health = self.health = spec["hp"]
        self.score = spec["score"]
        self.speed = spec["speed"]
        self.dive_speed = spec["dive"]
        self.color = spec["color"]
        self.screen_w = screen_width
        self.screen_h = _screen_size()[1]
        self.index = index
        self.wave = 1
        self.is_alive = True
        self.age = 0
        self.hit_flash = 0
        self.shoot_delay = 700          # ms, used by the boss
        self.target_mid_y = 80          # boss hover height
        self.expendable = False         # summoned minions vanish after one dive
        self.summon = 0                 # boss asks the game for N minions
        self.phase = 1
        self.phase_flash = 0
        self.variant = 0                # boss look / pattern set (0-2)
        self.shots = 0
        self.fire_timer = random.randint(60, 220)
        self.charge = 0
        self.aim_pt = None
        self.dive_shot = False
        self.timer = 0
        self.vx = 0.0
        self.settle = 0.0
        self.sway_amp = 28
        self.sprites = None
        self.sprite_file = "assets/images/enemy.png"   # game manager sets enemy1.png for wave 3+ bosses
        self.dive_target = (screen_width / 2, 500)

        if kind == "boss":
            self.x = screen_width / 2 - self.width / 2
            self.y = -self.height - 10
            self.slot_x = self.x
            self.slot_y = self.target_mid_y
            self.state = "entering"
            self.fire_timer = 90
        else:
            cols = min(count, 7)
            row, col = divmod(index, cols)
            row_count = min(cols, count - row * cols)
            margin = 60
            usable = screen_width - 2 * margin
            self.slot_x = margin + usable * (col + 0.5) / row_count - self.width / 2
            self.slot_y = 92 + row * 84
            self.x = self.slot_x
            self.y = -60 - index * 28
            self.state = "entering"

    # ------------------------------------------------------------------ AI
    @property
    def bullet_speed(self):
        return 3.6 + min(self.wave * 0.12, 2.4)

    @property
    def intensity(self):
        """Bullet-count factor: ~0.52 on wave 1, reaches 1.0 around wave 8."""
        return min(1.0, 0.45 + 0.07 * self.wave)

    def _n(self, n, lo=1):
        """Scale a bullet count by wave intensity (never below `lo`)."""
        return max(lo, round(n * self.intensity))

    def _delay(self, base):
        # slower fire early on (x1.4 on wave 1), faster later (floor x0.55)
        return base * max(0.55, 1.5 - 0.1 * self.wave)

    def _aim(self, ox, oy, target, speed):
        if target is None:
            return 0.0, speed
        a = math.atan2(target[1] - oy, target[0] - ox)
        return math.cos(a) * speed, math.sin(a) * speed

    def update(self, screen_width, enemy_bullets, target=None):
        if not self.is_alive:
            return
        self.age += 1
        if self.hit_flash > 0:
            self.hit_flash -= 1
        if self.enemy_type == "boss":
            self._update_boss(screen_width, enemy_bullets, target)
            return

        s = self.state
        if s == "entering":
            self.y += 4.5
            self.x += (self.slot_x - self.x) * 0.08
            if self.y >= self.slot_y:
                self.y = self.slot_y
                self.state = "waiting"
                self.settle = 0.0

        elif s == "waiting":
            self.settle = min(1.0, self.settle + 0.02)
            self.x = self.slot_x + math.sin(self.age * 0.022) * self.sway_amp * self.settle
            self.y = self.slot_y + math.sin(self.age * 0.05 + self.index) * 4
            if self.enemy_type in ("power", "tank", "sniper") and self.y > 20:
                self._shooter(enemy_bullets, target)

        elif s == "diving":
            tx, ty = self.dive_target
            self.y += self.dive_speed * (1.0 + min(self.wave, 15) * 0.02)
            cx = self.x + self.width / 2
            if self.y < ty:
                want = max(-self.dive_speed, min(self.dive_speed, (tx - cx) * 0.03))
                self.vx += (want - self.vx) * 0.1
            weave = {"scout": 2.6, "normal": 1.2}.get(self.enemy_type, 0.0)
            self.x += self.vx + math.sin(self.age * 0.14 + self.index) * weave
            self.x = max(0, min(self.screen_w - self.width, self.x))
            if not self.dive_shot and self.y > 140 and self.enemy_type in ("normal", "power"):
                self.dive_shot = True
                ox, oy = self.x + self.width / 2, self.y + self.height
                if self.enemy_type == "normal":
                    vx, vy = self._aim(ox, oy, target, self.bullet_speed)
                    enemy_bullets.append(EnemyBullet(ox, oy, vx, vy, 1, (255, 120, 90), 5))
                else:
                    cnt = self._n(3)
                    for k in range(cnt):
                        a = math.pi / 2 + (k - (cnt - 1) / 2) * 0.28
                        enemy_bullets.append(EnemyBullet(ox, oy, math.cos(a) * self.bullet_speed,
                                                         math.sin(a) * self.bullet_speed, 1,
                                                         (200, 130, 240), 5))
            if self.y > self.screen_h + 20:
                if self.expendable:
                    self.is_alive = False
                else:
                    self.state = "offscreen"
                    self.timer = 45

        elif s == "offscreen":
            self.timer -= 1
            if self.timer <= 0:
                self.x = self.slot_x
                self.y = -60
                self.vx = 0.0
                self.dive_shot = False
                self.state = "entering"

    def _shooter(self, bullets, target):
        t = self.enemy_type
        self.fire_timer -= 1
        ox, oy = self.x + self.width / 2, self.y + self.height - 6
        bs = self.bullet_speed
        if t == "sniper":
            if self.charge > 0:
                self.charge -= 1
                self.aim_pt = target
                if self.charge == 0:
                    vx, vy = self._aim(ox, oy, self.aim_pt, bs * 2.0)
                    bullets.append(EnemyBullet(ox, oy, vx, vy, 2, (255, 235, 90), 4, "laser"))
                    self.fire_timer = self._delay(240)
            elif self.fire_timer <= 0:
                self.charge = 45
            return
        if self.fire_timer > 0:
            return
        if t == "power":
            vx, vy = self._aim(ox, oy, target, bs)
            bullets.append(EnemyBullet(ox, oy, vx, vy, 1, (200, 130, 240), 5))
            self.fire_timer = self._delay(190) + random.randint(0, 60)
        elif t == "tank":
            cnt = self._n(3)
            for k in range(cnt):
                a = math.pi / 2 + (k - (cnt - 1) / 2) * 0.3
                bullets.append(EnemyBullet(ox, oy, math.cos(a) * bs * 0.9, math.sin(a) * bs * 0.9,
                                           1, (120, 175, 225), 7))
            self.fire_timer = self._delay(260) + random.randint(0, 60)

    # ---------------------------------------------------------------- boss
    def _update_boss(self, screen_width, bullets, target):
        ratio = self.health / max(1, self.max_health)
        phase = 1 if ratio > 0.66 else (2 if ratio > 0.33 else 3)
        if phase != self.phase:
            self.phase = phase
            self.phase_flash = 60
            self.summon = 2
        if self.phase_flash > 0:
            self.phase_flash -= 1

        if self.state == "entering":
            self.y += 2.2
            if self.y >= self.target_mid_y:
                self.y = self.target_mid_y
                self.state = "waiting"
                self.age = 0
            return

        amp = (screen_width - self.width) / 2 - 24
        rate = 0.010 * self.speed * (1.0, 1.15, 1.45)[self.phase - 1]
        self.x = screen_width / 2 - self.width / 2 + math.sin(self.age * rate) * amp
        self.y = self.target_mid_y + math.sin(self.age * 0.03) * (6 + (10 if self.phase == 3 else 0))

        self.fire_timer -= 1
        if self.fire_timer <= 0:
            self._boss_fire(bullets, target)
            frames = self._delay(self.shoot_delay * 0.06) / (1.0, 1.0, 1.1)[self.phase - 1]
            self.fire_timer = max(22, frames)

    def _boss_fire(self, bullets, target):
        ox, oy = self.x + self.width / 2, self.y + self.height - 14
        bs = self.bullet_speed + (0.6 if self.phase == 3 else 0.0)
        shot_col = (255, 110, 90) if self.variant % 3 == 0 else ((200, 140, 255) if self.variant % 3 == 1 else (255, 190, 80))
        n = self.shots
        self.shots += 1

        def fan(count, spread, speed=bs):
            count = self._n(count)
            for k in range(count):
                a = math.pi / 2 + (k - (count - 1) / 2) * spread
                bullets.append(EnemyBullet(ox, oy, math.cos(a) * speed, math.sin(a) * speed, 1, shot_col, 6))

        def aimed(count, spread, speed=bs):
            count = self._n(count)
            base = math.atan2(target[1] - oy, target[0] - ox) if target else math.pi / 2
            for k in range(count):
                a = base + (k - (count - 1) / 2) * spread
                bullets.append(EnemyBullet(ox, oy, math.cos(a) * speed, math.sin(a) * speed, 1, (255, 235, 150), 5))

        def ring(count, rot, speed=bs * 0.85):
            count = self._n(count, 6)       # a ring never gets sparser than 6
            for k in range(count):
                a = rot + k * math.tau / count
                bullets.append(EnemyBullet(ox, oy, math.cos(a) * speed, math.sin(a) * speed, 1, shot_col, 6))

        v = self.variant % 3
        if self.phase == 1:
            if v == 0:
                fan(5, 0.26)
            elif v == 1:
                aimed(2 + n % 2, 0.16)
            else:
                ring(8, n * 0.2)
        elif self.phase == 2:
            if n % 3 == 2:
                ring(12, n * 0.15)
            else:
                fan(5 + 2 * (n % 2), 0.22)
            if n % 2 == 0:
                aimed(1, 0, bs * 1.15)
        else:
            if n % 2 == 0:
                ring(12, n * 0.11, bs * 0.85)
            else:
                aimed(3, 0.18, bs * 1.1)
                fan(5, 0.22)
            if n % 4 == 3:
                for dx in {1: (0,), 2: (-20, 20)}.get(self._n(3), (-40, 0, 40)):
                    bullets.append(EnemyBullet(ox + dx, oy, 0, bs * 1.7, 2, (255, 235, 90), 4, "laser"))

    # -------------------------------------------------------------- helpers
    def start_drop(self, tx, ty):
        if self.state != "waiting" or self.enemy_type == "boss":
            return
        self.state = "diving"
        self.dive_target = (tx, ty)
        self.vx = 0.0
        self.dive_shot = False

    def damage(self, amount=1):
        if not self.is_alive:
            return False
        self.health -= amount
        self.hit_flash = 4
        if self.health <= 0:
            self.health = 0
            self.is_alive = False
            return True
        return False

    def get_rect(self):
        if self.state == "offscreen" or not self.is_alive:
            return pygame.Rect(-999, -999, 1, 1)
        if self.enemy_type == "boss":
            return pygame.Rect(int(self.x) + 12, int(self.y) + 8, self.width - 24, self.height - 16)
        return pygame.Rect(int(self.x) + 4, int(self.y) + 4, self.width - 8, self.height - 8)

    # ----------------------------------------------------------------- draw
    def _sprite(self):
        if self.sprites is None:
            boss = self.enemy_type == "boss"
            color = BOSS_COLORS[self.variant % 3] if boss else self.color
            key = f"{self.enemy_type}{self.variant if boss else ''}"
            custom = boss and self.sprite_file != "assets/images/enemy.png"
            spr = _load_sprite(key, self.width, self.height, color, self.sprite_file, tint=not custom)
            if spr is None and custom:      # enemy1.png missing -> fall back to enemy.png
                spr = _load_sprite(key, self.width, self.height, color)
            self.sprites = spr or False
        return self.sprites or None

    def draw(self, screen):
        if not self.is_alive or self.state == "offscreen":
            return
        spr = self._sprite()
        if spr is not None:
            if self.enemy_type == "boss":
                # no white hit-flash or phase-flash on the boss
                screen.blit(spr[0], (int(self.x), int(self.y)))
            else:
                screen.blit(spr[1] if self.hit_flash > 0 else spr[0], (int(self.x), int(self.y)))
                self._draw_telegraph(screen)
            return
        if self.enemy_type == "boss":
            self._draw_boss(screen)
            return
        x, y, w, h = int(self.x), int(self.y), self.width, self.height
        body = (255, 255, 255) if self.hit_flash > 0 else self.color
        pts = [(x + px * w, y + py * h) for px, py in SHAPES[self.enemy_type]]
        pygame.draw.polygon(screen, body, pts)
        pygame.draw.polygon(screen, _shade(self.color, 0.55), pts, 2)
        cx, cy = x + w // 2, y + int(h * 0.38)
        t = self.enemy_type
        if t == "tank":
            pygame.draw.rect(screen, _shade(self.color, 0.6), (cx - 8, y + h - 14, 16, 14), border_radius=3)
            pygame.draw.circle(screen, (255, 210, 120), (cx, cy), 6)
        elif t == "sniper":
            pygame.draw.rect(screen, (30, 60, 45), (cx - 3, y + h - 16, 6, 16))
            pygame.draw.circle(screen, (255, 90, 90), (cx, cy), 5)
        elif t == "scout":
            pygame.draw.circle(screen, (255, 250, 200), (cx, cy), 4)
        elif t == "power":
            pygame.draw.circle(screen, (255, 230, 255), (cx, cy), 7)
            pygame.draw.circle(screen, (90, 40, 130), (cx, cy), 3)
        else:
            pygame.draw.circle(screen, (255, 235, 200), (cx - 8, cy), 4)
            pygame.draw.circle(screen, (255, 235, 200), (cx + 8, cy), 4)
        self._draw_telegraph(screen)

    def _draw_telegraph(self, screen):
        """Sniper charge: a thin red line to where it is aiming, getting brighter."""
        if self.enemy_type == "sniper" and self.charge > 0 and self.aim_pt:
            cx, by = int(self.x + self.width / 2), int(self.y + self.height)
            alpha = 80 + (45 - self.charge) * 4
            pygame.draw.line(screen, (min(255, alpha), 60, 60), (cx, by), self.aim_pt, 1)
            pygame.draw.circle(screen, (255, 90, 90), (cx, by), 3 + (45 - self.charge) // 10)

    def _draw_boss(self, screen):
        x, y, w, h = int(self.x), int(self.y), self.width, self.height
        base = BOSS_COLORS[self.variant % 3]
        body = base
        dark = _shade(base, 0.45)
        # wings
        wing_l = [(x, y + 10), (x + w * .32, y + 24), (x + w * .28, y + h * .75), (x + 4, y + h * .55)]
        wing_r = [(x + w, y + 10), (x + w * .68, y + 24), (x + w * .72, y + h * .75), (x + w - 4, y + h * .55)]
        pygame.draw.polygon(screen, dark, wing_l)
        pygame.draw.polygon(screen, dark, wing_r)
        # hull
        hull = [(x + w * .5, y + h), (x + w * .2, y + h * .7), (x + w * .12, y + h * .2),
                (x + w * .3, y), (x + w * .7, y), (x + w * .88, y + h * .2), (x + w * .8, y + h * .7)]
        pygame.draw.polygon(screen, body, hull)
        pygame.draw.polygon(screen, dark, hull, 3)
        # cannons
        for fx in (.28, .5, .72):
            pygame.draw.rect(screen, dark, (x + w * fx - 5, y + h - 20, 10, 20), border_radius=3)
        # glowing core, brighter each phase
        pulse = 0.5 + 0.5 * math.sin(self.age * (0.1 + 0.05 * self.phase))
        core = (255, int(210 - 60 * self.phase + 40 * pulse), int(120 - 30 * self.phase))
        cx, cy = x + w // 2, y + int(h * 0.42)
        pygame.draw.circle(screen, dark, (cx, cy), 20)
        pygame.draw.circle(screen, core, (cx, cy), 14 + int(3 * pulse))
        pygame.draw.circle(screen, (255, 255, 255), (cx, cy), 5)
        for ex in (-34, 34):
            pygame.draw.circle(screen, (255, 235, 200), (cx + ex, cy - 8), 6)
            pygame.draw.circle(screen, (60, 20, 30), (cx + ex, cy - 8), 2)



# ---------------------------------------------------------------------------
# Power-ups: subtle pulse glow, small bob and slight drift while falling.
POWERUPS = {
    #            letter  colour             duration (frames, 0 = instant)
    "rapid": dict(letter="R", color=(255, 210, 70), duration=480),
    "spread": dict(letter="S", color=(110, 220, 120), duration=480),
    "shield": dict(letter="D", color=(90, 200, 255), duration=420),
    "life": dict(letter="+", color=(255, 100, 120), duration=0),
}
DROP_CHANCE = {"scout": .06, "normal": .08, "sniper": .12, "power": .15, "tank": .25, "boss": 1.0}
_FONT = None


class PowerUp:
    def __init__(self, x, y, kind=None):
        self.kind = kind or random.choices(list(POWERUPS), weights=(4, 4, 3, 1))[0]
        spec = POWERUPS[self.kind]
        self.color = spec["color"]
        self.letter = spec["letter"]
        self.duration = spec["duration"]
        self.x, self.y = float(x), float(y)
        self.vy = 1.8
        self.radius = 14
        self.age = 0
        self.is_active = True
        self.screen_h = _screen_size()[1]

    def update(self):
        self.age += 1
        self.y += self.vy
        self.x += math.sin(self.age * 0.06) * 0.4
        if self.y > self.screen_h + 30:
            self.is_active = False

    def get_rect(self):
        r = self.radius
        return pygame.Rect(int(self.x - r), int(self.y - r), 2 * r, 2 * r)

    def draw(self, screen):
        global _FONT
        if _FONT is None:
            _FONT = pygame.font.Font(None, 22)
        pulse = 0.5 + 0.5 * math.sin(self.age * 0.1)
        c = (int(self.x), int(self.y + math.sin(self.age * 0.08) * 2))
        gr = self.radius + 6 + int(3 * pulse)
        glow = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, self.color + (45 + int(30 * pulse),), (gr, gr), gr)
        screen.blit(glow, (c[0] - gr, c[1] - gr))
        pygame.draw.circle(screen, _shade(self.color, 0.35), c, self.radius)
        pygame.draw.circle(screen, self.color, c, self.radius, 2)
        txt = _FONT.render(self.letter, True, (255, 255, 255))
        screen.blit(txt, txt.get_rect(center=c))


def roll_powerup(enemy):
    """Call when an enemy dies. Returns a PowerUp or None."""
    if enemy.expendable:                      # boss-summoned minions drop nothing
        return None
    if random.random() < DROP_CHANCE.get(enemy.enemy_type, 0.08):
        return PowerUp(enemy.x + enemy.width / 2, enemy.y + enemy.height / 2)
    return None