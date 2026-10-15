
import sys
import asyncio
import pygame

from audio import initialize_audio, play_button, unlock_audio
from db import initialize_database
from screens.login import LoginScreen
from screens.register import RegisterScreen
from screens.menu import MenuScreen
from screens.profile import ProfileScreen
from screens.leaderboard import LeaderboardScreen
from screens.settings import SettingsScreen
from managers.game_manager import GameManager

IS_WEB = sys.platform == "emscripten"

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
MIN_WIDTH, MIN_HEIGHT = 600, 500

pygame.init()

try:
    initialize_audio()
except Exception as exc:
    print(f"[AUDIO] Initialization skipped: {exc}")

pygame.display.set_caption("Space Invaders by Relativo, Alner A.")

screen = pygame.display.set_mode(
    (SCREEN_WIDTH, SCREEN_HEIGHT),
    pygame.RESIZABLE
)
clock = pygame.time.Clock()

# MySQL is only used on desktop.
if not IS_WEB:
    try:
        initialize_database()
    except Exception as exc:
        print(f"[DATABASE] Initialization failed: {exc}")

player = (
    {
        "player_id": None,
        "id": None,
        "player_name": "GUEST",
        "username": "GUEST",
        "avatar": "astronaut",
    }
    if IS_WEB else None
)

state = "menu" if IS_WEB else "login"

login_screen = None
register_screen = None
menu_screen = None
profile_screen = None
leaderboard_screen = None
settings_screen = None
game_manager = None


def get_player_id():
    return (player or {}).get("player_id") or (player or {}).get("id")


def get_player_name():
    return (
        (player or {}).get("player_name")
        or (player or {}).get("username")
        or "PLAYER"
    )


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
    menu_screen = MenuScreen(
        screen, SCREEN_WIDTH, SCREEN_HEIGHT, player
    )


def create_profile():
    global profile_screen
    update_size()
    profile_screen = ProfileScreen(
        screen, SCREEN_WIDTH, SCREEN_HEIGHT, player
    )


def create_leaderboard():
    global leaderboard_screen
    update_size()
    leaderboard_screen = LeaderboardScreen(
        screen, SCREEN_WIDTH, SCREEN_HEIGHT, player
    )


def create_settings():
    global settings_screen
    update_size()
    settings_screen = SettingsScreen(
        screen, SCREEN_WIDTH, SCREEN_HEIGHT
    )


def create_game():
    global game_manager
    update_size()
    game_manager = GameManager(
        screen,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        get_player_id(),
        get_player_name()
    )


def update_screen(screen_obj, dt):
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

    screen = pygame.display.set_mode(
        (SCREEN_WIDTH, SCREEN_HEIGHT),
        pygame.RESIZABLE
    )

    if state == "login":
        create_login()
    elif state == "register":
        create_register()
    elif state == "menu":
        create_menu()
    elif state == "profile":
        create_profile()
    elif state == "leaderboard":
        create_leaderboard()
    elif state == "settings":
        create_settings()
    elif state == "game":
        create_game()


def handle_event(event):
    global state, player, running

    if event.type == pygame.QUIT:
        running = False
        return

    if event.type == pygame.VIDEORESIZE:
        resize(event)
        return

    # Audio errors should never stop game input.
    if event.type == pygame.MOUSEBUTTONDOWN:
        if getattr(event, "button", None) == 1:
            try:
                unlock_audio()
                play_button()
            except Exception as exc:
                print(f"[AUDIO] Click audio unavailable: {exc}")

    elif event.type == pygame.KEYDOWN:
        try:
            unlock_audio()
        except Exception as exc:
            print(f"[AUDIO] Audio unlock unavailable: {exc}")

    if state == "login" and login_screen:
        result = login_screen.handle_event(event)

        if result == "register":
            create_register()
            state = "register"
        elif isinstance(result, dict):
            player = result
            create_menu()
            state = "menu"

    elif state == "register" and register_screen:
        result = register_screen.handle_event(event)

        if result == "login":
            create_login()
            state = "login"
        elif isinstance(result, dict):
            player = result
            create_menu()
            state = "menu"

    elif state == "menu" and menu_screen:
        result = menu_screen.handle_event(event)

        if result == "game":
            create_game()
            state = "game"
        elif result == "profile":
            create_profile()
            state = "profile"
        elif result == "leaderboard":
            create_leaderboard()
            state = "leaderboard"
        elif result == "settings":
            create_settings()
            state = "settings"
        elif result == "logout":
            if IS_WEB:
                # Guests stay in guest mode in the browser.
                player = {
                    "player_id": None,
                    "id": None,
                    "player_name": "GUEST",
                    "username": "GUEST",
                    "avatar": "astronaut",
                }
                create_menu()
                state = "menu"
            else:
                logout()
        elif result == "quit":
            running = False

    elif state == "profile" and profile_screen:
        result = profile_screen.handle_event(event)

        if isinstance(result, dict):
            player = result
        elif result in ("back", "menu"):
            create_menu()
            state = "menu"
        elif result == "logout":
            logout()

    elif state == "leaderboard" and leaderboard_screen:
        result = leaderboard_screen.handle_event(event)

        if result in ("back", "menu"):
            create_menu()
            state = "menu"

    elif state == "settings" and settings_screen:
        result = settings_screen.handle_event(event)

        if result in ("back", "menu"):
            create_menu()
            state = "menu"


def update_and_draw(dt, events):
    global state, running

    if state == "login" and login_screen:
        update_screen(login_screen, dt)
        login_screen.draw()

    elif state == "register" and register_screen:
        update_screen(register_screen, dt)
        register_screen.draw()

    elif state == "menu" and menu_screen:
        update_screen(menu_screen, dt)
        menu_screen.draw()

    elif state == "profile" and profile_screen:
        update_screen(profile_screen, dt)
        profile_screen.draw()

    elif state == "leaderboard" and leaderboard_screen:
        update_screen(leaderboard_screen, dt)
        leaderboard_screen.draw()

    elif state == "settings" and settings_screen:
        update_screen(settings_screen, dt)
        settings_screen.draw()

    elif state == "game" and game_manager:
        result = game_manager.update(events)

        if result == "menu":
            create_menu()
            state = "menu"
        elif result == "quit":
            running = False

        if state == "game" and game_manager:
            game_manager.draw()
        elif state == "menu" and menu_screen:
            menu_screen.draw()

    pygame.display.flip()


async def main():
    global running

    if IS_WEB:
        create_menu()
    else:
        create_login()

    running = True

    while running:
        events = pygame.event.get()

        for event in events:
            handle_event(event)

        dt = min(clock.tick(60) / 1000.0, 0.1)
        update_and_draw(dt, events)

        # Let the browser event loop run; important for Pygbag.
        await asyncio.sleep(0)

    pygame.quit()


asyncio.run(main())
