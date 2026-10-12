import os
import math
import random

import pygame

from db import get_leaderboard

# Optional: used to fetch each player's chosen ship (the same photo that
# is shown on the profile page) when the leaderboard rows don't carry it.
try:
    from db import get_player
except Exception:
    get_player = None


class LeaderboardScreen:
    """
    Leaderboard screen  (esports poster style).

    Same constructor and return values as before:
        handle_event() -> None | "back"

    Features
    --------
    * Top-3 podium (gold / silver / bronze)
    * "Your rank" strip, plus JUMP TO ME button
    * Live search by commander name (click the box or press / or Ctrl+F)
    * Scrollable table with draggable scrollbar, mouse wheel and keys
    * Score lines relative to the top score, hover highlight
    * Refresh button / R key, auto-hiding messages, full resize support
    * Every commander shows the same ship photo as on their profile page
    """

    # ============================================================
    # FONTS
    # ============================================================

    HEAVY = "impact,haettenschweiler,arialblack,franklingothicheavy"
    SANS = "bahnschrift,segoeui,arial,helvetica,consolas"

    # ============================================================
    # PROFILE PHOTO (ship chosen on the profile page)
    # ============================================================

    # Keys that may hold the selected ship, in a player dict / db row
    SHIP_KEYS = (
        "ship", "ship_id", "selected_ship", "spaceship",
        "ship_image", "ship_choice", "avatar", "profile_picture",
    )

    SHIP_DIRS = (
        "", "assets", "assets/images", "assets/ships",
        "assets/images/ships", "images",
    )

    # Fallback letter-avatar colours (only used if a ship image is missing)
    AVATAR_COLORS = {
        "astronaut": (120, 200, 255),
        "alien": (120, 255, 170),
        "robot": (190, 190, 225),
        "pilot": (255, 170, 90),
        "commander": (255, 110, 140),
        "galaxy": (190, 120, 255),
        "gamer": (90, 255, 230),
        "explorer": (255, 220, 110),
    }

    # ============================================================
    # COLORS  (matched to the main menu / profile)
    # ============================================================

    PURPLE = (170, 70, 255)
    BRIGHT_PURPLE = (210, 120, 255)
    CYAN = (0, 220, 255)

    WHITE = (240, 240, 255)
    SOFT = (205, 190, 235)
    MUTED = (150, 125, 205)
    DIM = (105, 90, 145)

    GREEN = (0, 255, 150)
    RED = (255, 80, 110)
    YELLOW = (255, 205, 100)

    GOLD = (255, 215, 100)
    SILVER = (210, 215, 235)
    BRONZE = (232, 150, 95)

    MEDALS = {1: GOLD, 2: SILVER, 3: BRONZE}

    # 11 x 8 classic invader sprite (the game logo)
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

    ROW_H = 44
    ROW_GAP = 6

    # ============================================================
    # INIT
    # ============================================================

    def __init__(
        self,
        screen,
        screen_width,
        screen_height,
        player=None
    ):

        self.screen = screen
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.player = player if isinstance(player, dict) else {}

        self.player_id = self.player.get(
            "id",
            self.player.get("player_id")
        )

        # --------------------------------------------------------
        # STATE
        # --------------------------------------------------------

        self.time = 0.0

        self.entries = []      # full normalized list
        self.view = []         # after search filter

        self.scroll = 0
        self.dragging = False

        self.search_text = ""
        self.search_active = False

        self.message = ""
        self.message_type = "info"
        self.message_until = 0

        self.empty_text = ""

        # caches
        self._cache = {}
        self._ship_raw = {}
        self._ship_scaled = {}
        self._player_cache = {}
        self._get_player_ok = get_player is not None
        self._title_fonts = {}

        # --------------------------------------------------------
        # BACKGROUND
        # --------------------------------------------------------

        self.background = None
        self.bg_cache = None
        self.bg_cache_size = None

        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(current_dir)

        self.base_dirs = ["", project_dir, current_dir]

        path = self.find_background()

        if path:
            try:
                self.background = pygame.image.load(path).convert()
            except Exception:
                self.background = None

        # --------------------------------------------------------
        # STARS
        # --------------------------------------------------------

        self.stars = [
            {
                "x": random.random(),
                "y": random.random(),
                "speed": random.uniform(0.008, 0.028),
                "size": random.choice([1, 1, 1, 2]),
                "phase": random.uniform(0, 6.28),
            }
            for _ in range(100)
        ]

        # --------------------------------------------------------
        # FONTS
        # --------------------------------------------------------

        self.ordinal_font = self.make_font(self.HEAVY, 24, False, True)
        self.ordinal_big_font = self.make_font(self.HEAVY, 30, False, True)

        self.heading_font = self.make_font(self.SANS, 22, True)
        self.font = self.make_font(self.SANS, 17, True)
        self.small_font = self.make_font(self.SANS, 13, True)
        self.tiny_font = self.make_font(self.SANS, 11, True)
        self.btn_font = self.make_font(self.SANS, 13, True, True)

        self.avatar_font = self.make_font(self.SANS, 16, True)
        self.avatar_big_font = self.make_font(self.SANS, 26, True)

        self.load_scores()

    @staticmethod
    def make_font(names, size, bold=False, italic=False):

        font = pygame.font.SysFont(names, size, bold=bold)

        try:
            font.set_italic(italic)
        except Exception:
            pass

        return font

    def get_title_font(self, size):

        if size not in self._title_fonts:

            self._title_fonts[size] = self.make_font(
                self.HEAVY, size, False, True
            )

        return self._title_fonts[size]

    # ============================================================
    # BACKGROUND FILE
    # ============================================================

    def find_background(self):

        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(current_dir)

        paths = [
            os.path.join(project_dir, "assets", "images", "bg3.png"),
            os.path.join(project_dir, "assets", "bg3.png"),
            os.path.join(project_dir, "images", "bg3.png"),
            os.path.join(project_dir, "bg3.png"),
            os.path.join("assets", "images", "bg3.png"),
            os.path.join("assets", "bg3.png"),
            "bg3.png",
        ]

        for path in paths:

            if os.path.exists(path):
                return path

        return None

    # ============================================================
    # SHIP PHOTOS (same as the profile page)
    # ============================================================

    def ship_candidates(self, value):

        names = []

        if isinstance(value, bool) or value is None:
            return names

        if isinstance(value, int) or (
            isinstance(value, str) and value.strip().isdigit()
        ):

            names.append("Ship" + str(int(value)) + ".png")

        elif isinstance(value, str):

            v = value.strip()

            if v.lower().endswith((".png", ".jpg", ".jpeg")):
                names.extend([v, os.path.basename(v)])

            elif v.lower().startswith("ship"):
                names.append(v + ".png")

        return names

    def ship_from(self, source):

        if not hasattr(source, "get"):
            return None

        for key in self.SHIP_KEYS:

            value = source.get(key)

            if self.ship_candidates(value):
                return value

        return None

    def resolve_ship(self, raw, player_id):
        """Find which ship this player picked on their profile page."""

        value = self.ship_from(raw)

        # Ask the profile data if the leaderboard row doesn't have it

        if value is None and player_id is not None and self._get_player_ok:

            if player_id in self._player_cache:

                profile = self._player_cache[player_id]

            else:

                try:
                    profile = get_player(player_id)
                except Exception:
                    profile = None
                    self._get_player_ok = False

                self._player_cache[player_id] = profile

            value = self.ship_from(profile)

        # It's me: use the player dict that was passed in

        if (
            value is None
            and self.player_id is not None
            and player_id == self.player_id
        ):
            value = self.ship_from(self.player)

        return value if value is not None else "Ship1.png"

    def load_ship_raw(self, value):

        key = str(value)

        if key in self._ship_raw:
            return self._ship_raw[key]

        image = None

        for name in self.ship_candidates(value):

            for base in self.base_dirs:

                for folder in self.SHIP_DIRS:

                    path = os.path.join(base, folder, name)

                    if not os.path.exists(path):
                        continue

                    try:

                        image = pygame.image.load(path).convert_alpha()

                        break

                    except (pygame.error, OSError):
                        continue

                if image:
                    break

            if image:
                break

        self._ship_raw[key] = image

        return image

    def get_ship_image(self, value, size):

        key = (str(value), size)

        if key in self._ship_scaled:
            return self._ship_scaled[key]

        raw = self.load_ship_raw(value)

        scaled = None

        if raw is not None and size > 2:

            iw, ih = raw.get_size()

            ratio = min(size / iw, size / ih)

            scaled = pygame.transform.smoothscale(
                raw,
                (max(1, int(iw * ratio)), max(1, int(ih * ratio)))
            )

        self._ship_scaled[key] = scaled

        return scaled

    # ============================================================
    # DATA
    # ============================================================

    def load_scores(self):

        self.entries = []

        try:

            raw = get_leaderboard(50) or []

            for index, entry in enumerate(raw):

                if not hasattr(entry, "get"):
                    continue

                name = entry.get(
                    "player_name",
                    entry.get("username", "UNKNOWN")
                )

                try:
                    score = int(entry.get("score", 0) or 0)
                except (TypeError, ValueError):
                    score = 0

                player_id = entry.get("player_id")

                self.entries.append({
                    "rank": entry.get("rank", index + 1),
                    "player_id": player_id,
                    "name": str(name or "UNKNOWN"),
                    "score": score,
                    "avatar": entry.get("avatar", "astronaut") or "astronaut",
                    "ship": self.resolve_ship(entry, player_id),
                })

            self.empty_text = (
                "" if self.entries
                else "No scores have been recorded yet."
            )

        except Exception:

            self.entries = []

            self.empty_text = "Unable to load the leaderboard."

        self.apply_filter()

    def apply_filter(self):

        query = self.search_text.strip().lower()

        if query:

            self.view = [
                e for e in self.entries
                if query in e["name"].lower()
            ]

        else:

            self.view = list(self.entries)

        self.scroll = 0

    def my_entry(self):

        if self.player_id is None:
            return None

        for entry in self.entries:

            if entry["player_id"] == self.player_id:
                return entry

        return None

    # ============================================================
    # UPDATE / RESIZE / MESSAGE
    # ============================================================

    def update(self, dt):

        for star in self.stars:

            star["y"] += star["speed"] * dt

            if star["y"] > 1.0:
                star["y"] = 0.0
                star["x"] = random.random()

    def resize(self, width, height):

        self.screen_width = width
        self.screen_height = height

        self.bg_cache = None

    def set_message(self, message, message_type="info"):

        self.message = message
        self.message_type = message_type
        self.message_until = pygame.time.get_ticks() + 4000

    # ============================================================
    # LAYOUT (shared by draw + events)
    # ============================================================

    def compute_layout(self):

        w = self.screen_width
        h = self.screen_height

        margin = 20

        cw = min(1000, max(0, w - margin * 2))

        x0 = (w - cw) // 2

        content = pygame.Rect(x0, 0, cw, h)

        L = {"panel": content}

        # Top bar buttons

        L["back"] = pygame.Rect(x0, 16, 96, 34)
        L["refresh"] = pygame.Rect(content.right - 112, 16, 112, 34)
        L["jump"] = pygame.Rect(L["refresh"].x - 12 - 132, 16, 132, 34)

        # Title (shrinks to fit narrow windows)

        size = int(max(34, min(92, h * 0.105)))

        title_font = self.get_title_font(size)

        while title_font.size("LEADERBOARD")[0] > cw * 0.94 and size > 22:

            size -= 2

            title_font = self.get_title_font(size)

        title_top = 64

        title_h = title_font.get_height()

        L["title_font"] = title_font
        L["title_center"] = (w // 2, title_top + title_h // 2)

        sub_y = title_top + int(title_h * 0.9) + 6

        L["sub_y"] = sub_y

        ix = content.x
        iw = content.width

        y = sub_y + 30

        # Podium

        show_podium = (
            h >= 700
            and not self.search_text.strip()
            and len(self.entries) > 0
        )

        if show_podium:

            L["podium"] = pygame.Rect(ix, y, iw, 132)

            y += 132 + 12

        else:

            L["podium"] = None

        # "Your rank" strip + search

        strip = pygame.Rect(ix, y, iw, 40)

        L["strip"] = strip

        L["search"] = pygame.Rect(strip.right - 270, strip.y + 3, 270, 34)

        L["search_clear"] = pygame.Rect(
            L["search"].right - 28,
            L["search"].y + 7,
            20,
            20
        )

        y += 40 + 10

        # Table header

        L["table_head"] = pygame.Rect(ix, y, iw, 26)

        y += 26 + 6

        # Rows

        bottom = h - 52

        step = self.ROW_H + self.ROW_GAP

        visible = max(1, (bottom - y) // step)

        L["rows_top"] = y
        L["visible"] = visible

        needs_bar = len(self.view) > visible

        L["rows_w"] = iw - (16 if needs_bar else 0)

        L["ix"] = ix
        L["iw"] = iw

        L["track"] = pygame.Rect(
            ix + iw - 8,
            y,
            8,
            visible * step - self.ROW_GAP
        )

        return L

    def max_scroll(self, L):

        return max(0, len(self.view) - L["visible"])

    def clamp_scroll(self, L):

        self.scroll = max(0, min(int(self.scroll), self.max_scroll(L)))

    # ============================================================
    # DRAW HELPERS
    # ============================================================

    @staticmethod
    def ordinal(n):

        try:
            n = int(n)
        except (TypeError, ValueError):
            return str(n)

        if 10 <= n % 100 <= 20:
            suffix = "TH"
        else:
            suffix = {1: "ST", 2: "ND", 3: "RD"}.get(n % 10, "TH")

        return str(n) + suffix

    def draw_box(self, rect, fill, border=None, radius=8, width=1):

        layer = pygame.Surface(rect.size, pygame.SRCALPHA)

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

    def hline(self, x1, x2, y, color, alpha, thick=1):

        width = int(x2 - x1)

        if width <= 0:
            return

        key = ("hl", width, thick, color, alpha)

        surf = self._cache.get(key)

        if surf is None:

            surf = pygame.Surface((width, thick), pygame.SRCALPHA)

            surf.fill((*color, alpha))

            self._cache[key] = surf

        self.screen.blit(surf, (int(x1), int(y)))

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

    def spaced(self, value, font, color, spacing):
        """Text with extra letter spacing (cached)."""

        value = str(value)

        key = ("sp", value, id(font), color, spacing)

        if key in self._cache:
            return self._cache[key]

        glyphs = [font.render(ch, True, color) for ch in value]

        total = sum(g.get_width() for g in glyphs)
        total += spacing * max(0, len(value) - 1)

        surf = pygame.Surface(
            (max(1, total), font.get_height()),
            pygame.SRCALPHA
        )

        x = 0

        for g in glyphs:
            surf.blit(g, (x, 0))
            x += g.get_width() + spacing

        self._cache[key] = surf

        return surf

    def draw_spaced(self, value, font, color, spacing, x, y, align="left"):
        """y is the vertical centre."""

        surf = self.spaced(value, font, color, spacing)

        if align == "center":
            rect = surf.get_rect(center=(x, y))
        elif align == "right":
            rect = surf.get_rect(midright=(x, y))
        else:
            rect = surf.get_rect(midleft=(x, y))

        self.screen.blit(surf, rect)

        return rect

    def glow_surface(self, value, font, color, glow, blur, strength, pad):

        key = ("glow", str(value), id(font), color, glow, blur, strength, pad)

        if key in self._cache:
            return self._cache[key]

        base = font.render(str(value), True, color)

        cw = base.get_width() + pad * 2
        ch = base.get_height() + pad * 2

        canvas = pygame.Surface((cw, ch), pygame.SRCALPHA)

        canvas.blit(base, (pad, pad))

        small = pygame.transform.smoothscale(
            canvas,
            (max(1, cw // blur), max(1, ch // blur))
        )

        halo = pygame.transform.smoothscale(small, (cw, ch))

        tint = pygame.Surface((cw, ch), pygame.SRCALPHA)

        tint.fill((*glow, 255))

        halo.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        out = pygame.Surface((cw, ch), pygame.SRCALPHA)

        for _ in range(strength):
            out.blit(halo, (0, 0))

        out.blit(base, (pad, pad))

        self._cache[key] = out

        return out

    def draw_glow(
        self, value, font, color, glow, x, y,
        align="left", blur=5, strength=2, pad=14
    ):
        """Glowing text. y is the vertical centre."""

        surf = self.glow_surface(value, font, color, glow, blur, strength, pad)

        if align == "center":
            rect = surf.get_rect(center=(x, y))
        elif align == "right":
            rect = surf.get_rect(midright=(x + pad, y))
        else:
            rect = surf.get_rect(midleft=(x - pad, y))

        self.screen.blit(surf, rect)

        return rect

    def fit(self, value, font, max_width):

        value = str(value)

        if font.size(value)[0] <= max_width:
            return value

        while len(value) > 1 and font.size(value + "...")[0] > max_width:
            value = value[:-1]

        return value + "..."

    def draw_button(self, rect, label, style="normal"):

        hover = rect.collidepoint(pygame.mouse.get_pos())

        slant = 10
        pad = 8

        layer = pygame.Surface(
            (rect.width + pad * 2, rect.height + pad * 2),
            pygame.SRCALPHA
        )

        ox, oy = pad, pad

        points = [
            (ox + slant, oy),
            (ox + rect.width, oy),
            (ox + rect.width - slant, oy + rect.height),
            (ox, oy + rect.height),
        ]

        if hover:

            pygame.draw.polygon(layer, (170, 90, 255, 55), points, 7)

        if style == "accent":

            fill = (120, 50, 230, 215) if hover else (90, 38, 190, 200)
            border = (255, 255, 255, 230)

        else:

            fill = (110, 45, 215, 190) if hover else (16, 10, 40, 175)
            border = (255, 255, 255, 220) if hover else (255, 255, 255, 120)

        pygame.draw.polygon(layer, fill, points)
        pygame.draw.polygon(layer, border, points, 1)

        self.screen.blit(layer, (rect.x - pad, rect.y - pad))

        self.text(
            label,
            self.btn_font,
            self.WHITE if hover or style == "accent" else self.SOFT,
            rect.centerx,
            rect.centery,
            "center"
        )

    def avatar_color(self, entry):

        color = self.AVATAR_COLORS.get(entry.get("avatar"))

        if color:
            return color

        palette = list(self.AVATAR_COLORS.values())

        return palette[sum(ord(c) for c in entry["name"]) % len(palette)]

    def draw_avatar(self, center, size, entry, ring=None):
        """The commander's profile photo (their chosen ship)."""

        frame = pygame.Rect(0, 0, size, size)

        frame.center = center

        self.draw_box(frame, (10, 6, 30, 230), None, 4)

        image = self.get_ship_image(entry.get("ship"), size - 6)

        if image is not None:

            self.screen.blit(image, image.get_rect(center=frame.center))

        else:

            font = self.avatar_big_font if size >= 40 else self.avatar_font

            self.text(
                entry["name"][:1].upper(),
                font,
                self.avatar_color(entry),
                frame.centerx,
                frame.centery,
                "center"
            )

        pygame.draw.rect(
            self.screen,
            ring or (130, 80, 210),
            frame,
            2,
            border_radius=4
        )

    # ============================================================
    # LOGO  (space invader)
    # ============================================================

    def draw_logo(self, cx, top, s):

        pulse = 0.5 + 0.5 * math.sin(self.time * 3)

        pts = [
            (cx - s * 0.5, top + s * 0.14),
            (cx, top),
            (cx + s * 0.5, top + s * 0.14),
            (cx + s * 0.5, top + s * 0.62),
            (cx, top + s),
            (cx - s * 0.5, top + s * 0.62),
        ]

        # glow

        gs = int(s * 1.7)

        gx = int(cx - gs / 2)
        gy = int(top - s * 0.35)

        glow = pygame.Surface((gs, gs), pygame.SRCALPHA)

        local = [(int(px - gx), int(py - gy)) for px, py in pts]

        pygame.draw.polygon(glow, (150, 70, 255, int(35 + 25 * pulse)), local, 9)
        pygame.draw.polygon(glow, (0, 200, 255, int(30 + 20 * pulse)), local, 4)

        self.screen.blit(glow, (gx, gy))

        # shield

        ipts = [(int(px), int(py)) for px, py in pts]

        pygame.draw.polygon(self.screen, (22, 10, 55), ipts)
        pygame.draw.polygon(self.screen, (255, 255, 255), ipts, 2)

        # invader inside

        cell = max(2, int(s * 0.05))

        sw = 11 * cell

        sx = int(cx - sw / 2)
        sy = int(top + s * 0.30)

        wobble = int(self.time * 2) % 2

        for row, line in enumerate(self.ALIEN):

            for col, ch in enumerate(line):

                if ch != "#":
                    continue

                dx = cell if (row >= 5 and wobble and col > 5) else 0

                pygame.draw.rect(
                    self.screen,
                    (245, 240, 255),
                    (sx + col * cell + dx, sy + row * cell, cell, cell)
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

            surface.fill((5, 4, 18))

        layer = pygame.Surface((w, h), pygame.SRCALPHA)

        layer.fill((3, 2, 12, 150))

        surface.blit(layer, (0, 0))

        # Purple light from the top, fading into black at the bottom

        layer = pygame.Surface((w, h), pygame.SRCALPHA)

        top_h = max(1, int(h * 0.55))

        for row in range(top_h):

            t = row / top_h

            pygame.draw.line(
                layer,
                (105, 50, 255, int(165 * (1 - t) ** 1.6)),
                (0, row),
                (w, row)
            )

        start = int(h * 0.30)

        for row in range(start, h):

            t = (row - start) / max(1, h - start)

            pygame.draw.line(
                layer,
                (2, 2, 8, int(235 * min(1.0, t * 1.5))),
                (0, row),
                (w, row)
            )

        surface.blit(layer, (0, 0))

        return surface

    def draw_background(self):

        w = self.screen_width
        h = self.screen_height

        if self.bg_cache is None or self.bg_cache_size != (w, h):

            self.bg_cache = self.build_background(w, h)
            self.bg_cache_size = (w, h)

        self.screen.blit(self.bg_cache, (0, 0))

        for star in self.stars:

            twinkle = 0.6 + 0.4 * math.sin(self.time * 2 + star["phase"])

            pygame.draw.circle(
                self.screen,
                (
                    int(170 * twinkle),
                    int(110 * twinkle),
                    int(255 * twinkle)
                ),
                (int(star["x"] * w), int(star["y"] * h)),
                star["size"]
            )

    # ============================================================
    # DRAW: HEADER
    # ============================================================

    def draw_header(self, L):

        w = self.screen_width

        # Logo

        self.draw_logo(w // 2, 10, 54)

        # Speed streaks behind the title

        cx, cy = L["title_center"]

        for dy, alpha in ((-16, 55), (2, 40), (20, 28)):

            self.hline(0, w, cy + dy, (200, 180, 255), alpha, 2)

        # Title

        self.draw_glow(
            "LEADERBOARD",
            L["title_font"],
            (255, 255, 255),
            (170, 130, 255),
            cx,
            cy,
            "center",
            blur=6,
            strength=3,
            pad=30
        )

        # Subtitle

        count = len(self.entries)

        sub = "TOP GALACTIC COMMANDERS"

        if count:
            sub += "   //   1ST TO " + self.ordinal(count) + " PLACE"

        self.draw_spaced(
            sub,
            self.tiny_font,
            (205, 195, 230),
            3,
            w // 2,
            L["sub_y"] + 7,
            "center"
        )

        # Buttons

        self.draw_button(L["back"], "BACK", "accent")
        self.draw_button(L["jump"], "JUMP TO ME")
        self.draw_button(L["refresh"], "REFRESH")

    # ============================================================
    # DRAW: PODIUM
    # ============================================================

    def draw_podium(self, L):

        area = L["podium"]

        top = self.entries[:3]

        gap = 14

        card_w = min(240, (area.width - gap * 2) // 3)

        # slots: (rank, x offset index, height)
        slots = [(2, 0, 108), (1, 1, 128), (3, 2, 100)]

        total_w = card_w * 3 + gap * 2

        start_x = area.centerx - total_w // 2

        for rank, slot, height in slots:

            if rank > len(top):
                continue

            entry = top[rank - 1]

            color = self.MEDALS[rank]

            rect = pygame.Rect(
                start_x + slot * (card_w + gap),
                area.bottom - height,
                card_w,
                height
            )

            is_me = (
                self.player_id is not None
                and entry["player_id"] == self.player_id
            )

            self.draw_box(
                rect,
                (70, 30, 140, 150) if is_me else (10, 6, 30, 150),
                (255, 255, 255, 55),
                4,
                1
            )

            # Medal-colored top edge

            self.hline(rect.x, rect.right, rect.y, color, 255, 3)

            # Rank

            self.draw_glow(
                self.ordinal(rank),
                self.ordinal_font,
                color,
                color,
                rect.x + 12,
                rect.y + 20,
                "left",
                blur=4,
                strength=2,
                pad=12
            )

            if rank == 1:

                self.draw_spaced(
                    "CHAMPION",
                    self.tiny_font,
                    color,
                    2,
                    rect.right - 12,
                    rect.y + 20,
                    "right"
                )

            size = 52 if rank == 1 else 42

            self.draw_avatar(
                (rect.centerx, rect.y + 30 + size // 2),
                size,
                entry,
                color
            )

            name_y = rect.y + 30 + size + 10

            self.text(
                self.fit(entry["name"].upper(), self.small_font, rect.width - 20),
                self.small_font,
                self.WHITE,
                rect.centerx,
                name_y + 6,
                "center"
            )

            self.draw_spaced(
                f"{entry['score']:,}",
                self.font,
                color,
                2,
                rect.centerx,
                name_y + 28,
                "center"
            )

    # ============================================================
    # DRAW: YOUR RANK STRIP + SEARCH
    # ============================================================

    def draw_strip(self, L):

        strip = L["strip"]

        mine = self.my_entry()

        left = pygame.Rect(
            strip.x,
            strip.y,
            strip.width - L["search"].width - 12,
            strip.height
        )

        self.draw_box(left, (10, 6, 30, 140), (255, 255, 255, 60), 4, 1)

        if self.player_id is None:

            self.text(
                "GUEST  //  LOG IN TO APPEAR ON THE BOARD",
                self.small_font,
                self.MUTED,
                strip.x + 14,
                strip.y + 12
            )

        elif mine:

            # Your profile photo, same as on the profile page

            self.draw_avatar(
                (strip.x + 26, strip.centery),
                30,
                mine,
                self.CYAN
            )

            self.draw_spaced(
                "YOUR RANK",
                self.tiny_font,
                self.MUTED,
                2,
                strip.x + 52,
                strip.y + 11
            )

            self.draw_glow(
                self.ordinal(mine["rank"]),
                self.ordinal_font,
                (255, 255, 255),
                self.CYAN,
                strip.x + 52,
                strip.y + 28,
                "left",
                blur=4,
                strength=2,
                pad=10
            )

            self.draw_spaced(
                f"SCORE  {mine['score']:,}",
                self.small_font,
                self.WHITE,
                2,
                strip.x + 150,
                strip.centery,
                "left"
            )

            best = self.entries[0]["score"] if self.entries else 0

            gap_to_top = best - mine["score"]

            self.draw_spaced(
                "YOU ARE #1" if gap_to_top <= 0
                else f"{gap_to_top:,} BEHIND #1",
                self.tiny_font,
                self.GREEN if gap_to_top <= 0 else self.SOFT,
                2,
                strip.x + 330,
                strip.centery,
                "left"
            )

        else:

            self.text(
                "NOT IN THE TOP 50 YET  //  PLAY A MISSION TO CLIMB",
                self.small_font,
                self.MUTED,
                strip.x + 14,
                strip.y + 12
            )

        # Search box

        search = L["search"]

        self.draw_box(
            search,
            (4, 3, 18, 175),
            (210, 120, 255, 255) if self.search_active else (255, 255, 255, 80),
            4,
            2 if self.search_active else 1
        )

        max_w = search.width - 54

        if self.search_text:

            shown = self.search_text

            while self.small_font.size(shown)[0] > max_w and len(shown) > 1:
                shown = shown[1:]

            rect = self.text(
                shown,
                self.small_font,
                self.WHITE,
                search.x + 12,
                search.centery - 8
            )

            cursor_x = rect.right + 2

        else:

            self.text(
                "SEARCH COMMANDER  ( / )",
                self.small_font,
                self.DIM,
                search.x + 12,
                search.centery - 8
            )

            cursor_x = search.x + 12

        if self.search_active and int(self.time * 2) % 2 == 0:

            pygame.draw.line(
                self.screen,
                self.BRIGHT_PURPLE,
                (cursor_x, search.centery - 10),
                (cursor_x, search.centery + 10),
                2
            )

        if self.search_text:

            clear = L["search_clear"]

            hover = clear.collidepoint(pygame.mouse.get_pos())

            self.text(
                "x",
                self.font,
                self.WHITE if hover else self.MUTED,
                clear.centerx,
                clear.centery - 1,
                "center"
            )

    # ============================================================
    # DRAW: TABLE
    # ============================================================

    def draw_table(self, L):

        head = L["table_head"]

        ix = L["ix"]

        rank_x = ix + 12
        avatar_cx = ix + 100
        name_x = ix + 134
        score_right = ix + L["rows_w"] - 18

        self.draw_spaced("RANK", self.tiny_font, self.MUTED, 3, rank_x, head.centery, "left")
        self.draw_spaced("COMMANDER", self.tiny_font, self.MUTED, 3, name_x, head.centery, "left")
        self.draw_spaced("SCORE", self.tiny_font, self.MUTED, 3, score_right, head.centery, "right")

        self.hline(head.x, head.x + L["rows_w"], head.bottom - 1, (255, 255, 255), 90)

        # Empty states

        if not self.view:

            if self.search_text.strip():
                message = f"No commanders match \"{self.search_text.strip()}\"."
            else:
                message = self.empty_text or "No scores available."

            self.text(
                message,
                self.font,
                self.MUTED,
                L["panel"].centerx,
                L["rows_top"] + 70,
                "center"
            )

            return

        self.clamp_scroll(L)

        step = self.ROW_H + self.ROW_GAP

        top_score = max(1, self.entries[0]["score"] if self.entries else 1)

        mouse = pygame.mouse.get_pos()

        end = min(len(self.view), self.scroll + L["visible"])

        for slot, index in enumerate(range(self.scroll, end)):

            entry = self.view[index]

            row = pygame.Rect(
                ix,
                L["rows_top"] + slot * step,
                L["rows_w"],
                self.ROW_H
            )

            is_me = (
                self.player_id is not None
                and entry["player_id"] == self.player_id
            )

            hover = row.collidepoint(mouse)

            medal = self.MEDALS.get(entry["rank"])

            accent = medal or (self.CYAN if is_me else self.PURPLE)

            # Row highlight

            if is_me:
                self.draw_box(row, (95, 40, 190, 115), None, 2)
            elif hover:
                self.draw_box(row, (70, 35, 150, 85), None, 2)

            # Double line like the poster: thin line above and below

            self.hline(
                row.x, row.right, row.y,
                (255, 255, 255),
                170 if (hover or is_me) else 100
            )

            by = row.bottom - 1

            self.hline(row.x, row.right, by, (255, 255, 255), 60)

            # Score line (relative to the top score)

            fill_w = max(6, int(row.width * entry["score"] / top_score))

            self.hline(row.x, row.x + fill_w, by - 1, accent, 240, 2)

            # Rank

            self.draw_glow(
                self.ordinal(entry["rank"]),
                self.ordinal_font,
                medal or (255, 255, 255),
                medal or (170, 120, 255),
                rank_x,
                row.centery,
                "left",
                blur=4,
                strength=2,
                pad=12
            )

            # Profile photo (same ship as on the profile page)

            self.draw_avatar(
                (avatar_cx, row.centery),
                32,
                entry,
                medal or (self.CYAN if is_me else None)
            )

            # Name

            name_w = max(60, score_right - name_x - 150)

            name_rect = self.text(
                self.fit(entry["name"].upper(), self.font, name_w),
                self.font,
                self.WHITE if (is_me or hover) else self.SOFT,
                name_x,
                row.centery - self.font.get_height() // 2
            )

            if is_me:

                tag = pygame.Rect(0, 0, 38, 16)

                tag.midleft = (name_rect.right + 10, row.centery)

                self.draw_box(tag, (0, 200, 255, 60), (0, 220, 255, 230), 3, 1)

                self.text("YOU", self.tiny_font, self.CYAN, tag.centerx, tag.centery, "center")

            # Score

            self.draw_spaced(
                f"{entry['score']:,}",
                self.font,
                medal or self.WHITE,
                3,
                score_right,
                row.centery,
                "right"
            )

        # Scrollbar

        if len(self.view) > L["visible"]:

            track = L["track"]

            self.draw_box(track, (255, 255, 255, 30), None, 4)

            thumb_h = max(28, int(track.height * L["visible"] / len(self.view)))

            max_scroll = max(1, self.max_scroll(L))

            thumb_y = track.y + int(
                (track.height - thumb_h) * self.scroll / max_scroll
            )

            self.draw_box(
                pygame.Rect(track.x, thumb_y, track.width, thumb_h),
                (*self.BRIGHT_PURPLE, 240 if self.dragging else 200),
                None,
                4
            )

    # ============================================================
    # DRAW
    # ============================================================

    def draw(self):

        self.time = pygame.time.get_ticks() / 1000.0

        L = self.compute_layout()

        self.draw_background()

        self.draw_header(L)

        # Body

        if L["podium"]:
            self.draw_podium(L)

        self.draw_strip(L)

        self.draw_table(L)

        # Footer

        content = L["panel"]

        h = self.screen_height

        self.draw_spaced(
            "WHEEL / UP / DOWN  SCROLL     /  SEARCH     R  REFRESH     ESC  BACK",
            self.tiny_font,
            self.DIM,
            1,
            content.x,
            h - 24,
            "left"
        )

        if self.view:

            first = self.scroll + 1
            last = min(len(self.view), self.scroll + L["visible"])

            self.draw_spaced(
                f"SHOWING {first}-{last} OF {len(self.view)}   >>",
                self.tiny_font,
                self.MUTED,
                2,
                content.right,
                h - 24,
                "right"
            )

        if self.message:

            if pygame.time.get_ticks() > self.message_until:

                self.message = ""

            else:

                color = {
                    "success": self.GREEN,
                    "error": self.RED,
                    "warning": self.YELLOW,
                }.get(self.message_type, self.SOFT)

                self.text(
                    self.message,
                    self.small_font,
                    color,
                    content.right,
                    h - 48,
                    "right"
                )

    # ============================================================
    # ACTIONS
    # ============================================================

    def refresh(self):

        self._player_cache = {}
        self._ship_raw = {}
        self._ship_scaled = {}

        self.load_scores()

        if self.entries:
            self.set_message("Leaderboard refreshed.", "success")
        else:
            self.set_message(self.empty_text or "Nothing to show.", "warning")

    def jump_to_me(self):

        L = self.compute_layout()

        mine = self.my_entry()

        if self.player_id is None:

            self.set_message("Log in to see your own rank.", "warning")

            return

        if not mine:

            self.set_message("You are not in the top 50 yet.", "warning")

            return

        if self.search_text:

            self.search_text = ""

            self.apply_filter()

            L = self.compute_layout()

        index = self.view.index(mine)

        # Center the row where possible

        self.scroll = index - L["visible"] // 2

        self.clamp_scroll(L)

        self.set_message(f"You are rank #{mine['rank']}.", "success")

    def set_scroll_from_mouse(self, y, L):

        track = L["track"]

        thumb_h = max(28, int(track.height * L["visible"] / max(1, len(self.view))))

        span = max(1, track.height - thumb_h)

        ratio = (y - track.y - thumb_h / 2) / span

        self.scroll = int(round(max(0.0, min(1.0, ratio)) * self.max_scroll(L)))

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

            # Typing into search

            if self.search_active:

                if event.key == pygame.K_ESCAPE:

                    if self.search_text:

                        self.search_text = ""
                        self.apply_filter()

                    else:

                        self.search_active = False

                elif event.key == pygame.K_RETURN:

                    self.search_active = False

                elif event.key == pygame.K_BACKSPACE:

                    self.search_text = self.search_text[:-1]
                    self.apply_filter()

                elif event.key in (pygame.K_DOWN, pygame.K_UP):

                    step = 1 if event.key == pygame.K_DOWN else -1

                    self.scroll += step
                    self.clamp_scroll(L)

                elif event.unicode and event.unicode.isprintable():

                    if len(self.search_text) < 20:

                        self.search_text += event.unicode
                        self.apply_filter()

                return None

            # Normal keys

            if event.key == pygame.K_ESCAPE:

                if self.search_text:

                    self.search_text = ""
                    self.apply_filter()

                    return None

                return "back"

            if event.key == pygame.K_r:

                self.refresh()

                return None

            if (
                event.key == pygame.K_SLASH
                or (
                    event.key == pygame.K_f
                    and (event.mod & pygame.KMOD_CTRL)
                )
            ):

                self.search_active = True

                return None

            if event.key == pygame.K_DOWN:
                self.scroll += 1

            elif event.key == pygame.K_UP:
                self.scroll -= 1

            elif event.key == pygame.K_PAGEDOWN:
                self.scroll += L["visible"]

            elif event.key == pygame.K_PAGEUP:
                self.scroll -= L["visible"]

            elif event.key == pygame.K_HOME:
                self.scroll = 0

            elif event.key == pygame.K_END:
                self.scroll = len(self.view)

            self.clamp_scroll(L)

            return None

        # --------------------------------------------------------
        # MOUSE WHEEL
        # --------------------------------------------------------

        if event.type == pygame.MOUSEWHEEL:

            self.scroll -= event.y

            self.clamp_scroll(L)

            return None

        # --------------------------------------------------------
        # SCROLLBAR DRAG
        # --------------------------------------------------------

        if event.type == pygame.MOUSEMOTION and self.dragging:

            self.set_scroll_from_mouse(event.pos[1], L)

            self.clamp_scroll(L)

            return None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:

            self.dragging = False

            return None

        # --------------------------------------------------------
        # MOUSE CLICK
        # --------------------------------------------------------

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

            pos = event.pos

            if L["back"].collidepoint(pos):
                return "back"

            if L["refresh"].collidepoint(pos):

                self.refresh()

                return None

            if L["jump"].collidepoint(pos):

                self.jump_to_me()

                return None

            if self.search_text and L["search_clear"].collidepoint(pos):

                self.search_text = ""
                self.apply_filter()
                self.search_active = True

                return None

            if L["search"].collidepoint(pos):

                self.search_active = True

                return None

            self.search_active = False

            if (
                len(self.view) > L["visible"]
                and L["track"].inflate(10, 0).collidepoint(pos)
            ):

                self.dragging = True

                self.set_scroll_from_mouse(pos[1], L)

                self.clamp_scroll(L)

                return None

        return None