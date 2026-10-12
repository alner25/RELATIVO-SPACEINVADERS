import base64
import hashlib
import json
import math
import os
import random

import pygame

import auth
from auth import login


AUTO_EVENT = pygame.USEREVENT + 8

try:
    import keyring
except Exception:
    keyring = None

REMEMBER_FILE = "remembered_login.json"
KEYRING_SERVICE = "SpaceInvaderLogin"
AUTO_LOGIN_MS = 2200


def _obf_key():
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    seed = f"space-invader:{user}:{os.path.abspath(REMEMBER_FILE)}"
    return hashlib.sha256(seed.encode("utf-8")).digest()


def _obfuscate(text):
    key = _obf_key()
    data = text.encode("utf-8")
    return base64.b64encode(
        bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    ).decode("ascii")


def _deobfuscate(token):
    key = _obf_key()
    data = base64.b64decode(token.encode("ascii"))
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data)).decode("utf-8")


def _load_remembered():
    try:
        with open(REMEMBER_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return None

    if (
        isinstance(data, dict)
        and data.get("method") == "password"
        and data.get("username")
    ):
        return data

    return None


def _save_remembered(record, password):
    record = dict(record)

    stored = False

    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE, record["username"], password)
            stored = True
        except Exception:
            stored = False

    if not stored:
        record["secret"] = _obfuscate(password)

    try:
        with open(REMEMBER_FILE, "w", encoding="utf-8") as file:
            json.dump(record, file, indent=2)
    except OSError:
        pass


def _forget_remembered():
    record = _load_remembered()

    if record and keyring is not None:
        try:
            keyring.delete_password(KEYRING_SERVICE, record["username"])
        except Exception:
            pass

    try:
        os.remove(REMEMBER_FILE)
    except OSError:
        pass


def _remembered_password(record):
    if record.get("secret"):
        try:
            return _deobfuscate(record["secret"])
        except Exception:
            return None

    if keyring is not None and record.get("username"):
        try:
            return keyring.get_password(KEYRING_SERVICE, record["username"])
        except Exception:
            return None

    return None


def _clipboard_text():
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()

        try:
            return root.clipboard_get()
        finally:
            root.destroy()
    except Exception:
        return ""


