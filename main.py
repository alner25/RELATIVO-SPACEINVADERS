import sys
import pygame
from audio import initialize_audio, play_button

from db import initialize_database
from screens.login import LoginScreen
from screens.register import RegisterScreen
from screens.menu import MenuScreen
from screens.profile import ProfileScreen
from screens.leaderboard import LeaderboardScreen
from screens.settings import SettingsScreen
from managers.game_manager import GameManager

pygame.init()
initialize_audio()
pygame.display.set_caption("Space Invaders by Relativo, Alner A.")

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
MIN_WIDTH, MIN_HEIGHT = 600, 500
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
clock = pygame.time.Clock()

# Initialize database before opening the login screen.
initialize_database()

state = "login"
player = None
login_screen = register_screen = menu_screen = None
profile_screen = leaderboard_screen = settings_screen = None
game_manager = None


def player_id():
    return (player or {}).get("player_id") or (player or {}).get("id")


def player_name():
    return (player or {}).get("player_name") or (player or {}).get("username") or "PLAYER"


def update_size():
    global SCREEN_WIDTH, SCREEN_HEIGHT, screen
    screen = pygame.display.get_surface() or screen
    SCREEN_WIDTH, SCREEN_HEIGHT = screen.get_size()


def create_login():
    global login_screen
    update_size()
    login_screen = LoginScreen(screen, SCREEN_WIDTH, SCREEN_HEIGHT)


def create_register():
    global register_screen
    update_size()
    register_screen = RegisterScreen(screen, SCREEN_WIDTH, SCREEN_HEIGHT)


def create_menu():
    global menu_screen
    update_size()
    menu_screen = MenuScreen(screen, SCREEN_WIDTH, SCREEN_HEIGHT, player)


def create_profile():
    global profile_screen
    update_size()
    profile_screen = ProfileScreen(screen, SCREEN_WIDTH, SCREEN_HEIGHT, player)


def create_leaderboard():
    global leaderboard_screen
    update_size()
    leaderboard_screen = LeaderboardScreen(screen, SCREEN_WIDTH, SCREEN_HEIGHT, player)


def create_settings():
    global settings_screen
    update_size()
    settings_screen = SettingsScreen(screen, SCREEN_WIDTH, SCREEN_HEIGHT)


def create_game():
    global game_manager
    update_size()
    game_manager = GameManager(screen, SCREEN_WIDTH, SCREEN_HEIGHT, player_id(), player_name())


def update_screen(screen_obj, dt):
    """Call a screen's optional per-frame update hook safely."""
    method = getattr(screen_obj, "update", None)
    if callable(method):
        method(dt)

def logout():
    global player, state, profile_screen, leaderboard_screen
    player = None
    profile_screen = None
    leaderboard_screen = None
    create_login()
    state = "login"


def resize(event):
    global screen, SCREEN_WIDTH, SCREEN_HEIGHT
    SCREEN_WIDTH = max(MIN_WIDTH, event.w)
    SCREEN_HEIGHT = max(MIN_HEIGHT, event.h)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
    if state == "login": create_login()
    elif state == "register": create_register()
    elif state == "menu": create_menu()
    elif state == "profile": create_profile()
    elif state == "leaderboard": create_leaderboard()
    elif state == "settings": create_settings()
    elif state == "game": create_game()


create_login()
running = True

while running:
    events = pygame.event.get()

    for event in events:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            play_button()
        if event.type == pygame.QUIT:
            running = False
            continue
        if event.type == pygame.VIDEORESIZE:
            resize(event)
            continue

        if state == "login" and login_screen:
            result = login_screen.handle_event(event)
            if result == "register":
                create_register(); state = "register"
            elif isinstance(result, dict):
                player = result
                create_menu(); state = "menu"

        elif state == "register" and register_screen:
            result = register_screen.handle_event(event)
            if result == "login":
                create_login(); state = "login"
            elif isinstance(result, dict):
                player = result
                create_menu(); state = "menu"

        elif state == "menu" and menu_screen:
            result = menu_screen.handle_event(event)
            if result == "game": create_game(); state = "game"
            elif result == "profile": create_profile(); state = "profile"
            elif result == "leaderboard": create_leaderboard(); state = "leaderboard"
            elif result == "settings": create_settings(); state = "settings"
            elif result == "logout": logout()
            elif result == "quit": running = False

        elif state == "profile" and profile_screen:
            result = profile_screen.handle_event(event)
            if isinstance(result, dict):
                player = result
            elif result in ("back", "menu"):
                create_menu(); state = "menu"
            elif result == "logout": logout()

        elif state == "leaderboard" and leaderboard_screen:
            result = leaderboard_screen.handle_event(event)
            if result in ("back", "menu"):
                create_menu(); state = "menu"

        elif state == "settings" and settings_screen:
            result = settings_screen.handle_event(event)
            if result in ("back", "menu"):
                create_menu(); state = "menu"

    dt = min(clock.tick(60) / 1000.0, 0.1)

    if state == "login" and login_screen:
        update_screen(login_screen, dt)
    elif state == "register" and register_screen:
        update_screen(register_screen, dt)
    elif state == "menu" and menu_screen:
        update_screen(menu_screen, dt)
    elif state == "profile" and profile_screen:
        update_screen(profile_screen, dt)
    elif state == "leaderboard" and leaderboard_screen:
        update_screen(leaderboard_screen, dt)
    elif state == "settings" and settings_screen:
        update_screen(settings_screen, dt)
    elif state == "game" and game_manager:
        # GameManager owns keyboard/mouse gameplay events.
        result = game_manager.update(events)
        if result == "menu":
            create_menu(); state = "menu"
        elif result == "quit":
            running = False

    if state == "login" and login_screen: login_screen.draw()
    elif state == "register" and register_screen: register_screen.draw()
    elif state == "menu" and menu_screen: menu_screen.draw()
    elif state == "profile" and profile_screen: profile_screen.draw()
    elif state == "leaderboard" and leaderboard_screen: leaderboard_screen.draw()
    elif state == "settings" and settings_screen: settings_screen.draw()
    elif state == "game" and game_manager: game_manager.draw()

    pygame.display.flip()

pygame.quit()
sys.exit()
