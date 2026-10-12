import math
import os
import random
import pygame

from entities.player import Player
from entities.button import MobileButtons
from entities.enemy import Enemy, EnemyBullet, PowerUp, POWERUPS, roll_powerup
from entities.bullet import BulletManager
from db import save_score
from audio import play


BULLET_STYLES = ("bolt", "needle", "orb", "comet", "crystal")   # one per ship, in unlock order


def draw_bullet(screen, rect, style, color):
    """Draws one player shot in the given style, centred on rect. Colour = ship accent colour."""
    cx, cy = rect.center
    w = max(6, rect.w)
    h = max(14, rect.h)
    dim = tuple(int(c * 0.4) for c in color)
    core = tuple(min(255, int(c + (255 - c) * 0.75)) for c in color)
    if style == "needle":                      # long thin dart
        outer = [(cx, cy - h // 2 - 5), (cx + w // 2 + 1, cy + 2), (cx, cy + h // 2), (cx - w // 2 - 1, cy + 2)]
        inner = [(cx, cy - h // 2 - 2), (cx + w // 3, cy + 2), (cx, cy + h // 2 - 3), (cx - w // 3, cy + 2)]
        pygame.draw.polygon(screen, dim, outer)
        pygame.draw.polygon(screen, color, inner)
        pygame.draw.line(screen, core, (cx, cy - h // 2), (cx, cy + h // 3), 1)
    elif style == "orb":                       # glowing plasma ball
        r = max(5, w // 2 + 2)
        pygame.draw.circle(screen, dim, (cx, cy), r + 4)
        pygame.draw.circle(screen, color, (cx, cy), r + 4, 1)
        pygame.draw.circle(screen, color, (cx, cy), r)
        pygame.draw.circle(screen, core, (cx, cy), max(2, r // 2))
    elif style == "comet":                     # round head with a fading tail
        r = max(4, w // 2 + 1)
        for i in range(3, 0, -1):
            k = 0.2 + 0.15 * (3 - i)
            tail = tuple(int(c * k) for c in color)
            pygame.draw.circle(screen, tail, (cx, cy - h // 4 + i * (h // 4)), max(2, int(r * (0.45 + 0.15 * (3 - i)))))
        pygame.draw.circle(screen, color, (cx, cy - h // 4), r)
        pygame.draw.circle(screen, core, (cx, cy - h // 4), max(2, r // 2))
    elif style == "crystal":                   # faceted gem
        hw = w // 2 + 3
        outer = [(cx, cy - h // 2 - 3), (cx + hw, cy - h // 6), (cx + hw, cy + h // 6), (cx, cy + h // 2 + 3),
                 (cx - hw, cy + h // 6), (cx - hw, cy - h // 6)]
        inner = [(cx, cy - h // 2), (cx + hw - 3, cy - h // 6), (cx + hw - 3, cy + h // 6), (cx, cy + h // 2),
                 (cx - hw + 3, cy + h // 6), (cx - hw + 3, cy - h // 6)]
        pygame.draw.polygon(screen, dim, outer)
        pygame.draw.polygon(screen, color, inner)
        pygame.draw.polygon(screen, core, [(cx, cy - h // 4), (cx + 2, cy), (cx, cy + h // 4), (cx - 2, cy)])
    else:                                      # "bolt": rounded capsule
        glow = pygame.Rect(0, 0, w + 4, h + 4)
        glow.center = (cx, cy)
        body = pygame.Rect(0, 0, w, h)
        body.center = (cx, cy)
        stripe = pygame.Rect(0, 0, max(2, w // 3), h - 6)
        stripe.center = (cx, cy)
        pygame.draw.rect(screen, dim, glow, border_radius=6)
        pygame.draw.rect(screen, color, body, border_radius=5)
        pygame.draw.rect(screen, core, stripe, border_radius=2)


class PlayerShot:
    """Extra player shots from power-ups (rapid / spread).

    Same interface as the bullets in BulletManager: is_active, damage,
    update(), get_rect(), draw().
    """

    def __init__(self, x, y, vx=0.0, vy=-11.0, damage=1, color=(120, 230, 255), style="bolt"):
        self.x = float(x)
        self.y = float(y)
        self.vx = vx
        self.vy = vy
        self.damage = damage
        self.color = color
        self.style = style
        self.is_active = True
        surf = pygame.display.get_surface()
        self.screen_w = surf.get_width() if surf else 800

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.y < -20 or self.x < -20 or self.x > self.screen_w + 20:
            self.is_active = False

    def get_rect(self):
        return pygame.Rect(int(self.x) - 3, int(self.y) - 9, 6, 18)

    def draw(self, screen):
        draw_bullet(screen, self.get_rect(), self.style, self.color)


class GameManager:
    """Main gameplay controller.

    Every boss you destroy awards the next ship (Ship1 is the starting ship,
    Ship2..Ship5 are unlocked by bosses 1..4). Each new ship comes with a
    "NEW SHIP RECEIVED" reward animation, +1 max hull and a full repair.
    """

    HIT_INVULN = 45         # frames of invulnerability after a normal hit
    RESPAWN_FRAMES = 45     # ship hidden while the explosion plays
    RESPAWN_INVULN = 70     # frames of invulnerability after respawning
    WAVE_DELAY = 150        # calm pause + banner at the start of every wave
    BOSS_WARNING = 150      # warning + soft screen shake before the boss appears
    CLEAR_FRAMES = 150      # level-clear fly-off after a boss
    REWARD_FRAMES = 220     # "new ship received" animation length
    REWARD_SKIP_AFTER = 90  # frames before the player may skip the animation
    REINFORCE_DIV = 3       # replacements per wave = formation size // this
    BASE_HEALTH = 4         # hull of the first ship
    MAX_HEALTH = 8          # hull cap
    FLEET_BONUS = 5000      # score bonus for bosses killed after all ships are unlocked
    SHOW_THRUSTER = True    # draw an engine flame behind the ship
    CUSTOM_BULLETS = True   # each ship draws its own bullet design + colour
    WORLD_STATES = ("playing", "respawning", "level_clear", "entering")

    # name shown in the reward animation, in unlock order (Ship1 .. Ship5)
    SHIPS = ("VANGUARD", "STARLANCE", "NOVA RAIDER", "PHANTOM", "TITAN")

    def __init__(self, screen, screen_width, screen_height, player_id, player_name):
        self.screen = screen
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.player_id = player_id
        self.player_name = player_name

        self.font = pygame.font.SysFont("Arial", 27, bold=True)
        self.small_font = pygame.font.SysFont("Arial", 17, bold=True)
        self.medium_font = pygame.font.SysFont("Arial", 22, bold=True)
        self.big_font = pygame.font.SysFont("Arial", 56, bold=True)
        self.title_font = pygame.font.SysFont("Arial", 31, bold=True)
        self.tiny_font = pygame.font.SysFont("Arial", 13)

        self.WHITE = (245, 250, 255)
        self.BLUE = (65, 155, 205)
        self.CYAN = (80, 190, 210)
        self.GREEN = (70, 200, 125)
        self.RED = (235, 75, 90)
        self.YELLOW = (245, 205, 70)
        self.ORANGE = (235, 135, 55)
        self.PURPLE = (150, 105, 190)

        # pause screen / pause button theme (red sci-fi HUD)
        self.HUD_RED = (240, 92, 82)      # change to self.ship_accent(self.ship_index) to follow the ship colour
        self.HUD_DIM = (125, 48, 44)
        self.HUD_FILL = (14, 6, 7)
        self.HUD_TEXT = (235, 228, 228)

        self.background_time = 0
        self.flash_timer = 0
        self.hit_timer = 0
        self.wave = 1
        self.lives = 3
        self.score = 0
        self.max_player_health = self.BASE_HEALTH
        self.boss_active = False
        self.game_state = "playing"
        self.score_saved = False
        self.player_history = []
        self.particles = []
        self.enemies = []
        self.enemy_bullets = []
        self.bullets = BulletManager()
        self.fire_held = False
        self.timer = 0
        self.state_timer = 0

        # stars: x, y, speed, size
        self.stars = [[random.randint(0, screen_width), random.randint(0, screen_height),
                       random.uniform(.4, 2), random.randint(1, 2)] for _ in range(110)]
        # moving background: "warp" is 0 (calm drift) .. 1 (hyperspace) and eases smoothly
        self.warp = 0.0
        self.bg_scroll = 0.0
        self.speed_lines = [[random.randint(0, screen_width), random.randint(0, screen_height),
                             random.randint(40, 120), random.uniform(0.6, 1.4)] for _ in range(36)]
        self.bg_tile = None
        try:
            bg = pygame.image.load("assets/images/bg3.png").convert()
            self.background_image = pygame.transform.smoothscale(bg, (screen_width, screen_height))
            # image + its mirror stacked, so the vertical scroll loops with no visible seam
            self.bg_tile = pygame.Surface((screen_width, screen_height * 2)).convert()
            self.bg_tile.blit(self.background_image, (0, 0))
            self.bg_tile.blit(pygame.transform.flip(self.background_image, False, True), (0, screen_height))
        except (pygame.error, FileNotFoundError):
            self.background_image = None

        # ships
        self.ship_index = 0
        self.ship_sources = [self.load_ship_image(i + 1) for i in range(len(self.SHIPS))]
        self._ship_cache = {}

        # cached decorative surfaces
        self.hud_surface = self.build_hud_surface()
        self.vignette = self.build_vignette()

        self.show_controls = True   # small toggle: hides/shows the on-screen LEFT / RIGHT / FIRE buttons
        self.create_buttons()
        self.reset_game()

    # ------------------------------------------------------------ ships
    def load_ship_image(self, number):
        """Loads Ship<number> from assets/images (or assets). Returns None if missing."""
        for folder in ("assets/images", "assets", "assets/ships"):
            for name in (f"Ship{number}", f"ship{number}", f"Ship{number}".upper()):
                for ext in (".png", ".PNG", ".jpg", ".jpeg", ".webp"):
                    path = f"{folder}/{name}{ext}"
                    if os.path.exists(path):
                        try:
                            return pygame.image.load(path).convert_alpha()
                        except pygame.error:
                            pass
        return None

    def ship_sprite(self, idx, w, h, dark=False):
        """Ship image scaled to fit inside w x h (aspect ratio kept). Cached."""
        key = (idx, int(w), int(h), dark)
        if key in self._ship_cache:
            return self._ship_cache[key]
        src = self.ship_sources[idx]
        if src is None:
            sprite = None
        else:
            iw, ih = src.get_size()
            k = min(w / iw, h / ih)
            sprite = pygame.transform.smoothscale(src, (max(1, int(iw * k)), max(1, int(ih * k))))
            if dark:
                sprite = sprite.copy()
                sprite.fill((25, 32, 45, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self._ship_cache[key] = sprite
        return sprite

    def ship_accent(self, idx):
        return (self.CYAN, self.GREEN, self.YELLOW, self.ORANGE, self.PURPLE)[idx % 5]

    def draw_ship_art(self, surface, idx, center, box, dark=False):
        """Draws ship idx centred on `center`; falls back to a simple shape if the image is missing."""
        sprite = self.ship_sprite(idx, box, box, dark)
        cx, cy = center
        if sprite is not None:
            surface.blit(sprite, sprite.get_rect(center=(int(cx), int(cy))))
            return
        if dark:
            q = self.small_font.render("?", True, (70, 80, 95))
            surface.blit(q, q.get_rect(center=(int(cx), int(cy))))
            return
        h = box / 2
        pts = [(cx, cy - h), (cx + h * .8, cy + h), (cx, cy + h * .45), (cx - h * .8, cy + h)]
        pygame.draw.polygon(surface, self.ship_accent(idx), pts)

    def draw_player(self):
        sprite = self.ship_sprite(self.ship_index, self.player.width, self.player.height)
        if sprite is None:                      # no ship images found: use the Player's own drawing
            self.player.draw(self.screen)
            return
        if not self.player.visible:             # blinking after a hit
            return
        cx, cy = self.player_center()
        if self.SHOW_THRUSTER:
            self.draw_thruster(cx, self.player.y + self.player.height - 6)
        self.screen.blit(sprite, sprite.get_rect(center=(cx, cy)))

    def draw_thruster(self, cx, bottom):
        length = 14 + random.randint(0, 7)
        if self.game_state == "level_clear":
            length += abs(self.ship_vy) * 3
        w = max(6, self.player.width // 7)
        pygame.draw.polygon(self.screen, (235, 110, 40),
                            [(cx - w, bottom), (cx + w, bottom), (cx, bottom + length)])
        pygame.draw.polygon(self.screen, (255, 225, 140),
                            [(cx - w // 2, bottom), (cx + w // 2, bottom), (cx, bottom + length * 0.6)])

    # ------------------------------------------------------------ cached visuals
    def build_hud_surface(self):
        surf = pygame.Surface((self.screen_width, 58))
        for y in range(58):
            k = y / 57
            pygame.draw.line(surf, (int(12 - 6 * k), int(22 - 11 * k), int(34 - 16 * k)), (0, y), (self.screen_width, y))
        return surf

    def build_vignette(self):
        w, h = self.screen_width, self.screen_height
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        steps = 70
        for i in range(steps):
            alpha = int(95 * (1 - i / steps) ** 2.2)
            pygame.draw.rect(surf, (0, 0, 0, alpha), (i, i, w - 2 * i, h - 2 * i), 1)
        return surf

    def create_buttons(self):
        cx, cy = self.screen_width // 2, self.screen_height // 2
        self.reload_button_rect = pygame.Rect(cx - 120, cy + 65, 240, 52)
        self.menu_button_rect = pygame.Rect(cx - 120, cy + 130, 240, 48)
        self.pause_button_rect = pygame.Rect(self.screen_width - 125, 12, 105, 42)
        self.fire_radius = 50
        self.fire_center = (self.screen_width - self.fire_radius - 22, self.screen_height - self.fire_radius - 22)

        # --- pause screen layout (HUD style): banner on top, menu box below ---
        self.pause_banner_rect = pygame.Rect(cx - 150, cy - 150, 300, 64)
        item_h, item_w = 46, 190
        self.pause_panel_rect = pygame.Rect(cx - 115, self.pause_banner_rect.bottom + 14, 230, item_h * 4 + 32)
        y0 = self.pause_panel_rect.y + 16
        ix = cx - item_w // 2
        self.resume_button_rect = pygame.Rect(ix, y0, item_w, item_h - 6)
        self.restart_button_rect = pygame.Rect(ix, y0 + item_h, item_w, item_h - 6)
        self.pause_menu_button_rect = pygame.Rect(ix, y0 + item_h * 2, item_w, item_h - 6)
        self.quit_button_rect = pygame.Rect(ix, y0 + item_h * 3, item_w, item_h - 6)

        # left / right buttons: lower-left corner (fire button stays lower-right)
        bs = 70
        self.left_button_rect = pygame.Rect(22, self.screen_height - bs - 22, bs, bs)
        self.right_button_rect = pygame.Rect(22 + bs + 16, self.screen_height - bs - 22, bs, bs)
        # small toggle under the pause button
        self.toggle_button_rect = pygame.Rect(self.screen_width - 125, 64, 105, 26)

    def reset_game(self):
        self.ship_index = 0
        self.max_player_health = self.BASE_HEALTH
        self.player = Player(self.screen_width, self.screen_height)
        self.player.max_health = self.max_player_health
        self.player.health = self.player.max_health
        self.buttons = MobileButtons()
        self.hide_native_fire()
        self.warp = 0.0
        self.bullets.clear()
        self.enemy_bullets.clear()
        self.enemies = []
        self.powerups = []
        self.bonus_shots = []
        self.effects = {"rapid": 0, "spread": 0, "shield": 0}
        self.rapid_timer = 0
        self.rapid_side = 1
        self.invuln_timer = 0
        self.respawn_timer = 0
        self.respawn_y = self.screen_height - 100
        self.clear_timer = 0
        self.ship_vy = 0.0
        self.enter_timer = 0
        self.pending = []
        self.reserve = 0
        self.form_count = 1
        self.shake = 0.0
        self.score = 0
        self.wave = 1
        self.lives = 3
        self.game_state = "playing"
        self.player_history = []
        self.timer = 0
        self.state_timer = 0
        self.flash_timer = 0
        self.hit_timer = 0
        self.score_saved = False
        self.reward_timer = 0
        self.reward_bonus = False
        self.reward_sparks = []
        self.spawn_enemies()

    FORMATIONS = ("grid", "staggered", "chevron", "pyramid", "zigzag", "split", "arch", "diamond")

    def formation_slots(self, rows, cols):
        """Slot centres (cx, y), row by row, for this wave. The formation changes every wave."""
        name = self.FORMATIONS[(self.wave - 1) % len(self.FORMATIONS)]
        spacing = min(120, (self.screen_width - 120) / cols)
        gap = 84 if rows <= 4 else 72
        mid_c = (cols - 1) / 2
        mid_r = (rows - 1) / 2
        slots = []
        for r in range(rows):
            for c in range(cols):
                dx = (c - mid_c) * spacing
                y = 92 + r * gap
                edge = abs(c - mid_c) / max(1, mid_c)          # 0 centre .. 1 outer column
                if name == "staggered":
                    dx += (r % 2) * spacing / 2 - spacing / 4
                elif name == "chevron":
                    y += abs(c - mid_c) * 20
                elif name == "pyramid":
                    dx *= 0.5 + 0.5 * (r / max(1, rows - 1))
                elif name == "zigzag":
                    y += (c % 2) * 38
                elif name == "split":
                    dx += 34 if c > mid_c else (-34 if c < mid_c else 0)
                elif name == "arch":
                    y += 36 * edge * edge
                elif name == "diamond":
                    dx *= 1.0 - 0.3 * abs(r - mid_r) / max(0.5, mid_r)
                slots.append((self.screen_width / 2 + dx, y))
        return slots

    def spawn_enemies(self):
        self.enemies.clear()
        self.boss_active = False
        rows = min(1 + self.wave, 5)        # wave 1 = 2 lines, +1 line each wave (max 5)
        cols = 5
        slots = self.formation_slots(rows, cols)
        self.form_count = rows * cols
        self.reserve = self.form_count // self.REINFORCE_DIV    # replacements for enemies that die
        self.pending = []
        for r in range(rows):
            for c in range(cols):
                i = r * cols + c
                # from wave 3 the top row gets power enemies; from wave 6 a second row too
                power = self.wave >= 3 and ((r == 0 and c % 2 == 0) or
                                            (self.wave >= 6 and r == 1 and c % 2 == 1))
                cx, y = slots[i]
                self.enemies.append(self.make_enemy("power" if power else "normal", i, cx, y, r))

        # Boss is NOT spawned with the normal enemies. It appears only after
        # every regular enemy in this wave has been destroyed.
        self.enemy_bullets.clear()
        self.timer = 0
        self.wave_delay = self.WAVE_DELAY     # enemies hold back while the banner shows
        self.boss_warning = -1

    def spawn_boss(self):
        if self.boss_active: return
        self.boss_active = True
        boss = Enemy(0, 1, self.screen_width, "boss")
        boss.wave = self.wave
        boss.variant = (self.wave // 3 - 1) % 3     # cycles the 3 attack patterns, one per boss
        # wave 3 and every wave after it: the boss is enemy1.png
        boss.sprite_file = "assets/images/enemy1.png" if self.wave >= 3 else "assets/images/enemy.png"
        boss.max_health = boss.health = 30 + self.wave * 8
        boss.speed = min(2.0 + self.wave * .08, 3.5)
        boss.shoot_delay = max(320, 700 - self.wave * 25)
        boss.target_mid_y = 55
        self.enemies.append(boss)
        self.enemy_bullets.clear()
        self.shake = max(self.shake, 3.0)
        play("boss")

    def create_particle(self, x, y, color=None, count=12):
        color = color or self.CYAN
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(1, 5)
            self.particles.append([x, y, math.cos(angle) * speed, math.sin(angle) * speed, random.randint(10, 28), color])

    def update_particles(self):
        for p in self.particles[:]:
            p[0] += p[2]
            p[1] += p[3]
            p[4] -= 1
            if p[4] <= 0:
                self.particles.remove(p)

    def update_background(self):
        if self.game_state == "paused":
            return
        self.background_time += 1

        # target speed: hyperspace while the ship leaves after a boss, easing back down on the next wave
        state = self.game_state
        if state == "level_clear":
            target = 1.0 if self.clear_timer > 45 else 0.25
        elif state == "ship_reward":
            target = 0.8
        elif state == "entering":
            target = 0.4
        elif self.boss_warning > 0:
            target = 0.12
        else:
            target = 0.0
        self.warp += (target - self.warp) * (0.06 if target > self.warp else 0.025)
        if abs(self.warp - target) < 0.003:
            self.warp = target

        mult = 1.0 + self.warp * 14
        self.bg_scroll = (self.bg_scroll + 0.5 + self.warp * 18) % (self.screen_height * 2)
        for star in self.stars:
            star[1] += star[2] * mult
            if star[1] >= self.screen_height:
                star[0] = random.randint(0, self.screen_width)
                star[1] = -random.randint(0, 20)
        if self.warp > 0.05:
            for ln in self.speed_lines:
                ln[1] += ln[3] * (6 + self.warp * 40)
                if ln[1] - ln[2] > self.screen_height:
                    ln[0] = random.randint(0, self.screen_width)
                    ln[1] = -random.randint(0, 60)

    def get_attack_delay(self):
        return max(45, 155 - self.wave * 6)

    def player_center(self):
        return (self.player.x + self.player.width // 2, self.player.y + self.player.height // 2)

    # ------------------------------------------------------------ update
    def update(self, events):
        self.update_background()
        self.update_particles()
        self.player.update_blink()

        if self.flash_timer > 0: self.flash_timer -= 1
        if self.hit_timer > 0: self.hit_timer -= 1

        state = self.game_state          # state at the start of the frame

        if state == "playing":
            self.player_history.append((self.player.x, self.player.y))
            if len(self.player_history) > 60:
                self.player_history.pop(0)
            self.handle_input(events)

        if state in self.WORLD_STATES:
            self.update_world()

        elif state == "ship_reward":
            self.update_reward(events)

        elif state == "paused":
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_p, pygame.K_ESCAPE): self.game_state = "playing"
                    elif event.key == pygame.K_r: self.reset_game()
                    elif event.key == pygame.K_q: return "quit"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.resume_button_rect.collidepoint(event.pos): self.game_state = "playing"
                    elif self.restart_button_rect.collidepoint(event.pos): self.reset_game()
                    elif self.pause_menu_button_rect.collidepoint(event.pos): return "menu"
                    elif self.quit_button_rect.collidepoint(event.pos): return "quit"

        elif state == "game_over":
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r: self.reset_game()
                    elif event.key == pygame.K_ESCAPE: return "menu"
                    elif event.key == pygame.K_q: return "quit"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.reload_button_rect.collidepoint(event.pos): self.reset_game()
                    elif self.menu_button_rect.collidepoint(event.pos): return "menu"

        self.draw()
        return None

    def handle_input(self, events):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]: self.player.move_left()
        if keys[pygame.K_RIGHT]: self.player.move_right()

        self.hide_native_fire()
        mouse_down = pygame.mouse.get_pressed()[0]
        mouse_pos = pygame.mouse.get_pos()
        if self.show_controls and mouse_down:
            if self.left_button_rect.collidepoint(mouse_pos): self.player.move_left()
            elif self.right_button_rect.collidepoint(mouse_pos): self.player.move_right()
        self.fire_held = bool(keys[pygame.K_SPACE] or (self.show_controls and mouse_down and self.fire_button_hit(mouse_pos)))

        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.fire_held = True
                elif event.key in (pygame.K_p, pygame.K_ESCAPE):
                    self.game_state = "paused"
            elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                self.fire_held = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.pause_button_rect.collidepoint(event.pos):
                    self.game_state = "paused"
                elif self.toggle_button_rect.collidepoint(event.pos):
                    self.show_controls = not self.show_controls

        # RAPID CONTINUOUS FIRE
        if self.fire_held:
            self.fire_player()

        self.player.keep_inside_screen()

    def fire_player(self):
        px = self.player.x + self.player.width // 2
        py = self.player.y - 10
        if self.bullets.shoot(px - 9, py):
            play("bullet_fire")
            if self.effects["spread"] > 0:
                for vx in (-2.4, 2.4):
                    self.bonus_shots.append(PlayerShot(px, py, vx, -10.5, 1, (130, 235, 140), BULLET_STYLES[self.ship_index]))
        if self.effects["rapid"] > 0:
            self.rapid_timer -= 1
            if self.rapid_timer <= 0:
                self.rapid_timer = 5
                self.rapid_side = -self.rapid_side
                self.bonus_shots.append(PlayerShot(px + 12 * self.rapid_side, py + 6, 0.0, -12.0, 1, (255, 215, 110), BULLET_STYLES[self.ship_index]))

    def update_world(self):
        playing = self.game_state == "playing"

        if playing:                       # power-up timers only run while you are flying
            for k in self.effects:
                if self.effects[k] > 0:
                    self.effects[k] -= 1

        # invulnerability after a hit / respawn (ship stays fully controllable)
        if self.invuln_timer > 0:
            self.invuln_timer -= 1
            if self.invuln_timer == 0:
                self.player.is_blinking = False
                self.player.visible = True

        # respawn countdown
        if self.game_state == "respawning":
            self.respawn_timer -= 1
            if self.respawn_timer <= 0:
                self.begin_enter()
        elif self.game_state == "level_clear":
            self.update_level_clear()
        elif self.game_state == "entering":
            self.update_entering()

        self.bullets.update()
        for s in self.bonus_shots:
            s.update()
        self.bonus_shots = [s for s in self.bonus_shots if s.is_active]

        # shake decays smoothly
        self.shake *= 0.92
        if self.shake < 0.3:
            self.shake = 0.0

        intro = self.wave_delay > 0
        if intro:
            self.wave_delay -= 1          # enemies wait offscreen during the wave banner
        else:
            self.timer += 1
            if self.timer >= self.get_attack_delay():
                waiting = [e for e in self.enemies if e.state == "waiting" and e.enemy_type != "boss"]
                if waiting and self.player_history:
                    enemy = random.choice(waiting)
                    target = self.player_history[0]
                    enemy.start_drop(*target)
                self.timer = 0

            # replacements fly in to fill the slots of enemies that died
            for item in self.pending:
                item[0] -= 1
            ready = [it for it in self.pending if it[0] <= 0]
            self.pending = [it for it in self.pending if it[0] > 0]
            for _, kind, idx, cx, y in ready:
                self.enemies.append(self.make_enemy(kind, idx, cx, y))

            target = self.player_center()
            bullets_before = len(self.enemy_bullets)
            for enemy in self.enemies:
                enemy.update(self.screen_width, self.enemy_bullets, target)
            if len(self.enemy_bullets) > bullets_before:
                play("enemy_bullet")

        for eb in self.enemy_bullets:
            eb.update()
        self.enemy_bullets = [b for b in self.enemy_bullets if b.is_active]

        pstate = self.game_state
        for p in self.powerups:
            p.update()
            if pstate == "level_clear" and self.clear_timer > 8:
                px, py = self.player_center()           # the ship scoops up the boss's drops
                p.x += (px - p.x) * 0.1
                p.y += (py - p.y) * 0.1
            if pstate in ("playing", "level_clear") and p.is_active and p.get_rect().colliderect(self.player.get_rect()):
                self.collect_powerup(p)
        self.powerups = [p for p in self.powerups if p.is_active]

        self.check_collisions()

        if self.game_state == "game_over":
            return

        living_regular = [e for e in self.enemies if e.is_alive and e.enemy_type != "boss"]
        living_boss = [e for e in self.enemies if e.is_alive and e.enemy_type == "boss"]
        if self.game_state not in ("playing", "respawning"):
            return
        cleared = not living_regular and not self.pending and self.reserve == 0
        if cleared and not self.boss_active and not intro:
            if self.wave % 3 != 0:
                self.next_wave()                            # bosses only on waves 3, 6, 9 ...
            elif self.boss_warning < 0:
                self.boss_warning = self.BOSS_WARNING      # start the warning
            else:
                self.boss_warning -= 1
                self.shake = max(self.shake, 2.5)           # soft rumble while it approaches
                if self.boss_warning == 0:
                    self.boss_warning = -1
                    self.spawn_boss()
        elif self.boss_active and not living_boss:
            self.start_level_clear()

    @property
    def level(self):
        return (self.wave - 1) // 3 + 1                     # waves 1-3 = level 1, 4-6 = level 2 ...

    def next_wave(self):
        self.wave += 1
        self.score += self.wave * 50
        self.bullets.new_wave(self.wave)
        self.spawn_enemies()

    def make_enemy(self, kind, index, cx, y, row=0):
        enemy = Enemy(index, self.form_count, self.screen_width, kind)
        enemy.slot_x = cx - enemy.width / 2
        enemy.slot_y = y
        enemy.x = enemy.slot_x
        enemy.y = -60 - row * 60            # each line flies in together
        enemy.formation_index = index
        enemy.slot_cx = cx
        enemy.wave = self.wave              # enemy bullets scale with the wave
        enemy.max_health = enemy.health = min(enemy.max_health + (self.wave - 1) // 3, 8)
        return enemy

    def queue_replacement(self, enemy):
        """A dead formation enemy is replaced by a new one flying into the same slot."""
        if self.reserve > 0 and getattr(enemy, "slot_cx", None) is not None:
            self.reserve -= 1
            self.pending.append([45, enemy.enemy_type, enemy.formation_index, enemy.slot_cx, enemy.slot_y])

    # ------------------------------------------------------------ level change
    def start_level_clear(self):
        """Boss down: the ship collects the drops, flies off the top, receives a new ship, next level begins."""
        self.game_state = "level_clear"
        self.clear_timer = 0
        self.ship_vy = 0.0
        self.enemy_bullets.clear()
        self.player.is_blinking = False
        self.player.visible = True
        self.invuln_timer = 0

    def update_level_clear(self):
        self.clear_timer += 1
        t = self.clear_timer
        target_x = self.screen_width // 2 - self.player.width // 2
        self.player.x = int(round(self.player.x + (target_x - self.player.x) * 0.08))
        if t > 45:
            self.ship_vy += 0.45                            # accelerates upward and leaves the screen
            self.player.y = int(self.player.y - self.ship_vy)
            if t % 2 == 0:
                self.particles.append([self.player.x + self.player.width // 2, self.player.y + self.player.height,
                                       random.uniform(-0.6, 0.6), random.uniform(2, 4), 14, self.ORANGE])
        if t >= self.CLEAR_FRAMES:
            for p in self.powerups:                         # anything the ship missed is collected
                if p.is_active:
                    self.collect_powerup(p)
            self.powerups = []
            self.next_wave()
            self.start_ship_reward()                        # boss reward: a new ship

    def begin_enter(self):
        """Ship flies in from below the screen (after a respawn or a level change)."""
        self.respawn_y = self.screen_height - 100
        self.player.x = self.screen_width // 2 - self.player.width // 2
        self.player.y = self.screen_height + 30
        self.player.visible = True
        self.player.is_blinking = True
        self.player.blink_timer = 0
        self.invuln_timer = self.RESPAWN_INVULN
        self.enter_timer = 0
        self.game_state = "entering"

    def update_entering(self):
        self.enter_timer += 1
        self.player.y = int(self.player.y + (self.respawn_y - self.player.y) * 0.12)
        if abs(self.respawn_y - self.player.y) <= 2 or self.enter_timer > 70:
            self.player.y = self.respawn_y
            self.game_state = "playing"

    # ------------------------------------------------------------ new ship reward
    def start_ship_reward(self):
        """Unlocks the next ship (Ship2..Ship5) and starts the 'NEW SHIP RECEIVED' animation."""
        self.reward_timer = 0
        self.reward_sparks = []
        self.player.is_blinking = False
        self.player.visible = False
        if self.ship_index < len(self.SHIPS) - 1:
            self.ship_index += 1
            self.reward_bonus = False
            self.max_player_health = min(self.MAX_HEALTH, self.BASE_HEALTH + self.ship_index)
            self.player.max_health = self.max_player_health
            self.player.health = self.player.max_health       # new ship = fully repaired hull
        else:
            self.reward_bonus = True                          # every ship already owned
            self.score += self.FLEET_BONUS
            self.player.health = self.player.max_health
        self.game_state = "ship_reward"

    def reward_center(self):
        """Screen position of the ship inside the reward card (for sparks)."""
        fit = self.reward_fit()
        return (self.screen_width // 2, int(self.screen_height // 2 - 35 * fit))

    def reward_fit(self):
        return min(1.0, (self.screen_height - 30) / 500)

    def update_reward(self, events):
        self.reward_timer += 1
        t = self.reward_timer
        cx, cy = self.reward_center()
        accent = self.ship_accent(self.ship_index)

        if t == 1:                                            # big burst when the card appears
            for _ in range(80):
                a = random.uniform(0, math.tau)
                s = random.uniform(2, 9)
                self.reward_sparks.append([cx, cy, math.cos(a) * s, math.sin(a) * s,
                                           random.randint(30, 70), random.choice((accent, self.WHITE, self.YELLOW))])
        if t % 2 == 0 and t < 170:                            # gentle trickle around the ship
            for _ in range(2):
                a = random.uniform(0, math.tau)
                self.reward_sparks.append([cx + math.cos(a) * 80, cy + math.sin(a) * 80,
                                           math.cos(a) * 0.8, math.sin(a) * 0.8 - 0.4,
                                           random.randint(25, 45), random.choice((accent, self.WHITE))])
        for s in self.reward_sparks:
            s[0] += s[2]
            s[1] += s[3]
            s[3] += 0.05
            s[4] -= 1
        self.reward_sparks = [s for s in self.reward_sparks if s[4] > 0]

        skip = False
        for event in events:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                skip = True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                skip = True
        if (skip and t >= self.REWARD_SKIP_AFTER) or t >= self.REWARD_FRAMES:
            self.reward_sparks = []
            self.begin_enter()

    # ------------------------------------------------------------ power-ups
    def collect_powerup(self, p):
        p.is_active = False
        self.create_particle(p.x, p.y, p.color, 10)
        if p.kind == "life":
            # heal the hull; if it is already full, restore a lost life instead
            if self.player.health < self.player.max_health:
                self.player.health = min(self.player.max_health, self.player.health + 3)
            elif self.lives < 3:
                self.lives += 1
        else:
            self.effects[p.kind] = p.duration       # picking up again refreshes the timer

    # ------------------------------------------------------------ combat
    def game_over(self):
        self.game_state = "game_over"
        if not self.score_saved:
            try: save_score(self.player_id, self.score)
            except Exception: pass
            self.score_saved = True

    def create_explosion(self, x, y, count=28):
        # Multi-ring particle explosion used for enemy/boss/player destruction.
        self.create_particle(x, y, self.ORANGE, count)
        self.create_particle(x, y, self.YELLOW, max(8, count//2))
        self.flash_timer = max(self.flash_timer, 8)

    def damage_enemy(self, enemy, damage=1):
        defeated = enemy.damage(damage)
        self.hit_timer = 7
        play("hit")
        self.create_particle(enemy.x + enemy.width // 2, enemy.y + enemy.height // 2, self.ORANGE, 8)
        if defeated:
            self.score += enemy.score + self.wave * 10
            self.create_explosion(enemy.x + enemy.width // 2, enemy.y + enemy.height // 2, 42 if enemy.enemy_type == "boss" else 24)
            play("explosion")
            self.bullets.enemy_destroyed()
            if enemy.enemy_type == "boss":
                self.score += 2500 + self.wave * 500
                self.shake = max(self.shake, 7.0)
                self.drop_boss_rewards(enemy)
            else:
                drop = roll_powerup(enemy)
                if drop:
                    self.powerups.append(drop)
                self.queue_replacement(enemy)

    def drop_boss_rewards(self, boss):
        """Power-ups scattered when a boss dies; 3 on wave 3, 5 on wave 6, 6 from wave 8 on."""
        n = min(2 + self.wave // 2, 6)
        cx = boss.x + boss.width / 2
        cy = boss.y + boss.height / 2
        kinds = list(POWERUPS)                      # rapid, spread, shield, life
        for i in range(n):
            kind = random.choices(kinds, weights=(4, 4, 3, 2))[0]
            p = PowerUp(cx + (i - (n - 1) / 2) * 46, cy + random.randint(-10, 10), kind)
            p.age = random.randint(0, 60)           # so they don't drift in sync
            p.vy = 1.5 + random.random() * 0.5
            self.powerups.append(p)

    def check_collisions(self):
        if self.game_state == "playing":
            player_rect = self.player.get_rect()
            hit = False
            for enemy in self.enemies:
                if enemy.is_alive and player_rect.colliderect(enemy.get_rect()):
                    if enemy.enemy_type != "boss":
                        self.damage_enemy(enemy, 99)     # ramming a regular enemy destroys it
                    self.damage_player(2)
                    hit = True
                    break
            if not hit:
                for eb in self.enemy_bullets:
                    if eb.is_active and eb.get_rect().colliderect(player_rect):
                        eb.is_active = False
                        self.damage_player(eb.damage)
                        break

        if self.game_state not in ("playing", "respawning"):
            return
        shots = list(self.bullets.get_active_bullets()) + self.bonus_shots
        for bullet in shots:
            if not bullet.is_active:
                continue
            for enemy in self.enemies:
                if enemy.is_alive and bullet.get_rect().colliderect(enemy.get_rect()):
                    bullet.is_active = False
                    self.damage_enemy(enemy, bullet.damage)
                    break

    def damage_player(self, amount=1):
        if self.game_state != "playing" or self.invuln_timer > 0:
            return

        # shield absorbs the hit (and loses some of its time)
        if self.effects["shield"] > 0:
            self.effects["shield"] = max(0, self.effects["shield"] - 90)
            self.invuln_timer = 20
            cx, cy = self.player_center()
            self.create_particle(cx, cy, (90, 200, 255), 8)
            return

        defeated = self.player.take_damage(amount)
        play("hit")
        cx, cy = self.player_center()
        if defeated:
            self.lives -= 1
            if self.lives <= 0:
                self.create_explosion(cx, cy, 40)
                self.game_over()
                return
            self.player.restore_health()
            self.start_respawn(cx, cy)
            return

        self.create_explosion(cx, cy, 14)
        # no frozen state: the ship stays controllable while it blinks
        self.invuln_timer = self.HIT_INVULN
        self.player.is_blinking = True
        self.player.blink_timer = 0
        self.player.visible = True

    def start_respawn(self, cx, cy):
        self.create_explosion(cx, cy, 40)
        self.enemy_bullets.clear()
        self.bullets.clear()
        self.bonus_shots.clear()
        self.effects = {"rapid": 0, "spread": 0, "shield": 0}
        self.player.is_blinking = False
        self.player.visible = False
        self.invuln_timer = 0
        self.respawn_timer = self.RESPAWN_FRAMES
        self.game_state = "respawning"

    # ------------------------------------------------------------ drawing
    def draw(self):
        self.draw_background()
        if self.game_state != "game_over":
            for p in self.powerups:
                p.draw(self.screen)
            if self.game_state not in ("respawning", "ship_reward"):
                self.draw_player()
                self.draw_shield()
            for enemy in self.enemies:
                enemy.draw(self.screen)
                self.draw_enemy_health(enemy)
            for eb in self.enemy_bullets:
                eb.draw(self.screen)
            if self.CUSTOM_BULLETS:
                self.draw_player_bullets()
            else:
                self.bullets.draw(self.screen)
            for s in self.bonus_shots:
                s.draw(self.screen)
            self.hide_native_fire()
            if self.show_controls:
                self.draw_move_buttons()
                self.draw_fire_button()
            self.draw_toggle_button()
            self.draw_particles()
            self.apply_shake()
        else:
            self.draw_particles()
        self.screen.blit(self.vignette, (0, 0))
        self.draw_hud()
        self.draw_effects()
        if self.game_state in self.WORLD_STATES:
            self.draw_banners()
        if self.game_state == "paused": self.draw_pause_screen()
        elif self.game_state == "game_over": self.draw_game_over()
        elif self.game_state == "ship_reward": self.draw_ship_reward()

    def hide_native_fire(self):
        """The old on-screen fire button is moved off-screen; GameManager draws its own in the corner."""
        fire = getattr(self.buttons, "fire", None)
        if isinstance(fire, pygame.Rect):
            fire.topleft = (-2000, -2000)

    def fire_button_hit(self, pos):
        dx, dy = pos[0] - self.fire_center[0], pos[1] - self.fire_center[1]
        return dx * dx + dy * dy <= self.fire_radius * self.fire_radius

    def draw_move_buttons(self):
        accent = self.ship_accent(self.ship_index)
        mouse_down = pygame.mouse.get_pressed()[0]
        pos = pygame.mouse.get_pos()
        for rect, direction in ((self.left_button_rect, -1), (self.right_button_rect, 1)):
            pressed = (mouse_down and rect.collidepoint(pos)) and self.game_state == "playing"
            hover = rect.collidepoint(pos)
            surf = pygame.Surface((rect.w + 16, rect.h + 16), pygame.SRCALPHA)
            r = pygame.Rect(8, 8, rect.w, rect.h)
            pygame.draw.rect(surf, accent + (70 if (pressed or hover) else 35,), r.inflate(10, 10), border_radius=18)
            pygame.draw.rect(surf, (8, 14, 22, 215), r, border_radius=14)
            if pressed:
                pygame.draw.rect(surf, accent + (95,), r.inflate(-10, -10), border_radius=10)
            pygame.draw.rect(surf, accent, r, 3, border_radius=14)
            cx, cy = r.center
            pygame.draw.polygon(surf, self.WHITE, [(cx + direction * 14, cy - 18), (cx + direction * 14, cy + 18), (cx - direction * 16, cy)])
            self.screen.blit(surf, (rect.x - 8, rect.y - 8))

    def draw_toggle_button(self):
        text = "BUTTONS: ON" if self.show_controls else "BUTTONS: OFF"
        fill = self.HUD_FILL if self.show_controls else (40, 14, 14)
        border = self.HUD_DIM if self.show_controls else self.HUD_RED
        self.draw_button(self.toggle_button_rect, text, fill, border, self.tiny_font, glow=False)

    def draw_fire_button(self):
        r = self.fire_radius
        accent = self.ship_accent(self.ship_index)
        pos = pygame.mouse.get_pos()
        pressed = self.fire_held and self.game_state == "playing"
        hover = self.fire_button_hit(pos)
        size = 2 * r + 24
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = (size // 2, size // 2)
        pygame.draw.circle(surf, accent + (70 if (pressed or hover) else 35,), c, r + (10 if pressed else 6))
        pygame.draw.circle(surf, (8, 14, 22, 215), c, r)
        if pressed:
            pygame.draw.circle(surf, accent + (95,), c, r - 5)
        pygame.draw.circle(surf, accent, c, r, 3)
        pygame.draw.circle(surf, accent + (120,), c, r - 8, 1)
        icon = pygame.Rect(0, 0, 12, 30)
        icon.center = (c[0], c[1] - 9)
        draw_bullet(surf, icon, BULLET_STYLES[self.ship_index], accent)
        label = self.small_font.render("FIRE", True, self.WHITE)
        surf.blit(label, label.get_rect(center=(c[0], c[1] + 28)))
        self.screen.blit(surf, surf.get_rect(center=self.fire_center))

    def draw_player_bullets(self):
        """Main-gun bullets drawn with the current ship's design and colour."""
        style = BULLET_STYLES[self.ship_index]
        color = self.ship_accent(self.ship_index)
        for b in list(self.bullets.get_active_bullets()):
            if b.is_active:
                draw_bullet(self.screen, b.get_rect(), style, color)

    def apply_shake(self):
        if self.shake < 0.3 or self.game_state not in self.WORLD_STATES:
            return
        amp = int(round(self.shake))
        dx, dy = random.randint(-amp, amp), random.randint(-amp, amp)
        snap = self.screen.copy()
        self.screen.blit(snap, (dx, dy))

    def draw_banners(self):
        cx = self.screen_width // 2
        if self.wave_delay > 0:
            total = self.WAVE_DELAY
            t = self.wave_delay
            fade = max(0.0, min(1.0, (total - t) / 20, t / 25))     # fade in, hold, fade out
            title = self.big_font.render(f"WAVE {self.wave}", True, self.YELLOW)
            if (self.wave - 1) % 3 == 0:
                sub_text = f"LEVEL {self.level}"
            elif self.wave % 3 == 0:
                sub_text = "BOSS WAVE"
            else:
                sub_text = "GET READY"
            sub = self.medium_font.render(sub_text, True, self.WHITE)
            title.set_alpha(int(255 * fade))
            sub.set_alpha(int(200 * fade))
            y = self.screen_height // 3
            self.screen.blit(title, title.get_rect(center=(cx, y)))
            self.screen.blit(sub, sub.get_rect(center=(cx, y + 48)))
            line = pygame.Surface((220, 2), pygame.SRCALPHA)
            line.fill((245, 205, 70, int(190 * fade)))
            self.screen.blit(line, (cx - 110, y + 70))
        elif self.game_state == "level_clear":
            t = self.clear_timer
            fade = max(0.0, min(1.0, t / 20, (self.CLEAR_FRAMES - t) / 25))
            title = self.big_font.render("LEVEL CLEARED", True, self.GREEN)
            sub = self.medium_font.render(f"NEXT: LEVEL {self.level + 1}", True, self.WHITE)
            if self.ship_index < len(self.SHIPS) - 1:
                tag = self.small_font.render("A NEW SHIP IS WAITING FOR YOU", True, self.YELLOW)
            else:
                tag = self.small_font.render("FLEET COMPLETE BONUS INCOMING", True, self.YELLOW)
            title.set_alpha(int(255 * fade))
            sub.set_alpha(int(200 * fade))
            tag.set_alpha(int(230 * fade))
            y = self.screen_height // 3
            self.screen.blit(title, title.get_rect(center=(cx, y)))
            self.screen.blit(sub, sub.get_rect(center=(cx, y + 48)))
            self.screen.blit(tag, tag.get_rect(center=(cx, y + 80)))
        elif self.boss_warning > 0:
            pulse = 0.6 + 0.4 * math.sin(self.background_time * 0.18)
            title = self.big_font.render("WARNING", True, self.RED)
            sub = self.medium_font.render("BOSS APPROACHING", True, self.WHITE)
            title.set_alpha(int(255 * pulse))
            sub.set_alpha(int(220 * pulse))
            y = self.screen_height // 3
            self.screen.blit(title, title.get_rect(center=(cx, y)))
            self.screen.blit(sub, sub.get_rect(center=(cx, y + 48)))
            line = pygame.Surface((300, 2), pygame.SRCALPHA)
            line.fill((235, 75, 90, int(200 * pulse)))
            self.screen.blit(line, (cx - 150, y - 42))
            self.screen.blit(line, (cx - 150, y + 72))

    # --- reward animation ---------------------------------------------------
    @staticmethod
    def ease_out_back(x):
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

    @staticmethod
    def blit_fade(dest, surf, center, t, start, dur=14, slide=12):
        """Fades + slides a freshly rendered surface in once t passes `start`."""
        p = max(0.0, min(1.0, (t - start) / dur))
        if p <= 0:
            return
        surf.set_alpha(int(255 * p))
        dest.blit(surf, surf.get_rect(center=(center[0], center[1] + int((1 - p) * slide))))

    def draw_ship_slot(self, surface, rect, idx, unlocked, current, pulse=0.0):
        accent = self.ship_accent(idx)
        pygame.draw.rect(surface, (18, 30, 42, 255) if unlocked else (12, 16, 22, 255), rect, border_radius=9)
        if unlocked:
            if current:
                glow = rect.inflate(int(6 + 6 * pulse), int(6 + 6 * pulse))
                pygame.draw.rect(surface, accent, glow, 1, border_radius=11)
            pygame.draw.rect(surface, accent, rect, 3 if current else 1, border_radius=9)
        else:
            pygame.draw.rect(surface, (45, 55, 65), rect, 1, border_radius=9)
        self.draw_ship_art(surface, idx, rect.center, rect.height - 12, dark=not unlocked)

    def draw_ship_reward(self):
        W, H = self.screen_width, self.screen_height
        t = self.reward_timer
        a = max(0.0, min(1.0, t / 18, (self.REWARD_FRAMES - t) / 18))
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((2, 5, 12, int(205 * a)))
        self.screen.blit(overlay, (0, 0))

        idx = self.ship_index
        accent = self.ship_accent(idx)
        cw, ch = 460, 500
        card = pygame.Surface((cw, ch), pygame.SRCALPHA)
        pygame.draw.rect(card, (8, 13, 22, 245), (0, 0, cw, ch), border_radius=18)

        # rotating light rays + glow + expanding ring (drawn on a clean layer, then blended)
        rcx, rcy = cw // 2, 215
        fx = pygame.Surface((cw, ch), pygame.SRCALPHA)
        rot = t * 0.012
        for i in range(12):
            a0 = rot + i * math.tau / 12
            a1 = a0 + math.tau / 26
            pts = [(rcx, rcy),
                   (rcx + math.cos(a0) * 165, rcy + math.sin(a0) * 165),
                   (rcx + math.cos(a1) * 165, rcy + math.sin(a1) * 165)]
            pygame.draw.polygon(fx, accent + (38,), pts)
        pygame.draw.circle(fx, accent + (34,), (rcx, rcy), 105)
        pygame.draw.circle(fx, accent + (40,), (rcx, rcy), 78)
        phase = (t % 70) / 70
        pygame.draw.circle(fx, accent + (int(170 * (1 - phase)),), (rcx, rcy), int(70 + phase * 85), 2)
        card.blit(fx, (0, 0))

        # frame
        pygame.draw.rect(card, accent, (0, 0, cw, ch), 2, border_radius=18)
        pygame.draw.line(card, accent, (40, 68), (cw - 40, 68), 1)

        # title
        title_text = "FLEET COMPLETE" if self.reward_bonus else "NEW SHIP RECEIVED"
        title = self.title_font.render(title_text, True, self.YELLOW)
        self.blit_fade(card, title, (cw // 2, 40), t, 8)

        # the ship: pops in with an overshoot, then hovers
        p = max(0.0, min(1.0, (t - 8) / 32))
        if p > 0:
            k = max(0.05, self.ease_out_back(p))
            base = self.ship_sprite(idx, 160, 160)
            bob = math.sin(t * 0.08) * 6
            if base is not None:
                w, h = base.get_size()
                spr = pygame.transform.smoothscale(base, (max(1, int(w * k)), max(1, int(h * k)))) if p < 1 else base
                card.blit(spr, spr.get_rect(center=(rcx, int(rcy + bob))))
            else:
                self.draw_ship_art(card, idx, (rcx, int(rcy + bob)), int(150 * k))

        # name, counter, perk
        if self.reward_bonus:
            name_text, count_text, perk_text = "ALL 5 SHIPS UNLOCKED", f"FLYING: {self.SHIPS[idx]}", f"+{self.FLEET_BONUS:,} BONUS SCORE"
        else:
            name_text, count_text = self.SHIPS[idx], f"SHIP {idx + 1} / {len(self.SHIPS)}"
            perk_text = "+1 MAX HULL   /   FULL REPAIR"
        self.blit_fade(card, self.title_font.render(name_text, True, self.WHITE), (cw // 2, 332), t, 36)
        self.blit_fade(card, self.small_font.render(count_text, True, (150, 165, 175)), (cw // 2, 360), t, 44)
        self.blit_fade(card, self.medium_font.render(perk_text, True, self.GREEN), (cw // 2, 386), t, 54)

        # this ship's shot design, shown on both sides of the ship
        if t >= 60:
            for sx in (rcx - 128, rcx + 128):
                r = pygame.Rect(0, 0, 12, 28)
                r.center = (sx, int(rcy + math.sin(t * 0.1) * 4))
                draw_bullet(card, r, BULLET_STYLES[idx], accent)
                lab = self.tiny_font.render("NEW SHOT", True, (150, 165, 175))
                card.blit(lab, lab.get_rect(center=(sx, rcy + 34)))

        # fleet row
        row = pygame.Surface((cw, 62), pygame.SRCALPHA)
        slot, gap = 52, 12
        x0 = (cw - (slot * 5 + gap * 4)) // 2
        pulse = 0.5 + 0.5 * math.sin(t * 0.15)
        for i in range(5):
            r = pygame.Rect(x0 + i * (slot + gap), 5, slot, slot)
            self.draw_ship_slot(row, r, i, i <= idx, i == idx and not self.reward_bonus, pulse)
        pr = max(0.0, min(1.0, (t - 66) / 16))
        if pr > 0:
            row.set_alpha(int(255 * pr))
            card.blit(row, (0, 412))

        # hint
        if t >= self.REWARD_SKIP_AFTER and (t // 25) % 2 == 0:
            hint = self.small_font.render("PRESS SPACE TO CONTINUE", True, (170, 185, 195))
            card.blit(hint, hint.get_rect(center=(cw // 2, 482)))

        # scale-in of the whole card
        ep = max(0.0, min(1.0, t / 28))
        k = max(0.05, self.ease_out_back(ep)) * self.reward_fit()
        card.set_alpha(int(255 * a))
        if abs(k - 1.0) > 0.001:
            card = pygame.transform.smoothscale(card, (max(1, int(cw * k)), max(1, int(ch * k))))
            card.set_alpha(int(255 * a))
        self.screen.blit(card, card.get_rect(center=(W // 2, H // 2)))

        # sparks on top
        for s in self.reward_sparks:
            pygame.draw.circle(self.screen, s[5], (int(s[0]), int(s[1])), max(1, min(4, s[4] // 9)))

    # --- other drawing ------------------------------------------------------
    def draw_shield(self):
        t = self.effects["shield"]
        if t <= 0:
            return
        if t < 90 and (t // 6) % 2:          # gentle warning blink when it is about to end
            return
        cx, cy = self.player_center()
        r = max(self.player.width, self.player.height) // 2 + 10
        pulse = 0.5 + 0.5 * math.sin(self.background_time * 0.1)
        surf = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
        c = (r + 3, r + 3)
        pygame.draw.circle(surf, (90, 200, 255, 28 + int(18 * pulse)), c, r)
        pygame.draw.circle(surf, (140, 220, 255, 150), c, r, 2)
        self.screen.blit(surf, (cx - r - 3, cy - r - 3))

    def draw_background(self):
        H = self.screen_height
        if self.bg_tile:
            y = int(self.bg_scroll)
            self.screen.blit(self.bg_tile, (0, y - 2 * H))
            self.screen.blit(self.bg_tile, (0, y))
        else:
            for y in range(H):
                ratio = y / max(1, H)
                pygame.draw.line(self.screen, (3 + int(ratio * 4), 7 + int(ratio * 8), 18 + int(ratio * 20)), (0, y), (self.screen_width, y))

        # hyperspace tint + speed lines while warping
        if self.warp > 0.2:
            accent = self.ship_accent(self.ship_index)
            k = min(1.0, (self.warp - 0.2) / 0.8)
            for x, y, length, spd in self.speed_lines:
                col = tuple(int(c * 0.55 * k) for c in accent)
                pygame.draw.line(self.screen, col, (int(x), int(y)), (int(x), int(y - length * spd * (0.5 + self.warp))), 1)

        # twinkling stars: faster stars are brighter, and stretch into streaks when warping
        mult = 1.0 + self.warp * 14
        for i, (x, y, speed, size) in enumerate(self.stars):
            tw = 0.75 + 0.25 * math.sin(self.background_time * 0.07 + i)
            b = int((95 + 55 * (speed / 2)) * tw)
            col = (b, min(255, b + 20), min(255, b + 40))
            if self.warp > 0.12:
                length = int(speed * mult * 1.8)
                pygame.draw.line(self.screen, col, (int(x), int(y)), (int(x), int(y) - length), size)
            else:
                pygame.draw.circle(self.screen, col, (int(x), int(y)), size)

    def draw_particles(self):
        for p in self.particles:
            pygame.draw.circle(self.screen, p[5], (int(p[0]), int(p[1])), max(1, min(4, p[4] // 8)))

    def draw_enemy_health(self, enemy):
        if not enemy.is_alive or enemy.state == "offscreen": return
        bar_w = enemy.width
        bar_h = 6
        x, y = int(enemy.x), max(2, int(enemy.y - 10))
        pygame.draw.rect(self.screen, (35, 40, 45), (x, y, bar_w, bar_h), border_radius=3)
        ratio = max(0, min(1, enemy.health / max(1, enemy.max_health)))
        color = self.RED if enemy.enemy_type == "boss" else self.GREEN
        pygame.draw.rect(self.screen, color, (x, y, int(bar_w * ratio), bar_h), border_radius=3)
        pygame.draw.rect(self.screen, (90, 100, 110), (x, y, bar_w, bar_h), 1, border_radius=3)
        if enemy.enemy_type == "boss":
            label = self.tiny_font.render(f"BOSS  WAVE {self.wave}", True, self.RED)
            self.screen.blit(label, (x, y - 18))

    def draw_effects(self):
        """Small active power-up indicators under the HUD bar."""
        x, y = 15, 68
        for kind in ("rapid", "spread", "shield"):
            t = self.effects[kind]
            if t <= 0:
                continue
            spec = POWERUPS[kind]
            pygame.draw.circle(self.screen, tuple(int(c * 0.35) for c in spec["color"]), (x + 11, y + 11), 11)
            pygame.draw.circle(self.screen, spec["color"], (x + 11, y + 11), 11, 2)
            letter = self.tiny_font.render(spec["letter"], True, self.WHITE)
            self.screen.blit(letter, letter.get_rect(center=(x + 11, y + 11)))
            ratio = max(0.0, min(1.0, t / spec["duration"]))
            pygame.draw.rect(self.screen, (35, 40, 45), (x + 28, y + 9, 46, 4), border_radius=2)
            pygame.draw.rect(self.screen, spec["color"], (x + 28, y + 9, int(46 * ratio), 4), border_radius=2)
            x += 90

    def draw_hud(self):
        W = self.screen_width
        accent = self.ship_accent(self.ship_index)
        self.screen.blit(self.hud_surface, (0, 0))
        pygame.draw.line(self.screen, accent, (0, 57), (W, 57), 2)

        # current ship + score
        pygame.draw.rect(self.screen, (18, 30, 42), (10, 9, 40, 40), border_radius=8)
        pygame.draw.rect(self.screen, accent, (10, 9, 40, 40), 1, border_radius=8)
        self.draw_ship_art(self.screen, self.ship_index, (30, 29), 32)
        self.screen.blit(self.tiny_font.render("SCORE", True, (150, 165, 175)), (60, 6))
        self.screen.blit(self.font.render(f"{self.score:,}", True, self.WHITE), (60, 20))

        # wave / level
        wave = self.medium_font.render(f"WAVE {self.wave}", True, self.YELLOW)
        self.screen.blit(wave, wave.get_rect(center=(W // 2, 22)))
        lv = self.tiny_font.render(f"LEVEL {self.level}  /  {self.SHIPS[self.ship_index]}", True, (150, 165, 175))
        self.screen.blit(lv, lv.get_rect(center=(W // 2, 45)))

        # HP
        hud_x = W - 330
        self.screen.blit(self.small_font.render("HP", True, (190, 200, 205)), (hud_x, 7))
        bar = pygame.Rect(hud_x, 30, 80, 10)
        pygame.draw.rect(self.screen, (35, 40, 45), bar, border_radius=4)
        hp_ratio = self.player.health / max(1, self.player.max_health)
        pygame.draw.rect(self.screen, self.GREEN if hp_ratio > .4 else self.RED, (bar.x, bar.y, int(bar.w * hp_ratio), bar.h), border_radius=4)
        pygame.draw.rect(self.screen, (90, 105, 115), bar, 1, border_radius=4)
        self.screen.blit(self.tiny_font.render(f"{self.player.health}/{self.player.max_health}", True, self.WHITE), (hud_x + 85, 28))

        # lives (moved left so the pause button fits)
        self.screen.blit(self.small_font.render("LIVES", True, (150, 165, 175)), (W - 205, 7))
        for i in range(3):
            on = i < self.lives
            pygame.draw.circle(self.screen, self.RED if on else (40, 45, 50), (W - 195 + i * 22, 39), 7)
            if on:
                pygame.draw.circle(self.screen, (255, 150, 160), (W - 197 + i * 22, 37), 2)

        self.draw_pause_button()

    def draw_button(self, rect, text, fill, border, font=None, glow=True):
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if hover:
            fill = tuple(min(255, c + 24) for c in fill)
            if glow:
                pygame.draw.rect(self.screen, border, rect.inflate(8, 8), 1, border_radius=11)
        pygame.draw.rect(self.screen, fill, rect, border_radius=8)
        pygame.draw.rect(self.screen, border, rect, 2 if hover else 1, border_radius=8)
        t = (font or self.medium_font).render(text, True, self.WHITE)
        self.screen.blit(t, t.get_rect(center=rect.center))

    def draw_panel(self, rect, border, shadow=True):
        if shadow:
            sh = pygame.Surface((rect.w + 24, rect.h + 24), pygame.SRCALPHA)
            pygame.draw.rect(sh, (0, 0, 0, 90), sh.get_rect(), border_radius=22)
            self.screen.blit(sh, (rect.x - 12, rect.y - 4))
        pygame.draw.rect(self.screen, (8, 13, 20), rect, border_radius=14)
        pygame.draw.rect(self.screen, border, rect, 1, border_radius=14)
        pygame.draw.line(self.screen, border, (rect.x + 30, rect.y + 2), (rect.right - 30, rect.y + 2), 2)

    # --- HUD-style pause button + pause screen --------------------------------
    def draw_spaced(self, text, font, color, center, spacing=4):
        """Renders text with extra letter spacing (sci-fi look)."""
        glyphs = [font.render(ch, True, color) for ch in text]
        total = sum(g.get_width() for g in glyphs) + spacing * (len(glyphs) - 1)
        x = center[0] - total // 2
        for g in glyphs:
            self.screen.blit(g, g.get_rect(midleft=(x, center[1])))
            x += g.get_width() + spacing

    def draw_brackets(self, rect, color, ln=9, width=2):
        """Corner brackets around a rect (used for highlighted items)."""
        x, y, r, b = rect.left, rect.top, rect.right - 1, rect.bottom - 1
        for px, py, dx, dy in ((x, y, 1, 1), (r, y, -1, 1), (x, b, 1, -1), (r, b, -1, -1)):
            pygame.draw.line(self.screen, color, (px, py), (px + dx * ln, py), width)
            pygame.draw.line(self.screen, color, (px, py), (px, py + dy * ln), width)

    def draw_pause_button(self):
        """The PAUSE button in the top-right of the HUD."""
        rect = self.pause_button_rect
        hover = rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen, (40, 14, 14) if hover else self.HUD_FILL, rect)
        pygame.draw.rect(self.screen, self.HUD_RED if hover else self.HUD_DIM, rect, 1)
        self.draw_brackets(rect, self.HUD_RED, ln=8, width=2 if hover else 1)
        # small accent bars on the top and bottom edges, like the banner
        pygame.draw.rect(self.screen, self.HUD_RED, (rect.centerx - 8, rect.top - 1, 16, 3))
        pygame.draw.rect(self.screen, self.HUD_RED, (rect.centerx - 8, rect.bottom - 2, 16, 3))
        self.draw_spaced("PAUSE", self.small_font, self.WHITE, rect.center, 3)

    def draw_pause_screen(self):
        W, H = self.screen_width, self.screen_height
        cx = W // 2
        RED, DIM, FILL, TEXT = self.HUD_RED, self.HUD_DIM, self.HUD_FILL, self.HUD_TEXT

        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 205))
        self.screen.blit(overlay, (0, 0))

        banner = self.pause_banner_rect
        panel = self.pause_panel_rect
        mid = banner.center

        def diamond(c, hw, hh, col, width=1):
            pygame.draw.polygon(self.screen, col, [(c[0], c[1] - hh), (c[0] + hw, c[1]),
                                                   (c[0], c[1] + hh), (c[0] - hw, c[1])], width)

        # big nested diamonds behind everything
        diamond(mid, 143, 143, DIM)
        diamond(mid, 108, 108, DIM)

        # side wings: angled lines, end squares, diamond tips, dotted tick
        for s in (-1, 1):
            tip = (cx + s * 237, mid[1])
            for end_y in (mid[1] - 82, mid[1] + 82):
                end = (cx + s * 157, end_y)
                pygame.draw.line(self.screen, RED, tip, end, 1)
                pygame.draw.rect(self.screen, RED, (end[0] - 3, end[1] - 3, 6, 6))
            diamond(tip, 8, 8, RED)
            for d in (197, 187, 177):
                pygame.draw.circle(self.screen, RED, (cx + s * d, mid[1]), 1)
            pygame.draw.line(self.screen, RED, (cx + s * 160, mid[1]), (cx + s * 152, mid[1]), 1)
            pygame.draw.line(self.screen, RED, (cx + s * 152, mid[1] - 18), (cx + s * 152, mid[1] + 18), 1)

        # title banner
        pygame.draw.rect(self.screen, FILL, banner)
        pygame.draw.rect(self.screen, RED, banner, 1)
        diamond(mid, 110, 31, RED)
        pygame.draw.rect(self.screen, RED, (cx - 10, banner.top - 1, 20, 3))
        pygame.draw.rect(self.screen, RED, (cx - 10, banner.bottom - 2, 20, 3))
        for s, x in ((-1, banner.left), (1, banner.right)):
            wx = x if s == -1 else x - 36
            pygame.draw.rect(self.screen, RED, (wx, banner.bottom - 4, 36, 5))
            pygame.draw.rect(self.screen, RED, (x + (2 if s == -1 else -14), banner.top, 12, 6))
        self.draw_spaced("PAUSE", self.title_font, self.WHITE, mid, 7)

        # menu box
        pygame.draw.rect(self.screen, FILL, panel)
        pygame.draw.rect(self.screen, DIM, panel, 1)
        self.draw_brackets(panel, RED, ln=12, width=1)

        mouse = pygame.mouse.get_pos()
        items = ((self.resume_button_rect, "RESUME"),
                 (self.restart_button_rect, "RESTART"),
                 (self.pause_menu_button_rect, "MAIN MENU"),
                 (self.quit_button_rect, "EXIT GAME"))
        for rect, label in items:
            hover = rect.collidepoint(mouse)
            if hover:
                pygame.draw.rect(self.screen, (40, 14, 14), rect)
                self.draw_brackets(rect, RED)
            self.draw_spaced(label, self.small_font, self.WHITE if hover else TEXT, rect.center, 3)

    def draw_game_over(self):
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 210))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(self.screen_width // 2 - 220, self.screen_height // 2 - 205, 440, 420)
        self.draw_panel(panel, self.RED)
        cx = panel.centerx
        t = self.big_font.render("GAME OVER", True, self.RED)
        self.screen.blit(t, t.get_rect(center=(cx, panel.y + 55)))
        name = self.small_font.render(self.player_name, True, self.WHITE)
        self.screen.blit(name, name.get_rect(center=(cx, panel.y + 112)))
        s = self.font.render(f"{self.score:,}", True, self.YELLOW)
        self.screen.blit(s, s.get_rect(center=(cx, panel.y + 150)))
        w = self.small_font.render(f"WAVE {self.wave}   /   LEVEL {self.level}", True, self.CYAN)
        self.screen.blit(w, w.get_rect(center=(cx, panel.y + 185)))
        # ships collected
        slot, gap = 36, 10
        x0 = cx - (slot * 5 + gap * 4) // 2
        for i in range(5):
            r = pygame.Rect(x0 + i * (slot + gap), panel.y + 208, slot, slot)
            self.draw_ship_slot(self.screen, r, i, i <= self.ship_index, i == self.ship_index)
        self.draw_button(self.reload_button_rect, "PLAY AGAIN", (25, 95, 65), self.GREEN)
        self.draw_button(self.menu_button_rect, "MAIN MENU", (45, 55, 65), self.BLUE)

    def run(self):
        clock = pygame.time.Clock()
        while True:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    return "quit"
            result = self.update(events)
            pygame.display.flip()
            clock.tick(60)
            if result in ("menu", "quit"):
                return result