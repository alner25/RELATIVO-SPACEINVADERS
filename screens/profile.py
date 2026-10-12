import os
import sys
import json
import math
import random

import pygame

from db import (
    get_player,
    get_player_high_score,
    get_player_scores,
    update_player_profile,
    delete_player,
)

# Optional: used to show the player's global leaderboard rank
try:
    from db import get_leaderboard
except Exception:
    get_leaderboard = None


class ProfileScreen:
    """
    Profile screen  ("pilot dossier" style).

    Same constructor and return values as before:
        handle_event() -> None | "back" | "logout" | "stay"

    Main view
    ---------
    A clean dossier card: big profile photo, callsign, rank + progress,
    mission record, equipped ship and the HIGH SCORE panel with your
    global leaderboard rank.

    Feature buttons (each opens its own window, so nothing is crowded)
    ------------------------------------------------------------------
    * EDIT PROFILE   (E)  username, password, icon avatar, photo, save,
                          delete account
    * MATCH HISTORY  (H)  scrollable list of your scores
    * SPACESHIP      (S)  pick one of 5 ships (Ship1.png ... Ship5.png)
    * CHANGE PHOTO   (P)  pick a picture (or drag & drop one on the
                          window) - saved straight away

    ENTER saves unsaved changes, ESC closes a window / goes back.

    From your game you can still use:
        ProfileScreen.load_profile_photo(player_id)   # Surface or None
        ProfileScreen.get_selected_ship(player_id)    # 1-5
        ProfileScreen.load_ship_image(number)         # Surface or None
    """

    # ============================================================
    # FONTS
    # ============================================================

    HEAVY = "impact,haettenschweiler,arialblack,franklingothicheavy"
    SANS = "bahnschrift,segoeui,arial,helvetica,consolas"

    # ============================================================
    # AVATARS
    # ============================================================

    AVATARS = {
        "astronaut": "ASTRONAUT",
        "alien": "ALIEN",
        "robot": "ROBOT",
        "pilot": "PILOT",
        "commander": "COMMANDER",
        "galaxy": "GALAXY",
        "gamer": "GAMER",
        "explorer": "EXPLORER",
    }

    AVATAR_SYMBOLS = {
        "astronaut": "A",
        "alien": "X",
        "robot": "R",
        "pilot": "P",
        "commander": "C",
        "galaxy": "*",
        "gamer": "G",
        "explorer": "E",
    }

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

    # (score needed, rank name)
    RANKS = [
        (0, "CADET"),
        (1000, "SPACE PILOT"),
        (5000, "ACE PILOT"),
        (15000, "COMMANDER"),
        (40000, "ADMIRAL"),
    ]

    # ============================================================
    # COLORS
    # ============================================================

    # Main highlight of the dossier (labels, corners, score).
    # Change this one colour to re-theme the whole screen.
    ACCENT = (255, 196, 92)

    PURPLE = (170, 70, 255)
    BRIGHT_PURPLE = (210, 120, 255)
    DEEP_PURPLE = (80, 25, 150)
    CYAN = (0, 220, 255)

    WHITE = (240, 240, 255)
    SOFT = (205, 190, 235)
    MUTED = (150, 125, 205)
    DIM = (105, 90, 145)

    GREEN = (0, 255, 150)
    RED = (255, 80, 110)
    YELLOW = (255, 205, 100)

    STAT_COLORS = [
        (255, 205, 100),
        (0, 220, 255),
        (120, 255, 170),
        (190, 120, 255),
    ]

    FIELD_ORDER = ["username", "password", "confirm"]

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

    # ============================================================
    # PROFILE PHOTO
    # ============================================================

    PHOTO_SIZE = 256

    @classmethod
    def photos_dir(cls):

        return os.path.join(cls.project_dir(), "profile_photos")

    @staticmethod
    def photo_key(player_id):

        return str(player_id) if player_id is not None else "guest"

    @classmethod
    def photo_file(cls, player_id):

        return os.path.join(
            cls.photos_dir(),
            cls.photo_key(player_id) + ".png"
        )

    @classmethod
    def load_profile_photo(cls, player_id=None):
        """Returns the player's saved photo (square Surface) or None.
        Use this from your game:  ProfileScreen.load_profile_photo(id)"""

        path = cls.photo_file(player_id)

        if not os.path.isfile(path):
            return None

        try:
            return pygame.image.load(path).convert_alpha()
        except Exception:
            return None

    @classmethod
    def prepare_photo(cls, path):
        """Loads any image file and returns a centered square Surface."""

        image = pygame.image.load(path).convert_alpha()

        w, h = image.get_size()

        if w <= 0 or h <= 0:
            raise ValueError("empty image")

        side = min(w, h)

        crop = pygame.Rect((w - side) // 2, (h - side) // 2, side, side)

        image = image.subsurface(crop).copy()

        return pygame.transform.smoothscale(
            image,
            (cls.PHOTO_SIZE, cls.PHOTO_SIZE)
        )

    @staticmethod
    def pick_image_file():
        """Opens the system file picker. Returns (path, error)."""

        try:
            import tkinter
            from tkinter import filedialog
        except Exception:
            return None, (
                "File picker unavailable - drag an image onto the window."
            )

        start = os.path.expanduser("~")

        for name in ("Pictures", "Photos", "Downloads"):

            candidate = os.path.join(start, name)

            if os.path.isdir(candidate):
                start = candidate
                break

        try:

            root = tkinter.Tk()
            root.withdraw()

            try:
                root.attributes("-topmost", True)
            except Exception:
                pass

            path = filedialog.askopenfilename(
                parent=root,
                title="Choose a profile photo",
                initialdir=start,
                filetypes=[
                    (
                        "Images",
                        "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tga",
                    ),
                    ("All files", "*.*"),
                ],
            )

            root.destroy()

        except Exception:

            return None, "Could not open the file picker."

        return (path or None), ""

    # ============================================================
    # SPACESHIPS
    # ============================================================

    SHIP_COUNT = 5

    SHIP_FILES = {n: "Ship" + str(n) + ".png" for n in range(1, 6)}

    SHIP_COLORS = {
        1: (120, 200, 255),
        2: (255, 110, 140),
        3: (120, 255, 170),
        4: (255, 205, 100),
        5: (190, 120, 255),
    }

    @staticmethod
    def project_dir():

        return os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

    @classmethod
    def ship_selection_file(cls):

        return os.path.join(cls.project_dir(), "ship_selection.json")

    @classmethod
    def get_selected_ship(cls, player_id=None):
        """Returns the equipped ship number (1-5) for a player.
        Use this from your game:  ProfileScreen.get_selected_ship(id)"""

        key = str(player_id) if player_id is not None else "guest"

        try:

            with open(
                cls.ship_selection_file(),
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            number = int(data.get(key, 1))

        except (OSError, ValueError, TypeError, AttributeError):

            number = 1

        return number if 1 <= number <= cls.SHIP_COUNT else 1

    @classmethod
    def search_roots(cls):
        """Every place a project could keep its assets folder."""

        here = os.path.dirname(os.path.abspath(__file__))

        roots = [
            os.path.dirname(here),
            here,
            os.getcwd(),
        ]

        try:
            roots.append(
                os.path.dirname(os.path.abspath(sys.argv[0]))
            )
        except Exception:
            pass

        unique = []

        for root in roots:

            if root and root not in unique and os.path.isdir(root):
                unique.append(root)

        return unique

    @classmethod
    def find_ship_path(cls, number):

        name = cls.SHIP_FILES.get(number)

        if not name:
            return None

        roots = cls.search_roots()

        subfolders = [
            os.path.join("assets", "images"),
            os.path.join("assets", "ships"),
            "assets",
            "images",
            "",
        ]

        # 1) Exact, common locations

        for root in roots:

            for sub in subfolders:

                path = os.path.join(root, sub, name)

                if os.path.isfile(path):
                    return path

        # 2) Any sub-folder of assets / images / img, ignoring letter case

        wanted = name.lower()

        for root in roots:

            for base_name in ("assets", "images", "img"):

                base = os.path.join(root, base_name)

                if not os.path.isdir(base):
                    continue

                for folder, _dirs, files in os.walk(base):

                    for file_name in files:

                        if file_name.lower() == wanted:
                            return os.path.join(folder, file_name)

        return None

    @classmethod
    def load_ship_image(cls, number):
        """Returns the ship image as a pygame Surface, or None.
        Use this from your game to draw the player's ship."""

        path = cls.find_ship_path(number)

        if not path:
            return None

        try:
            return pygame.image.load(path).convert_alpha()
        except Exception:
            return None

    # ============================================================
    # INIT
    # ============================================================

    def __init__(
        self,
        screen,
        screen_width,
        screen_height,
        player=None,
        player_name=None
    ):

        self.screen = screen
        self.screen_width = screen_width
        self.screen_height = screen_height

        # --------------------------------------------------------
        # PLAYER COMPATIBILITY
        # --------------------------------------------------------

        self.player = player if isinstance(player, dict) else {}

        if isinstance(player, dict):

            self.player_id = player.get("id", player.get("player_id"))

            self.player_name = player.get(
                "player_name",
                player.get("username", player_name or "PLAYER")
            )

            self.avatar = player.get("avatar", "astronaut") or "astronaut"

        else:

            self.player_id = player
            self.player_name = player_name or "PLAYER"
            self.avatar = "astronaut"

        if self.avatar not in self.AVATARS:
            self.avatar = "astronaut"

        self.saved_avatar = self.avatar

        # --------------------------------------------------------
        # CACHES
        # --------------------------------------------------------

        self._cache = {}
        self._heavy_fonts = {}

        # --------------------------------------------------------
        # PROFILE PHOTO
        # --------------------------------------------------------

        self.saved_photo = None        # what is stored on disk
        self.photo_surface = None      # what is shown right now
        self.photo_pending = None      # None | "set" | "remove"
        self.photo_version = 0
        self.photo_cache = {}

        # --------------------------------------------------------
        # SPACESHIP
        # --------------------------------------------------------

        self.ship = self.get_selected_ship(self.player_id)
        self.saved_ship = self.ship

        self.player["ship"] = self.ship

        self.ship_images = {}      # number -> raw Surface or None
        self.ship_cache = {}       # (number, w, h) -> scaled Surface

        # --------------------------------------------------------
        # STATE
        # --------------------------------------------------------

        self.fields = {
            "username": self.player_name,
            "password": "",
            "confirm": "",
        }

        self.active_field = None
        self.show_password = False

        self.modal_open = False         # feature window open?
        self.tab = "account"            # "account", "history", "ships"

        self.message = ""
        self.message_type = "info"
        self.message_until = 0

        self.delete_confirm = False
        self.delete_text = ""

        self.history_scroll = 0

        self.time = 0.0

        # --------------------------------------------------------
        # STATS
        # --------------------------------------------------------

        self.high_score = 0
        self.games = 0
        self.total_score = 0
        self.average_score = 0
        self.history = []
        self.global_rank = None

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

        # --------------------------------------------------------
        # STARS
        # --------------------------------------------------------

        self.stars = [
            {
                "x": random.uniform(0, 1),
                "y": random.uniform(0, 1),
                "speed": random.uniform(0.008, 0.03),
                "size": random.choice([1, 1, 1, 2]),
                "phase": random.uniform(0, 6.28),
            }
            for _ in range(110)
        ]

        # --------------------------------------------------------
        # FONTS
        # --------------------------------------------------------

        self.title_font = self.make_font(self.HEAVY, 30, False, True)

        self.big_font = self.make_font(self.SANS, 28, True)
        self.heading_font = self.make_font(self.SANS, 22, True)
        self.font = self.make_font(self.SANS, 17, True)
        self.small_font = self.make_font(self.SANS, 13, True)
        self.tiny_font = self.make_font(self.SANS, 11, True)
        self.btn_font = self.make_font(self.SANS, 13, True, True)

        self.avatar_font = self.make_font(self.SANS, 44, True)
        self.avatar_small_font = self.make_font(self.SANS, 26, True)

        self.load_player_data()

    @staticmethod
    def make_font(names, size, bold=False, italic=False):

        font = pygame.font.SysFont(names, size, bold=bold)

        try:
            font.set_italic(italic)
        except Exception:
            pass

        return font

    def heavy_font(self, size):

        if size not in self._heavy_fonts:

            self._heavy_fonts[size] = self.make_font(
                self.HEAVY, size, False, True
            )

        return self._heavy_fonts[size]

    # ============================================================
    # FIND BACKGROUND
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
    # DATA
    # ============================================================

    @staticmethod
    def score_of(entry):

        try:

            if hasattr(entry, "keys"):

                for key in ("score", "points", "value"):

                    if key in entry.keys():
                        return int(entry[key])

                return 0

            if isinstance(entry, (int, float)):
                return int(entry)

            if isinstance(entry, (list, tuple)):

                for item in entry:

                    if (
                        isinstance(item, (int, float))
                        and not isinstance(item, bool)
                    ):
                        return int(item)

        except Exception:
            pass

        return 0

    @staticmethod
    def date_of(entry):

        try:

            if hasattr(entry, "keys"):

                for key in (
                    "created_at",
                    "date",
                    "played_at",
                    "timestamp",
                    "time"
                ):

                    if key in entry.keys() and entry[key]:

                        return (
                            str(entry[key])[:16].replace("T", " ")
                        )

        except Exception:
            pass

        return ""

    def load_player_data(self):

        self.global_rank = None

        # --------------------------------------------------------
        # Photo (works for guests too)
        # --------------------------------------------------------

        self.saved_photo = self.load_profile_photo(self.player_id)
        self.photo_surface = self.saved_photo
        self.photo_pending = None

        self.bump_photo()

        if self.player_id is None:
            return

        # --------------------------------------------------------
        # Player record
        # --------------------------------------------------------

        try:

            data = get_player(self.player_id)

            if data:

                self.player.update(data)

                self.player_name = data.get("player_name", self.player_name)

                self.fields["username"] = self.player_name

                self.avatar = data.get("avatar", self.avatar) or "astronaut"

                if self.avatar not in self.AVATARS:
                    self.avatar = "astronaut"

                self.saved_avatar = self.avatar

        except Exception:

            self.set_message("Could not load profile.", "error")

        # --------------------------------------------------------
        # Scores (loaded once, not every frame)
        # --------------------------------------------------------

        try:

            self.high_score = int(
                get_player_high_score(self.player_id) or 0
            )

        except Exception:

            self.high_score = 0

        try:

            raw = get_player_scores(self.player_id) or []

            self.history = [
                {
                    "score": self.score_of(entry),
                    "date": self.date_of(entry),
                }
                for entry in raw
            ]

        except Exception:

            self.history = []

        self.games = len(self.history)

        self.total_score = sum(item["score"] for item in self.history)

        self.average_score = (
            self.total_score // self.games if self.games else 0
        )

        if self.history:
            self.high_score = max(
                self.high_score,
                max(item["score"] for item in self.history)
            )

        self.history_scroll = 0

        # --------------------------------------------------------
        # Global leaderboard rank
        # --------------------------------------------------------

        if get_leaderboard is not None:

            try:

                for index, entry in enumerate(get_leaderboard(50) or []):

                    if (
                        hasattr(entry, "get")
                        and entry.get("player_id") == self.player_id
                    ):

                        self.global_rank = entry.get("rank", index + 1)

                        break

            except Exception:

                self.global_rank = None

    def get_rank(self):

        index = 0

        for i, (need, _name) in enumerate(self.RANKS):

            if self.high_score >= need:
                index = i

        current = self.RANKS[index]

        if index + 1 < len(self.RANKS):

            nxt = self.RANKS[index + 1]

            span = max(1, nxt[0] - current[0])

            progress = (self.high_score - current[0]) / span

            return current[1], nxt, max(0.0, min(1.0, progress))

        return current[1], None, 1.0

    def latest_mission(self):

        if not self.history:
            return None

        if any(item["date"] for item in self.history):
            return max(self.history, key=lambda item: item["date"])

        return self.history[0]

    def profile_fields_changed(self):

        return (
            self.fields["username"].strip() != self.player_name
            or bool(self.fields["password"])
            or bool(self.fields["confirm"])
            or self.avatar != self.saved_avatar
        )

    def has_changes(self):

        return (
            self.profile_fields_changed()
            or self.photo_pending is not None
        )

    # ============================================================
    # PHOTO ACTIONS
    # ============================================================

    def bump_photo(self):

        self.photo_version += 1
        self.photo_cache = {}

    def circle_photo(self, radius):
        """The current photo scaled to a circle of this radius (cached)."""

        if self.photo_surface is None or radius < 2:
            return None

        key = (self.photo_version, radius)

        cached = self.photo_cache.get(key)

        if cached is not None:
            return cached

        d = radius * 2

        image = pygame.transform.smoothscale(
            self.photo_surface,
            (d, d)
        ).convert_alpha()

        mask = pygame.Surface((d, d), pygame.SRCALPHA)

        pygame.draw.circle(
            mask,
            (255, 255, 255, 255),
            (radius, radius),
            radius
        )

        image.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        if len(self.photo_cache) > 24:
            self.photo_cache = {}

        self.photo_cache[key] = image

        return image

    def cover_photo(self, w, h):
        """The photo scaled + center-cropped to fill w x h (cached)."""

        if self.photo_surface is None or w < 2 or h < 2:
            return None

        key = ("cover", self.photo_version, w, h)

        cached = self.photo_cache.get(key)

        if cached is not None:
            return cached

        pw, ph = self.photo_surface.get_size()

        scale = max(w / pw, h / ph)

        sw = max(w, int(pw * scale) + 1)
        sh = max(h, int(ph * scale) + 1)

        image = pygame.transform.smoothscale(self.photo_surface, (sw, sh))

        crop = image.subsurface(
            ((sw - w) // 2, (sh - h) // 2, w, h)
        ).copy()

        if len(self.photo_cache) > 24:
            self.photo_cache = {}

        self.photo_cache[key] = crop

        return crop

    def choose_photo(self, auto_save=False):

        path, error = self.pick_image_file()

        if error:

            self.set_message(error, "error")

            return

        if path and self.set_photo_from_path(path) and auto_save:
            self.save_photo_now()

    def set_photo_from_path(self, path):

        path = str(path).strip().strip('"')

        if not os.path.isfile(path):

            self.set_message("Could not find that file.", "error")

            return False

        try:

            photo = self.prepare_photo(path)

        except Exception:

            self.set_message(
                "That file is not a supported image.",
                "error"
            )

            return False

        self.photo_surface = photo
        self.photo_pending = "set"

        self.bump_photo()

        self.set_message(
            "Photo ready - press SAVE CHANGES to keep it.",
            "success"
        )

        return True

    def save_photo_now(self):
        """Saves a freshly chosen photo straight away (main view)."""

        if self.apply_photo():

            self.set_message("Profile photo updated.", "success")

        else:

            self.set_message("The photo could not be saved.", "error")

    def remove_photo(self):

        if self.photo_surface is None:

            self.set_message("You have no photo to remove.", "warning")

            return

        self.photo_surface = None

        if self.saved_photo is not None:

            self.photo_pending = "remove"

            self.set_message(
                "Photo removed - press SAVE CHANGES to confirm.",
                "warning"
            )

        else:

            self.photo_pending = None

            self.set_message("Photo discarded.", "info")

        self.bump_photo()

    def apply_photo(self):
        """Writes the pending photo change to disk."""

        if self.photo_pending is None:
            return True

        path = self.photo_file(self.player_id)

        try:

            if self.photo_pending == "set":

                os.makedirs(self.photos_dir(), exist_ok=True)

                pygame.image.save(self.photo_surface, path)

                self.saved_photo = self.photo_surface

            else:

                if os.path.isfile(path):
                    os.remove(path)

                self.saved_photo = None

        except Exception:

            return False

        self.photo_pending = None

        self.player["has_photo"] = self.saved_photo is not None

        return True

    # ============================================================
    # UPDATE / RESIZE
    # ============================================================

    def update(self, dt):

        for star in self.stars:

            star["y"] += star["speed"] * dt

            if star["y"] > 1.0:
                star["y"] = 0.0
                star["x"] = random.uniform(0, 1)

    def resize(self, width, height):

        self.screen_width = width
        self.screen_height = height

        self.bg_cache = None

    # ============================================================
    # MESSAGES
    # ============================================================

    def set_message(self, message, message_type="info"):

        self.message = message
        self.message_type = message_type
        self.message_until = pygame.time.get_ticks() + 5000

    # ============================================================
    # LAYOUT (shared by draw + events, so they never disagree)
    # ============================================================

    def compute_layout(self):

        w = self.screen_width
        h = self.screen_height

        L = {}

        # ========================================================
        # DOSSIER (main view)
        # ========================================================

        pw = min(1040, max(300, w - 28))
        ph = min(620, max(300, h - 28))

        card = pygame.Rect((w - pw) // 2, (h - ph) // 2, pw, ph)

        L["card"] = card

        L["back"] = pygame.Rect(card.right - 24 - 96, card.y + 16, 96, 34)
        L["refresh"] = pygame.Rect(L["back"].x - 12 - 104, card.y + 16, 104, 34)

        top = card.y + 80
        bottom = card.bottom - 40

        body_h = max(200, bottom - top)

        left_w = int(max(190, min(340, card.width * 0.33)))

        photo_h = min(body_h - 22, int(left_w * 1.3))

        L["photo"] = pygame.Rect(card.x + 24, top, left_w, photo_h)

        rx = L["photo"].right + 28
        rw = max(200, card.right - 24 - rx)

        L["rx"] = rx
        L["rw"] = rw

        # Feature buttons (bottom of the right column)

        btn_h = 40
        btn_y = bottom - btn_h

        gap = 10

        btn_w = (rw - gap * 3) // 4

        labels = (
            ("edit", "EDIT PROFILE"),
            ("history", "MATCH HISTORY"),
            ("ships", "SPACESHIP"),
            ("photo", "CHANGE PHOTO"),
        )

        L["feat"] = [
            (
                key,
                label,
                pygame.Rect(rx + i * (btn_w + gap), btn_y, btn_w, btn_h)
            )
            for i, (key, label) in enumerate(labels)
        ]

        # High-score panel

        bounty_h = 96 if body_h >= 440 else 80

        L["bounty"] = pygame.Rect(rx, btn_y - 14 - bounty_h, rw, bounty_h)

        # Info rows

        rows_top = top
        rows_bottom = L["bounty"].y - 14

        avail = max(60, rows_bottom - rows_top)

        count = 5 if avail >= 5 * 58 else (4 if avail >= 4 * 58 else 3)

        row_h = min(76, avail // count)

        L["rows"] = [
            pygame.Rect(rx, rows_top + i * row_h, rw, row_h)
            for i in range(count)
        ]

        # ========================================================
        # FEATURE WINDOW (modal) - same inner layouts as before
        # ========================================================

        mw = min(800, max(300, w - 30))
        mh = min(640, max(300, h - 30))

        right = pygame.Rect((w - mw) // 2, (h - mh) // 2, mw, mh)

        L["right"] = right

        L["modal_close"] = pygame.Rect(right.right - 18 - 96, right.y + 14, 96, 34)

        ix = right.x + 18
        iw = right.width - 36

        L["ix"] = ix
        L["iw"] = iw

        L["tab_account"] = pygame.Rect(ix, right.y + 14, 120, 34)
        L["tab_history"] = pygame.Rect(ix + 128, right.y + 14, 150, 34)
        L["tab_ships"] = pygame.Rect(ix + 286, right.y + 14, 130, 34)

        # --------------------------------------------------------
        # ACCOUNT tab
        # --------------------------------------------------------

        y = right.y + 66

        photo_box = pygame.Rect(ix, y, iw, 72)

        L["photo_box"] = photo_box
        L["photo_center"] = (ix + 44, y + 36)
        L["photo_radius"] = 28

        bx = photo_box.right - 144

        L["photo_upload"] = pygame.Rect(bx, y + 6, 132, 28)
        L["photo_remove"] = pygame.Rect(bx, y + 38, 132, 28)

        y += 72 + 26

        L["username"] = pygame.Rect(ix, y, iw, 38)

        y += 38 + 32

        if iw >= 480:

            half = (iw - 14) // 2

            L["password"] = pygame.Rect(ix, y, half, 38)
            L["confirm"] = pygame.Rect(ix + half + 14, y, half, 38)

            y += 38

        else:

            L["password"] = pygame.Rect(ix, y, iw, 38)

            y += 38 + 30

            L["confirm"] = pygame.Rect(ix, y, iw, 38)

            y += 38

        L["hint_y"] = y + 6

        y += 28

        L["avatar_title_y"] = y

        grid_top = y + 22

        abtn_h = 38

        abtn_y = right.bottom - 18 - abtn_h

        half_btn = (iw - 14) // 2

        L["save"] = pygame.Rect(ix, abtn_y, half_btn, abtn_h)

        L["delete"] = pygame.Rect(ix + half_btn + 14, abtn_y, half_btn, abtn_h)

        L["toggle_pw"] = pygame.Rect(
            L["password"].right - 64,
            L["password"].y + 6,
            58,
            26
        )

        # Avatar grid (one row when wide, two rows when narrow)

        cols = 8 if iw >= 600 else 4
        rows = len(self.AVATARS) // cols
        agap = 8

        available = abtn_y - 16 - grid_top

        cell_h = max(50, min(76, (available - agap * (rows - 1)) // rows))

        cell_w = (iw - agap * (cols - 1)) // cols

        L["avatars"] = []

        for index, avatar in enumerate(self.AVATARS.keys()):

            row = index // cols
            col = index % cols

            rect = pygame.Rect(
                ix + col * (cell_w + agap),
                grid_top + row * (cell_h + agap),
                cell_w,
                cell_h
            )

            L["avatars"].append((avatar, rect))

        # --------------------------------------------------------
        # HISTORY tab
        # --------------------------------------------------------

        hist_top = right.y + 66

        L["hist"] = pygame.Rect(
            ix,
            hist_top,
            iw,
            max(80, right.bottom - 18 - hist_top)
        )

        # --------------------------------------------------------
        # SPACESHIP tab
        # --------------------------------------------------------

        ship_top = right.y + 66

        L["ship_area"] = pygame.Rect(
            ix,
            ship_top,
            iw,
            max(120, right.bottom - 18 - ship_top)
        )

        equip_y = right.bottom - 18 - 38

        L["ship_equip"] = pygame.Rect(ix, equip_y, iw, 38)

        ship_gap = 10

        card_w = (iw - ship_gap * (self.SHIP_COUNT - 1)) // self.SHIP_COUNT

        card_h = 104

        cards_y = equip_y - 14 - card_h

        L["ship_cards"] = [
            (
                n,
                pygame.Rect(
                    ix + (n - 1) * (card_w + ship_gap),
                    cards_y,
                    card_w,
                    card_h
                )
            )
            for n in range(1, self.SHIP_COUNT + 1)
        ]

        preview_top = ship_top + 40

        L["ship_preview"] = pygame.Rect(
            ix,
            preview_top,
            iw,
            max(80, cards_y - 14 - preview_top)
        )

        # --------------------------------------------------------
        # Delete modal
        # --------------------------------------------------------

        dw = min(480, w - 30)
        dh = 250

        modal = pygame.Rect((w - dw) // 2, (h - dh) // 2, dw, dh)

        L["modal"] = modal

        L["modal_input"] = pygame.Rect(
            modal.x + 30,
            modal.y + 128,
            modal.width - 60,
            38
        )

        bw = (modal.width - 60 - 14) // 2

        L["modal_yes"] = pygame.Rect(
            modal.x + 30,
            modal.bottom - 54,
            bw,
            36
        )

        L["modal_no"] = pygame.Rect(
            L["modal_yes"].right + 14,
            modal.bottom - 54,
            bw,
            36
        )

        return L

    # ============================================================
    # DRAW HELPERS
    # ============================================================

    def panel_points(self, w, h, cut):

        cut = max(2, min(cut, w // 4, h // 4))

        return [
            (cut, 0),
            (w - cut, 0),
            (w, cut),
            (w, h - cut),
            (w - cut, h),
            (cut, h),
            (0, h - cut),
            (0, cut),
        ]

    def draw_glass_panel(self, rect, cut=20):

        if rect.width <= 0 or rect.height <= 0:
            return

        layer = pygame.Surface(rect.size, pygame.SRCALPHA)

        points = self.panel_points(rect.width, rect.height, cut)

        pygame.draw.polygon(layer, (8, 5, 28, 235), points)

        inner = pygame.Rect(5, 5, rect.width - 10, rect.height - 10)

        pygame.draw.polygon(
            layer,
            (80, 20, 120, 35),
            [
                (px + 5, py + 5)
                for px, py in self.panel_points(
                    inner.width,
                    inner.height,
                    max(2, cut - 4)
                )
            ]
        )

        pygame.draw.polygon(layer, (*self.ACCENT, 200), points, 2)

        self.screen.blit(layer, rect.topleft)

    def draw_corner(self, x, y, left, top, length=24, color=None):

        color = color or self.PURPLE

        x2 = x + length if left else x - length
        y2 = y + length if top else y - length

        pygame.draw.line(self.screen, color, (x, y), (x2, y), 2)
        pygame.draw.line(self.screen, color, (x, y), (x, y2), 2)

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

    def draw_glow(self, rect, color, radius=8, steps=4, alpha=34):
        """Soft outer glow around a rectangle."""

        for i in range(steps, 0, -1):

            size = i * 2

            glow = pygame.Surface(
                (rect.width + size * 2, rect.height + size * 2),
                pygame.SRCALPHA
            )

            pygame.draw.rect(
                glow,
                (*color[:3], max(3, alpha - i * 6)),
                glow.get_rect(),
                2,
                border_radius=radius + size
            )

            self.screen.blit(glow, (rect.x - size, rect.y - size))

    def draw_card(self, rect, accent=None):
        """Glass card with a glowing accent line on top."""

        accent = accent or self.PURPLE

        self.draw_box(rect, (10, 6, 32, 150), (110, 55, 190, 170), 10, 1)

        length = min(110, rect.width // 3)

        for i in range(length):

            fade = 1.0 - i / max(1, length)

            color = tuple(
                int(c * (0.35 + 0.65 * fade)) for c in accent
            )

            self.screen.set_at((rect.x + 14 + i, rect.y + 1), color)
            self.screen.set_at((rect.x + 14 + i, rect.y + 2), color)

    def draw_gradient_bar(self, rect, c1, c2):
        """Horizontal gradient with a moving shimmer."""

        if rect.width <= 0 or rect.height <= 0:
            return

        shimmer = rect.x + int((self.time * 70) % (rect.width + 40)) - 20

        for i in range(rect.width):

            t = i / max(1, rect.width - 1)

            color = [int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3)]

            distance = abs((rect.x + i) - shimmer)

            if distance < 10:

                boost = int(70 * (1 - distance / 10))

                color = [min(255, c + boost) for c in color]

            pygame.draw.line(
                self.screen,
                tuple(color),
                (rect.x + i, rect.y),
                (rect.x + i, rect.bottom - 1)
            )

    def draw_camera_icon(self, center, color, scale=1.0):

        x, y = center

        w = int(16 * scale)
        h = int(11 * scale)

        body = pygame.Rect(0, 0, w, h)
        body.center = (x, y + 1)

        pygame.draw.rect(self.screen, color, body, 2, border_radius=3)

        pygame.draw.rect(
            self.screen,
            color,
            (
                x - int(3 * scale),
                body.y - int(3 * scale),
                int(6 * scale),
                int(3 * scale)
            )
        )

        pygame.draw.circle(
            self.screen,
            color,
            (x, y + 1),
            max(2, int(3 * scale)),
            2
        )

    def draw_diamond(self, x, y, r, color):

        pygame.draw.polygon(
            self.screen,
            color,
            [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]
        )

    def text(self, text, font, color, x, y, align="left"):

        surface = font.render(str(text), True, color)

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

        if len(self._cache) > 400:
            self._cache = {}

        self._cache[key] = out

        return out

    def draw_text_glow(
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

    def fit(self, text, font, max_width):

        text = str(text)

        if font.size(text)[0] <= max_width:
            return text

        while len(text) > 1 and font.size(text + "...")[0] > max_width:
            text = text[:-1]

        return text + "..."

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

    def draw_button(
        self,
        rect,
        label,
        style="normal",
        disabled=False
    ):
        """Slanted esports-style button."""

        hover = (
            not disabled
            and rect.collidepoint(pygame.mouse.get_pos())
        )

        slant = min(10, rect.height // 3)
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

        if disabled:

            fill = (20, 14, 40, 120)
            border = (255, 255, 255, 40)
            color = self.DIM

        elif style == "danger":

            fill = (130, 28, 56, 210) if hover else (70, 20, 40, 170)
            border = (255, 110, 140, 255) if hover else (230, 100, 130, 170)
            color = (255, 200, 210)

            if hover:
                pygame.draw.polygon(layer, (255, 80, 120, 60), points, 7)

        elif style == "accent":

            fill = (125, 55, 235, 220) if hover else (90, 38, 190, 200)
            border = (255, 255, 255, 235)
            color = self.WHITE

            if hover:
                pygame.draw.polygon(layer, (170, 90, 255, 60), points, 7)

        else:

            fill = (110, 45, 215, 190) if hover else (16, 10, 40, 175)
            border = (255, 255, 255, 220) if hover else (255, 255, 255, 120)
            color = self.WHITE if hover else self.SOFT

            if hover:
                pygame.draw.polygon(layer, (170, 90, 255, 55), points, 7)

        pygame.draw.polygon(layer, fill, points)
        pygame.draw.polygon(layer, border, points, 1)

        self.screen.blit(layer, (rect.x - pad, rect.y - pad))

        self.text(
            label,
            self.btn_font,
            color,
            rect.centerx,
            rect.centery,
            "center"
        )

        return hover

    def draw_input(
        self,
        rect,
        label,
        value,
        active=False,
        password=False,
        reserve_right=0,
        placeholder=""
    ):

        self.text(
            label,
            self.tiny_font,
            self.BRIGHT_PURPLE if active else self.MUTED,
            rect.x,
            rect.y - 17
        )

        if active:
            self.draw_glow(rect, self.BRIGHT_PURPLE, 7, 3, 32)

        self.draw_box(
            rect,
            (4, 3, 18, 175),
            (210, 120, 255, 255) if active else (100, 55, 160, 180),
            7,
            2 if active else 1
        )

        if password and not self.show_password:
            display = "*" * len(value)
        else:
            display = value

        max_width = rect.width - 22 - reserve_right

        text_rect = None

        if not display:

            shown = self.fit(placeholder, self.font, max_width)

            self.text(
                shown,
                self.font,
                self.DIM,
                rect.x + 11,
                rect.centery - 9
            )

        else:

            while (
                self.font.size(display)[0] > max_width
                and len(display) > 1
            ):
                display = display[1:]

            text_rect = self.text(
                display,
                self.font,
                self.WHITE,
                rect.x + 11,
                rect.centery - 9
            )

        if active and int(self.time * 2) % 2 == 0:

            if text_rect is not None:
                cx = text_rect.right + 2
            else:
                cx = rect.x + 12

            pygame.draw.line(
                self.screen,
                self.BRIGHT_PURPLE,
                (cx, rect.centery - 10),
                (cx, rect.centery + 10),
                2
            )

    def draw_avatar(self, center, radius, avatar, selected=False, big=False):

        color = self.AVATAR_COLORS.get(avatar, self.PURPLE)

        x, y = center

        if selected:

            pulse = int(3 + 2 * math.sin(self.time * 3))

            ring = pygame.Surface(
                (radius * 2 + 40, radius * 2 + 40),
                pygame.SRCALPHA
            )

            pygame.draw.circle(
                ring,
                (*color, 55),
                (radius + 20, radius + 20),
                radius + pulse + 6,
                3
            )

            self.screen.blit(ring, (x - radius - 20, y - radius - 20))

        pygame.draw.circle(self.screen, (10, 6, 30), center, radius)

        pygame.draw.circle(
            self.screen,
            color if selected else tuple(int(c * 0.55) for c in color),
            center,
            radius,
            3 if selected else 2
        )

        pygame.draw.circle(
            self.screen,
            (28, 16, 58),
            center,
            max(4, radius - 7)
        )

        font = self.avatar_font if big else self.avatar_small_font

        self.text(
            self.AVATAR_SYMBOLS.get(avatar, "?"),
            font,
            color if selected else tuple(int(c * 0.75) for c in color),
            x,
            y,
            "center"
        )

    def draw_profile_picture(self, center, radius, big=False):
        """The player's photo (circular) or, without one, the icon avatar."""

        image = self.circle_photo(radius - 3)

        if image is None:

            self.draw_avatar(center, radius, self.avatar, True, big)

            return

        x, y = center

        color = self.AVATAR_COLORS.get(self.avatar, self.PURPLE)

        pulse = int(3 + 2 * math.sin(self.time * 3))

        ring = pygame.Surface(
            (radius * 2 + 40, radius * 2 + 40),
            pygame.SRCALPHA
        )

        pygame.draw.circle(
            ring,
            (*color, 55),
            (radius + 20, radius + 20),
            radius + pulse + 6,
            3
        )

        self.screen.blit(ring, (x - radius - 20, y - radius - 20))

        pygame.draw.circle(self.screen, (10, 6, 30), center, radius)

        self.screen.blit(image, image.get_rect(center=center))

        pygame.draw.circle(
            self.screen,
            self.BRIGHT_PURPLE,
            center,
            radius,
            3
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

        gs = int(s * 1.7)

        gx = int(cx - gs / 2)
        gy = int(top - s * 0.35)

        glow = pygame.Surface((gs, gs), pygame.SRCALPHA)

        local = [(int(px - gx), int(py - gy)) for px, py in pts]

        pygame.draw.polygon(glow, (150, 70, 255, int(35 + 25 * pulse)), local, 9)
        pygame.draw.polygon(glow, (0, 200, 255, int(30 + 20 * pulse)), local, 4)

        self.screen.blit(glow, (gx, gy))

        ipts = [(int(px), int(py)) for px, py in pts]

        pygame.draw.polygon(self.screen, (22, 10, 55), ipts)
        pygame.draw.polygon(self.screen, (255, 255, 255), ipts, 2)

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

            size = (
                max(1, int(bw * scale)),
                max(1, int(bh * scale))
            )

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
                    (
                        int(5 + 10 * t),
                        int(4 + 3 * t),
                        int(18 + 22 * t)
                    ),
                    (0, row),
                    (w, row)
                )

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)

        overlay.fill((3, 2, 12, 150))

        surface.blit(overlay, (0, 0))

        return surface

    def draw_background(self):

        w = self.screen_width
        h = self.screen_height

        if self.bg_cache is None or self.bg_cache_size != (w, h):

            self.bg_cache = self.build_background(w, h)
            self.bg_cache_size = (w, h)

        self.screen.blit(self.bg_cache, (0, 0))

        # Pulsing glow

        glow = pygame.Surface((w, h), pygame.SRCALPHA)

        pulse = int(25 + 15 * math.sin(self.time * 2))

        pygame.draw.circle(
            glow,
            (130, 30, 255, pulse),
            (int(w * 0.22), int(h * 0.50)),
            270
        )

        pygame.draw.circle(
            glow,
            (0, 130, 255, pulse // 2),
            (int(w * 0.82), int(h * 0.35)),
            230
        )

        self.screen.blit(glow, (0, 0))

        # Stars

        for star in self.stars:

            twinkle = 0.6 + 0.4 * math.sin(self.time * 2 + star["phase"])

            color = (
                int(170 * twinkle),
                int(110 * twinkle),
                int(255 * twinkle)
            )

            pygame.draw.circle(
                self.screen,
                color,
                (int(star["x"] * w), int(star["y"] * h)),
                star["size"]
            )

    # ============================================================
    # DRAW: DOSSIER (main view)
    # ============================================================

    def draw_photo_frame(self, L):

        rect = L["photo"]

        mouse = pygame.mouse.get_pos()

        hover = (
            not self.modal_open
            and not self.delete_confirm
            and rect.collidepoint(mouse)
        )

        accent = self.ACCENT

        self.draw_box(rect, (14, 9, 30, 255), None, 2)

        image = self.cover_photo(rect.width, rect.height)

        if image is not None:

            self.screen.blit(image, rect.topleft)

        else:

            center = (rect.centerx, rect.centery - 14)

            radius = max(30, min(rect.width, rect.height) // 5)

            self.draw_avatar(center, radius, self.avatar, True, True)

            self.text(
                "NO PHOTO",
                self.small_font,
                self.MUTED,
                rect.centerx,
                center[1] + radius + 26,
                "center"
            )

            self.text(
                "CLICK TO UPLOAD",
                self.tiny_font,
                self.DIM,
                rect.centerx,
                center[1] + radius + 44,
                "center"
            )

        # Scan lines

        key = ("scan", rect.size)

        scan = self._cache.get(key)

        if scan is None:

            scan = pygame.Surface(rect.size, pygame.SRCALPHA)

            for y in range(0, rect.height, 3):
                pygame.draw.line(scan, (0, 0, 0, 38), (0, y), (rect.width, y))

            self._cache[key] = scan

        self.screen.blit(scan, rect.topleft)

        # Bottom shade

        key = ("shade", rect.size)

        shade = self._cache.get(key)

        if shade is None:

            shade = pygame.Surface(rect.size, pygame.SRCALPHA)

            start = int(rect.height * 0.62)

            for y in range(start, rect.height):

                t = (y - start) / max(1, rect.height - start)

                pygame.draw.line(
                    shade,
                    (4, 3, 10, int(215 * t)),
                    (0, y),
                    (rect.width, y)
                )

            self._cache[key] = shade

        self.screen.blit(shade, rect.topleft)

        # Online pill

        pulse = int(120 + 120 * math.sin(self.time * 4))

        pygame.draw.circle(
            self.screen,
            (0, max(120, pulse), 120),
            (rect.x + 16, rect.bottom - 18),
            4
        )

        self.draw_spaced(
            "ONLINE",
            self.tiny_font,
            (150, 255, 210),
            3,
            rect.x + 28,
            rect.bottom - 18,
            "left"
        )

        # Hover: change photo

        if hover:

            dim = pygame.Surface(rect.size, pygame.SRCALPHA)

            dim.fill((5, 3, 20, 165))

            self.screen.blit(dim, rect.topleft)

            self.draw_camera_icon(
                (rect.centerx, rect.centery - 10),
                self.WHITE,
                1.6
            )

            self.text(
                "CHANGE PHOTO",
                self.small_font,
                self.WHITE,
                rect.centerx,
                rect.centery + 26,
                "center"
            )

        # Frame

        pygame.draw.rect(self.screen, (255, 255, 255), rect, 1)

        for x, y, left, top in (
            (rect.x - 5, rect.y - 5, True, True),
            (rect.right + 4, rect.y - 5, False, True),
            (rect.x - 5, rect.bottom + 4, True, False),
            (rect.right + 4, rect.bottom + 4, False, False),
        ):

            self.draw_corner(x, y, left, top, 22, accent)

        # Caption under the photo (when there is room)

        caption_y = rect.bottom + 14

        if caption_y < L["card"].bottom - 36:

            self.draw_spaced(
                "CLICK THE PHOTO TO CHANGE IT",
                self.tiny_font,
                self.DIM,
                2,
                rect.x,
                caption_y,
                "left"
            )

    def draw_row_frame(self, rect, label):

        accent = self.ACCENT

        self.hline(rect.x, rect.right, rect.y, (255, 255, 255), 55)

        self.draw_diamond(rect.x + 5, rect.y + 14, 4, accent)

        self.draw_spaced(
            label,
            self.tiny_font,
            accent,
            3,
            rect.x + 18,
            rect.y + 14,
            "left"
        )

    def draw_info_rows(self, L):

        rank_name, next_rank, progress = self.get_rank()

        latest = self.latest_mission()

        rows = L["rows"]

        order = ["callsign", "rank", "record", "ship", "latest"]

        for index, rect in enumerate(rows):

            kind = order[index]

            if kind == "callsign":

                self.draw_row_frame(rect, "CALLSIGN")

                font = self.big_font if rect.height >= 64 else self.heading_font

                self.text(
                    self.fit(self.player_name.upper(), font, rect.width - 24),
                    font,
                    self.WHITE,
                    rect.x + 18,
                    rect.y + 26
                )

            elif kind == "rank":

                self.draw_row_frame(rect, "RANK")

                self.text(
                    rank_name,
                    self.font,
                    self.CYAN,
                    rect.x + 18,
                    rect.y + 26
                )

                if next_rank:

                    caption = (
                        f"{self.high_score:,} / {next_rank[0]:,}  >  {next_rank[1]}"
                    )

                else:

                    caption = "MAX RANK ACHIEVED"

                self.text(
                    self.fit(caption, self.tiny_font, rect.width // 2),
                    self.tiny_font,
                    self.MUTED,
                    rect.right,
                    rect.y + 8,
                    "right"
                )

                bar = pygame.Rect(
                    rect.x + 18,
                    rect.bottom - 11,
                    rect.width - 18,
                    7
                )

                self.draw_box(bar, (30, 15, 65, 200), (90, 50, 150, 200), 3, 1)

                if progress > 0:

                    fill = pygame.Rect(
                        bar.x + 1,
                        bar.y + 1,
                        max(6, int((bar.width - 2) * progress)),
                        bar.height - 2
                    )

                    self.draw_gradient_bar(fill, self.PURPLE, self.CYAN)

            elif kind == "record":

                self.draw_row_frame(rect, "MISSION RECORD")

                self.text(
                    f"{self.games:,} MISSIONS FLOWN",
                    self.font,
                    self.WHITE,
                    rect.x + 18,
                    rect.y + 26
                )

                self.text(
                    self.fit(
                        f"AVG {self.average_score:,}    TOTAL {self.total_score:,}",
                        self.tiny_font,
                        rect.width // 2
                    ),
                    self.tiny_font,
                    self.MUTED,
                    rect.right,
                    rect.y + 30,
                    "right"
                )

            elif kind == "ship":

                self.draw_row_frame(rect, "EQUIPPED SHIP")

                color = self.SHIP_COLORS.get(self.saved_ship, self.PURPLE)

                self.text(
                    "SHIP " + str(self.saved_ship),
                    self.font,
                    color,
                    rect.x + 18,
                    rect.y + 26
                )

                icon = pygame.Rect(
                    rect.right - 64,
                    rect.y + 6,
                    58,
                    max(20, rect.height - 12)
                )

                self.draw_ship(icon, self.saved_ship)

            else:

                self.draw_row_frame(rect, "LATEST MISSION")

                if latest:

                    self.text(
                        f"{latest['score']:,} PTS",
                        self.font,
                        self.WHITE,
                        rect.x + 18,
                        rect.y + 26
                    )

                    if latest["date"]:

                        self.text(
                            latest["date"],
                            self.tiny_font,
                            self.MUTED,
                            rect.right,
                            rect.y + 30,
                            "right"
                        )

                else:

                    self.text(
                        "NO MISSIONS YET",
                        self.font,
                        self.MUTED,
                        rect.x + 18,
                        rect.y + 26
                    )

        # closing line under the last row

        last = rows[-1]

        self.hline(last.x, last.right, last.bottom, (255, 255, 255), 55)

    def draw_score_panel(self, L):

        rect = L["bounty"]

        accent = self.ACCENT

        self.draw_box(rect, (12, 9, 22, 240), (*accent, 150), 4, 1)

        self.hline(rect.x, rect.x + 120, rect.y, accent, 255, 3)

        self.draw_diamond(rect.x + 16, rect.y + 16, 4, accent)

        self.draw_spaced(
            "HIGH SCORE",
            self.tiny_font,
            accent,
            3,
            rect.x + 30,
            rect.y + 16,
            "left"
        )

        # Logo + global rank on the right

        logo_s = min(60, rect.height - 24)

        logo_x = rect.right - 20 - logo_s // 2

        self.draw_logo(logo_x, rect.y + 12, logo_s)

        rank_right = logo_x - logo_s // 2 - 22

        if self.global_rank is not None:

            self.draw_spaced(
                "GLOBAL RANK",
                self.tiny_font,
                self.MUTED,
                2,
                rank_right,
                rect.y + 28,
                "right"
            )

            self.draw_text_glow(
                self.ordinal(self.global_rank),
                self.heavy_font(30),
                (255, 255, 255),
                self.CYAN,
                rank_right,
                rect.y + 56,
                "right",
                blur=4,
                strength=2,
                pad=10
            )

            number_limit = rank_right - 110 - (rect.x + 20)

        else:

            self.draw_spaced(
                "UNRANKED",
                self.tiny_font,
                self.DIM,
                2,
                rank_right,
                rect.y + 40,
                "right"
            )

            number_limit = rank_right - 90 - (rect.x + 20)

        # Big score (shrinks to fit)

        value = f"{self.high_score:,}"

        size = 56

        while size > 20 and self.heavy_font(size).size(value)[0] > number_limit:
            size -= 2

        font = self.heavy_font(size)

        number_rect = self.draw_text_glow(
            value,
            font,
            accent,
            accent,
            rect.x + 20,
            rect.y + rect.height // 2 + 12,
            "left",
            blur=6,
            strength=2,
            pad=16
        )

        self.draw_spaced(
            "PTS",
            self.small_font,
            self.MUTED,
            3,
            number_rect.right - 16 + 10,
            rect.y + rect.height // 2 + 18,
            "left"
        )

    def draw_feature_buttons(self, L):

        for key, label, rect in L["feat"]:

            active = (
                self.modal_open
                and (
                    (key == "edit" and self.tab == "account")
                    or (key == "history" and self.tab == "history")
                    or (key == "ships" and self.tab == "ships")
                )
            )

            self.draw_button(
                rect,
                label,
                "accent" if (active or key == "edit") else "normal"
            )

    def draw_dossier(self, L):

        card = L["card"]

        accent = self.ACCENT

        self.draw_box(card, (7, 6, 14, 226), (255, 255, 255, 45), 4, 1)

        for x, y, left, top in (
            (card.x + 8, card.y + 8, True, True),
            (card.right - 8, card.y + 8, False, True),
            (card.x + 8, card.bottom - 8, True, False),
            (card.right - 8, card.bottom - 8, False, False),
        ):

            self.draw_corner(x, y, left, top, 18, accent)

        # ---- Header ----

        title = "PILOT DOSSIER"

        tw = self.title_font.size(title)[0]

        tab = pygame.Rect(card.x + 24, card.y + 14, tw + 58, 40)

        pygame.draw.polygon(
            self.screen,
            (18, 14, 30),
            [
                (tab.x, tab.y),
                (tab.right, tab.y),
                (tab.right - 16, tab.bottom),
                (tab.x, tab.bottom),
            ]
        )

        pygame.draw.rect(self.screen, accent, (tab.x, tab.y, 5, tab.height))

        self.draw_text_glow(
            title,
            self.title_font,
            (255, 255, 255),
            (150, 90, 255),
            tab.x + 24,
            tab.centery,
            "left",
            blur=6,
            strength=2,
            pad=14
        )

        sub_x = tab.right + 18

        if sub_x + 200 < L["refresh"].x:

            self.draw_spaced(
                "SPACE COMMAND  //  CLASSIFIED",
                self.tiny_font,
                self.MUTED,
                3,
                sub_x,
                tab.centery,
                "left"
            )

        self.hline(card.x + 24, card.right - 24, card.y + 66, accent, 120)
        self.hline(card.x + 24, card.x + 24 + 170, card.y + 65, accent, 255, 3)

        self.draw_button(L["refresh"], "REFRESH")
        self.draw_button(L["back"], "BACK", "accent")

        # ---- Body ----

        self.draw_photo_frame(L)

        self.draw_info_rows(L)

        self.draw_score_panel(L)

        self.draw_feature_buttons(L)

        # ---- Footer ----

        self.draw_spaced(
            "E  EDIT     H  HISTORY     S  SHIP     P  PHOTO     ESC  BACK",
            self.tiny_font,
            self.DIM,
            1,
            card.x + 24,
            card.bottom - 20,
            "left"
        )

        if self.has_changes():

            dot = int(150 + 100 * math.sin(self.time * 5))

            self.draw_spaced(
                "UNSAVED CHANGES  -  PRESS ENTER TO SAVE",
                self.tiny_font,
                (dot, int(dot * 0.8), 60),
                2,
                card.right - 24,
                card.bottom - 20,
                "right"
            )

    # ============================================================
    # DRAW: FEATURE WINDOW
    # ============================================================

    def draw_modal(self, L):

        dim = pygame.Surface(
            (self.screen_width, self.screen_height),
            pygame.SRCALPHA
        )

        dim.fill((0, 0, 8, 190))

        self.screen.blit(dim, (0, 0))

        right = L["right"]

        self.draw_glass_panel(right, 22)

        self.draw_corner(right.x + 10, right.y + 10, True, True, 20, self.ACCENT)
        self.draw_corner(right.right - 10, right.y + 10, False, True, 20, self.ACCENT)
        self.draw_corner(right.x + 10, right.bottom - 10, True, False, 20, self.ACCENT)
        self.draw_corner(right.right - 10, right.bottom - 10, False, False, 20, self.ACCENT)

        self.draw_tabs(L)

        self.draw_button(L["modal_close"], "CLOSE", "accent")

        if self.tab == "account":
            self.draw_account_tab(L)
        elif self.tab == "history":
            self.draw_history_tab(L)
        else:
            self.draw_ships_tab(L)

    # ============================================================
    # DRAW: TABS
    # ============================================================

    def draw_tabs(self, L):

        right = L["right"]

        mouse = pygame.mouse.get_pos()

        for key, label in (
            ("account", "ACCOUNT"),
            ("history", "MATCH HISTORY"),
            ("ships", "SPACESHIP"),
        ):

            rect = L["tab_" + key]

            active = (self.tab == key)

            hover = rect.collidepoint(mouse)

            if active:

                fill = (100, 30, 160, 150)
                border = (220, 120, 255, 255)
                color = self.WHITE

            else:

                fill = (30, 15, 65, 140) if not hover else (60, 25, 110, 150)
                border = (110, 60, 180, 170)
                color = self.SOFT if hover else self.MUTED

            self.draw_box(rect, fill, border, 7, 2 if active else 1)

            self.text(
                label,
                self.small_font,
                color,
                rect.centerx,
                rect.centery,
                "center"
            )

            if active:

                pygame.draw.line(
                    self.screen,
                    self.ACCENT,
                    (rect.x + 10, rect.bottom + 5),
                    (rect.right - 10, rect.bottom + 5),
                    2
                )

        pygame.draw.line(
            self.screen,
            (90, 50, 150),
            (L["ix"], right.y + 58),
            (L["ix"] + L["iw"], right.y + 58),
            1
        )

    # ============================================================
    # DRAW: ACCOUNT TAB
    # ============================================================

    def draw_photo_section(self, L):

        box = L["photo_box"]

        mouse = pygame.mouse.get_pos()

        self.draw_box(
            box,
            (6, 4, 24, 160),
            (150, 80, 230, 190) if box.collidepoint(mouse) else (100, 55, 170, 150),
            10,
            1
        )

        self.draw_profile_picture(L["photo_center"], L["photo_radius"])

        tx = box.x + 88

        max_w = L["photo_upload"].x - tx - 12

        self.text("PROFILE PHOTO", self.small_font, self.SOFT, tx, box.y + 9)

        if self.photo_surface is not None:

            if self.photo_pending == "set":
                status, color = "New photo - save to apply", self.YELLOW
            else:
                status, color = "Custom photo in use", self.GREEN

        elif self.photo_pending == "remove":

            status, color = "Photo removed - save to apply", self.YELLOW

        else:

            status = "Using icon: " + self.AVATARS.get(self.avatar, "")
            color = self.MUTED

        self.text(
            self.fit(status, self.tiny_font, max_w),
            self.tiny_font,
            color,
            tx,
            box.y + 29
        )

        self.text(
            self.fit(
                "JPG PNG BMP GIF  -  or drag a file here",
                self.tiny_font,
                max_w
            ),
            self.tiny_font,
            self.DIM,
            tx,
            box.y + 47
        )

        self.draw_button(L["photo_upload"], "UPLOAD PHOTO", "accent")

        self.draw_button(
            L["photo_remove"],
            "REMOVE PHOTO",
            "danger",
            disabled=self.photo_surface is None
        )

    def draw_account_tab(self, L):

        self.draw_photo_section(L)

        self.draw_input(
            L["username"],
            "USERNAME",
            self.fields["username"],
            self.active_field == "username",
            placeholder="Enter username (3-20 characters)"
        )

        self.draw_input(
            L["password"],
            "NEW PASSWORD",
            self.fields["password"],
            self.active_field == "password",
            password=True,
            reserve_right=70,
            placeholder="Leave empty to keep"
        )

        # Show / hide password

        toggle = L["toggle_pw"]

        hover = toggle.collidepoint(pygame.mouse.get_pos())

        self.draw_box(
            toggle,
            (100, 30, 160, 140) if hover else (40, 20, 80, 150),
            (130, 60, 210, 180),
            5,
            1
        )

        self.text(
            "HIDE" if self.show_password else "SHOW",
            self.tiny_font,
            self.SOFT,
            toggle.centerx,
            toggle.centery,
            "center"
        )

        self.draw_input(
            L["confirm"],
            "CONFIRM PASSWORD",
            self.fields["confirm"],
            self.active_field == "confirm",
            password=True,
            placeholder="Repeat new password"
        )

        # Hint / live validation

        pw = self.fields["password"]
        cf = self.fields["confirm"]

        hint_y = L["hint_y"]

        if pw and cf and pw != cf:

            self.text(
                "Passwords do not match.",
                self.tiny_font,
                self.RED,
                L["ix"],
                hint_y
            )

        elif pw and len(pw) < 4:

            self.text(
                "Password must be at least 4 characters.",
                self.tiny_font,
                self.YELLOW,
                L["ix"],
                hint_y
            )

        else:

            self.text(
                self.fit(
                    "Leave the password fields empty to keep your current password.",
                    self.tiny_font,
                    L["iw"]
                ),
                self.tiny_font,
                self.DIM,
                L["ix"],
                hint_y
            )

        # Avatar selector

        title_rect = self.text(
            "PROFILE ICON",
            self.small_font,
            self.SOFT,
            L["ix"],
            L["avatar_title_y"]
        )

        if self.photo_surface is not None:

            note, note_color = "Remove your photo to show an icon", self.YELLOW

        else:

            note, note_color = "Shown whenever you have no photo", self.DIM

        self.text(
            self.fit(note, self.tiny_font, L["iw"] - title_rect.width - 14),
            self.tiny_font,
            note_color,
            title_rect.right + 12,
            L["avatar_title_y"] + 2
        )

        mouse = pygame.mouse.get_pos()

        for avatar, rect in L["avatars"]:

            selected = (avatar == self.avatar)

            hover = rect.collidepoint(mouse)

            color = self.AVATAR_COLORS[avatar]

            if selected:

                self.draw_glow(rect, color, 8, 3, 30)

                fill = (60, 25, 110, 170)
                border = (*color, 255)

            elif hover:

                fill = (45, 20, 85, 150)
                border = (190, 110, 255, 220)

            else:

                fill = (14, 8, 38, 140)
                border = (90, 50, 150, 160)

            self.draw_box(rect, fill, border, 8, 2 if selected else 1)

            radius = max(12, min(22, rect.height // 2 - 16))

            self.draw_avatar(
                (rect.centerx, rect.y + radius + 7),
                radius,
                avatar,
                selected
            )

            self.text(
                self.fit(self.AVATARS[avatar], self.tiny_font, rect.width - 6),
                self.tiny_font,
                color if selected else self.MUTED,
                rect.centerx,
                rect.bottom - 10,
                "center"
            )

        # Buttons

        changed = self.has_changes()

        self.draw_button(
            L["save"],
            "SAVE CHANGES",
            "accent",
            disabled=not changed
        )

        self.draw_button(L["delete"], "DELETE ACCOUNT", "danger")

        if changed:

            dot = int(150 + 100 * math.sin(self.time * 5))

            pygame.draw.circle(
                self.screen,
                (dot, int(dot * 0.8), 60),
                (L["save"].x + 4, L["save"].y - 10),
                3
            )

            self.text(
                "UNSAVED CHANGES",
                self.tiny_font,
                self.YELLOW,
                L["save"].x + 14,
                L["save"].y - 16
            )

    # ============================================================
    # DRAW: HISTORY TAB
    # ============================================================

    def draw_history_tab(self, L):

        area = L["hist"]

        self.text(
            "RECENT MISSIONS",
            self.small_font,
            self.SOFT,
            area.x,
            area.y - 2
        )

        self.text(
            f"{self.games} TOTAL",
            self.tiny_font,
            self.MUTED,
            area.right,
            area.y + 1,
            "right"
        )

        head_y = area.y + 26

        self.text("#", self.tiny_font, self.MUTED, area.x + 12, head_y)
        self.text("SCORE", self.tiny_font, self.MUTED, area.x + 70, head_y)
        self.text("DATE", self.tiny_font, self.MUTED, area.x + area.width // 2, head_y)

        pygame.draw.line(
            self.screen,
            (90, 50, 150),
            (area.x, head_y + 18),
            (area.right, head_y + 18),
            1
        )

        if not self.history:

            self.text(
                "No missions flown yet.",
                self.font,
                self.MUTED,
                area.centerx,
                area.y + 120,
                "center"
            )

            self.text(
                "Play a game and your scores will appear here.",
                self.tiny_font,
                self.DIM,
                area.centerx,
                area.y + 146,
                "center"
            )

            return

        row_h = 34

        list_top = head_y + 24

        visible = max(1, (area.bottom - list_top) // row_h)

        max_scroll = max(0, len(self.history) - visible)

        self.history_scroll = max(0, min(self.history_scroll, max_scroll))

        best = max(item["score"] for item in self.history)

        for row in range(visible):

            index = self.history_scroll + row

            if index >= len(self.history):
                break

            item = self.history[index]

            rect = pygame.Rect(
                area.x,
                list_top + row * row_h,
                area.width - 14,
                row_h - 4
            )

            is_best = (item["score"] == best and best > 0)

            self.draw_box(
                rect,
                (60, 25, 110, 120) if is_best else (
                    (14, 8, 38, 130) if row % 2 == 0 else (22, 12, 52, 110)
                ),
                (0, 255, 150, 120) if is_best else None,
                6,
                1
            )

            self.text(
                index + 1,
                self.small_font,
                self.MUTED,
                rect.x + 12,
                rect.centery - 8
            )

            self.text(
                f"{item['score']:,}",
                self.font,
                self.GREEN if is_best else self.WHITE,
                rect.x + 70,
                rect.centery - 9
            )

            if item["date"]:

                self.text(
                    item["date"],
                    self.small_font,
                    self.SOFT,
                    area.x + area.width // 2,
                    rect.centery - 8
                )

            if is_best:

                self.text(
                    "BEST",
                    self.tiny_font,
                    self.GREEN,
                    rect.right - 10,
                    rect.centery - 6,
                    "right"
                )

        # Scrollbar

        if max_scroll > 0:

            track = pygame.Rect(
                area.right - 8,
                list_top,
                6,
                visible * row_h - 4
            )

            self.draw_box(track, (30, 15, 65, 160), None, 3)

            thumb_h = max(24, int(track.height * visible / len(self.history)))

            thumb_y = track.y + int(
                (track.height - thumb_h)
                * self.history_scroll / max_scroll
            )

            self.draw_box(
                pygame.Rect(track.x, thumb_y, track.width, thumb_h),
                (*self.BRIGHT_PURPLE, 230),
                None,
                3
            )

    # ============================================================
    # SPACESHIP: IMAGES
    # ============================================================

    def ship_surface(self, number, max_w, max_h):
        """Ship image scaled to fit inside max_w x max_h (cached)."""

        key = (number, max_w, max_h)

        if key in self.ship_cache:
            return self.ship_cache[key]

        if number not in self.ship_images:
            self.ship_images[number] = self.load_ship_image(number)

        raw = self.ship_images[number]

        result = None

        if raw is not None:

            rw, rh = raw.get_size()

            scale = min(
                max_w / max(1, rw),
                max_h / max(1, rh)
            )

            size = (
                max(1, int(rw * scale)),
                max(1, int(rh * scale))
            )

            result = pygame.transform.smoothscale(raw, size)

        self.ship_cache[key] = result

        return result

    def draw_fallback_ship(self, rect, number):
        """Shown only when ShipN.png cannot be found."""

        box = rect.inflate(-4, -4)

        pygame.draw.rect(
            self.screen,
            (70, 35, 120),
            box,
            1,
            border_radius=6
        )

        self.text(
            "?",
            self.heading_font,
            self.DIM,
            box.centerx,
            box.centery - (8 if box.height >= 60 else 0),
            "center"
        )

        if box.height >= 60:

            self.text(
                "Ship" + str(number),
                self.tiny_font,
                self.DIM,
                box.centerx,
                box.centery + 14,
                "center"
            )

    def draw_ship(self, rect, number):

        image = self.ship_surface(
            number,
            max(1, rect.width),
            max(1, rect.height)
        )

        if image is not None:

            self.screen.blit(image, image.get_rect(center=rect.center))

        else:

            self.draw_fallback_ship(rect, number)

    # ============================================================
    # SPACESHIP: SAVE
    # ============================================================

    def save_ship(self):

        if self.ship == self.saved_ship:

            self.set_message("This ship is already equipped.", "warning")

            return

        key = (
            str(self.player_id)
            if self.player_id is not None
            else "guest"
        )

        path = self.ship_selection_file()

        try:

            try:

                with open(path, "r", encoding="utf-8") as file:
                    data = json.load(file)

                if not isinstance(data, dict):
                    data = {}

            except (OSError, ValueError):

                data = {}

            data[key] = self.ship

            with open(path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4)

        except OSError:

            self.set_message("Could not save your ship.", "error")

            return

        self.saved_ship = self.ship

        self.player["ship"] = self.ship

        self.set_message("SHIP " + str(self.ship) + " equipped.", "success")

    # ============================================================
    # DRAW: SPACESHIP TAB
    # ============================================================

    def draw_ships_tab(self, L):

        area = L["ship_area"]

        self.text(
            "SPACESHIP HANGAR",
            self.small_font,
            self.SOFT,
            area.x,
            area.y - 2
        )

        self.text(
            "Choose the ship you fly into battle.",
            self.tiny_font,
            self.MUTED,
            area.x,
            area.y + 16
        )

        # ---- Preview ----

        preview = L["ship_preview"]

        color = self.SHIP_COLORS.get(self.ship, self.PURPLE)

        self.draw_box(preview, (8, 5, 28, 175), (*color, 200), 10, 2)

        glow = pygame.Surface(preview.size, pygame.SRCALPHA)

        pulse = int(40 + 20 * math.sin(self.time * 2.5))

        pygame.draw.circle(
            glow,
            (*color, pulse),
            (preview.width // 2, preview.height // 2),
            max(10, min(preview.width, preview.height) // 2 - 6)
        )

        self.screen.blit(glow, preview.topleft)

        bob = int(math.sin(self.time * 2) * 4)

        ship_box = pygame.Rect(
            preview.x + 20,
            preview.y + 38,
            max(1, preview.width - 40),
            max(1, preview.height - 52)
        ).move(0, bob)

        self.draw_ship(ship_box, self.ship)

        self.text(
            "SHIP " + str(self.ship),
            self.heading_font,
            color,
            preview.x + 16,
            preview.y + 10
        )

        if self.ship == self.saved_ship:

            self.text(
                "EQUIPPED",
                self.small_font,
                self.GREEN,
                preview.right - 16,
                preview.y + 14,
                "right"
            )

        else:

            self.text(
                "NOT EQUIPPED",
                self.small_font,
                self.YELLOW,
                preview.right - 16,
                preview.y + 14,
                "right"
            )

        if self.ship_images.get(self.ship, "loaded") is None:

            self.text(
                "Ship" + str(self.ship) + ".png not found - showing a placeholder",
                self.tiny_font,
                self.DIM,
                preview.centerx,
                preview.bottom - 12,
                "center"
            )

        # ---- Cards ----

        mouse = pygame.mouse.get_pos()

        for number, rect in L["ship_cards"]:

            selected = (number == self.ship)

            equipped = (number == self.saved_ship)

            hover = rect.collidepoint(mouse)

            card_color = self.SHIP_COLORS.get(number, self.PURPLE)

            if selected:

                self.draw_glow(rect, card_color, 8, 3, 30)

                fill = (60, 25, 110, 170)
                border = (*card_color, 255)

            elif hover:

                fill = (45, 20, 85, 150)
                border = (190, 110, 255, 220)

            else:

                fill = (14, 8, 38, 140)
                border = (90, 50, 150, 160)

            self.draw_box(rect, fill, border, 8, 2 if selected else 1)

            icon = pygame.Rect(
                rect.x + 4,
                rect.y + 4,
                max(1, rect.width - 8),
                max(1, rect.height - 30)
            )

            self.draw_ship(icon, number)

            self.text(
                "SHIP " + str(number),
                self.tiny_font,
                card_color if selected else self.MUTED,
                rect.centerx,
                rect.bottom - 12,
                "center"
            )

            if equipped:

                pygame.draw.circle(
                    self.screen,
                    self.GREEN,
                    (rect.right - 12, rect.y + 12),
                    4
                )

        # ---- Equip button ----

        same = (self.ship == self.saved_ship)

        self.draw_button(
            L["ship_equip"],
            "SHIP EQUIPPED" if same else "EQUIP SHIP",
            "accent",
            disabled=same
        )

    # ============================================================
    # DRAW: DELETE MODAL
    # ============================================================

    def draw_delete_modal(self, L):

        overlay = pygame.Surface(
            (self.screen_width, self.screen_height),
            pygame.SRCALPHA
        )

        overlay.fill((0, 0, 0, 175))

        self.screen.blit(overlay, (0, 0))

        modal = L["modal"]

        self.draw_glass_panel(modal, 16)

        self.text(
            "DELETE ACCOUNT?",
            self.heading_font,
            (255, 150, 170),
            modal.centerx,
            modal.y + 34,
            "center"
        )

        self.text(
            "This permanently removes your account",
            self.small_font,
            self.SOFT,
            modal.centerx,
            modal.y + 70,
            "center"
        )

        self.text(
            "and all saved scores. It cannot be undone.",
            self.small_font,
            self.SOFT,
            modal.centerx,
            modal.y + 90,
            "center"
        )

        self.draw_input(
            L["modal_input"],
            "TYPE  DELETE  TO CONFIRM",
            self.delete_text,
            True,
            placeholder="DELETE"
        )

        ready = (self.delete_text.strip().upper() == "DELETE")

        self.draw_button(
            L["modal_yes"],
            "DELETE",
            "danger",
            disabled=not ready
        )

        self.draw_button(L["modal_no"], "CANCEL")

    # ============================================================
    # DRAW: TOAST
    # ============================================================

    def draw_toast(self, card):

        remaining = self.message_until - pygame.time.get_ticks()

        if remaining <= 0:

            self.message = ""

            return

        fade = max(0.0, min(1.0, remaining / 400.0))

        color = {
            "success": self.GREEN,
            "error": self.RED,
            "warning": self.YELLOW,
        }.get(self.message_type, self.SOFT)

        label = self.small_font.render(self.message, True, color)

        label.set_alpha(int(255 * fade))

        rect = pygame.Rect(0, 0, label.get_width() + 40, 28)

        rect.midbottom = (card.centerx, card.bottom - 46)

        self.draw_box(
            rect,
            (8, 5, 28, int(235 * fade)),
            (*color, int(230 * fade)),
            14,
            1
        )

        pygame.draw.circle(
            self.screen,
            color,
            (rect.x + 14, rect.centery),
            4
        )

        self.screen.blit(
            label,
            label.get_rect(midleft=(rect.x + 26, rect.centery))
        )

    # ============================================================
    # DRAW
    # ============================================================

    def draw(self):

        self.time = pygame.time.get_ticks() / 1000.0

        L = self.compute_layout()

        self.draw_background()

        self.draw_dossier(L)

        if self.modal_open:
            self.draw_modal(L)

        if self.message:
            self.draw_toast(L["card"])

        if self.delete_confirm:
            self.draw_delete_modal(L)

    # ============================================================
    # SAVE
    # ============================================================

    def save_changes(self):

        if self.player_id is None:

            self.set_message("No player account is loaded.", "error")

            return

        if not self.has_changes():

            self.set_message("Nothing to save.", "warning")

            return

        profile_changed = self.profile_fields_changed()

        new_name = self.fields["username"].strip()
        password = self.fields["password"]
        confirm = self.fields["confirm"]

        if profile_changed:

            if len(new_name) < 3:

                self.set_message(
                    "Username must be at least 3 characters.",
                    "error"
                )

                return

            if len(new_name) > 20:

                self.set_message("Username is too long (max 20).", "error")

                return

            if password or confirm:

                if len(password) < 4:

                    self.set_message(
                        "Password must be at least 4 characters.",
                        "error"
                    )

                    return

                if password != confirm:

                    self.set_message("Passwords do not match.", "error")

                    return

            new_password = password if password else None

            success = False

            try:

                success = update_player_profile(
                    self.player_id,
                    new_name,
                    new_password,
                    self.avatar
                )

            except TypeError:

                # Older db version without the avatar argument

                try:

                    success = update_player_profile(
                        self.player_id,
                        new_name,
                        new_password
                    )

                except Exception:

                    success = False

            except Exception:

                success = False

            if not success:

                self.set_message(
                    "Could not save changes. Username may already exist.",
                    "error"
                )

                return

            self.player_name = new_name

            self.saved_avatar = self.avatar

            self.fields["username"] = new_name
            self.fields["password"] = ""
            self.fields["confirm"] = ""

            self.active_field = None

            self.player["id"] = self.player_id
            self.player["player_id"] = self.player_id
            self.player["player_name"] = new_name
            self.player["username"] = new_name
            self.player["avatar"] = self.avatar

        if not self.apply_photo():

            self.set_message(
                "Profile saved, but the photo could not be written.",
                "error"
            )

            return

        self.set_message("Profile changes saved.", "success")

    # ============================================================
    # DELETE
    # ============================================================

    def confirm_delete(self):

        if self.delete_text.strip().upper() != "DELETE":

            self.set_message("Type DELETE to confirm.", "warning")

            return "stay"

        if self.player_id is None:

            self.delete_confirm = False

            self.set_message("No player account is loaded.", "error")

            return "stay"

        try:

            success = delete_player(self.player_id)

        except Exception:

            success = False

        self.delete_confirm = False
        self.delete_text = ""

        if success:

            # Remove the stored photo too

            try:

                path = self.photo_file(self.player_id)

                if os.path.isfile(path):
                    os.remove(path)

            except OSError:
                pass

            return "logout"

        self.set_message("Could not delete the account.", "error")

        return "stay"

    # ============================================================
    # TEXT INPUT HELPERS
    # ============================================================

    def type_into(self, key, event, limit):

        if event.key == pygame.K_BACKSPACE:

            self.fields[key] = self.fields[key][:-1]

        elif event.unicode and event.unicode.isprintable():

            if len(self.fields[key]) < limit:
                self.fields[key] += event.unicode

    # ============================================================
    # WINDOW HELPERS
    # ============================================================

    def open_window(self, tab):

        self.tab = tab
        self.modal_open = True
        self.active_field = None

    def close_window(self):

        self.modal_open = False
        self.active_field = None

    def press_feature(self, key):

        if key == "edit":
            self.open_window("account")

        elif key == "history":
            self.open_window("history")

        elif key == "ships":
            self.open_window("ships")

        elif key == "photo":
            self.choose_photo(auto_save=True)

    # ============================================================
    # HANDLE EVENT
    # ============================================================

    def handle_event(self, event):

        if event.type == pygame.VIDEORESIZE:

            self.resize(event.w, event.h)

            return None

        # --------------------------------------------------------
        # DRAG & DROP AN IMAGE ONTO THE WINDOW
        # --------------------------------------------------------

        if event.type == pygame.DROPFILE:

            if not self.delete_confirm:

                if self.modal_open:

                    # Inside the edit window: keep it pending until saved

                    self.tab = "account"
                    self.active_field = None

                    self.set_photo_from_path(event.file)

                else:

                    # Main view: save the new photo straight away

                    if self.set_photo_from_path(event.file):
                        self.save_photo_now()

            return None

        L = self.compute_layout()

        # --------------------------------------------------------
        # MOUSE WHEEL (history scrolling)
        # --------------------------------------------------------

        if event.type == pygame.MOUSEWHEEL:

            if (
                self.modal_open
                and self.tab == "history"
                and not self.delete_confirm
            ):

                self.history_scroll = max(
                    0,
                    self.history_scroll - event.y
                )

            return None

        # --------------------------------------------------------
        # KEYBOARD
        # --------------------------------------------------------

        if event.type == pygame.KEYDOWN:

            # ---- Delete modal ----

            if self.delete_confirm:

                if event.key == pygame.K_ESCAPE:

                    self.delete_confirm = False
                    self.delete_text = ""

                elif event.key == pygame.K_RETURN:

                    return self.confirm_delete()

                elif event.key == pygame.K_BACKSPACE:

                    self.delete_text = self.delete_text[:-1]

                elif event.unicode and event.unicode.isprintable():

                    if len(self.delete_text) < 10:
                        self.delete_text += event.unicode

                return None

            # ---- Main view ----

            if not self.modal_open:

                if event.key == pygame.K_ESCAPE:

                    return "back"

                if event.key == pygame.K_RETURN:

                    if self.has_changes():
                        self.save_changes()

                elif event.key == pygame.K_e:
                    self.press_feature("edit")

                elif event.key == pygame.K_h:
                    self.press_feature("history")

                elif event.key == pygame.K_s:
                    self.press_feature("ships")

                elif event.key == pygame.K_p:
                    self.press_feature("photo")

                elif event.key == pygame.K_r:

                    self.load_player_data()

                    self.set_message("Profile refreshed.", "success")

                return None

            # ---- Feature window ----

            if event.key == pygame.K_ESCAPE:

                self.close_window()

                return None

            if self.tab == "ships":

                if event.key == pygame.K_LEFT:

                    self.ship = max(1, self.ship - 1)

                elif event.key == pygame.K_RIGHT:

                    self.ship = min(self.SHIP_COUNT, self.ship + 1)

                elif event.key == pygame.K_RETURN:

                    self.save_ship()

                elif event.unicode in ("1", "2", "3", "4", "5"):

                    self.ship = int(event.unicode)

                return None

            if self.tab == "history":

                if event.key == pygame.K_DOWN:
                    self.history_scroll += 1

                elif event.key == pygame.K_UP:
                    self.history_scroll = max(0, self.history_scroll - 1)

                elif event.key == pygame.K_PAGEDOWN:
                    self.history_scroll += 8

                elif event.key == pygame.K_PAGEUP:
                    self.history_scroll = max(0, self.history_scroll - 8)

                return None

            if event.key == pygame.K_RETURN:

                self.save_changes()

                return None

            if event.key == pygame.K_TAB:

                if self.active_field in self.FIELD_ORDER:

                    step = -1 if (event.mod & pygame.KMOD_SHIFT) else 1

                    index = self.FIELD_ORDER.index(self.active_field)

                    self.active_field = self.FIELD_ORDER[
                        (index + step) % len(self.FIELD_ORDER)
                    ]

                else:

                    self.active_field = "username"

                return None

            if self.active_field == "username":

                self.type_into("username", event, 20)

            elif self.active_field in ("password", "confirm"):

                self.type_into(self.active_field, event, 30)

            return None

        # --------------------------------------------------------
        # MOUSE
        # --------------------------------------------------------

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

            pos = event.pos

            # ---- Delete modal ----

            if self.delete_confirm:

                if L["modal_yes"].collidepoint(pos):

                    return self.confirm_delete()

                if L["modal_no"].collidepoint(pos):

                    self.delete_confirm = False
                    self.delete_text = ""

                return None

            # ---- Main view ----

            if not self.modal_open:

                if L["back"].collidepoint(pos):
                    return "back"

                if L["refresh"].collidepoint(pos):

                    self.load_player_data()

                    self.set_message("Profile refreshed.", "success")

                    return None

                if L["photo"].collidepoint(pos):

                    self.choose_photo(auto_save=True)

                    return None

                for key, _label, rect in L["feat"]:

                    if rect.collidepoint(pos):

                        self.press_feature(key)

                        return None

                return None

            # ---- Feature window ----

            if L["modal_close"].collidepoint(pos):

                self.close_window()

                return None

            if not L["right"].collidepoint(pos):

                self.close_window()

                return None

            # Tabs

            if L["tab_account"].collidepoint(pos):

                self.tab = "account"
                self.active_field = None

                return None

            if L["tab_history"].collidepoint(pos):

                self.tab = "history"
                self.active_field = None

                return None

            if L["tab_ships"].collidepoint(pos):

                self.tab = "ships"
                self.active_field = None

                return None

            if self.tab == "ships":

                for number, rect in L["ship_cards"]:

                    if rect.collidepoint(pos):

                        self.ship = number

                        return None

                if L["ship_equip"].collidepoint(pos):

                    self.save_ship()

                return None

            if self.tab != "account":
                return None

            # ---- Account tab ----

            if L["photo_upload"].collidepoint(pos):

                self.active_field = None

                self.choose_photo(auto_save=False)

                return None

            if L["photo_remove"].collidepoint(pos):

                self.active_field = None

                self.remove_photo()

                return None

            if L["toggle_pw"].collidepoint(pos):

                self.show_password = not self.show_password

                return None

            for key in self.FIELD_ORDER:

                if L[key].collidepoint(pos):

                    self.active_field = key

                    return None

            for avatar, rect in L["avatars"]:

                if rect.collidepoint(pos):

                    self.avatar = avatar

                    self.active_field = None

                    return None

            if L["save"].collidepoint(pos):

                self.save_changes()

                return None

            if L["delete"].collidepoint(pos):

                self.delete_confirm = True
                self.delete_text = ""
                self.active_field = None

                return None

            # Clicked empty space

            self.active_field = None

        return None