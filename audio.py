```python
import os
import pygame

# ============================================================
# AUDIO PATHS
# ============================================================

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

# ============================================================
# AUDIO SETTINGS
# ============================================================

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


# ============================================================
# INITIALIZE AUDIO
# ============================================================

def initialize_audio():
    """
    Initialize the mixer and load audio assets.

    Background music is deliberately NOT started here.
    Call unlock_audio() after a player interaction.
    """

    global _enabled, _initialized

    if _initialized:
        return _enabled

    _initialized = True
    _enabled = False

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
        print("[AUDIO] Audio system initialized.")

    except (pygame.error, OSError, RuntimeError) as exc:
        print(f"[AUDIO] Audio unavailable: {exc}")
        _enabled = False

    return _enabled


# ============================================================
# ENABLE AUDIO AFTER PLAYER INTERACTION
# ============================================================

def unlock_audio():
    """
    Call this after a mouse click or keyboard input.

    This also starts background music when audio is available.
    """

    global _enabled, _music_started

    if not _initialized:
        initialize_audio()

    if not _enabled:
        return False

    try:
        if not pygame.mixer.get_init():
            return False

        if not _music_started:
            if os.path.isfile(BACKGROUND_MUSIC_PATH):
                pygame.mixer.music.load(BACKGROUND_MUSIC_PATH)
                pygame.mixer.music.set_volume(_music_volume)
                pygame.mixer.music.play(-1)

            _music_started = True

        return True

    except (pygame.error, OSError, RuntimeError) as exc:
        print(f"[AUDIO] Music could not start: {exc}")
        return False


# ============================================================
# PLAY SOUND EFFECTS
# ============================================================

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


# ============================================================
# VOLUME CONTROLS
# ============================================================

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


# ============================================================
# MUSIC CONTROLS
# ============================================================

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
    return _enabled and pygame.mixer.get_init() is not None
```
