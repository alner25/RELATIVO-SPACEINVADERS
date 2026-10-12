import pygame


class MobileButtons:
    def __init__(self):
        self.left = pygame.Rect(20, 520, 80, 60)
        self.right = pygame.Rect(120, 520, 80, 60)
        self.fire = pygame.Rect(680, 520, 100, 60)

    def draw(self, screen):
        # Position is recalculated by GameManager for the common 800x600 layout.
        for rect, color, label in (
            (self.left, (35, 45, 52), "<"),
            (self.right, (35, 45, 52), ">"),
            (self.fire, (90, 45, 45), "FIRE"),
        ):
            pygame.draw.rect(screen, color, rect, border_radius=8)
            pygame.draw.rect(screen, (105, 120, 125), rect, 1, border_radius=8)
            font = pygame.font.SysFont("Arial", 18, bold=True)
            text = font.render(label, True, (235, 240, 245))
            screen.blit(text, text.get_rect(center=rect.center))

    def handle_mouse(self, player, events):
        mouse_pos = pygame.mouse.get_pos()
        if pygame.mouse.get_pressed()[0]:
            if self.left.collidepoint(mouse_pos):
                player.move_left()
            elif self.right.collidepoint(mouse_pos):
                player.move_right()

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.fire.collidepoint(event.pos):
                    return True
        return False
