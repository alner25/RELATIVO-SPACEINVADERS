
import math
import random
import pygame

from auth import register


class RegisterScreen:
    DESIGN_WIDTH = 1000
    DESIGN_HEIGHT = 650

    # Shared column for every form element (perfect alignment)
    COL_X = 320
    COL_W = 360

    def __init__(self, screen, width, height):
        self.screen = screen
        self.width = width
        self.height = height

        self.bg_raw = None
        for path in ("assets/images/world_map.png", "assets/images/bg.png"):
            try:
                self.bg_raw = pygame.image.load(path).convert()
                break
            except (pygame.error, FileNotFoundError):
                pass

        self.bg_image = None
        self.background_fx = None

        self.username = ""
        self.password = ""
        self.confirm_password = ""
        self.active_field = "username"
        self.fields = ["username", "password", "confirm"]

        self.message = ""
        self.message_color = (255, 100, 110)

        self.scale = 1.0
        self.origin_x = 0
        self.origin_y = 0

        self.frame_rect = pygame.Rect(0, 0, 0, 0)
        self.screen_rect = pygame.Rect(0, 0, 0, 0)
        self.bottom_bar = pygame.Rect(0, 0, 0, 0)

        self.username_rect = pygame.Rect(0, 0, 0, 0)
        self.password_rect = pygame.Rect(0, 0, 0, 0)
        self.confirm_rect = pygame.Rect(0, 0, 0, 0)
        self.register_button = pygame.Rect(0, 0, 0, 0)
        self.back_button = pygame.Rect(0, 0, 0, 0)

        self.bolt_seed = 0
        self.bolts = []

        self.recalculate_layout()
        self.resize_background(width, height)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _rect(self, x, y, w, h):
        return pygame.Rect(
            round(self.origin_x + x * self.scale),
            round(self.origin_y + y * self.scale),
            max(1, round(w * self.scale)),
            max(1, round(h * self.scale)),
        )

    def _point(self, x, y):
        return (
            round(self.origin_x + x * self.scale),
            round(self.origin_y + y * self.scale),
        )

    def _font(self, size, bold=False):
        return pygame.font.SysFont(
            "Consolas", max(9, round(size * self.scale)), bold=bold
        )

    def _build_fonts(self):
        self.title_font = self._font(30, bold=True)
        self.subtitle_font = self._font(14)
        self.font = self._font(17, bold=True)
        self.label_font = self._font(12, bold=True)
        self.button_font = self._font(17, bold=True)
        self.small_font = self._font(11)

    def recalculate_layout(self):
        old_scale = self.scale
        self.scale = max(
            0.1,
            min(self.width / self.DESIGN_WIDTH, self.height / self.DESIGN_HEIGHT),
        )
        self.origin_x = (self.width - self.DESIGN_WIDTH * self.scale) / 2
        self.origin_y = (self.height - self.DESIGN_HEIGHT * self.scale) / 2

        if abs(old_scale - self.scale) > 0.001 or not hasattr(self, "font"):
            self._build_fonts()

        # Main monitor frame + inner screen + bottom strip
        self.frame_rect = self._rect(205, 55, 590, 490)
        self.screen_rect = self._rect(233, 83, 534, 434)
        self.bottom_bar = self._rect(205, 553, 590, 30)

        # All form elements share COL_X / COL_W
        x, w = self.COL_X, self.COL_W
        self.username_rect = self._rect(x, 196, w, 46)
        self.password_rect = self._rect(x, 268, w, 46)
        self.confirm_rect = self._rect(x, 340, w, 46)
        self.register_button = self._rect(x, 408, w, 48)
        self.back_button = self._rect(x, 466, w, 38)

    # ------------------------------------------------------------------
    # Background
    # ------------------------------------------------------------------

    def resize_background(self, width, height):
        width, height = max(1, width), max(1, height)

        if self.bg_raw:
            rw, rh = self.bg_raw.get_size()
            cover = max(width / rw, height / rh) * 1.08
            self.bg_image = pygame.transform.smoothscale(
                self.bg_raw,
                (max(1, round(rw * cover)), max(1, round(rh * cover))),
            )
        else:
            self.bg_image = self._create_fallback_background(width, height)

        fx = pygame.Surface((width, height), pygame.SRCALPHA)
        fx.fill((0, 4, 16, 150))

        # Faint perspective floor grid
        horizon = int(height * 0.62)
        for i in range(0, 30):
            y = horizon + int((i / 30) ** 2 * (height - horizon))
            pygame.draw.line(fx, (0, 120, 190, 18), (0, y), (width, y))
        cx = width // 2
        for i in range(-14, 15):
            pygame.draw.line(
                fx,
                (0, 120, 190, 14),
                (cx + i * width // 8, height),
                (cx + i * 25, horizon),
            )

        for y in range(0, height, 4):
            pygame.draw.line(fx, (0, 0, 0, 16), (0, y), (width, y))

        self.background_fx = fx

    def _create_fallback_background(self, width, height):
        surface = pygame.Surface((width, height))
        for y in range(height):
            r = y / max(1, height - 1)
            pygame.draw.line(
                surface,
                (1, 5 + round(9 * r), 16 + round(20 * r)),
                (0, y),
                (width, y),
            )
        rnd = random.Random(23)
        for _ in range(max(30, width * height // 18000)):
            b = rnd.randrange(25, 75)
            pygame.draw.circle(
                surface,
                (b // 3, b // 2, b),
                (rnd.randrange(width), rnd.randrange(height)),
                rnd.choice((1, 1, 1, 2)),
            )
        return surface

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _angular_points(rect, cut):
        cut = max(1, min(cut, rect.width // 3, rect.height // 3))
        return [
            (rect.left + cut, rect.top),
            (rect.right - cut, rect.top),
            (rect.right, rect.top + cut),
            (rect.right, rect.bottom - cut),
            (rect.right - cut, rect.bottom),
            (rect.left + cut, rect.bottom),
            (rect.left, rect.bottom - cut),
            (rect.left, rect.top + cut),
        ]

    def _draw_poly_glow(self, points, color, spread):
        spread = max(3, round(spread * self.scale))
        min_x = min(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_x = max(p[0] for p in points)
        max_y = max(p[1] for p in points)
        pad = spread + 3
        surf = pygame.Surface(
            (max_x - min_x + pad * 2 + 1, max_y - min_y + pad * 2 + 1),
            pygame.SRCALPHA,
        )
        pts = [(x - min_x + pad, y - min_y + pad) for x, y in points]
        pygame.draw.lines(surf, (*color, 20), True, pts, spread * 2)
        pygame.draw.lines(surf, (*color, 40), True, pts, max(2, spread))
        pygame.draw.lines(
            surf, (*color, 95), True, pts, max(1, round(2 * self.scale))
        )
        self.screen.blit(surf, (min_x - pad, min_y - pad))

    def _draw_electric_aura(self, ticks):
        """Big soft blue glow + flickering lightning bolts around the frame."""
        fr = self.frame_rect
        aura = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        # Soft radial glow layers
        for i in range(8, 0, -1):
            grow = int(i * 22 * self.scale)
            alpha = 8 + int(4 * math.sin(ticks * 0.003 + i))
            pygame.draw.ellipse(
                aura,
                (0, 150, 255, alpha),
                fr.inflate(
                    grow * 2 + int(160 * self.scale),
                    grow * 2 + int(60 * self.scale),
                ),
            )

        # Regenerate bolts every 120 ms for flicker
        seed = ticks // 120
        if seed != self.bolt_seed:
            self.bolt_seed = seed
            rnd = random.Random(seed)
            self.bolts = []
            for _ in range(7):
                side = rnd.choice(("left", "right", "top", "bottom"))
                if side == "left":
                    sx, sy = fr.left, rnd.randint(fr.top, fr.bottom)
                    dx, dy = -1, 0
                elif side == "right":
                    sx, sy = fr.right, rnd.randint(fr.top, fr.bottom)
                    dx, dy = 1, 0
                elif side == "top":
                    sx, sy = rnd.randint(fr.left, fr.right), fr.top
                    dx, dy = 0, -1
                else:
                    sx, sy = rnd.randint(fr.left, fr.right), fr.bottom
                    dx, dy = 0, 1
                pts = [(sx, sy)]
                x, y = sx, sy
                for _ in range(rnd.randint(4, 8)):
                    step = rnd.randint(8, 22) * self.scale
                    jit = rnd.randint(-14, 14) * self.scale
                    x += dx * step + (jit if dy else 0)
                    y += dy * step + (jit if dx else 0)
                    pts.append((x, y))
                self.bolts.append(pts)

        for pts in self.bolts:
            pygame.draw.lines(
                aura, (60, 170, 255, 45), False, pts, max(3, int(6 * self.scale))
            )
            pygame.draw.lines(
                aura, (170, 230, 255, 140), False, pts, max(1, int(2 * self.scale))
            )

        self.screen.blit(aura, (0, 0))

    def _draw_side_ghost_panels(self):
        """Faded duplicate frames at the left and right edges."""
        for side in (-1, 1):
            w = int(120 * self.scale)
            h = int(260 * self.scale)
            x = 0 if side < 0 else self.width - w
            y = self.frame_rect.centery - h // 2
            ghost = pygame.Surface((w, h), pygame.SRCALPHA)
            ghost.fill((3, 25, 55, 70))
            pygame.draw.rect(
                ghost, (0, 160, 230, 90), ghost.get_rect(), max(2, int(5 * self.scale))
            )
            for ly in range(0, h, 5):
                pygame.draw.line(ghost, (0, 0, 0, 25), (0, ly), (w, ly))
            self.screen.blit(ghost, (x, y))

    def _draw_monitor_frame(self, pulse):
        fr = self.frame_rect
        cut = max(10, round(26 * self.scale))
        outer = self._angular_points(fr, cut)

        # Neon outline glow
        self._draw_poly_glow(outer, (0, 190, 255), 18)

        # Thick metallic-cyan frame body
        pygame.draw.polygon(self.screen, (6, 60, 95), outer)
        pygame.draw.lines(
            self.screen, (0, pulse, 255), True, outer, max(2, round(3 * self.scale))
        )

        # Corner notch details
        notch = max(4, round(9 * self.scale))
        for (px, py) in (fr.topleft, fr.topright, fr.bottomleft, fr.bottomright):
            sx = 1 if px == fr.left else -1
            sy = 1 if py == fr.top else -1
            pygame.draw.rect(
                self.screen,
                (0, 230, 255),
                (
                    px + sx * cut - (0 if sx > 0 else notch),
                    py + sy * notch - (0 if sy > 0 else notch),
                    notch,
                    notch,
                ),
            )

        # Dark inner monitor screen (subtle vertical gradient)
        sr = self.screen_rect
        screen_surf = pygame.Surface(sr.size)
        for y in range(sr.height):
            r = y / max(1, sr.height - 1)
            c = int(38 - 26 * r)
            pygame.draw.line(screen_surf, (c, c + 2, c + 6), (0, y), (sr.width, y))
        for y in range(0, sr.height, 4):
            pygame.draw.line(screen_surf, (0, 0, 0), (0, y), (sr.width, y))
        self.screen.blit(screen_surf, sr.topleft)
        pygame.draw.rect(self.screen, (0, 200, 240), sr, max(1, round(2 * self.scale)))

        # LED strip on the frame's top-left
        led_y = fr.top + int(12 * self.scale)
        for i in range(4):
            pygame.draw.rect(
                self.screen,
                (0, 230, 255) if i % 2 == 0 else (0, 120, 170),
                (
                    fr.left + int((60 + i * 14) * self.scale),
                    led_y,
                    int(8 * self.scale),
                    int(4 * self.scale),
                ),
            )

    def _draw_bottom_bar(self):
        bar = self.bottom_bar
        pts = self._angular_points(bar, max(4, round(8 * self.scale)))
        self._draw_poly_glow(pts, (0, 170, 255), 6)
        pygame.draw.polygon(self.screen, (2, 20, 42), pts)
        pygame.draw.lines(
            self.screen, (0, 200, 240), True, pts, max(1, round(2 * self.scale))
        )

        segments = ["SPACE INVADER", "NEW PILOT REGISTRATION", "SECURE CHANNEL", "v1.0"]
        seg_w = bar.width / len(segments)
        for i, text in enumerate(segments):
            cx = bar.left + int(seg_w * i + seg_w / 2)
            if i:
                pygame.draw.line(
                    self.screen,
                    (0, 120, 170),
                    (bar.left + int(seg_w * i), bar.top + 6),
                    (bar.left + int(seg_w * i), bar.bottom - 6),
                )
            dot_r = max(2, int(3 * self.scale))
            pygame.draw.circle(
                self.screen,
                (0, 230, 255),
                (cx - int(seg_w / 2) + int(14 * self.scale), bar.centery),
                dot_r,
            )
            t = self.small_font.render(text, True, (150, 235, 255))
            self.screen.blit(t, t.get_rect(center=(cx + dot_r, bar.centery)))

    def _draw_input(self, rect, label, value, active):
        cut = max(4, round(8 * self.scale))
        pts = self._angular_points(rect, cut)

        if active:
            self._draw_poly_glow(pts, (0, 190, 255), 6)

        pygame.draw.polygon(self.screen, (4, 16, 34), pts)
        pygame.draw.lines(
            self.screen,
            (0, 225, 255) if active else (0, 100, 150),
            True,
            pts,
            max(1, round((2 if active else 1) * self.scale)),
        )

        lbl = self.label_font.render(
            label.upper(), True, (70, 225, 255) if active else (30, 140, 185)
        )
        self.screen.blit(
            lbl, (rect.x, rect.y - lbl.get_height() - max(3, round(4 * self.scale)))
        )

        if value:
            shown, color = value, (225, 248, 255)
        else:
            shown, color = f"ENTER {label.upper()}", (30, 110, 150)

        txt = self.font.render(shown, True, color)
        tx = rect.x + max(7, round(12 * self.scale))
        ty = rect.centery - txt.get_height() // 2

        clip = self.screen.get_clip()
        self.screen.set_clip(rect.inflate(-max(5, round(10 * self.scale)), -4))
        self.screen.blit(txt, (tx, ty))
        if active and pygame.time.get_ticks() // 500 % 2 == 0:
            cx = tx + txt.get_width() + 2
            pygame.draw.line(
                self.screen,
                (130, 245, 255),
                (cx, ty + 2),
                (cx, ty + txt.get_height() - 2),
                max(1, round(2 * self.scale)),
            )
        self.screen.set_clip(clip)

    def _draw_button(self, rect, text, primary=True):
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        pts = self._angular_points(rect, max(5, round(10 * self.scale)))

        if primary:
            glow, outline = (0, 190, 255), (0, 235, 255)
            fill = (7, 58, 82) if hovered else (4, 38, 61)
        else:
            glow, outline = (40, 90, 150), (70, 140, 200)
            fill = (18, 30, 55) if hovered else (10, 20, 40)

        self._draw_poly_glow(pts, glow, 8 if hovered else 4)
        pygame.draw.polygon(self.screen, fill, pts)
        pygame.draw.lines(
            self.screen, outline, True, pts, max(1, round(2 * self.scale))
        )

        d = max(4, round(7 * self.scale))
        pygame.draw.rect(
            self.screen,
            outline,
            (rect.x + max(10, round(18 * self.scale)), rect.centery - d // 2, d, d),
            max(1, round(self.scale)),
        )

        t = self.button_font.render(text, True, (225, 250, 255))
        self.screen.blit(t, t.get_rect(center=rect.center))

    # ------------------------------------------------------------------
    # Main drawing
    # ------------------------------------------------------------------

    def update(self, dt):
        """Per-frame update hook used by main.py.

        These screens are event-driven, but main.py updates every screen
        uniformly. Keeping this method makes LoginScreen/RegisterScreen
        compatible with that loop.
        """
        return None

    def draw(self):
        self.screen.fill((0, 3, 12))
        ticks = pygame.time.get_ticks()
        motion = ticks * 0.00035

        bw, bh = self.bg_image.get_size()
        dx = round(math.sin(motion) * min(max(0, (bw - self.width) // 2), 10))
        dy = round(math.sin(motion * 0.7) * min(max(0, (bh - self.height) // 2), 7))
        self.screen.blit(
            self.bg_image, ((self.width - bw) // 2 + dx, (self.height - bh) // 2 + dy)
        )
        self.screen.blit(self.background_fx, (0, 0))

        pulse = 205 + round(45 * math.sin(ticks * 0.004))

        self._draw_side_ghost_panels()
        self._draw_electric_aura(ticks)
        self._draw_monitor_frame(pulse)
        self._draw_bottom_bar()

        # ---- Content inside the monitor (all centered on the shared column) ----
        col_left = self._point(self.COL_X, 0)[0]
        col_right = self._point(self.COL_X + self.COL_W, 0)[0]
        col_center_x = (col_left + col_right) // 2

        title = self.title_font.render("SPACE INVADER", True, (205, 248, 255))
        self.screen.blit(
            title, title.get_rect(center=(col_center_x, self._point(0, 118)[1]))
        )

        subtitle = self.subtitle_font.render(
            "CREATE PLAYER ACCOUNT", True, (40, 170, 210)
        )
        self.screen.blit(
            subtitle, subtitle.get_rect(center=(col_center_x, self._point(0, 150)[1]))
        )

        # Divider line, same width as the column
        ly = self._point(0, 166)[1]
        pygame.draw.line(self.screen, (0, 110, 160), (col_left, ly), (col_right, ly), 1)

        self._draw_input(
            self.username_rect, "Username", self.username,
            self.active_field == "username",
        )
        self._draw_input(
            self.password_rect, "Password", "•" * len(self.password),
            self.active_field == "password",
        )
        self._draw_input(
            self.confirm_rect, "Confirm Password", "•" * len(self.confirm_password),
            self.active_field == "confirm",
        )

        self._draw_button(self.register_button, "CREATE ACCOUNT", primary=True)
        self._draw_button(self.back_button, "BACK TO LOGIN", primary=False)

        # Feedback message only (no hint text)
        if self.message:
            msg = self.small_font.render(self.message.upper(), True, self.message_color)
            self.screen.blit(
                msg,
                msg.get_rect(
                    center=(col_center_x, self.screen_rect.bottom - int(14 * self.scale))
                ),
            )

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def handle_event(self, event):
        if event.type == pygame.VIDEORESIZE:
            self.width, self.height = event.w, event.h
            self.recalculate_layout()
            self.resize_background(event.w, event.h)
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.username_rect.collidepoint(event.pos):
                self.active_field = "username"
            elif self.password_rect.collidepoint(event.pos):
                self.active_field = "password"
            elif self.confirm_rect.collidepoint(event.pos):
                self.active_field = "confirm"
            elif self.register_button.collidepoint(event.pos):
                return self.do_register()
            elif self.back_button.collidepoint(event.pos):
                return "login"

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                i = self.fields.index(self.active_field)
                self.active_field = self.fields[(i + 1) % len(self.fields)]
            elif event.key == pygame.K_ESCAPE:
                return "login"
            elif event.key == pygame.K_BACKSPACE:
                if self.active_field == "username":
                    self.username = self.username[:-1]
                elif self.active_field == "password":
                    self.password = self.password[:-1]
                else:
                    self.confirm_password = self.confirm_password[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self.do_register()
            elif event.unicode and event.unicode.isprintable():
                if self.active_field == "username":
                    if len(self.username) < 20:
                        self.username += event.unicode
                elif self.active_field == "password":
                    if len(self.password) < 30:
                        self.password += event.unicode
                else:
                    if len(self.confirm_password) < 30:
                        self.confirm_password += event.unicode

        return None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def do_register(self):
        if (
            not self.username.strip()
            or not self.password
            or not self.confirm_password
        ):
            self.message = "ALL FIELDS ARE REQUIRED"
            self.message_color = (255, 105, 115)
            return None

        success, message = register(
            self.username.strip(), self.password, self.confirm_password
        )
        self.message = message

        if success:
            self.message_color = (80, 255, 165)
            return "login"

        self.message_color = (255, 100, 110)
        return None
