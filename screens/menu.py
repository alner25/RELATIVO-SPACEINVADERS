import os
import json
import math
import random
import struct

import pygame


class MenuScreen:

    # ==============================================================
    # MUSIC SETTINGS
    # ==============================================================

    MUSIC_NAME = "backgroundmusic1.mp3"

    MUSIC_PATHS = [
        "assets/audio/backgroundmusic1.mp3",
        "assets/sounds/backgroundmusic1.mp3",
        "assets/music/backgroundmusic1.mp3",
        "assets/backgroundmusic1.mp3",
        "backgroundmusic1.mp3",
    ]

    # Shared between instances so re-creating the menu does not
    # restart the song every time you come back from another screen.
    _current_track = None

    # ==============================================================
    # MENU ITEMS  (action, label)
    # Actions returned to your main loop: "game", "leaderboard",
    # "settings", "logout", "profile"   (unchanged from before)
    # "howto" opens the built-in How To Play window, "quit" closes
    # the game.
    # ==============================================================

    MENU_ITEMS = [
        ("game", "START MISSION"),
        ("howto", "HOW TO PLAY"),
        ("leaderboard", "LEADERBOARD"),
        ("settings", "SETTINGS"),
        ("logout", "LOG OUT"),
        ("quit", "QUIT"),
    ]

    TAGLINE = "DEFEND THE GALAXY"

    # How much bigger than the window the background is drawn,
    # so it has room to slowly drift around.
    PAN_SCALE = 1.12

    # Keys in the player dict that may hold the chosen spaceship
    SHIP_KEYS = (
        "ship", "ship_id", "selected_ship", "spaceship",
        "ship_image", "ship_choice", "avatar", "profile_picture",
    )

    SHIP_DIRS = (
        "", "assets", "assets/images", "assets/ships",
        "assets/images/ships", "images",
    )

    # Edit these if your in-game controls are different
    HOW_TO_PLAY_CONTROLS = [
        ("LEFT / RIGHT  or  A / D", "MOVE YOUR SHIP"),
        ("SPACE", "FIRE LASER"),
    ]

    HOW_TO_PLAY_TEXT = [
        "Destroy every invader before they reach Earth.",
        "Dodge enemy fire. Lose all your lives and the mission is over.",
        "Earn points for every kill and climb the leaderboard.",
    ]

    SERIF = "cinzel,trajanpro,palatinolinotype,georgia,timesnewroman"

    # 11 x 8 classic invader sprite
    ALIEN = [
        "..#.....#..",
        "...#...#...",
        "..#######..",
        ".##.###.##.",
        "###########",
        "#.#######.#",
        "#.#.....#.#",
        "...##.##...",
    ]

    def __init__(self, screen, width, height, player):

        self.screen = screen
        self.width = width
        self.height = height
        self.player = player if isinstance(player, dict) else {}

        # ==========================================================
        # COLORS
        # ==========================================================

        self.bg_color = (5, 4, 18)

        self.purple = (170, 70, 255)
        self.bright_purple = (210, 120, 255)
        self.deep_purple = (80, 25, 150)

        self.cyan = (0, 220, 255)
        self.white = (235, 235, 255)

        self.green = (0, 255, 150)
        self.red = (255, 80, 110)

        # ==========================================================
        # BACKGROUND (your existing bg3.png stays)
        # ==========================================================

        self.bg_raw = None
        self.bg_image = None

        self.load_background()

        # ==========================================================
        # MUSIC
        # ==========================================================

        self.start_music()

        # ==========================================================
        # STAR FIELD
        # ==========================================================

        self.stars = []

        for _ in range(130):

            self.stars.append({
                "x": random.randint(0, max(1, self.width)),
                "y": random.randint(0, max(1, self.height)),
                "speed": random.uniform(0.15, 0.8),
                "size": random.choice([1, 1, 1, 2]),
                "alpha": random.randint(80, 220)
            })

        # ==========================================================
        # STATE
        # ==========================================================

        self.time = 0.0
        self.selected = 0
        self.hover_button = None
        self.howto_open = False
        self._last_mouse = (-1, -1)
        self._cache = {}

        self._last_time = 0.0
        self.shooters = []
        self.next_shoot = 2.0
        self.blobs = []

        self.avatar_raw = None
        self.avatar = None
        self.avatar_size = 44
        self.rank_text = None

        self.init_sounds()
        self.load_avatar()
        self.load_rank()

        # Kept so other code that reads these attributes still works
        self.play_button = pygame.Rect(0, 0, 10, 10)
        self.profile_button = pygame.Rect(0, 0, 10, 10)
        self.leaderboard_button = pygame.Rect(0, 0, 10, 10)
        self.settings_button = pygame.Rect(0, 0, 10, 10)
        self.logout_button = pygame.Rect(0, 0, 10, 10)

        self.update_layout()

    # ==============================================================
    # MENU MUSIC
    # ==============================================================

    def start_music(self, volume=0.5):

        try:

            if not pygame.mixer.get_init():
                pygame.mixer.init()

        except pygame.error:
            return

        # Already playing? Let it continue without restarting.

        if (
            MenuScreen._current_track == self.MUSIC_NAME
            and pygame.mixer.music.get_busy()
        ):
            return

        for path in self.MUSIC_PATHS:

            if not os.path.exists(path):
                continue

            try:

                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(volume)
                pygame.mixer.music.play(-1)   # -1 = loop forever

                MenuScreen._current_track = self.MUSIC_NAME

                return

            except pygame.error:
                continue

        print(
            "Menu music not found. Put "
            + self.MUSIC_NAME
            + " in one of: "
            + ", ".join(self.MUSIC_PATHS)
        )

    # ==============================================================
    # SOUND EFFECTS (button click)
    # ==============================================================

    def init_sounds(self):

        self.click_sound = None
        self.tick_sound = None

        try:

            if not pygame.mixer.get_init():
                pygame.mixer.init()

        except pygame.error:
            return

        # Use your own click file if you have one...

        folders = ("assets/audio", "assets/sounds", "assets/sfx", "assets", "")
        names = ("click", "button_click", "menu_click", "select")
        exts = (".wav", ".ogg", ".mp3")

        for folder in folders:

            for name in names:

                for ext in exts:

                    path = os.path.join(folder, name + ext)

                    if self.click_sound is None and os.path.exists(path):

                        try:
                            self.click_sound = pygame.mixer.Sound(path)
                        except pygame.error:
                            pass

        # ...otherwise generate a short arcade-style blip

        if self.click_sound is None:
            self.click_sound = self.make_tone([(880, 0.045), (1320, 0.065)], 0.45)

        self.tick_sound = self.make_tone([(1000, 0.025)], 0.22)

    def make_tone(self, segments, volume):

        init = pygame.mixer.get_init()

        if not init:
            return None

        rate, fmt, channels = init

        if fmt != -16:
            return None

        data = bytearray()

        for freq, duration in segments:

            n = int(rate * duration)

            for i in range(n):

                envelope = (1 - i / n) ** 2

                value = int(
                    math.sin(2 * math.pi * freq * i / rate)
                    * envelope * volume * 32767
                )

                data += struct.pack("<h", value) * channels

        try:
            return pygame.mixer.Sound(buffer=bytes(data))
        except pygame.error:
            return None

    def get_sfx_volume(self):
        """Follows your settings.json if it has a sound-effects volume."""

        try:

            with open("settings.json", "r") as f:
                data = json.load(f)

        except Exception:
            return 1.0

        for key in (
            "sfx_volume", "sound_volume", "effects_volume",
            "sound_effects_volume", "sfx"
        ):

            if key in data:

                try:
                    value = float(data[key])
                except (TypeError, ValueError):
                    continue

                if value > 1:
                    value /= 100.0

                return max(0.0, min(1.0, value))

        return 1.0

    def play_click(self):

        if self.click_sound is None:
            return

        try:
            self.click_sound.set_volume(self.get_sfx_volume())
            self.click_sound.play()
        except pygame.error:
            pass

    def play_tick(self):

        if self.tick_sound is None:
            return

        try:
            self.tick_sound.set_volume(self.get_sfx_volume())
            self.tick_sound.play()
        except pygame.error:
            pass

    def set_selected(self, index):

        if index != self.selected:

            self.selected = index

            self.play_tick()

    # ==============================================================
    # PROFILE PHOTO (the ship chosen on the profile page)
    # ==============================================================

    def ship_candidates(self, value):

        names = []

        if isinstance(value, bool) or value is None:
            return names

        if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):

            names.append("Ship" + str(int(value)) + ".png")

        elif isinstance(value, str):

            v = value.strip()

            if v.lower().endswith((".png", ".jpg", ".jpeg")):
                names.extend([v, os.path.basename(v)])

            elif v.lower().startswith("ship"):
                names.append(v + ".png")

        return names

    def load_avatar(self):

        names = []

        for key in self.SHIP_KEYS:

            names = self.ship_candidates(self.player.get(key))

            if names:
                break

        if not names:
            names = ["Ship1.png"]

        for name in names:

            for folder in self.SHIP_DIRS:

                path = os.path.join(folder, name) if folder else name

                if not os.path.exists(path):
                    continue

                try:

                    self.avatar_raw = pygame.image.load(path).convert_alpha()

                    return

                except (pygame.error, OSError):
                    continue

    def scale_avatar(self, image, size):

        if image is None:
            return None

        iw, ih = image.get_size()

        side = min(iw, ih)

        crop = image.subsurface(
            ((iw - side) // 2, (ih - side) // 2, side, side)
        )

        return pygame.transform.smoothscale(crop, (size, size))

    # ==============================================================
    # PROFILE <-> LEADERBOARD LINK
    # ==============================================================

    def load_rank(self):
        """Looks the player up in the leaderboard so the badge shows
        their real rank and score."""

        self.rank_text = None

        try:

            import db

            rows = db.get_leaderboard()

            name = str(
                self.player.get("username")
                or self.player.get("player_name")
                or ""
            ).lower()

            if not name:
                return

            self.rank_text = "UNRANKED"

            for i, row in enumerate(rows):

                score = None

                if isinstance(row, dict):

                    rname = row.get(
                        "username",
                        row.get("player_name", row.get("name"))
                    )

                    score = row.get(
                        "score",
                        row.get("high_score", row.get("best_score"))
                    )

                elif isinstance(row, (list, tuple)) and row:

                    if isinstance(row[0], int) and len(row) > 2:
                        rname = row[1]
                        score = row[2]
                    else:
                        rname = row[0]
                        score = row[1] if len(row) > 1 else None

                else:
                    continue

                if str(rname).lower() == name:

                    self.rank_text = "RANK #" + str(i + 1)

                    if score is not None:
                        self.rank_text += "  " + str(score) + " PTS"

                    return

        except Exception:
            return

    def stop_music(self, fade_ms=500):

        try:
            pygame.mixer.music.fadeout(fade_ms)
        except pygame.error:
            pass

        MenuScreen._current_track = None

    # ==============================================================
    # BACKGROUND LOADING
    # ==============================================================

    def load_background(self):

        paths = [
            "assets/images/bg3.png",
            "assets/bg3.png",
            "bg3.png"
        ]

        for path in paths:

            try:

                self.bg_raw = pygame.image.load(path).convert()

                self.build_background()

                return

            except (
                pygame.error,
                FileNotFoundError,
                OSError
            ):
                continue

        self.bg_raw = None

        self.build_background()

    def build_background(self):
        """Scale the background once (slightly oversized so it can drift)."""

        self.bg_w = max(1, int(self.width * self.PAN_SCALE))
        self.bg_h = max(1, int(self.height * self.PAN_SCALE))

        if self.bg_raw is not None:

            self.bg_image = pygame.transform.smoothscale(
                self.bg_raw,
                (self.bg_w, self.bg_h)
            )

            return

        # Fallback background

        self.bg_image = pygame.Surface((self.bg_w, self.bg_h))

        self.bg_image.fill(self.bg_color)

        glow = pygame.Surface(
            (self.bg_w, self.bg_h),
            pygame.SRCALPHA
        )

        pygame.draw.circle(
            glow,
            (90, 20, 180, 80),
            (int(self.bg_w * 0.25), int(self.bg_h * 0.50)),
            280
        )

        pygame.draw.circle(
            glow,
            (20, 60, 180, 50),
            (int(self.bg_w * 0.80), int(self.bg_h * 0.35)),
            260
        )

        self.bg_image.blit(glow, (0, 0))

    # ==============================================================
    # RESPONSIVE LAYOUT
    # ==============================================================

    def update_layout(self):

        w = self.width
        h = self.height
        cx = w // 2

        self._cache = {}

        self.build_background()

        base = min(h, w * 0.75)

        # ----------------------------------------------------------
        # FONTS
        # ----------------------------------------------------------

        title_size = max(34, int(base * 0.115))
        sub_size = max(20, int(title_size * 0.52))
        menu_size = max(14, int(base * 0.034))

        self.title_font = pygame.font.SysFont(
            self.SERIF, title_size, bold=True
        )
        self.subtitle_font = pygame.font.SysFont(
            self.SERIF, sub_size, bold=False
        )
        self.menu_font = pygame.font.SysFont(
            self.SERIF, menu_size, bold=True
        )

        self.heading_font = pygame.font.SysFont("Consolas", 22, bold=True)
        self.font = pygame.font.SysFont("Consolas", 18, bold=True)
        self.small_font = pygame.font.SysFont("Consolas", 14, bold=True)
        self.tiny_font = pygame.font.SysFont("Consolas", 11)

        # ----------------------------------------------------------
        # TITLE BLOCK POSITIONS
        # ----------------------------------------------------------

        self.icon_cell = max(2, int(base * 0.007))
        self.icon_top = int(h * 0.05)

        icon_bottom = self.icon_top + 8 * self.icon_cell

        self.title_y = icon_bottom + 10

        title_h = self.title_font.get_height()

        self.divider_y = self.title_y + int(title_h * 0.98)

        self.sub_y = self.divider_y + 8

        sub_bottom = self.sub_y + self.subtitle_font.get_height()

        # ----------------------------------------------------------
        # MENU BUTTONS
        # ----------------------------------------------------------

        footer_h = 60
        count = len(self.MENU_ITEMS)
        gap = 6

        start_y = sub_bottom + max(18, int(h * 0.04))

        available = h - footer_h - start_y

        button_h = max(26, min(44, (available - gap * (count - 1)) // count))

        button_w = min(max(240, int(w * 0.34)), int(w * 0.92))

        button_x = cx - button_w // 2

        self.buttons = []

        for i, (action, label) in enumerate(self.MENU_ITEMS):

            rect = pygame.Rect(
                button_x,
                start_y + i * (button_h + gap),
                button_w,
                button_h
            )

            self.buttons.append((action, label, rect))

        # Legacy attribute aliases

        lookup = {a: r for a, _, r in self.buttons}

        self.play_button = lookup["game"]
        self.leaderboard_button = lookup["leaderboard"]
        self.settings_button = lookup["settings"]
        self.logout_button = lookup["logout"]

        # ----------------------------------------------------------
        # TOP-LEFT PLAYER BADGE  ->  PROFILE
        # ----------------------------------------------------------

        self.badge_rect = pygame.Rect(0, 0, 250, 62)

        self.profile_button = self.badge_rect

        self.avatar_size = self.badge_rect.height - 14
        self.avatar = self.scale_avatar(self.avatar_raw, self.avatar_size)

        # ----------------------------------------------------------
        # TOP-RIGHT ICON CLUSTER
        # ----------------------------------------------------------

        icon = 38
        pad = 10

        box_w = icon * 2 + pad * 3
        box_h = icon + pad * 2

        self.icon_box = pygame.Rect(w - box_w, 0, box_w, box_h)

        self.icon_rects = {}

        for i, action in enumerate(("settings", "leaderboard")):

            self.icon_rects[action] = pygame.Rect(
                self.icon_box.x + pad + i * (icon + pad),
                pad,
                icon,
                icon
            )

        # ----------------------------------------------------------
        # HOW TO PLAY WINDOW
        # ----------------------------------------------------------

        pw = min(600, int(w * 0.92))
        ph = min(430, int(h * 0.88))

        self.howto_rect = pygame.Rect(0, 0, pw, ph)
        self.howto_rect.center = (cx, h // 2)

        self.howto_back = pygame.Rect(0, 0, 170, 38)
        self.howto_back.midbottom = (
            self.howto_rect.centerx,
            self.howto_rect.bottom - 22
        )

        # ----------------------------------------------------------
        # VIGNETTE + SOFT DARK BAND BEHIND THE MENU
        # ----------------------------------------------------------

        self.vignette = self.make_vignette(w, h)

        self.overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        self.overlay.fill((3, 2, 15, 95))

        self.star_layer = pygame.Surface((w, h), pygame.SRCALPHA)

        radius = int(max(w, h) * 0.28)

        self.blobs = [
            {"surf": self.make_blob(radius, (130, 40, 255)),
             "fx": 0.22, "fy": 0.50, "speed": 0.35, "phase": 0.0},
            {"surf": self.make_blob(int(radius * 0.85), (0, 120, 255)),
             "fx": 0.82, "fy": 0.35, "speed": 0.28, "phase": 2.0},
            {"surf": self.make_blob(int(radius * 0.7), (200, 60, 200)),
             "fx": 0.55, "fy": 0.80, "speed": 0.22, "phase": 4.0},
        ]
        self.band = self.make_band(int(button_w * 2.1), h)

    def make_vignette(self, w, h):

        small = pygame.Surface((64, 64), pygame.SRCALPHA)

        for y in range(64):
            for x in range(64):

                dx = (x - 31.5) / 31.5
                dy = (y - 31.5) / 31.5

                d = math.sqrt(dx * dx + dy * dy)

                alpha = int(max(0, min(190, (d - 0.5) * 260)))

                small.set_at((x, y), (2, 1, 10, alpha))

        return pygame.transform.smoothscale(
            small, (max(1, w), max(1, h))
        )

    def make_band(self, band_w, h):

        small = pygame.Surface((64, 1), pygame.SRCALPHA)

        for x in range(64):

            t = abs((x - 31.5) / 31.5)

            alpha = int(120 * (1 - t) ** 0.8)

            small.set_at((x, 0), (3, 2, 14, alpha))

        return pygame.transform.smoothscale(
            small, (max(1, band_w), max(1, h))
        )

    def make_blob(self, radius, color):

        small = pygame.Surface((64, 64), pygame.SRCALPHA)

        for y in range(64):
            for x in range(64):

                dx = (x - 31.5) / 31.5
                dy = (y - 31.5) / 31.5

                d = math.sqrt(dx * dx + dy * dy)

                alpha = int(max(0.0, 1.0 - d) ** 1.6 * 80)

                small.set_at((x, y), (*color, alpha))

        return pygame.transform.smoothscale(
            small, (max(2, radius * 2), max(2, radius * 2))
        )

    # ==============================================================
    # TEXT HELPERS
    # ==============================================================

    def spaced(self, text, font, color, spacing):
        """Render text with extra letter spacing (cached)."""

        key = ("sp", text, id(font), color, spacing)

        if key in self._cache:
            return self._cache[key]

        glyphs = [font.render(ch, True, color) for ch in text]

        total_w = sum(g.get_width() for g in glyphs)
        total_w += spacing * max(0, len(text) - 1)

        surf = pygame.Surface(
            (max(1, total_w), font.get_height()),
            pygame.SRCALPHA
        )

        x = 0

        for g in glyphs:
            surf.blit(g, (x, 0))
            x += g.get_width() + spacing

        self._cache[key] = surf

        return surf

    def wrap_text(self, text, font, max_w):

        words = text.split(" ")
        lines = []
        line = ""

        for word in words:

            test = word if not line else line + " " + word

            if font.size(test)[0] <= max_w:
                line = test
            else:
                lines.append(line)
                line = word

        if line:
            lines.append(line)

        return lines

    def get_player_name(self):

        name = self.player.get(
            "player_name",
            self.player.get("username", "PLAYER")
        )

        if not name:
            name = "PLAYER"

        return str(name).upper()

    # ==============================================================
    # BACKGROUND
    # ==============================================================

    def draw_background(self):

        w, h = self.width, self.height

        dt = min(0.1, max(0.0, self.time - self._last_time))

        self._last_time = self.time

        # ----------------------------------------------------------
        # SLOWLY DRIFTING BACKGROUND IMAGE
        # ----------------------------------------------------------

        extra_x = self.bg_w - w
        extra_y = self.bg_h - h

        ox = int(extra_x * (0.5 + 0.5 * math.sin(self.time * 0.15)))
        oy = int(extra_y * (0.5 + 0.5 * math.cos(self.time * 0.11)))

        self.screen.blit(self.bg_image, (-ox, -oy))

        self.screen.blit(self.overlay, (0, 0))

        # ----------------------------------------------------------
        # FLOATING NEBULA GLOWS
        # ----------------------------------------------------------

        for b in self.blobs:

            x = w * b["fx"] + math.sin(self.time * b["speed"] + b["phase"]) * w * 0.08
            y = h * b["fy"] + math.cos(self.time * b["speed"] * 0.8 + b["phase"]) * h * 0.06

            b["surf"].set_alpha(int(150 + 90 * math.sin(self.time * 0.9 + b["phase"])))

            self.screen.blit(
                b["surf"],
                b["surf"].get_rect(center=(int(x), int(y)))
            )

        # ----------------------------------------------------------
        # MOVING STARS
        # ----------------------------------------------------------

        layer = self.star_layer

        layer.fill((0, 0, 0, 0))

        for star in self.stars:

            star["y"] += star["speed"]
            star["x"] += star["speed"] * 0.25

            if star["y"] > h:

                star["y"] = -5

                star["x"] = random.randint(0, max(1, w))

            if star["x"] > w:
                star["x"] = 0

            alpha = int(
                star["alpha"]
                * (
                    0.65
                    + 0.35 * math.sin(self.time * 2 + star["x"])
                )
            )

            pygame.draw.circle(
                layer,
                (170, 110, 255, max(30, alpha)),
                (int(star["x"]), int(star["y"])),
                star["size"]
            )

        # ----------------------------------------------------------
        # SHOOTING STARS
        # ----------------------------------------------------------

        if self.time >= self.next_shoot:

            self.next_shoot = self.time + random.uniform(2.5, 6.0)

            self.shooters.append({
                "x": random.randint(int(w * 0.2), w),
                "y": random.randint(-20, int(h * 0.35)),
                "vx": -random.uniform(500, 800),
                "vy": random.uniform(250, 450),
                "life": 0.0,
            })

        alive = []

        for sh in self.shooters:

            sh["x"] += sh["vx"] * dt
            sh["y"] += sh["vy"] * dt
            sh["life"] += dt

            if sh["life"] > 1.4 or sh["x"] < -100 or sh["y"] > h + 100:
                continue

            alive.append(sh)

            fade = max(0.0, 1.0 - sh["life"] / 1.4)

            norm = math.hypot(sh["vx"], sh["vy"])

            ux = sh["vx"] / norm
            uy = sh["vy"] / norm

            for i in range(14):

                a = int(230 * fade * (1 - i / 14))

                x1 = sh["x"] - ux * i * 7
                y1 = sh["y"] - uy * i * 7
                x2 = sh["x"] - ux * (i + 1) * 7
                y2 = sh["y"] - uy * (i + 1) * 7

                pygame.draw.line(
                    layer, (200, 170, 255, a), (x1, y1), (x2, y2), 2
                )

        self.shooters = alive

        self.screen.blit(layer, (0, 0))

        # ----------------------------------------------------------
        # VIGNETTE + SOFT BAND BEHIND THE MENU
        # ----------------------------------------------------------

        self.screen.blit(self.vignette, (0, 0))

        self.screen.blit(
            self.band,
            (self.width // 2 - self.band.get_width() // 2, 0)
        )

    # ==============================================================
    # TITLE
    # ==============================================================

    def draw_title(self):

        cx = self.width // 2

        # ----------------------------------------------------------
        # INVADER EMBLEM
        # ----------------------------------------------------------

        cell = self.icon_cell

        icon_w = 11 * cell
        icon_h = 8 * cell

        ix = cx - icon_w // 2
        iy = self.icon_top

        pulse = 0.5 + 0.5 * math.sin(self.time * 3)

        color = (
            int(170 + 40 * pulse),
            int(110 + 90 * pulse),
            255
        )

        halo = pygame.Surface((icon_w + 40, icon_h + 40), pygame.SRCALPHA)

        pygame.draw.ellipse(
            halo,
            (150, 60, 255, int(30 + 25 * pulse)),
            halo.get_rect()
        )

        self.screen.blit(halo, (ix - 20, iy - 20))

        # little wobble like the arcade original

        wobble = int(self.time * 2) % 2

        for row, line in enumerate(self.ALIEN):

            for col, ch in enumerate(line):

                if ch != "#":
                    continue

                dx = cell if (row >= 5 and wobble and col > 5) else 0

                pygame.draw.rect(
                    self.screen,
                    color,
                    (ix + col * cell + dx, iy + row * cell, cell, cell)
                )

        # flanking lines

        ly = iy + icon_h // 2

        for side in (-1, 1):

            x1 = cx + side * (icon_w // 2 + 18)
            x2 = cx + side * (icon_w // 2 + 18 + max(50, self.width // 9))

            pygame.draw.line(
                self.screen, (130, 80, 210), (x1, ly), (x2, ly), 1
            )

            self.draw_diamond(x2, ly, 3, (200, 150, 255))

        # ----------------------------------------------------------
        # "SPACE"
        # ----------------------------------------------------------

        spacing = int(self.title_font.get_height() * 0.16)

        main = self.spaced(
            "SPACE", self.title_font, (225, 222, 242), spacing
        )
        shade = self.spaced(
            "SPACE", self.title_font, (0, 0, 0), spacing
        )
        tint = self.spaced(
            "SPACE", self.title_font, (140, 70, 230), spacing
        )

        tx = cx - main.get_width() // 2

        self.screen.blit(shade, (tx + 3, self.title_y + 3))
        self.screen.blit(tint, (tx + 1, self.title_y + 1))
        self.screen.blit(main, (tx, self.title_y))

        # ----------------------------------------------------------
        # DIVIDER
        # ----------------------------------------------------------

        half = main.get_width() // 2

        pygame.draw.line(
            self.screen,
            (150, 90, 230),
            (cx - half, self.divider_y),
            (cx - 12, self.divider_y),
            1
        )

        pygame.draw.line(
            self.screen,
            (150, 90, 230),
            (cx + 12, self.divider_y),
            (cx + half, self.divider_y),
            1
        )

        self.draw_diamond(cx, self.divider_y, 4, (0, 220, 255))

        # ----------------------------------------------------------
        # "INVADERS"
        # ----------------------------------------------------------

        sub_spacing = int(self.subtitle_font.get_height() * 0.42)

        sub = self.spaced(
            "INVADERS", self.subtitle_font, (190, 175, 220), sub_spacing
        )

        sub_shade = self.spaced(
            "INVADERS", self.subtitle_font, (0, 0, 0), sub_spacing
        )

        sx = cx - sub.get_width() // 2

        self.screen.blit(sub_shade, (sx + 2, self.sub_y + 2))
        self.screen.blit(sub, (sx, self.sub_y))

    def draw_diamond(self, x, y, r, color):

        pygame.draw.polygon(
            self.screen,
            color,
            [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]
        )

    # ==============================================================
    # MENU BUTTONS
    # ==============================================================

    def get_button_surface(self, size, selected):

        key = ("btn", size, selected)

        if key in self._cache:
            return self._cache[key]

        bw, bh = size

        surf = pygame.Surface(size, pygame.SRCALPHA)

        peak = 205 if selected else 120

        base = (62, 34, 110) if selected else (10, 8, 24)

        for x in range(bw):

            t = abs(x / max(1, bw - 1) - 0.5) * 2

            alpha = int(peak * (1 - t ** 3 * 0.85))

            pygame.draw.line(surf, (*base, alpha), (x, 0), (x, bh))

        if selected:

            edge = int(bw * 0.08)

            pygame.draw.line(
                surf, (205, 160, 255, 235),
                (edge, 0), (bw - edge, 0), 1
            )

            pygame.draw.line(
                surf, (205, 160, 255, 235),
                (edge, bh - 1), (bw - edge, bh - 1), 1
            )

        else:

            edge = int(bw * 0.12)

            pygame.draw.line(
                surf, (110, 80, 160, 70),
                (edge, bh - 1), (bw - edge, bh - 1), 1
            )

        self._cache[key] = surf

        return surf

    def draw_menu_button(self, rect, label, selected):

        self.screen.blit(
            self.get_button_surface(rect.size, selected),
            rect.topleft
        )

        # Ornaments on the selected button

        if selected:

            cy = rect.centery

            lx = rect.x + 24
            rx = rect.right - 24

            self.draw_diamond(lx, cy, 4, (210, 160, 255))
            self.draw_diamond(rx, cy, 4, (210, 160, 255))

            pygame.draw.line(
                self.screen, (160, 110, 230),
                (lx + 9, cy), (lx + 30, cy), 1
            )

            pygame.draw.line(
                self.screen, (160, 110, 230),
                (rx - 9, cy), (rx - 30, cy), 1
            )

        color = (250, 245, 255) if selected else (185, 175, 205)

        text = self.spaced(label, self.menu_font, color, 3)

        shade = self.spaced(label, self.menu_font, (0, 0, 0), 3)

        pos = text.get_rect(center=rect.center)

        self.screen.blit(shade, (pos.x + 1, pos.y + 2))
        self.screen.blit(text, pos)

    def draw_menu(self):

        for i, (action, label, rect) in enumerate(self.buttons):

            self.draw_menu_button(rect, label, i == self.selected)

    # ==============================================================
    # TOP-LEFT PLAYER BADGE
    # ==============================================================

    def draw_badge(self):

        rect = self.badge_rect

        mouse = pygame.mouse.get_pos()

        hovered = rect.collidepoint(mouse) and not self.howto_open

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)

        panel.fill((8, 6, 20, 215 if hovered else 185))

        self.screen.blit(panel, rect.topleft)

        edge = (210, 150, 255) if hovered else (110, 70, 170)

        pygame.draw.line(
            self.screen, edge,
            (rect.x, rect.bottom - 1), (rect.right, rect.bottom - 1), 1
        )

        pygame.draw.line(
            self.screen, edge,
            (rect.right - 1, rect.y), (rect.right - 1, rect.bottom), 1
        )

        # ----------------------------------------------------------
        # PROFILE PHOTO
        # ----------------------------------------------------------

        size = self.avatar_size

        frame = pygame.Rect(8, (rect.height - size) // 2, size, size)

        name = self.get_player_name()

        if self.avatar is not None:

            self.screen.blit(self.avatar, frame.topleft)

        else:

            pygame.draw.rect(self.screen, (25, 14, 55), frame)

            initial = self.font.render(name[:1], True, (235, 230, 250))

            self.screen.blit(initial, initial.get_rect(center=frame.center))

        pygame.draw.rect(self.screen, edge, frame, 2)

        # ----------------------------------------------------------
        # NAME + LEADERBOARD RANK
        # ----------------------------------------------------------

        if len(name) > 14:
            name = name[:13] + "."

        name_s = self.small_font.render(name, True, (235, 230, 250))

        if self.rank_text:
            sub_s = self.tiny_font.render(self.rank_text, True, (140, 225, 255))
        else:
            sub_s = self.tiny_font.render("SPACE PILOT", True, (150, 130, 200))

        tx = frame.right + 12

        self.screen.blit(name_s, (tx, 15))
        self.screen.blit(sub_s, (tx, 36))

    # ==============================================================
    # TOP-RIGHT ICONS
    # ==============================================================

    def draw_top_right(self):

        box = self.icon_box

        panel = pygame.Surface(box.size, pygame.SRCALPHA)

        panel.fill((8, 6, 20, 190))

        self.screen.blit(panel, box.topleft)

        pygame.draw.line(
            self.screen, (110, 70, 170),
            (box.x, box.bottom - 1), (box.right, box.bottom - 1), 1
        )

        pygame.draw.line(
            self.screen, (110, 70, 170),
            (box.x, box.y), (box.x, box.bottom), 1
        )

        mouse = pygame.mouse.get_pos()

        tip = None

        names = {
            "settings": "SETTINGS",
            "leaderboard": "LEADERBOARD",
            "profile": "PROFILE",
        }

        for action, rect in self.icon_rects.items():

            hovered = rect.collidepoint(mouse) and not self.howto_open

            color = (240, 225, 255) if hovered else (165, 140, 205)

            if hovered:

                hl = pygame.Surface(rect.size, pygame.SRCALPHA)

                hl.fill((140, 70, 230, 60))

                self.screen.blit(hl, rect.topleft)

                pygame.draw.rect(
                    self.screen, (200, 140, 255), rect, 1, border_radius=4
                )

                tip = (action, rect)

            cx, cy = rect.center

            if action == "settings":
                self.draw_gear_icon(cx, cy, color)
            elif action == "leaderboard":
                self.draw_trophy_icon(cx, cy, color)
            else:
                self.draw_person_icon(cx, cy, color)

        if tip:

            action, rect = tip

            label = self.tiny_font.render(names[action], True, (230, 215, 255))

            bg = pygame.Rect(0, 0, label.get_width() + 14, label.get_height() + 8)

            bg.midtop = (min(rect.centerx, self.width - bg.width // 2 - 4),
                         box.bottom + 6)

            pygame.draw.rect(self.screen, (10, 8, 24), bg, border_radius=4)
            pygame.draw.rect(self.screen, (150, 90, 230), bg, 1, border_radius=4)

            self.screen.blit(label, (bg.x + 7, bg.y + 4))

    def draw_gear_icon(self, cx, cy, color):

        for i in range(8):

            a = i * math.pi / 4

            pygame.draw.line(
                self.screen, color,
                (cx + math.cos(a) * 7, cy + math.sin(a) * 7),
                (cx + math.cos(a) * 11, cy + math.sin(a) * 11),
                3
            )

        pygame.draw.circle(self.screen, color, (cx, cy), 8, 3)
        pygame.draw.circle(self.screen, color, (cx, cy), 2)

    def draw_trophy_icon(self, cx, cy, color):

        pygame.draw.polygon(
            self.screen, color,
            [(cx - 7, cy - 9), (cx + 7, cy - 9), (cx + 5, cy + 2), (cx - 5, cy + 2)]
        )

        pygame.draw.circle(self.screen, color, (cx - 9, cy - 5), 4, 2)
        pygame.draw.circle(self.screen, color, (cx + 9, cy - 5), 4, 2)

        pygame.draw.rect(self.screen, color, (cx - 1, cy + 2, 3, 6))
        pygame.draw.rect(self.screen, color, (cx - 6, cy + 8, 12, 3))

    def draw_person_icon(self, cx, cy, color):

        pygame.draw.circle(self.screen, color, (cx, cy - 5), 5)

        pygame.draw.ellipse(self.screen, color, (cx - 9, cy + 2, 18, 13))

    # ==============================================================
    # FOOTER
    # ==============================================================

    def draw_footer(self):

        w, h = self.width, self.height
        cx = w // 2

        # Tagline with side dashes

        tag = self.spaced(self.TAGLINE, self.tiny_font, (175, 155, 205), 3)

        ty = h - 34

        self.screen.blit(tag, tag.get_rect(center=(cx, ty)))

        for side in (-1, 1):

            x1 = cx + side * (tag.get_width() // 2 + 12)
            x2 = cx + side * (tag.get_width() // 2 + 34)

            pygame.draw.line(
                self.screen, (130, 90, 190), (x1, ty), (x2, ty), 1
            )

        # Key hint (bottom-left)

        key = self.tiny_font.render("ENTER", True, (210, 195, 235))

        box = pygame.Rect(20, h - 42, key.get_width() + 12, 18)

        pygame.draw.rect(self.screen, (12, 9, 28), box, border_radius=3)
        pygame.draw.rect(self.screen, (130, 90, 190), box, 1, border_radius=3)

        self.screen.blit(key, (box.x + 6, box.y + 3))

        sel = self.tiny_font.render("SELECT", True, (150, 130, 190))

        self.screen.blit(sel, (box.right + 8, box.y + 3))

        # Version (bottom-right)

        ver = self.tiny_font.render("V2.0", True, (110, 100, 150))

        self.screen.blit(ver, (w - ver.get_width() - 20, h - 40))

    # ==============================================================
    # HOW TO PLAY WINDOW
    # ==============================================================

    def get_panel_points(self, x, y, w, h, cut=22):

        cut = min(cut, w // 4, h // 4)

        return [
            (x + cut, y),
            (x + w - cut, y),
            (x + w, y + cut),
            (x + w, y + h - cut),
            (x + w - cut, y + h),
            (x + cut, y + h),
            (x, y + h - cut),
            (x, y + cut)
        ]

    def draw_glass_panel(self, rect):

        x, y, w, h = rect

        points = self.get_panel_points(x, y, w, h)

        panel = pygame.Surface((w, h), pygame.SRCALPHA)

        local = [(px - x, py - y) for px, py in points]

        pygame.draw.polygon(panel, (8, 5, 28, 235), local)

        inner = [
            (px - x, py - y)
            for px, py in self.get_panel_points(x + 5, y + 5, w - 10, h - 10, 18)
        ]

        pygame.draw.polygon(panel, (80, 20, 120, 40), inner)

        pygame.draw.polygon(panel, (150, 70, 255, 230), local, width=2)

        pygame.draw.polygon(panel, (0, 190, 255, 90), inner, width=1)

        self.screen.blit(panel, (x, y))

    def draw_howto(self):

        dim = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        dim.fill((0, 0, 8, 170))

        self.screen.blit(dim, (0, 0))

        r = self.howto_rect

        self.draw_glass_panel(r)

        # Heading

        head = self.spaced(
            "HOW TO PLAY", self.heading_font, (220, 185, 255), 4
        )

        self.screen.blit(head, head.get_rect(center=(r.centerx, r.y + 42)))

        pygame.draw.line(
            self.screen, self.purple,
            (r.x + 40, r.y + 68), (r.right - 40, r.y + 68), 1
        )

        pygame.draw.line(
            self.screen, self.cyan,
            (r.x + 90, r.y + 72), (r.right - 90, r.y + 72), 1
        )

        y = r.y + 94

        # Controls

        label = self.tiny_font.render("CONTROLS", True, (145, 100, 200))

        self.screen.blit(label, (r.x + 40, y))

        y += 24

        for keys, desc in self.HOW_TO_PLAY_CONTROLS:

            key_s = self.small_font.render(keys, True, self.cyan)
            desc_s = self.small_font.render(desc, True, (225, 215, 245))

            self.screen.blit(key_s, (r.x + 40, y))

            self.screen.blit(
                desc_s, (r.right - 40 - desc_s.get_width(), y)
            )

            pygame.draw.line(
                self.screen, (60, 40, 100),
                (r.x + 40, y + 24), (r.right - 40, y + 24), 1
            )

            y += 34

        y += 12

        # Mission

        label = self.tiny_font.render("MISSION", True, (145, 100, 200))

        self.screen.blit(label, (r.x + 40, y))

        y += 24

        max_w = r.width - 100

        for text in self.HOW_TO_PLAY_TEXT:

            lines = self.wrap_text(text, self.small_font, max_w - 18)

            self.draw_diamond(r.x + 46, y + 8, 3, (200, 150, 255))

            for line in lines:

                s = self.small_font.render(line, True, (205, 195, 230))

                self.screen.blit(s, (r.x + 62, y))

                y += 20

            y += 10

        # Back button

        mouse = pygame.mouse.get_pos()

        hovered = self.howto_back.collidepoint(mouse)

        self.draw_menu_button(self.howto_back, "BACK", hovered)

    # ==============================================================
    # DRAW
    # ==============================================================

    def draw(self):

        self.time = pygame.time.get_ticks() / 1000.0

        # Mouse hover moves the selection highlight

        mouse = pygame.mouse.get_pos()

        if mouse != self._last_mouse:

            self._last_mouse = mouse

            if not self.howto_open:

                for i, (_, _, rect) in enumerate(self.buttons):

                    if rect.collidepoint(mouse):
                        self.set_selected(i)
                        break

        self.hover_button = self.buttons[self.selected][0]

        self.draw_background()

        self.draw_title()

        self.draw_menu()

        self.draw_badge()

        self.draw_top_right()

        self.draw_footer()

        if self.howto_open:
            self.draw_howto()

    # ==============================================================
    # ACTIONS
    # ==============================================================

    def activate(self, action):

        self.play_click()

        if action == "game":

            self.stop_music()

            return "game"

        if action == "howto":

            self.howto_open = True

            return None

        if action in ("profile", "leaderboard", "settings"):
            return action

        if action == "logout":

            self.stop_music()

            return "logout"

        if action == "quit":

            pygame.event.post(pygame.event.Event(pygame.QUIT))

            return None

        return None

    # ==============================================================
    # EVENT HANDLER
    # ==============================================================

    def handle_event(self, event):

        # ==========================================================
        # WINDOW RESIZE
        # ==========================================================

        if event.type == pygame.VIDEORESIZE:

            self.width = event.w
            self.height = event.h

            self.update_layout()

            return None

        # ==========================================================
        # HOW TO PLAY WINDOW OPEN
        # ==========================================================

        if self.howto_open:

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

                if (
                    self.howto_back.collidepoint(event.pos)
                    or not self.howto_rect.collidepoint(event.pos)
                ):
                    self.play_click()

                    self.howto_open = False

            if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_ESCAPE,
                pygame.K_RETURN,
                pygame.K_KP_ENTER,
                pygame.K_BACKSPACE,
                pygame.K_SPACE,
            ):
                self.play_click()

                self.howto_open = False

            return None

        # ==========================================================
        # MOUSE CLICK
        # ==========================================================

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

            pos = event.pos

            for i, (action, _, rect) in enumerate(self.buttons):

                if rect.collidepoint(pos):

                    self.selected = i

                    return self.activate(action)

            for action, rect in self.icon_rects.items():

                if rect.collidepoint(pos):
                    return self.activate(action)

            if self.badge_rect.collidepoint(pos):
                return self.activate("profile")

        # ==========================================================
        # KEYBOARD
        # ==========================================================

        if event.type == pygame.KEYDOWN:

            count = len(self.buttons)

            if event.key in (pygame.K_UP, pygame.K_w):

                self.set_selected((self.selected - 1) % count)

                return None

            if event.key in (pygame.K_DOWN, pygame.K_s):

                self.set_selected((self.selected + 1) % count)

                return None

            if event.key in (
                pygame.K_RETURN,
                pygame.K_KP_ENTER,
                pygame.K_e,
                pygame.K_SPACE,
            ):
                return self.activate(self.buttons[self.selected][0])

            # ESC can also log out

            if event.key == pygame.K_ESCAPE:

                self.stop_music()

                return "logout"

        return None