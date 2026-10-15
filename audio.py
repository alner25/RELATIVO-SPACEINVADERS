```python
import os
import pygame

AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets",
    "audio"
)

BUTTON_SOUND_PATH = os.path.join(AUDIO_DIR, "button_click.wav")
SHOOT_SOUND_PATH = os.path.join(AUDIO_DIR, "shoot.wav")
BULLET_FIRE_SOUND_PATH = os.path.join(AUDIO_DIR, "bullet_fire.wav")
ENEMY_BULLET_SOUND_PATH = os.path.join(AUDIO_DIR, "enemy_bullet.wav")
EXPLOSION_SOUND_PATH = os.path.join(AUDIO_DIR, "explosion.wav")
HIT_SOUND_PATH = os.path.join(AUDIO_DIR, "hit.wav")
BOSS_SOUND_PATH = os.path.join(AUDIO_DIR, "boss.wav")
BACKGROUND_MUSIC_PATH = os.path.join(
    AUDIO_DIR, "background_music1.ogg"
)

_enabled = False
_initialized = False
_music_started = False

_music_volume = 0.28
_sfx_volume = 0.55
_sounds = {}

_SOUND_FILES = {
    "button": BUTTON_SOUND_PATH,
    "shoot": SHOOT_SOUND_PATH,
    "bullet_fire": BULLET_FIRE_SOUND_PATH,
    "enemy_bullet": ENEMY_BULLET_SOUND_PATH,
    "explosion": EXPLOSION_SOUND_PATH,
    "hit": HIT_SOUND_PATH,
    "boss": BOSS_SOUND_PATH,
}


def initialize_audio():
    """Load available sounds without requiring audio to run the game."""
    global _enabled, _initialized

    if _initialized and _enabled:
        return True

    try:
        if not pygame.get_init():
            pygame.init()

        if not pygame.mixer.get_init():
            pygame.mixer.init(
                frequency=44100,
                size=-16,
                channels=2,
                buffer=512
            )

        _sounds.clear()

        for name, path in _SOUND_FILES.items():
            if not os.path.isfile(path):
                print(f"[AUDIO] Missing sound: {path}")
                continue

            try:
                sound = pygame.mixer.Sound(path)
                sound.set_volume(_sfx_volume)
                _sounds[name] = sound
            except (pygame.error, OSError) as exc:
                print(f"[AUDIO] Could not load {name}: {exc}")

        _enabled = True
        _initialized = True
        print("[AUDIO] Initialized successfully.")
        return True

    except (pygame.error, OSError, RuntimeError) as exc:
        _enabled = False
        _initialized = False
        print(f"[AUDIO] Unavailable; continuing without sound: {exc}")
        return False


def unlock_audio():
    """Start music after a player interaction when supported."""
    global _music_started

    if not _enabled and not initialize_audio():
        return False

    try:
        if not pygame.mixer.get_init():
            _enabled = False
            return False

        if not _music_started:
            if not os.path.isfile(BACKGROUND_MUSIC_PATH):
                print("[AUDIO] Background music file not found.")
                return False

            pygame.mixer.music.load(BACKGROUND_MUSIC_PATH)
            pygame.mixer.music.set_volume(_music_volume)
            pygame.mixer.music.play(-1)
            _music_started = True

        return True

    except (pygame.error, OSError, RuntimeError) as exc:
        print(f"[AUDIO] Could not start music: {exc}")
        return False


def play(name):
    if not _enabled:
        return

    sound = _sounds.get(name)
    if sound is None:
        return

    try:
        sound.play()
    except (pygame.error, RuntimeError) as exc:
        print(f"[AUDIO] Could not play {name}: {exc}")


def play_button():
    play("button")


def play_shoot():
    play("shoot")


def play_bullet_fire():
    play("bullet_fire")


def play_enemy_bullet():
    play("enemy_bullet")


def play_explosion():
    play("explosion")


def play_hit():
    play("hit")


def play_boss():
    play("boss")


def set_music_volume(value):
    global _music_volume

    try:
        _music_volume = max(0.0, min(1.0, float(value)))
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(_music_volume)
    except (pygame.error, ValueError, TypeError, RuntimeError):
        pass


def set_sfx_volume(value):
    global _sfx_volume

    try:
        _sfx_volume = max(0.0, min(1.0, float(value)))
        for sound in _sounds.values():
            sound.set_volume(_sfx_volume)
    except (pygame.error, ValueError, TypeError, RuntimeError):
        pass


def stop_music():
    global _music_started

    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except (pygame.error, RuntimeError):
        pass

    _music_started = False


def pause_music():
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.pause()
    except (pygame.error, RuntimeError):
        pass


def resume_music():
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.unpause()
    except (pygame.error, RuntimeError):
        pass


def audio_available():
    try:
        return _enabled and pygame.mixer.get_init() is not None
    except (pygame.error, RuntimeError):
        return False
```
