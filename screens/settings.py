import os
import json
import math
import random
import array

import pygame


class SettingsScreen:
    """
    Settings screen - clean dark UI with a single orange accent.

    Same constructor and return values as before:
        handle_event() -> None | "back"

    Features (unchanged)
    --------------------
    * AUDIO: master / music / sound-effect sliders that change the real
      music volume live, a MUTE ALL switch and a TEST SOUND button
    * GAMEPLAY: difficulty with a live readout of what it changes
    * DISPLAY & EFFECTS: fullscreen (applied instantly), screen shake,
      particle effects, FPS counter
    * Unsaved-changes indicator and a SAVE / DISCARD / CANCEL prompt
      when leaving with unsaved changes
    * Keyboard: Tab = focus slider, Left/Right = adjust, Enter = save,
      mouse wheel over a slider = adjust

    Helpers for the rest of your game (all static / class methods):
        SettingsScreen.read_settings()            -> dict (from settings.json)
        SettingsScreen.apply_audio(settings)      -> sets music volume
        SettingsScreen.sfx_volume(settings)       -> 0.0 - 1.0 for Sound.set_volume
        SettingsScreen.get_difficulty_modifiers(name)
    """

    # ============================================================
    # COLORS
    # ============================================================

    ORANGE = (232, 84, 44)
    ORANGE_DARK = (150, 48, 26)
    ORANGE_HI = (255, 120, 70)
    AMBER = (255, 176, 64)

    PANEL_BG = (19, 21, 24)
    CARD_BG = (27, 29, 33)
    ROW_BG = (22, 24, 27)
    ROW_HOVER = (35, 33, 33)
    LINE = (52, 55, 61)
    LINE_HI = (92, 96, 104)

    WHITE = (240, 241, 243)
    SOFT = (190, 194, 200)
    MUTED = (130, 135, 143)
    DIM = (84, 87, 94)

    GREEN = (90, 220, 145)
    RED = (255, 90, 90)
    YELLOW = (255, 190, 80)

    # legacy names kept so other code that referenced them still works
    PURPLE = ORANGE
    BRIGHT_PURPLE = ORANGE_HI
    CYAN = AMBER

    # ============================================================
    # DEFAULT SETTINGS
    # ============================================================

    DEFAULT_SETTINGS = {
        "master_volume": 80,
        "music_volume": 70,
        "sfx_volume": 85,
        "mute_all": False,
        "difficulty": "NORMAL",
        "screen_shake": True,
        "particles": True,
        "show_fps": False,
        "fullscreen": False,
    }

    SLIDERS = [
        ("master_volume", "MASTER VOLUME"),
        ("music_volume", "MUSIC VOLUME"),
        ("sfx_volume", "SOUND EFFECTS"),
    ]

    TOGGLES = [
        ("fullscreen", "FULLSCREEN", ""),
        ("screen_shake", "SCREEN SHAKE", ""),
        ("particles", "PARTICLE EFFECTS", ""),
        ("show_fps", "FPS COUNTER", ""),
    ]

    DIFFICULTIES = {
        "EASY": {
            "lives": 5,
            "enemy_speed": 0.75,
            "enemy_fire_rate": 0.70,
            "score_multiplier": 0.8,
        },
        "NORMAL": {
            "lives": 3,
            "enemy_speed": 1.0,
            "enemy_fire_rate": 1.0,
            "score_multiplier": 1.0,
        },
        "HARD": {
            "lives": 2,
            "enemy_speed": 1.3,
            "enemy_fire_rate": 1.5,
            "score_multiplier": 1.5,
        },
    }

    # ============================================================
    # STATIC HELPERS (usable from the rest of the game)
    # ============================================================

    @staticmethod
    def project_root():

        return os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

    @classmethod
    def settings_path(cls):

        return os.path.join(cls.project_root(), "settings.json")

    @classmethod
    def sanitize(cls, data):

        settings = cls.DEFAULT_SETTINGS.copy()

        if isinstance(data, dict):
            settings.update(data)

        for key in ("master_volume", "music_volume", "sfx_volume"):

            try:
                value = int(settings.get(key, cls.DEFAULT_SETTINGS[key]))
            except (TypeError, ValueError):
                value = cls.DEFAULT_SETTINGS[key]

            settings[key] = max(0, min(100, value))

        difficulty = str(settings.get("difficulty", "NORMAL")).upper()

        if difficulty not in cls.DIFFICULTIES:
            difficulty = "NORMAL"

        settings["difficulty"] = difficulty

        for key in (
            "mute_all",
            "screen_shake",
            "particles",
            "show_fps",
            "fullscreen"
        ):
            settings[key] = bool(settings.get(key, cls.DEFAULT_SETTINGS[key]))

        return settings

    @classmethod
    def read_settings(cls):

        try:

            with open(cls.settings_path(), "r", encoding="utf-8") as file:
                return cls.sanitize(json.load(file))

        except (OSError, ValueError, TypeError):

            return cls.sanitize(None)

    @staticmethod
    def music_volume(settings):

        if settings.get("mute_all"):
            return 0.0

        return (
            settings.get("master_volume", 80)
            * settings.get("music_volume", 70)
            / 10000.0
        )

    @staticmethod
    def sfx_volume(settings):

        if settings.get("mute_all"):
            return 0.0

        return (
            settings.get("master_volume", 80)
            * settings.get("sfx_volume", 85)
            / 10000.0
        )

    @classmethod
    def apply_audio(cls, settings):

        try:

            if pygame.mixer.get_init():
                pygame.mixer.music.set_volume(cls.music_volume(settings))

        except pygame.error:
            pass

    @classmethod
    def get_difficulty_modifiers(cls, name):

        return dict(
            cls.DIFFICULTIES.get(
                str(name).upper(),
                cls.DIFFICULTIES["NORMAL"]
            )
        )

    # ============================================================
    # INIT
    # ============================================================

    def __init__(self, screen, screen_width, screen_height):

        self.screen = screen
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.time = 0.0

        self.settings_file = self.settings_path()

        # --------------------------------------------------------
        # SETTINGS
        # --------------------------------------------------------

        self.settings = self.read_settings()

        # The fullscreen switch always reflects the real window state

        self.settings["fullscreen"] = self.is_fullscreen()

        self.saved_settings = self.settings.copy()

        # --------------------------------------------------------
        # STATE
        # --------------------------------------------------------

        self.dragging = None            # slider key while dragging
        self.focus_index = 0            # keyboard-focused slider
        self.leave_prompt = False

        self.message = ""
        self.message_type = "info"
        self.message_until = 0

        self.beep = None

        # --------------------------------------------------------
        # BACKGROUND
        # --------------------------------------------------------

        self.background = None
        self.bg_cache = None
        self.bg_cache_size = None

        path = self.find_background()

        if path:
            try:
                self.background = pygame.image.load(path).convert()
            except Exception:
                self.background = None

        # kept for compatibility with older code (no longer drawn)

        self.stars = [
            {
                "x": random.random(),
                "y": random.random(),
                "speed": random.uniform(0.008, 0.028),
                "size": 1,
                "phase": random.uniform(0, 6.28),
            }
            for _ in range(20)
        ]

        # --------------------------------------------------------
        # FONTS
        # --------------------------------------------------------

        face = "segoeui,calibri,helvetica,arial"

        self.title_font = pygame.font.SysFont(face, 30, bold=True)
        self.heading_font = pygame.font.SysFont(face, 16, bold=True)
        self.font = pygame.font.SysFont(face, 16, bold=True)
        self.small_font = pygame.font.SysFont(face, 14, bold=True)
        self.tiny_font = pygame.font.SysFont(face, 12)

        # Make the music volume match the saved settings right away

        self.apply_audio(self.settings)

    # ============================================================
    # FILES
    # ============================================================

    def find_background(self):

        root = self.project_root()

        paths = [
            os.path.join(root, "assets", "images", "bg3.png"),
            os.path.join(root, "assets", "bg3.png"),
            os.path.join(root, "images", "bg3.png"),
            os.path.join(root, "bg3.png"),
            os.path.join("assets", "images", "bg3.png"),
            os.path.join("assets", "bg3.png"),
            "bg3.png",
        ]

        for path in paths:

            if os.path.exists(path):
                return path

        return None

    def save_settings(self):

        try:

            with open(self.settings_file, "w", encoding="utf-8") as file:
                json.dump(self.settings, file, indent=4)

        except (OSError, TypeError) as error:

            print("Settings save error:", error)

            self.set_message("COULD NOT SAVE SETTINGS", "error")

            return False

        self.saved_settings = self.settings.copy()

        self.set_message("SETTINGS SAVED", "success")

        return True

    # ============================================================
    # LIVE EFFECTS
    # ============================================================

    def is_fullscreen(self):

        try:

            surface = pygame.display.get_surface()

            return bool(surface and (surface.get_flags() & pygame.FULLSCREEN))

        except pygame.error:

            return False

    def set_fullscreen(self, target):

        if self.is_fullscreen() != target:

            try:

                pygame.display.toggle_fullscreen()

            except pygame.error:

                self.set_message("FULLSCREEN NOT SUPPORTED HERE", "error")

        self.settings["fullscreen"] = self.is_fullscreen()

        surface = pygame.display.get_surface()

        if surface:

            width, height = surface.get_size()

            self.resize(width, height)

    def make_beep(self):

        init = pygame.mixer.get_init()

        if not init:
            return None

        frequency, fmt, channels = init

        if fmt != -16:
            return None

        samples = int(frequency * 0.14)

        data = array.array("h")

        for i in range(samples):

            envelope = 1.0 - i / samples

            value = int(
                9000
                * envelope
                * math.sin(2 * math.pi * 660 * i / frequency)
            )

            for _ in range(channels):
                data.append(value)

        return pygame.mixer.Sound(buffer=data.tobytes())

    def play_test_sound(self):

        try:

            if not pygame.mixer.get_init():
                pygame.mixer.init()

            if self.beep is None:
                self.beep = self.make_beep()

            if self.beep is None:

                self.set_message("TEST SOUND UNAVAILABLE", "warning")

                return

            self.beep.set_volume(self.sfx_volume(self.settings))

            self.beep.play()

        except (pygame.error, ValueError):

            self.set_message("TEST SOUND UNAVAILABLE", "warning")

    def has_changes(self):

        return self.settings != self.saved_settings

    # ============================================================
    # UPDATE / RESIZE / MESSAGE
    # ============================================================

    def update(self, dt):

        self.time += dt

    def resize(self, width, height):

        self.screen_width = width
        self.screen_height = height

        self.bg_cache = None

    def set_message(self, message, message_type="info"):

        self.message = message
        self.message_type = message_type
        self.message_until = pygame.time.get_ticks() + 3000

    # ============================================================
    # LAYOUT (shared by draw + events)
    # ============================================================

    HEAD = 72           # header height
    FOOT = 60           # footer height
    PAD = 24            # outer padding
    CARD_PAD = 22       # padding inside cards
    CARD_HEAD = 52      # card header height

    def compute_layout(self):

        w = self.screen_width
        h = self.screen_height

        pw = min(920, max(0, w - 32))
        ph = min(580, max(0, h - 32))

        panel = pygame.Rect((w - pw) // 2, (h - ph) // 2, pw, ph)

        L = {"panel": panel}

        # --------------------------------------------------------
        # Footer buttons
        # --------------------------------------------------------

        by = panel.bottom - self.FOOT + (self.FOOT - 36) // 2

        L["reset"] = pygame.Rect(panel.x + self.PAD, by, 160, 36)
        L["back"] = pygame.Rect(panel.right - self.PAD - 110, by, 110, 36)
        L["save"] = pygame.Rect(L["back"].x - 12 - 150, by, 150, 36)

        # --------------------------------------------------------
        # Cards
        # --------------------------------------------------------

        top = panel.y + self.HEAD + 16
        bottom = panel.bottom - self.FOOT - 16
        ch = max(300, bottom - top)

        inner = pw - self.PAD * 2
        left_w = (inner - 20) // 2

        left = pygame.Rect(panel.x + self.PAD, top, left_w, ch)
        right = pygame.Rect(left.right + 20, top, inner - 20 - left_w, ch)

        L["left"] = left
        L["right"] = right

        pad = self.CARD_PAD

        # --------------------------------------------------------
        # AUDIO card
        # --------------------------------------------------------

        test_h = 38
        mute_h = 44

        test = pygame.Rect(
            left.x + pad,
            left.bottom - 18 - test_h,
            left.width - pad * 2,
            test_h
        )

        mute = pygame.Rect(
            left.x + pad,
            test.y - 10 - mute_h,
            left.width - pad * 2,
            mute_h
        )

        region_top = left.y + self.CARD_HEAD + 14
        region_bottom = mute.y - 8

        sg = max(56, min(80, (region_bottom - region_top) // 3))

        L["sliders"] = []

        for index, (key, label) in enumerate(self.SLIDERS):

            L["sliders"].append((
                key,
                label,
                pygame.Rect(
                    left.x + pad,
                    region_top + index * sg + 34,
                    left.width - pad * 2,
                    6
                )
            ))

        L["mute"] = mute
        L["test"] = test

        rx = right.x + pad
        rw = right.width - pad * 2

        box = pygame.Rect(rx, right.y + self.CARD_HEAD + 14, rw, 38)

        L["difficulty_box"] = box

        seg_w = (rw - 6 - 4) // 3

        L["difficulty"] = []

        for index, name in enumerate(self.DIFFICULTIES.keys()):

            L["difficulty"].append((
                name,
                pygame.Rect(
                    box.x + 3 + index * (seg_w + 2),
                    box.y + 3,
                    seg_w,
                    box.height - 6
                )
            ))

        L["readout"] = pygame.Rect(rx, box.bottom + 10, rw, 54)

        L["display_title_y"] = L["readout"].bottom + 18

        L["toggles"] = []

        row_h = 40
        row_gap = 8

        for index, (key, title, desc) in enumerate(self.TOGGLES):

            L["toggles"].append((
                key,
                title,
                desc,
                pygame.Rect(
                    rx,
                    L["display_title_y"] + 28 + index * (row_h + row_gap),
                    rw,
                    row_h
                )
            ))

        # --------------------------------------------------------
        # Leave prompt
        # --------------------------------------------------------

        mw = min(520, w - 30)
        mh = 190

        modal = pygame.Rect((w - mw) // 2, (h - mh) // 2, mw, mh)

        L["modal"] = modal

        bw = (mw - 60 - 24) // 3

        by = modal.bottom - 58

        L["modal_save"] = pygame.Rect(modal.x + 30, by, bw, 38)
        L["modal_discard"] = pygame.Rect(L["modal_save"].right + 12, by, bw, 38)
        L["modal_cancel"] = pygame.Rect(L["modal_discard"].right + 12, by, bw, 38)

        return L

    # ============================================================
    # DRAW HELPERS
    # ============================================================

    def draw_box(self, rect, fill, border=None, radius=8, width=1):

        layer = pygame.Surface(
            (max(1, rect.width), max(1, rect.height)),
            pygame.SRCALPHA
        )

        pygame.draw.rect(
            layer,
            fill,
            layer.get_rect(),
            border_radius=radius
        )

        if border:

            pygame.draw.rect(
                layer,
                border,
                layer.get_rect(),
                width,
                border_radius=radius
            )

        self.screen.blit(layer, rect.topleft)

    def draw_glass_panel(self, rect, cut=14, border=None):
        """Rounded dark panel with a soft shadow (name kept for compatibility)."""

        if rect.width <= 0 or rect.height <= 0:
            return

        shadow = pygame.Surface(
            (rect.width + 40, rect.height + 40),
            pygame.SRCALPHA
        )

        for i in range(10):

            pygame.draw.rect(
                shadow,
                (0, 0, 0, 10),
                shadow.get_rect().inflate(-i * 3, -i * 3),
                border_radius=22
            )

        self.screen.blit(shadow, (rect.x - 20, rect.y - 12))

        self.draw_box(
            rect,
            (*self.PANEL_BG, 246),
            (*(border or self.LINE), 255),
            14,
            1
        )

    def text(self, value, font, color, x, y, align="left"):

        surface = font.render(str(value), True, color)

        if align == "center":
            rect = surface.get_rect(center=(x, y))
        elif align == "right":
            rect = surface.get_rect(topright=(x, y))
        else:
            rect = surface.get_rect(topleft=(x, y))

        self.screen.blit(surface, rect)

        return rect

    def spaced(self, value, font, color, x, y, spacing=2, align="left"):
        """Text with extra letter spacing. Returns the drawn width."""

        glyphs = [font.render(ch, True, color) for ch in str(value)]

        total = sum(g.get_width() for g in glyphs) + spacing * max(0, len(glyphs) - 1)

        if align == "center":
            x -= total // 2
        elif align == "right":
            x -= total

        for g in glyphs:

            self.screen.blit(g, (x, y))

            x += g.get_width() + spacing

        return total

    def draw_button(self, rect, label, style="normal", disabled=False):

        hover = (
            not disabled
            and rect.collidepoint(pygame.mouse.get_pos())
        )

        if disabled:

            fill = (30, 32, 36, 255)
            border = (44, 47, 52, 255)
            color = self.DIM

        elif style == "accent":

            fill = (*self.ORANGE_HI, 255) if hover else (*self.ORANGE, 255)
            border = None
            color = (255, 255, 255)

        elif style == "warning":

            fill = (60, 44, 22, 255) if hover else (0, 0, 0, 0)
            border = (*self.AMBER, 255) if hover else (150, 112, 52, 255)
            color = (255, 214, 140) if hover else (225, 180, 100)

        elif style == "danger":

            fill = (100, 32, 34, 255) if hover else (0, 0, 0, 0)
            border = (255, 110, 110, 255) if hover else (170, 72, 72, 255)
            color = (255, 190, 190)

        else:

            fill = (46, 48, 54, 255) if hover else (34, 36, 40, 255)
            border = (*self.ORANGE, 255) if hover else (*self.LINE_HI, 255)
            color = self.WHITE if hover else self.SOFT

        self.draw_box(rect, fill, border, 6, 1)

        self.spaced(
            label,
            self.small_font,
            color,
            rect.centerx,
            rect.centery - self.small_font.get_height() // 2,
            1,
            "center"
        )

    # ============================================================
    # BACKGROUND
    # ============================================================

    def build_background(self, w, h):

        surface = pygame.Surface((w, h))

        if self.background:

            bw, bh = self.background.get_size()

            scale = max(w / bw, h / bh)

            size = (max(1, int(bw * scale)), max(1, int(bh * scale)))

            image = pygame.transform.smoothscale(self.background, size)

            surface.blit(
                image,
                ((w - size[0]) // 2, (h - size[1]) // 2)
            )

        else:

            for row in range(h):

                t = row / max(1, h - 1)

                pygame.draw.line(
                    surface,
                    (int(10 + 8 * t), int(11 + 6 * t), int(14 + 6 * t)),
                    (0, row),
                    (w, row)
                )

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)

        overlay.fill((6, 7, 9, 200))

        surface.blit(overlay, (0, 0))

        return surface

    def draw_background(self):

        w = self.screen_width
        h = self.screen_height

        if self.bg_cache is None or self.bg_cache_size != (w, h):

            self.bg_cache = self.build_background(w, h)
            self.bg_cache_size = (w, h)

        self.screen.blit(self.bg_cache, (0, 0))

    # ============================================================
    # DRAW: WIDGETS
    # ============================================================

    def draw_card(self, rect, title, subtitle=None):

        self.draw_box(rect, (*self.CARD_BG, 255), (*self.LINE, 255), 10, 1)

        x = rect.x + self.CARD_PAD

        pygame.draw.rect(
            self.screen,
            self.ORANGE,
            pygame.Rect(x, rect.y + 17, 4, 18),
            border_radius=2
        )

        self.spaced(title, self.heading_font, self.WHITE, x + 14, rect.y + 16, 2)

        if subtitle:

            self.text(
                subtitle,
                self.tiny_font,
                self.MUTED,
                rect.right - self.CARD_PAD,
                rect.y + 19,
                "right"
            )

        pygame.draw.line(
            self.screen,
            self.LINE,
            (rect.x + self.CARD_PAD, rect.y + self.CARD_HEAD),
            (rect.right - self.CARD_PAD, rect.y + self.CARD_HEAD),
            1
        )

    def draw_slider(self, rect, label, key, focused):

        value = self.settings[key]

        muted = self.settings["mute_all"]

        self.text(
            label,
            self.small_font,
            self.ORANGE_HI if focused else self.SOFT,
            rect.x,
            rect.y - 28
        )

        self.text(
            f"{value}%",
            self.font,
            self.DIM if muted else self.WHITE,
            rect.right,
            rect.y - 30,
            "right"
        )

        # Track

        self.draw_box(rect, (12, 13, 15, 255), (*self.LINE, 255), 3, 1)

        fill_w = int(rect.width * value / 100)

        if fill_w > 0:

            color = (96, 84, 80) if muted else self.ORANGE

            self.draw_box(
                pygame.Rect(rect.x, rect.y, max(6, fill_w), rect.height),
                (*color, 255),
                None,
                3
            )

        # Handle

        hx = rect.x + fill_w

        hovered = (
            self.dragging == key
            or pygame.Rect(hx - 12, rect.centery - 12, 24, 24).collidepoint(
                pygame.mouse.get_pos()
            )
        )

        if (hovered or focused) and not muted:

            glow = pygame.Surface((40, 40), pygame.SRCALPHA)

            pygame.draw.circle(
                glow,
                (*self.ORANGE, 70 if hovered else 40),
                (20, 20),
                16 if hovered else 14
            )

            self.screen.blit(glow, (hx - 20, rect.centery - 20))

        pygame.draw.circle(self.screen, self.WHITE, (hx, rect.centery), 8)

        pygame.draw.circle(
            self.screen,
            self.DIM if muted else self.ORANGE,
            (hx, rect.centery),
            4
        )

    def draw_switch(self, rect, enabled):

        switch = pygame.Rect(0, 0, 40, 22)

        switch.midright = (rect.right - 14, rect.centery)

        self.draw_box(
            switch,
            (*self.ORANGE, 255) if enabled else (14, 15, 17, 255),
            (*self.ORANGE_HI, 255) if enabled else (*self.LINE_HI, 255),
            11,
            1
        )

        knob_x = switch.right - 11 if enabled else switch.left + 11

        pygame.draw.circle(
            self.screen,
            (255, 255, 255) if enabled else self.MUTED,
            (knob_x, switch.centery),
            8
        )

    def draw_toggle_row(self, rect, title, desc, enabled):

        hover = rect.collidepoint(pygame.mouse.get_pos())

        self.draw_box(
            rect,
            (*(self.ROW_HOVER if hover else self.ROW_BG), 255),
            (*(self.ORANGE_DARK if hover else self.LINE), 255),
            6,
            1
        )

        self.text(title, self.small_font, self.WHITE, rect.x + 14, rect.y + 4)

        self.text(desc, self.tiny_font, self.MUTED, rect.x + 14, rect.y + 22)

        self.draw_switch(rect, enabled)

    def draw_section_label(self, x, y, right, label):

        width = self.spaced(label, self.tiny_font, self.MUTED, x, y, 2)

        pygame.draw.line(
            self.screen,
            self.LINE,
            (x + width + 12, y + 7),
            (right, y + 7),
            1
        )

    def draw_hints(self, x_min, x_max, cy):
        """Keyboard hints in the footer. Items that do not fit are dropped."""

        items = [
            ("TAB", "focus"),
            ("< >", "adjust"),
            ("ENTER", "save"),
            ("ESC", "back"),
        ]

        def item_width(item):

            key, label = item

            return (
                self.tiny_font.size(key)[0] + 14
                + 6
                + self.tiny_font.size(label)[0]
            )

        while items and sum(item_width(i) for i in items) + 18 * (len(items) - 1) > x_max - x_min:
            items.pop()

        x = x_min

        for key, label in items:

            kw = self.tiny_font.size(key)[0] + 14

            cap = pygame.Rect(x, cy - 10, kw, 20)

            self.draw_box(cap, (30, 32, 36, 255), (*self.LINE_HI, 255), 4, 1)

            self.text(key, self.tiny_font, self.SOFT, cap.centerx, cap.centery, "center")

            lab = self.text(label, self.tiny_font, self.MUTED, cap.right + 6, cy - 7)

            x = lab.right + 18

    def draw_status_pill(self, panel):

        now = pygame.time.get_ticks()

        if self.message and now > self.message_until:
            self.message = ""

        if self.message:

            text = self.message

            color = {
                "success": self.GREEN,
                "error": self.RED,
                "warning": self.YELLOW,
            }.get(self.message_type, self.SOFT)

        elif self.has_changes():

            text, color = "UNSAVED CHANGES", self.YELLOW

        else:

            text, color = "ALL CHANGES SAVED", self.GREEN

        surface = self.small_font.render(text, True, color)

        rect = pygame.Rect(0, 0, surface.get_width() + 46, 30)

        rect.midright = (panel.right - self.PAD - 4, panel.y + self.HEAD // 2)

        self.draw_box(rect, (*color, 24), (*color, 110), 15, 1)

        pygame.draw.circle(self.screen, color, (rect.x + 17, rect.centery), 4)

        self.screen.blit(
            surface,
            (rect.x + 30, rect.centery - surface.get_height() // 2)
        )

    # ============================================================
    # DRAW: CARDS
    # ============================================================

    def draw_audio_card(self, L):

        left = L["left"]

        self.draw_card(left, "AUDIO", "Changes apply instantly")

        for index, (key, label, rect) in enumerate(L["sliders"]):

            self.draw_slider(rect, label, key, index == self.focus_index)

        self.draw_toggle_row(
            L["mute"],
            "MUTE ALL AUDIO",
            "Silence music and sound effects",
            self.settings["mute_all"]
        )

        self.draw_button(L["test"], "TEST SOUND", "accent")

    def draw_gameplay_card(self, L):

        right = L["right"]

        self.draw_card(right, "GAMEPLAY", "Difficulty & display")

        self.draw_box(
            L["difficulty_box"],
            (14, 15, 17, 255),
            (*self.LINE, 255),
            8,
            1
        )

        for name, rect in L["difficulty"]:

            selected = (name == self.settings["difficulty"])

            hover = rect.collidepoint(pygame.mouse.get_pos())

            if selected:

                self.draw_box(rect, (*self.ORANGE, 255), None, 6)
                color = (255, 255, 255)

            elif hover:

                self.draw_box(rect, (40, 38, 38, 255), None, 6)
                color = self.WHITE

            else:

                color = self.MUTED

            self.spaced(
                name,
                self.small_font,
                color,
                rect.centerx,
                rect.centery - self.small_font.get_height() // 2,
                2,
                "center"
            )

        mods = self.get_difficulty_modifiers(self.settings["difficulty"])

        readout = L["readout"]

        self.draw_box(readout, (14, 15, 17, 255), (*self.LINE, 255), 8, 1)

        cells = [
            ("LIVES", str(mods["lives"])),
            ("SPEED", f"x{mods['enemy_speed']:.2f}"),
            ("FIRE RATE", f"x{mods['enemy_fire_rate']:.2f}"),
            ("SCORE", f"x{mods['score_multiplier']:.1f}"),
        ]

        cell_w = readout.width // 4

        for index, (label, value) in enumerate(cells):

            cx = readout.x + index * cell_w + cell_w // 2

            if index > 0:

                pygame.draw.line(
                    self.screen,
                    self.LINE,
                    (readout.x + index * cell_w, readout.y + 12),
                    (readout.x + index * cell_w, readout.bottom - 12),
                    1
                )

            self.spaced(label, self.tiny_font, self.MUTED, cx, readout.y + 9, 1, "center")

            self.text(
                value,
                self.font,
                self.ORANGE_HI if index == 3 else self.WHITE,
                cx,
                readout.y + 28,
                "center"
            )

        x = right.x + self.CARD_PAD

        self.draw_section_label(
            x,
            L["display_title_y"],
            right.right - self.CARD_PAD,
            "DISPLAY & EFFECTS"
        )

        for key, title, desc, rect in L["toggles"]:

            self.draw_toggle_row(rect, title, desc, self.settings[key])

    # ============================================================
    # DRAW: LEAVE PROMPT
    # ============================================================

    def draw_leave_prompt(self, L):

        overlay = pygame.Surface(
            (self.screen_width, self.screen_height),
            pygame.SRCALPHA
        )

        overlay.fill((0, 0, 0, 170))

        self.screen.blit(overlay, (0, 0))

        modal = L["modal"]

        self.draw_glass_panel(modal, 12, self.ORANGE_DARK)

        self.spaced(
            "UNSAVED CHANGES",
            self.heading_font,
            self.AMBER,
            modal.centerx,
            modal.y + 26,
            2,
            "center"
        )

        self.text(
            "Save your settings before leaving?",
            self.small_font,
            self.WHITE,
            modal.centerx,
            modal.y + 68,
            "center"
        )

        self.text(
            "Discard will restore the last saved settings.",
            self.tiny_font,
            self.MUTED,
            modal.centerx,
            modal.y + 92,
            "center"
        )

        self.draw_button(L["modal_save"], "SAVE & EXIT", "accent")
        self.draw_button(L["modal_discard"], "DISCARD", "danger")
        self.draw_button(L["modal_cancel"], "CANCEL")

    # ============================================================
    # DRAW
    # ============================================================

    def draw(self):

        self.time = pygame.time.get_ticks() / 1000.0

        L = self.compute_layout()

        panel = L["panel"]

        self.draw_background()

        self.draw_glass_panel(panel)

        # ---- Header ----

        pygame.draw.rect(
            self.screen,
            self.ORANGE,
            pygame.Rect(panel.x + self.PAD + 2, panel.y + 16, 4, 40),
            border_radius=2
        )

        self.spaced(
            "SETTINGS",
            self.title_font,
            self.WHITE,
            panel.x + self.PAD + 20,
            panel.y + 10,
            3
        )

        self.text(
            "Audio, gameplay and display preferences",
            self.tiny_font,
            self.MUTED,
            panel.x + self.PAD + 21,
            panel.y + 48
        )

        self.draw_status_pill(panel)

        pygame.draw.line(
            self.screen,
            self.LINE,
            (panel.x + 1, panel.y + self.HEAD),
            (panel.right - 2, panel.y + self.HEAD),
            1
        )

        pygame.draw.line(
            self.screen,
            self.ORANGE,
            (panel.x + self.PAD, panel.y + self.HEAD),
            (panel.x + self.PAD + 64, panel.y + self.HEAD),
            2
        )

        # ---- Cards ----

        self.draw_audio_card(L)
        self.draw_gameplay_card(L)

        # ---- Footer ----

        fy = panel.bottom - self.FOOT

        pygame.draw.line(
            self.screen,
            self.LINE,
            (panel.x + 1, fy),
            (panel.right - 2, fy),
            1
        )

        self.draw_button(L["reset"], "RESET DEFAULTS", "warning")

        self.draw_button(
            L["save"],
            "SAVE SETTINGS",
            "accent",
            disabled=not self.has_changes()
        )

        self.draw_button(L["back"], "BACK")

        self.draw_hints(
            L["reset"].right + 24,
            L["save"].x - 24,
            L["reset"].centery
        )

        if self.leave_prompt:
            self.draw_leave_prompt(L)

    # ============================================================
    # ACTIONS
    # ============================================================

    def set_slider_from_mouse(self, key, rect, mouse_x):

        if rect.width <= 0:
            return

        ratio = max(0.0, min(1.0, (mouse_x - rect.x) / rect.width))

        self.settings[key] = int(round(ratio * 100))

        self.apply_audio(self.settings)

    def adjust_slider(self, key, delta):

        self.settings[key] = max(0, min(100, self.settings[key] + delta))

        self.apply_audio(self.settings)

    def toggle(self, key):

        if key == "fullscreen":

            self.set_fullscreen(not self.settings["fullscreen"])

            return

        self.settings[key] = not self.settings[key]

        if key == "mute_all":
            self.apply_audio(self.settings)

    def reset_defaults(self):

        defaults = self.DEFAULT_SETTINGS.copy()

        self.settings = defaults

        self.apply_audio(self.settings)

        self.set_fullscreen(defaults["fullscreen"])

        self.set_message("DEFAULTS RESTORED - PRESS SAVE TO KEEP", "warning")

    def discard_changes(self):

        self.settings = self.saved_settings.copy()

        self.apply_audio(self.settings)

        self.set_fullscreen(self.settings["fullscreen"])

        self.saved_settings = self.settings.copy()

    def request_back(self):

        if self.has_changes():

            self.leave_prompt = True

            return None

        return "back"

    # ============================================================
    # EVENTS
    # ============================================================

    def handle_event(self, event):

        if event.type == pygame.VIDEORESIZE:

            self.resize(event.w, event.h)

            return None

        L = self.compute_layout()

        # --------------------------------------------------------
        # KEYBOARD
        # --------------------------------------------------------

        if event.type == pygame.KEYDOWN:

            if self.leave_prompt:

                if event.key == pygame.K_ESCAPE:

                    self.leave_prompt = False

                elif event.key == pygame.K_RETURN:

                    if self.save_settings():

                        self.leave_prompt = False

                        return "back"

                return None

            if event.key == pygame.K_ESCAPE:

                self.dragging = None

                return self.request_back()

            if event.key == pygame.K_RETURN:

                self.save_settings()

                return None

            if event.key == pygame.K_TAB:

                step = -1 if (event.mod & pygame.KMOD_SHIFT) else 1

                self.focus_index = (self.focus_index + step) % len(self.SLIDERS)

                return None

            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):

                key = self.SLIDERS[self.focus_index][0]

                step = 5 if event.key == pygame.K_RIGHT else -5

                self.adjust_slider(key, step)

                if key == "sfx_volume":
                    self.play_test_sound()

                return None

            if event.key == pygame.K_UP:

                self.focus_index = (self.focus_index - 1) % len(self.SLIDERS)

            elif event.key == pygame.K_DOWN:

                self.focus_index = (self.focus_index + 1) % len(self.SLIDERS)

            return None

        # --------------------------------------------------------
        # MOUSE WHEEL OVER A SLIDER
        # --------------------------------------------------------

        if event.type == pygame.MOUSEWHEEL and not self.leave_prompt:

            mouse = pygame.mouse.get_pos()

            for index, (key, _label, rect) in enumerate(L["sliders"]):

                if rect.inflate(20, 40).collidepoint(mouse):

                    self.focus_index = index

                    self.adjust_slider(key, 5 * event.y)

                    return None

            return None

        # --------------------------------------------------------
        # SLIDER DRAG
        # --------------------------------------------------------

        if event.type == pygame.MOUSEMOTION and self.dragging:

            for key, _label, rect in L["sliders"]:

                if key == self.dragging:

                    self.set_slider_from_mouse(key, rect, event.pos[0])

            return None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:

            if self.dragging == "sfx_volume":
                self.play_test_sound()

            self.dragging = None

            return None

        # --------------------------------------------------------
        # MOUSE CLICK
        # --------------------------------------------------------

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

            pos = event.pos

            # ---- Leave prompt ----

            if self.leave_prompt:

                if L["modal_save"].collidepoint(pos):

                    if self.save_settings():

                        self.leave_prompt = False

                        return "back"

                elif L["modal_discard"].collidepoint(pos):

                    self.leave_prompt = False

                    self.discard_changes()

                    return "back"

                elif L["modal_cancel"].collidepoint(pos):

                    self.leave_prompt = False

                return None

            # ---- Sliders ----

            for index, (key, _label, rect) in enumerate(L["sliders"]):

                if rect.inflate(20, 30).collidepoint(pos):

                    self.dragging = key

                    self.focus_index = index

                    self.set_slider_from_mouse(key, rect, pos[0])

                    return None

            # ---- Audio buttons ----

            if L["mute"].collidepoint(pos):

                self.toggle("mute_all")

                return None

            if L["test"].collidepoint(pos):

                self.play_test_sound()

                return None

            for name, rect in L["difficulty"]:

                if rect.collidepoint(pos):

                    self.settings["difficulty"] = name

                    return None

            # ---- Toggles ----

            for key, _title, _desc, rect in L["toggles"]:

                if rect.collidepoint(pos):

                    self.toggle(key)

                    return None

            # ---- Bottom bar ----

            if L["reset"].collidepoint(pos):

                self.reset_defaults()

                return None

            if L["save"].collidepoint(pos):

                if self.has_changes():
                    self.save_settings()

                return None

            if L["back"].collidepoint(pos):

                return self.request_back()

        return None