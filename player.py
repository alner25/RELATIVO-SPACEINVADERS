import pygame

class Player:
    def __init__(self, screen_width, screen_height):
        self.width, self.height = 80, 80
        self.speed = 6
        self.max_health = 5
        self.health = self.max_health
        try:
            image = pygame.image.load("assets/images/ship.png").convert_alpha()
            self.image = pygame.transform.scale(image, (self.width, self.height))
        except (pygame.error, FileNotFoundError):
            self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.polygon(self.image, (170,190,205), [(40,2),(78,68),(58,60),(40,76),(22,60),(2,68)])
        self.x = screen_width // 2 - self.width // 2
        self.y = screen_height - 100
        self.screen_width, self.screen_height = screen_width, screen_height
        self.is_blinking = False
        self.blink_timer = 0
        self.visible = True

    def move_left(self):
        if not self.is_blinking: self.x -= self.speed
    def move_right(self):
        if not self.is_blinking: self.x += self.speed
    def keep_inside_screen(self):
        self.x = max(0, min(self.x, self.screen_width-self.width))
    def get_rect(self): return pygame.Rect(int(self.x), int(self.y), self.width, self.height)
    def take_damage(self, amount=1):
        if self.is_blinking: return False
        self.health = max(0, self.health - amount)
        return self.health <= 0
    def restore_health(self): self.health = self.max_health
    def update_blink(self):
        if self.is_blinking:
            self.blink_timer += 1
            if self.blink_timer % 8 == 0: self.visible = not self.visible
        else: self.visible = True
    def draw(self, screen):
        if self.visible: screen.blit(self.image, (int(self.x), int(self.y)))