class LoginScreen:
    DESIGN_WIDTH = 1000
    DESIGN_HEIGHT = 650

    MUSIC_PATHS = (
        "assets/audio/backgroundmusic1.mp3",
        "assets/sounds/backgroundmusic1.mp3",
        "assets/music/backgroundmusic1.mp3",
        "assets/backgroundmusic1.mp3",
        "backgroundmusic1.mp3",
    )
    MUSIC_VOLUME = 0.5
    _music_on = False
    _auto_done = False

    # The first existing file is used as the logo. Clicking the logo saves a
    # new picture to the FIRST path; right-click removes it again.
    LOGO_PATHS = (
        "assets/images/login_logo.png",
        "assets/images/logo.png",
        "assets/logo.png",
        "logo.png",
    )

    ALIEN = (
        "..#.......#..",
        "...#.....#...",
        "....#####....",
        "..#########..",
        ".###########.",
        ".##..###..##.",
        ".##..###..##.",
        ".###########.",
        "..##.###.##..",
        "..#..#.#..#..",
        ".##.......##.",
    )

    CARD_RIGHT = (14, 38, 48, 150)
    TEXT = (235, 248, 250)
    TEXT_SOFT = (150, 188, 194)
    TEAL = (70, 205, 212)

    def __init__(self, screen, width, height):
        self.screen = screen
        self.width = width
        self.height = height

        self.bg_raw = None

        for path in (
            "assets/images/world_map.png",
            "assets/images/bg3.png",
        ):
            try:
                self.bg_raw = pygame.image.load(path).convert()
                break
            except (pygame.error, FileNotFoundError):
                pass

        self.bg_image = None
        self.background_fx = None

        self.username = ""
        self.password = ""
        self.active_field = "username"
        self.show_password = False
        self.remember_me = True

        self.message = ""
        self.message_color = (255, 120, 120)

        self.is_minimized = False
        self.dragging = False
        self.drag_mouse_start = pygame.Vector2()
        self.drag_offset_start = pygame.Vector2()
        self.manual_offset = pygame.Vector2()

        self.mode = "signin"
        self.remembered = _load_remembered()
        self.auto_pending = False
        self.auto_deadline = 0

        self.logo_raw = None
        self._logo_cache = None
        self._logo_cache_key = None
        self._load_logo()

        rnd = random.Random(23)
        self.stars = [
            (
                rnd.uniform(0.06, 0.94),
                rnd.uniform(0.04, 0.50),
                rnd.uniform(0, 6.28),
                rnd.uniform(0.001, 0.004),
            )
            for _ in range(26)
        ]

        self._card_key = None
        self._card_surf = None
        self._card_pad = 0

        self.scale = 1.0
        self.origin_x = 0
        self.origin_y = 0

        self.card = pygame.Rect(0, 0, 0, 0)
        self.left_panel = pygame.Rect(0, 0, 0, 0)
        self.right_panel = pygame.Rect(0, 0, 0, 0)
        self.header_panel = pygame.Rect(0, 0, 0, 0)
        self.form_panel = pygame.Rect(0, 0, 0, 0)
        self.logo_rect = pygame.Rect(0, 0, 0, 0)

        self.username_rect = pygame.Rect(0, 0, 0, 0)
        self.password_rect = pygame.Rect(0, 0, 0, 0)
        self.eye_rect = pygame.Rect(0, 0, 0, 0)
        self.remember_rect = pygame.Rect(0, 0, 0, 0)
        self.login_button = pygame.Rect(0, 0, 0, 0)
        self.register_button = pygame.Rect(0, 0, 0, 0)
        self.continue_button = pygame.Rect(0, 0, 0, 0)
        self.forget_link = pygame.Rect(0, 0, 0, 0)

        self.close_button = pygame.Rect(0, 0, 0, 0)
        self.minimize_button = pygame.Rect(0, 0, 0, 0)

        self.forgot_link = pygame.Rect(0, 0, 0, 0)
        self.signup_link = pygame.Rect(0, 0, 0, 0)
        self.mini_rect = pygame.Rect(0, 0, 0, 0)

        self.recalculate_layout(reset_drag=True)
        self.resize_background(width, height)
        self.start_music()

        if self.remembered and not LoginScreen._auto_done:
            self._start_auto()

        LoginScreen._auto_done = True

    # ------------------------------------------------------------------
    # Music
    # ------------------------------------------------------------------

    def start_music(self):
        """Loops backgroundmusic1.mp3 while the login screen is open."""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            if LoginScreen._music_on and pygame.mixer.music.get_busy():
                return
            for path in self.MUSIC_PATHS:
                if os.path.exists(path):
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.set_volume(self.MUSIC_VOLUME)
                    pygame.mixer.music.play(-1, fade_ms=1200)
                    LoginScreen._music_on = True
                    return
        except pygame.error:
            pass

    @staticmethod
    def stop_music(fade_ms=800):
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.fadeout(fade_ms)
        except pygame.error:
            pass
        LoginScreen._music_on = False

    # ------------------------------------------------------------------
    # Logo (changeable)
    # ------------------------------------------------------------------

    def _load_logo(self):
        self.logo_raw = None
        self._logo_cache = None
        self._logo_cache_key = None

        for path in self.LOGO_PATHS:
            if os.path.exists(path):
                try:
                    self.logo_raw = pygame.image.load(path).convert_alpha()
                    return
                except (pygame.error, OSError):
                    continue

    def _logo_surface(self):
        if self.logo_raw is None:
            return None

        key = round(self.scale, 3)

        if self._logo_cache is not None and self._logo_cache_key == key:
            return self._logo_cache

        box_w = max(10, round(150 * self.scale))
        box_h = max(10, round(130 * self.scale))

        raw_w, raw_h = self.logo_raw.get_size()
        ratio = min(box_w / raw_w, box_h / raw_h)

        size = (max(1, round(raw_w * ratio)), max(1, round(raw_h * ratio)))

        self._logo_cache = pygame.transform.smoothscale(self.logo_raw, size)
        self._logo_cache_key = key

        return self._logo_cache

    def change_logo(self):
        """Opens a file picker and uses the chosen picture as the logo."""
        try:
            import tkinter
            from tkinter import filedialog
        except Exception:
            self.message = f"Picker unavailable: put your image at {self.LOGO_PATHS[0]}"
            self.message_color = (255, 190, 100)
            return

        root = tkinter.Tk()
        root.withdraw()

        try:
            root.attributes("-topmost", True)
        except Exception:
            pass

        try:
            path = filedialog.askopenfilename(
                title="Choose a logo image",
                filetypes=[
                    ("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                    ("All files", "*.*"),
                ],
            )
        finally:
            root.destroy()

        if not path:
            return

        try:
            image = pygame.image.load(path).convert_alpha()
            folder = os.path.dirname(self.LOGO_PATHS[0])

            if folder:
                os.makedirs(folder, exist_ok=True)

            pygame.image.save(image, self.LOGO_PATHS[0])
        except (pygame.error, OSError):
            self.message = "Could not use that image"
            self.message_color = (255, 120, 120)
            return

        self._load_logo()
        self.message = "Logo updated (right-click the logo to reset)"
        self.message_color = (110, 230, 170)

    def reset_logo(self):
        try:
            os.remove(self.LOGO_PATHS[0])
        except OSError:
            pass

        self._load_logo()
        self.message = "Logo reset"
        self.message_color = (110, 210, 220)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _rect(self, x, y, width, height):
        return pygame.Rect(
            round(self.origin_x + x * self.scale),
            round(self.origin_y + y * self.scale),
            max(1, round(width * self.scale)),
            max(1, round(height * self.scale)),
        )

    def _point(self, x, y):
        return (
            round(self.origin_x + x * self.scale),
            round(self.origin_y + y * self.scale),
        )

    def _font(self, size, bold=False):
        return pygame.font.SysFont(
            "segoeui,calibri,helvetica,arial",
            max(9, round(size * self.scale)),
            bold=bold,
        )

    def _build_fonts(self):
        self.title_font = self._font(36)
        self.label_font = self._font(12)
        self.value_font = self._font(20)
        self.button_font = self._font(16)
        self.small_font = self._font(13)
        self.caption_font = self._font(12, bold=True)
        self.font = self.value_font
        self.subtitle_font = self.small_font

    def recalculate_layout(self, reset_drag=False):
        if reset_drag:
            self.manual_offset.update(0, 0)

        old_scale = self.scale

        self.scale = max(
            0.1,
            min(
                self.width / self.DESIGN_WIDTH,
                self.height / self.DESIGN_HEIGHT,
            ),
        )

        self.origin_x = (
            self.width - self.DESIGN_WIDTH * self.scale
        ) / 2 + self.manual_offset.x

        self.origin_y = (
            self.height - self.DESIGN_HEIGHT * self.scale
        ) / 2 + self.manual_offset.y

        if abs(old_scale - self.scale) > 0.001 or not hasattr(self, "title_font"):
            self._build_fonts()

        s = self.scale

        self.card = self._rect(100, 80, 800, 490)
        self.left_panel = self._rect(100, 80, 360, 490)
        self.right_panel = self._rect(460, 80, 440, 490)

        self.header_panel = self._rect(460, 80, 370, 70)
        self.form_panel = self.card

        self.logo_rect = self._rect(205, 180, 150, 140)

        self.minimize_button = self._rect(836, 98, 26, 26)
        self.close_button = self._rect(868, 98, 26, 26)

        self.username_rect = self._rect(460, 160, 440, 64)
        self.password_rect = self._rect(460, 230, 440, 64)

        eye = max(16, round(34 * s))
        self.eye_rect = pygame.Rect(0, 0, eye, eye)
        self.eye_rect.center = (
            self.password_rect.right - round(98 * s),
            self.password_rect.centery,
        )

        self.remember_rect = self._rect(500, 304, 170, 28)

        self.forgot_link = self._rect(500, 346, 170, 46)
        self.login_button = self._rect(730, 346, 130, 46)

        self.continue_button = self._rect(500, 420, 360, 52)
        self.forget_link = self._rect(560, 480, 240, 26)

        self.register_button = self._rect(150, 345, 260, 46)
        self.signup_link = self.register_button.copy()

        mini_width = max(190, round(300 * s))
        mini_height = max(45, round(58 * s))

        self.mini_rect = pygame.Rect(0, 0, mini_width, mini_height)
        self.mini_rect.bottomright = (
            self.width - max(12, round(25 * s)),
            self.height - max(12, round(25 * s)),
        )

    def _clamp_drag_offset(self):
        scale = self.scale

        base_x = (self.width - self.DESIGN_WIDTH * scale) / 2
        base_y = (self.height - self.DESIGN_HEIGHT * scale) / 2

        panel_left = base_x + 100 * scale
        panel_right = base_x + 900 * scale
        panel_top = base_y + 80 * scale
        panel_bottom = base_y + 570 * scale

        visible = max(35, round(80 * scale))

        minimum_x = visible - panel_right
        maximum_x = self.width - visible - panel_left

        minimum_y = visible - panel_bottom
        maximum_y = self.height - visible - panel_top

        self.manual_offset.x = max(
            minimum_x,
            min(maximum_x, self.manual_offset.x),
        )

        self.manual_offset.y = max(
            minimum_y,
            min(maximum_y, self.manual_offset.y),
        )

    # ------------------------------------------------------------------
    # Background (unchanged)
    # ------------------------------------------------------------------

    def resize_background(self, width, height):
        width = max(1, width)
        height = max(1, height)

        if self.bg_raw:
            raw_width, raw_height = self.bg_raw.get_size()

            cover_scale = max(
                width / raw_width,
                height / raw_height,
            ) * 1.08

            scaled_width = max(1, round(raw_width * cover_scale))
            scaled_height = max(1, round(raw_height * cover_scale))

            self.bg_image = pygame.transform.smoothscale(
                self.bg_raw,
                (scaled_width, scaled_height),
            )
        else:
            self.bg_image = self._create_fallback_background(width, height)

        self.background_fx = pygame.Surface(
            (width, height),
            pygame.SRCALPHA,
        )

        self.background_fx.fill((0, 4, 16, 120))

        grid_spacing = max(25, round(48 * self.scale))

        for x in range(0, width, grid_spacing):
            pygame.draw.line(
                self.background_fx,
                (0, 100, 155, 12),
                (x, 0),
                (x, height),
            )

        for y in range(0, height, grid_spacing):
            pygame.draw.line(
                self.background_fx,
                (0, 100, 155, 12),
                (0, y),
                (width, y),
            )

        for y in range(0, height, 4):
            pygame.draw.line(
                self.background_fx,
                (0, 0, 0, 16),
                (0, y),
                (width, y),
            )

    def _create_fallback_background(self, width, height):
        surface = pygame.Surface((width, height))

        for y in range(height):
            ratio = y / max(1, height - 1)

            color = (
                1,
                5 + round(7 * ratio),
                16 + round(15 * ratio),
            )

            pygame.draw.line(
                surface,
                color,
                (0, y),
                (width, y),
            )

        randomizer = random.Random(17)

        for _ in range(max(30, width * height // 18000)):
            x = randomizer.randrange(width)
            y = randomizer.randrange(height)
            brightness = randomizer.randrange(25, 75)

            pygame.draw.circle(
                surface,
                (brightness // 3, brightness // 2, brightness),
                (x, y),
                randomizer.choice((1, 1, 1, 2)),
            )

        map_surface = pygame.Surface((width, height), pygame.SRCALPHA)

        def points(values):
            return [
                (round(px * width), round(py * height))
                for px, py in values
            ]

        continents = [
            [
                (0.05, 0.29), (0.13, 0.20), (0.24, 0.20),
                (0.34, 0.28), (0.29, 0.36), (0.23, 0.38),
                (0.19, 0.47), (0.11, 0.42), (0.07, 0.35),
            ],
            [
                (0.21, 0.43), (0.29, 0.48), (0.29, 0.59),
                (0.25, 0.73), (0.21, 0.65), (0.18, 0.52),
            ],
            [
                (0.36, 0.28), (0.46, 0.21), (0.57, 0.24),
                (0.66, 0.18), (0.79, 0.21), (0.92, 0.33),
                (0.84, 0.41), (0.70, 0.37), (0.61, 0.42),
                (0.51, 0.34), (0.43, 0.39), (0.37, 0.34),
            ],
            [
                (0.43, 0.38), (0.56, 0.39), (0.62, 0.49),
                (0.55, 0.67), (0.48, 0.60), (0.44, 0.49),
            ],
            [
                (0.77, 0.58), (0.88, 0.57), (0.93, 0.65),
                (0.86, 0.70), (0.77, 0.66),
            ],
        ]

        for continent in continents:
            pygame.draw.polygon(
                map_surface,
                (5, 42, 70, 145),
                points(continent),
            )

            pygame.draw.lines(
                map_surface,
                (7, 57, 91, 100),
                True,
                points(continent),
                1,
            )

        surface.blit(map_surface, (0, 0))
        return surface

    # ------------------------------------------------------------------
    # Card surface (shadow + glass right panel + left skyline), cached
    # ------------------------------------------------------------------

    def _build_left_panel(self, width, height, radius):
        s = self.scale
        surface = pygame.Surface((width, height), pygame.SRCALPHA)

        for y in range(height):
            t = y / max(1, height - 1)
            color = (
                round(14 - 7 * t),
                round(64 - 38 * t),
                round(70 - 38 * t),
                255,
            )
            pygame.draw.line(surface, color, (0, y), (width, y))

        rnd = random.Random(11)

        x = 0
        min_w = max(8, round(18 * s))
        max_w = max(min_w + 1, round(46 * s))
        step_y = max(4, round(9 * s))
        step_x = max(4, round(7 * s))

        while x < width:
            bw = rnd.randint(min_w, max_w)
            bh = rnd.randint(round(height * 0.30), round(height * 0.78))
            top = height - bh

            pygame.draw.rect(surface, (5, 25, 31, 255), (x, top, bw, bh))

            for wy in range(top + step_y, height, step_y):
                for wx in range(x + step_x // 2, x + bw - step_x // 2, step_x):
                    if rnd.random() < 0.22:
                        g = rnd.randrange(90, 145)
                        pygame.draw.rect(
                            surface,
                            (g // 3, g, g + 5, 255),
                            (wx, wy, max(1, round(2 * s)), max(1, round(3 * s))),
                        )

            x += bw + rnd.randint(0, max(1, round(4 * s)))

        fade = pygame.Surface((width, height), pygame.SRCALPHA)
        start = int(height * 0.45)

        for y in range(start, height):
            alpha = round(150 * (y - start) / max(1, height - start))
            pygame.draw.line(fade, (3, 14, 18, alpha), (0, y), (width, y))

        surface.blit(fade, (0, 0))

        mask = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(
            mask,
            (255, 255, 255, 255),
            mask.get_rect(),
            border_top_left_radius=radius,
            border_bottom_left_radius=radius,
        )
        surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.fill((255, 255, 255, 175), special_flags=pygame.BLEND_RGBA_MULT)

        return surface

    def _card_surface(self):
        key = (self.card.width, self.card.height)

        if key == self._card_key and self._card_surf is not None:
            return self._card_surf

        s = self.scale
        w, h = key
        pad = max(10, round(30 * s))
        radius = max(6, round(12 * s))

        surface = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)

        for i in range(pad):
            inflate = pad - i
            pygame.draw.rect(
                surface,
                (0, 0, 0, 3),
                pygame.Rect(
                    pad - inflate,
                    pad - inflate + pad // 3,
                    w + inflate * 2,
                    h + inflate * 2,
                ),
                border_radius=radius + inflate,
            )

        body = pygame.Rect(pad, pad, w, h)

        pygame.draw.rect(surface, self.CARD_RIGHT, body, border_radius=radius)

        left = self._build_left_panel(self.left_panel.width, h, radius)
        surface.fill(
            (0, 0, 0, 0),
            pygame.Rect(pad, pad, left.get_width(), h),
        )
        surface.blit(left, body.topleft)

        pygame.draw.rect(
            surface,
            (150, 215, 225, 110),
            body,
            1,
            border_radius=radius,
        )

        self._card_key = key
        self._card_surf = surface
        self._card_pad = pad

        return surface

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _fill_alpha(self, rect, color):
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        layer.fill(color)
        self.screen.blit(layer, rect.topleft)

    def _pill(self, rect, fill=None, border=None, width=1):
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        radius = rect.height // 2

        if fill:
            pygame.draw.rect(
                layer, fill, layer.get_rect(), border_radius=radius
            )

        if border:
            pygame.draw.rect(
                layer,
                border,
                layer.get_rect(),
                max(1, round(width * self.scale)),
                border_radius=radius,
            )

        self.screen.blit(layer, rect.topleft)

    @staticmethod
    def _fit_text(font, text, max_width):
        if font.size(text)[0] <= max_width:
            return text

        while text and font.size(text + "...")[0] > max_width:
            text = text[:-1]

        return text + "..."

    def _spaced_text(self, text, font, color, center, spacing):
        glyphs = [font.render(ch, True, color) for ch in text]
        total = sum(g.get_width() for g in glyphs) + spacing * max(0, len(glyphs) - 1)
        x = center[0] - total // 2
        y = center[1] - glyphs[0].get_height() // 2 if glyphs else center[1]

        for glyph in glyphs:
            self.screen.blit(glyph, (x, y))
            x += glyph.get_width() + spacing

    def _draw_user_icon(self, center, color):
        s = self.scale
        cx, cy = center

        pygame.draw.circle(
            self.screen,
            color,
            (cx, cy - round(5 * s)),
            max(3, round(5 * s)),
        )

        body = pygame.Rect(0, 0, round(18 * s), round(20 * s))
        body.midtop = (cx, cy + round(2 * s))

        old_clip = self.screen.get_clip()
        self.screen.set_clip(
            pygame.Rect(body.x, body.y, body.width, round(9 * s))
        )
        pygame.draw.ellipse(self.screen, color, body)
        self.screen.set_clip(old_clip)

    def _draw_lock_icon(self, center, color):
        s = self.scale
        cx, cy = center
        thickness = max(2, round(2 * s))

        shackle = pygame.Rect(0, 0, round(10 * s), round(13 * s))
        shackle.midtop = (cx, cy - round(10 * s))
        pygame.draw.arc(self.screen, color, shackle, 0, math.pi, thickness)

        body = pygame.Rect(0, 0, round(16 * s), round(12 * s))
        body.midtop = (cx, cy - round(3 * s))
        pygame.draw.rect(
            self.screen, color, body, border_radius=max(1, round(2 * s))
        )

    def _draw_eye_icon(self, center, color, crossed):
        s = self.scale
        cx, cy = center

        width = max(8, round(22 * s))
        height = max(5, round(13 * s))

        eye = pygame.Rect(0, 0, width, height)
        eye.center = center

        pygame.draw.ellipse(self.screen, color, eye, max(1, round(2 * s)))
        pygame.draw.circle(self.screen, color, center, max(2, round(3 * s)))

        if crossed:
            pygame.draw.line(
                self.screen,
                color,
                (cx - width // 2 + 1, cy + height // 2 + 1),
                (cx + width // 2 - 1, cy - height // 2 - 1),
                max(2, round(2 * s)),
            )

    def _draw_field(self, rect, label, value, active, icon, right_pad):
        s = self.scale

        self._fill_alpha(rect, (255, 255, 255, 24 if active else 10))

        pygame.draw.line(
            self.screen, (40, 72, 80), rect.topleft, rect.topright
        )

        if active:
            pygame.draw.line(
                self.screen,
                self.TEAL,
                (rect.left, rect.bottom - 1),
                (rect.right, rect.bottom - 1),
                max(1, round(2 * s)),
            )

            pygame.draw.rect(
                self.screen,
                self.TEAL,
                pygame.Rect(
                    rect.left,
                    rect.top + 1,
                    max(2, round(3 * s)),
                    rect.height - 2,
                ),
            )
        else:
            pygame.draw.line(
                self.screen,
                (40, 72, 80),
                (rect.left, rect.bottom - 1),
                (rect.right, rect.bottom - 1),
            )

        pad_x = max(12, round(40 * s))

        label_surface = self.label_font.render(
            label,
            True,
            (110, 215, 222) if active else (130, 170, 176),
        )
        self.screen.blit(
            label_surface,
            (rect.x + pad_x, rect.y + max(5, round(10 * s))),
        )

        text_x = rect.x + pad_x
        text_y = rect.y + max(16, round(30 * s))

        rendered = self.value_font.render(value, True, self.TEXT)

        available = rect.width - pad_x - max(40, round(right_pad * s))
        offset = max(0, rendered.get_width() - available + max(4, round(6 * s)))

        old_clip = self.screen.get_clip()
        self.screen.set_clip(
            pygame.Rect(rect.x + pad_x, rect.y + 2, available, rect.height - 4)
        )

        self.screen.blit(rendered, (text_x - offset, text_y))

        if active and pygame.time.get_ticks() // 500 % 2 == 0:
            cursor_x = text_x - offset + rendered.get_width() + max(1, round(2 * s))
            pygame.draw.line(
                self.screen,
                (150, 240, 245),
                (cursor_x, text_y + 2),
                (cursor_x, text_y + rendered.get_height() - 2),
                max(1, round(2 * s)),
            )

        self.screen.set_clip(old_clip)

        icon_color = (90, 190, 195) if active else (60, 95, 102)
        icon_center = (rect.right - max(20, round(46 * s)), rect.centery)

        if icon == "user":
            self._draw_user_icon(icon_center, icon_color)
        else:
            self._draw_lock_icon(icon_center, icon_color)

    def _draw_outline_pill(self, rect, text, bright=False):
        hovered = rect.collidepoint(pygame.mouse.get_pos())

        if bright:
            border = (235, 245, 247, 255) if hovered else (200, 225, 228, 255)
            color = (255, 255, 255)
        else:
            border = (130, 210, 215, 255) if hovered else (95, 160, 168, 255)
            color = (190, 238, 242) if hovered else (140, 205, 210)

        self._pill(
            rect,
            fill=(255, 255, 255, 18) if hovered else None,
            border=border,
        )

        surface = self.button_font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(center=rect.center))

    def _draw_primary_pill(self, rect, text):
        hovered = rect.collidepoint(pygame.mouse.get_pos())

        glow = pygame.Surface(
            (rect.width + 24, rect.height + 24), pygame.SRCALPHA
        )

        for i in range(8):
            pygame.draw.rect(
                glow,
                (60, 200, 210, 5 if not hovered else 8),
                pygame.Rect(i, i, rect.width + 24 - i * 2, rect.height + 24 - i * 2),
                border_radius=(rect.height + 24 - i * 2) // 2,
            )

        self.screen.blit(glow, (rect.x - 12, rect.y - 12))

        self._pill(
            rect,
            fill=(58, 190, 200, 255) if hovered else (40, 160, 172, 255),
            border=(150, 235, 240, 200),
        )

        surface = self.button_font.render(text, True, (255, 255, 255))
        self.screen.blit(surface, surface.get_rect(center=rect.center))

    def _draw_checkbox(self, rect, label, checked):
        s = self.scale
        hovered = rect.collidepoint(pygame.mouse.get_pos())

        size = max(12, round(17 * s))
        box = pygame.Rect(rect.x, rect.centery - size // 2, size, size)

        if checked:
            pygame.draw.rect(
                self.screen, self.TEAL, box, border_radius=max(2, round(4 * s))
            )

            pygame.draw.lines(
                self.screen,
                (6, 30, 36),
                False,
                [
                    (box.x + size * 0.22, box.y + size * 0.52),
                    (box.x + size * 0.43, box.y + size * 0.74),
                    (box.x + size * 0.78, box.y + size * 0.28),
                ],
                max(2, round(2 * s)),
            )
        else:
            pygame.draw.rect(
                self.screen,
                (150, 215, 222) if hovered else (90, 140, 148),
                box,
                max(1, round(2 * s)),
                border_radius=max(2, round(4 * s)),
            )

        text = self.small_font.render(
            label,
            True,
            self.TEXT if hovered else self.TEXT_SOFT,
        )
        self.screen.blit(
            text,
            text.get_rect(midleft=(box.right + max(6, round(9 * s)), rect.centery)),
        )

    def _draw_window_controls(self):
        mouse = pygame.mouse.get_pos()
        s = self.scale

        for rect, kind in (
            (self.minimize_button, "min"),
            (self.close_button, "close"),
        ):
            hovered = rect.collidepoint(mouse)

            if hovered:
                layer = pygame.Surface(rect.size, pygame.SRCALPHA)
                tint = (255, 90, 90, 60) if kind == "close" else (255, 255, 255, 30)
                pygame.draw.circle(
                    layer, tint, (rect.width // 2, rect.height // 2), rect.width // 2
                )
                self.screen.blit(layer, rect.topleft)

            color = (240, 250, 252) if hovered else (120, 160, 165)
            line_width = max(1, round(2 * s))
            size = max(3, round(6 * s))
            cx, cy = rect.center

            if kind == "min":
                pygame.draw.line(
                    self.screen, color, (cx - size, cy), (cx + size, cy), line_width
                )
            else:
                pygame.draw.line(
                    self.screen, color, (cx - size, cy - size), (cx + size, cy + size), line_width
                )
                pygame.draw.line(
                    self.screen, color, (cx + size, cy - size), (cx - size, cy + size), line_width
                )

    def _draw_stars(self, ticks):
        left = self.left_panel
        s = self.scale

        for fx, fy, phase, speed in self.stars:
            b = 0.5 + 0.5 * math.sin(ticks * speed + phase)
            shade = round(60 + 160 * b)

            x = left.x + round(fx * left.width)
            y = left.y + round(fy * left.height)

            radius = max(1, round((1 if b < 0.75 else 1.7) * s))

            pygame.draw.circle(
                self.screen, (shade // 2, shade, shade), (x, y), radius
            )

    def _draw_logo(self, ticks):
        s = self.scale

        bob = math.sin(ticks * 0.003) * 3 * s

        center_x, center_y = self._point(280, 250)
        center_y += round(bob)

        radius = round(100 * s)
        glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)

        alpha = 3 + round(1.5 * math.sin(ticks * 0.004))

        for r in range(radius, 0, -4):
            pygame.draw.circle(glow, (60, 200, 210, alpha), (radius, radius), r)

        self.screen.blit(glow, (center_x - radius, center_y - radius))

        image = self._logo_surface()

        if image is not None:
            self.screen.blit(
                image, image.get_rect(center=(center_x, center_y))
            )
            return

        cell = max(2, round(9 * s))

        rows = len(self.ALIEN)
        cols = len(self.ALIEN[0])

        x0 = center_x - cols * cell // 2
        y0 = center_y - rows * cell // 2

        for row, line in enumerate(self.ALIEN):
            for col, char in enumerate(line):
                if char == "#":
                    pygame.draw.rect(
                        self.screen,
                        (232, 248, 250),
                        (x0 + col * cell, y0 + row * cell, cell, cell),
                    )

        for row in (5, 6):
            for col in (3, 4, 8, 9):
                pygame.draw.rect(
                    self.screen,
                    (60, 215, 225),
                    (x0 + col * cell, y0 + row * cell, cell, cell),
                )

    def _draw_continue(self):
        if self.mode != "signin":
            return

        rect = self.continue_button
        s = self.scale
        mouse = pygame.mouse.get_pos()

        if not self.remembered:
            self._pill(
                rect,
                fill=(255, 255, 255, 8),
                border=(70, 110, 118, 160),
            )

            surface = self.button_font.render(
                "No saved account yet", True, (90, 125, 132)
            )
            self.screen.blit(surface, surface.get_rect(center=rect.center))
            return

        hovered = rect.collidepoint(mouse)

        self._pill(
            rect,
            fill=(255, 255, 255, 38 if hovered else 20),
            border=(120, 215, 222, 240 if hovered else 170),
        )

        name = self.remembered.get("display", "Pilot")

        radius = rect.height // 2 - max(5, round(7 * s))
        center = (rect.x + rect.height // 2, rect.centery)

        pygame.draw.circle(self.screen, (60, 170, 178), center, radius)

        initial = self.button_font.render(name[:1].upper(), True, (255, 255, 255))
        self.screen.blit(initial, initial.get_rect(center=center))

        text_x = rect.x + rect.height + max(2, round(4 * s))
        max_text = rect.right - text_x - max(30, round(44 * s))

        main = self.button_font.render(
            self._fit_text(self.button_font, "Continue to this account", max_text),
            True,
            self.TEXT,
        )

        sub_label = f"Signing in as {name}..." if self.auto_pending else name

        sub = self.small_font.render(
            self._fit_text(self.small_font, sub_label, max_text),
            True,
            self.TEXT_SOFT,
        )

        total = main.get_height() + sub.get_height() - 2
        y0 = rect.centery - total // 2

        self.screen.blit(main, (text_x, y0))
        self.screen.blit(sub, (text_x, y0 + main.get_height() - 2))

        arrow_x = rect.right - max(22, round(34 * s))
        arrow_size = max(3, round(6 * s))

        pygame.draw.lines(
            self.screen,
            (190, 235, 240) if hovered else (130, 190, 198),
            False,
            [
                (arrow_x - arrow_size, rect.centery - arrow_size),
                (arrow_x, rect.centery),
                (arrow_x - arrow_size, rect.centery + arrow_size),
            ],
            max(2, round(2 * s)),
        )

        if self.auto_pending:
            remaining = max(0, self.auto_deadline - pygame.time.get_ticks())
            progress = 1 - remaining / AUTO_LOGIN_MS

            bar_y = rect.bottom - max(5, round(8 * s))
            bar_x = rect.x + rect.height // 2
            bar_w = rect.width - rect.height

            pygame.draw.line(
                self.screen,
                (40, 80, 88),
                (bar_x, bar_y),
                (bar_x + bar_w, bar_y),
                max(1, round(2 * s)),
            )

            if progress > 0:
                pygame.draw.line(
                    self.screen,
                    self.TEAL,
                    (bar_x, bar_y),
                    (bar_x + round(bar_w * progress), bar_y),
                    max(1, round(2 * s)),
                )

        link_hover = self.forget_link.collidepoint(mouse)

        link = self.small_font.render(
            "Cancel auto sign-in"
            if self.auto_pending
            else "Not you? Forget this account",
            True,
            (150, 225, 232) if link_hover else (100, 150, 158),
        )

        link_rect = link.get_rect(center=self.forget_link.center)
        self.screen.blit(link, link_rect)

        if link_hover:
            pygame.draw.line(
                self.screen,
                (150, 225, 232),
                (link_rect.left, link_rect.bottom),
                (link_rect.right, link_rect.bottom),
            )

    # ------------------------------------------------------------------
    # Main drawing
    # ------------------------------------------------------------------

    def update(self, dt):
        """Per-frame update hook used by main.py."""
        return None

    def _draw_minimized(self, ticks):
        rect = self.mini_rect

        self._pill(
            rect,
            fill=self.CARD_RIGHT,
            border=(80, 140, 150, 160),
        )

        dot = (
            rect.x + max(15, round(26 * self.scale)),
            rect.centery,
        )

        status_color = (
            (0, 255, 160)
            if ticks // 500 % 2 == 0
            else (0, 90, 65)
        )

        pygame.draw.circle(
            self.screen, status_color, dot, max(3, round(5 * self.scale))
        )

        text = self.small_font.render(
            "SPACE INVADER  //  RESTORE", True, (190, 245, 255)
        )

        self.screen.blit(
            text,
            text.get_rect(
                midleft=(dot[0] + max(12, round(18 * self.scale)), rect.centery)
            ),
        )

    def draw(self):
        self.screen.fill((0, 3, 12))

        ticks = pygame.time.get_ticks()
        motion = ticks * 0.00035

        bg_width, bg_height = self.bg_image.get_size()

        bleed_x = max(0, (bg_width - self.width) // 2)
        bleed_y = max(0, (bg_height - self.height) // 2)

        drift_x = round(
            math.sin(motion) *
            min(bleed_x, max(2, round(10 * self.scale)))
        )

        drift_y = round(
            math.sin(motion * 0.7) *
            min(bleed_y, max(2, round(7 * self.scale)))
        )

        background_x = (self.width - bg_width) // 2 + drift_x
        background_y = (self.height - bg_height) // 2 + drift_y

        self.screen.blit(
            self.bg_image,
            (background_x, background_y),
        )

        self.screen.blit(self.background_fx, (0, 0))

        if self.is_minimized:
            self._draw_minimized(ticks)
            return

        s = self.scale
        mouse = pygame.mouse.get_pos()
        reset_mode = self.mode == "reset"

        surface = self._card_surface()
        self.screen.blit(
            surface,
            (self.card.x - self._card_pad, self.card.y - self._card_pad),
        )

        self._draw_stars(ticks)
        self._draw_logo(ticks)

        self._spaced_text(
            "SPACE INVADER",
            self.caption_font,
            (110, 190, 196),
            self._point(280, 118),
            max(2, round(3 * s)),
        )

        if self.logo_rect.collidepoint(mouse):
            hint = self.label_font.render(
                "Click to change logo  •  Right-click to reset",
                True,
                (150, 205, 212),
            )
            self.screen.blit(
                hint, hint.get_rect(center=self._point(280, 326))
            )

        self._draw_outline_pill(
            self.register_button, "Create an account", bright=True
        )

        title = self.title_font.render(
            "Reset password" if reset_mode else "Sign in",
            True,
            (170, 215, 222),
        )
        self.screen.blit(title, self._point(500, 90))

        accent_y = self._point(0, 138)[1]
        accent_x = self._point(500, 0)[0]

        pygame.draw.line(
            self.screen,
            self.TEAL,
            (accent_x, accent_y),
            (accent_x + round(44 * s), accent_y),
            max(2, round(3 * s)),
        )
        pygame.draw.line(
            self.screen,
            (40, 95, 104),
            (accent_x + round(48 * s), accent_y),
            (accent_x + round(120 * s), accent_y),
            max(1, round(2 * s)),
        )

        self._draw_window_controls()

        self._draw_field(
            self.username_rect,
            "Username",
            self.username,
            self.active_field == "username",
            "user",
            70,
        )

        password_text = (
            self.password
            if self.show_password
            else "•" * len(self.password)
        )

        self._draw_field(
            self.password_rect,
            "New password" if reset_mode else "Password",
            password_text,
            self.active_field == "password",
            "lock",
            130,
        )

        eye_hover = self.eye_rect.collidepoint(mouse)

        if eye_hover:
            layer = pygame.Surface(self.eye_rect.size, pygame.SRCALPHA)
            pygame.draw.circle(
                layer,
                (255, 255, 255, 28),
                (self.eye_rect.width // 2, self.eye_rect.height // 2),
                self.eye_rect.width // 2,
            )
            self.screen.blit(layer, self.eye_rect.topleft)

        self._draw_eye_icon(
            self.eye_rect.center,
            (200, 240, 245)
            if eye_hover
            else ((110, 215, 222) if self.show_password else (90, 140, 148)),
            crossed=not self.show_password,
        )

        if not reset_mode:
            self._draw_checkbox(self.remember_rect, "Remember me", self.remember_me)

        if pygame.key.get_mods() & pygame.KMOD_CAPS:
            caps = self.label_font.render(
                "Caps Lock is on", True, (255, 200, 110)
            )
            self.screen.blit(
                caps,
                caps.get_rect(midright=self._point(860, 318)),
            )

        forgot_hovered = self.forgot_link.collidepoint(mouse)

        forgot = self.button_font.render(
            "Back to sign in" if reset_mode else "Forgot password",
            True,
            (110, 225, 232) if forgot_hovered else (70, 190, 200),
        )

        forgot_rect = forgot.get_rect(midleft=self.forgot_link.midleft)
        self.screen.blit(forgot, forgot_rect)

        if forgot_hovered:
            pygame.draw.line(
                self.screen,
                (110, 225, 232),
                (forgot_rect.left, forgot_rect.bottom),
                (forgot_rect.right, forgot_rect.bottom),
            )

        self._draw_primary_pill(
            self.login_button,
            "Reset" if reset_mode else "Sign in",
        )

        if self.message:
            fitted = self._fit_text(
                self.small_font,
                self.message,
                round(380 * s),
            )

            message_surface = self.small_font.render(
                fitted, True, self.message_color
            )

            self.screen.blit(
                message_surface,
                message_surface.get_rect(center=self._point(680, 404)),
            )

        self._draw_continue()

    # ------------------------------------------------------------------
    # Saved account, auto sign-in, password reset
    # ------------------------------------------------------------------

    @classmethod
    def disable_auto_login(cls):
        """Call on sign-out so the next login screen won't sign the player back in."""
        cls._auto_done = True

    @staticmethod
    def forget_account():
        """Removes the remembered account (call this for a full sign-out)."""
        _forget_remembered()

    def _start_auto(self):
        self.auto_pending = True
        self.auto_deadline = pygame.time.get_ticks() + AUTO_LOGIN_MS

        try:
            pygame.time.set_timer(AUTO_EVENT, AUTO_LOGIN_MS, 1)
        except (TypeError, pygame.error):
            pass

    def cancel_auto(self):
        if not self.auto_pending:
            return

        self.auto_pending = False

        try:
            pygame.time.set_timer(AUTO_EVENT, 0)
        except pygame.error:
            pass

    def _remember_password(self, username, password):
        record = {"method": "password", "username": username, "display": username}
        _save_remembered(record, password)
        self.remembered = record

    def _run_remembered(self):
        record = self.remembered
        self.cancel_auto()

        if not record:
            self.message = "Sign in once and your account will be saved here"
            self.message_color = (110, 210, 220)
            return None

        password = _remembered_password(record)

        if not password:
            _forget_remembered()
            self.remembered = None
            self.message = "Saved sign-in expired, please sign in again"
            self.message_color = (255, 190, 100)
            return None

        player, message = login(record["username"], password)

        if player:
            name = record.get("display", "Pilot")
            self.message = message or f"Welcome back, {name}"
            self.message_color = (110, 230, 170)
            self.stop_music()
            return player

        _forget_remembered()
        self.remembered = None
        self.message = message or "Saved sign-in no longer works"
        self.message_color = (255, 120, 120)
        return None

    def toggle_mode(self):
        self.cancel_auto()

        self.mode = "reset" if self.mode == "signin" else "signin"
        self.password = ""
        self.show_password = False
        self.active_field = "username"

        if self.mode == "reset":
            self.message = "Enter your username and a new password"
            self.message_color = (110, 210, 220)
        else:
            self.message = ""

    def do_reset(self):
        username = self.username.strip()

        if not username or len(self.password) < 4:
            self.message = "Enter your username and a new password (4+ characters)"
            self.message_color = (255, 120, 120)
            return None

        hook = getattr(auth, "reset_password", None)

        if not callable(hook):
            self.message = "Password reset is not available yet (add reset_password to auth.py)"
            self.message_color = (255, 190, 100)
            return None

        try:
            outcome = hook(username, self.password)
        except Exception:
            self.message = "Could not reset the password"
            self.message_color = (255, 120, 120)
            return None

        if isinstance(outcome, tuple) and len(outcome) == 2:
            ok, message = outcome
        else:
            ok, message = bool(outcome), ""

        if ok:
            if self.remembered and self.remembered.get("username") == username:
                _forget_remembered()
                self.remembered = None

            self.mode = "signin"
            self.password = ""
            self.show_password = False
            self.message = message or "Password updated, sign in with the new password"
            self.message_color = (110, 230, 170)
        else:
            self.message = message or "Could not reset the password"
            self.message_color = (255, 120, 120)

        return None

    def _paste(self):
        text = _clipboard_text().replace("\r", "").replace("\n", "")
        text = "".join(ch for ch in text if ch.isprintable())

        if not text:
            return

        if self.active_field == "username":
            self.username = (self.username + text)[:20]
        else:
            self.password = (self.password + text)[:30]

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def handle_event(self, event):
        if self.auto_pending and (
            event.type == AUTO_EVENT
            or pygame.time.get_ticks() >= self.auto_deadline
        ):
            return self._run_remembered()

        if event.type == pygame.VIDEORESIZE:
            self.width = event.w
            self.height = event.h

            self.recalculate_layout(reset_drag=True)
            self.resize_background(event.w, event.h)
            return None

        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 3
            and not self.is_minimized
        ):
            if self.logo_rect.collidepoint(event.pos):
                self.reset_logo()

            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_minimized:
                if self.mini_rect.collidepoint(event.pos):
                    self.is_minimized = False
                    self.recalculate_layout(reset_drag=True)
                return None

            if self.close_button.collidepoint(event.pos):
                self.stop_music()
                return "exit"

            if self.minimize_button.collidepoint(event.pos):
                self.is_minimized = True
                self.dragging = False
                return None

            if self.eye_rect.collidepoint(event.pos):
                self.show_password = not self.show_password
                self.active_field = "password"
                return None

            if self.username_rect.collidepoint(event.pos):
                self.active_field = "username"
                return None

            if self.password_rect.collidepoint(event.pos):
                self.active_field = "password"
                return None

            if self.mode == "signin" and self.remember_rect.collidepoint(event.pos):
                self.remember_me = not self.remember_me
                return None

            if self.login_button.collidepoint(event.pos):
                if self.mode == "reset":
                    return self.do_reset()
                return self.do_login()

            if self.mode == "signin" and self.continue_button.collidepoint(event.pos):
                return self._run_remembered()

            if (
                self.mode == "signin"
                and self.remembered
                and self.forget_link.collidepoint(event.pos)
            ):
                if self.auto_pending:
                    self.cancel_auto()
                    self.message = "Auto sign-in cancelled"
                    self.message_color = (255, 190, 100)
                else:
                    _forget_remembered()
                    self.remembered = None
                    self.message = "Saved account removed"
                    self.message_color = (110, 210, 220)
                return None

            if (
                self.register_button.collidepoint(event.pos)
                or self.signup_link.collidepoint(event.pos)
            ):
                self.cancel_auto()
                return "register"

            if self.forgot_link.collidepoint(event.pos):
                self.toggle_mode()
                return None

            if self.logo_rect.collidepoint(event.pos):
                self.change_logo()
                return None

            if (
                self.left_panel.collidepoint(event.pos)
                or self.header_panel.collidepoint(event.pos)
            ):
                self.dragging = True
                self.drag_mouse_start.update(event.pos)
                self.drag_offset_start.update(self.manual_offset)

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False

        elif event.type == pygame.MOUSEMOTION and self.dragging:
            movement = (
                pygame.Vector2(event.pos) -
                self.drag_mouse_start
            )

            self.manual_offset = (
                self.drag_offset_start + movement
            )

            self._clamp_drag_offset()
            self.recalculate_layout()

        if event.type == pygame.KEYDOWN and not self.is_minimized:
            if self.auto_pending:
                self.cancel_auto()

                if event.key == pygame.K_ESCAPE:
                    self.message = "Auto sign-in cancelled"
                    self.message_color = (255, 190, 100)
                    return None

            if event.key == pygame.K_ESCAPE and self.mode == "reset":
                self.toggle_mode()

            elif event.key == pygame.K_TAB:
                self.active_field = (
                    "password"
                    if self.active_field == "username"
                    else "username"
                )

            elif event.key == pygame.K_BACKSPACE:
                if self.active_field == "username":
                    self.username = self.username[:-1]
                elif self.active_field == "password":
                    self.password = self.password[:-1]

            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.active_field == "username" and not self.password:
                    self.active_field = "password"
                    return None

                if self.mode == "reset":
                    return self.do_reset()

                return self.do_login()

            elif event.key == pygame.K_v and event.mod & pygame.KMOD_CTRL:
                self._paste()

            elif event.unicode and event.unicode.isprintable():
                if self.active_field == "username":
                    if len(self.username) < 20:
                        self.username += event.unicode

                elif self.active_field == "password":
                    if len(self.password) < 30:
                        self.password += event.unicode

        return None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def do_login(self):
        self.cancel_auto()

        if not self.username.strip() or not self.password:
            self.message = "Username and password required"
            self.message_color = (255, 120, 120)
            return None

        player, message = login(
            self.username.strip(),
            self.password,
        )

        if player:
            if self.remember_me:
                self._remember_password(self.username.strip(), self.password)
            else:
                _forget_remembered()
                self.remembered = None

            self.message = message
            self.message_color = (110, 230, 170)
            self.stop_music()
            return player

        self.message = message
        self.message_color = (255, 120, 120)
        return None