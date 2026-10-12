import os
import pygame

AUDIO_DIR = os.path.join(os.path.dirname(__file__), "assets", "audio")
BUTTON_SOUND_PATH = os.path.join(AUDIO_DIR, "button_click.wav")
SHOOT_SOUND_PATH = os.path.join(AUDIO_DIR, "shoot.wav")
BULLET_FIRE_SOUND_PATH = os.path.join(AUDIO_DIR, "bullet_fire.wav")
ENEMY_BULLET_SOUND_PATH = os.path.join(AUDIO_DIR, "enemy_bullet.wav")
EXPLOSION_SOUND_PATH = os.path.join(AUDIO_DIR, "explosion.wav")
HIT_SOUND_PATH = os.path.join(AUDIO_DIR, "hit.wav")
BOSS_SOUND_PATH = os.path.join(AUDIO_DIR, "boss.wav")
BACKGROUND_MUSIC_PATH = os.path.join(AUDIO_DIR, "background_music1.ogg")

_enabled = True
_music_volume = 0.28
_sfx_volume = 0.55
_sounds = {}

def initialize_audio():
    global _enabled
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        _sounds.clear()
        paths = {
            "button": BUTTON_SOUND_PATH, "shoot": SHOOT_SOUND_PATH,
            "bullet_fire": BULLET_FIRE_SOUND_PATH, "enemy_bullet": ENEMY_BULLET_SOUND_PATH,
            "explosion": EXPLOSION_SOUND_PATH, "hit": HIT_SOUND_PATH, "boss": BOSS_SOUND_PATH
        }
        for name, path in paths.items():
            if os.path.exists(path):
                try:
                    sound = pygame.mixer.Sound(path)
                    sound.set_volume(_sfx_volume)
                    _sounds[name] = sound
                except pygame.error:
                    pass
        if os.path.exists(BACKGROUND_MUSIC_PATH):
            try:
                pygame.mixer.music.load(BACKGROUND_MUSIC_PATH)
                pygame.mixer.music.set_volume(_music_volume)
                pygame.mixer.music.play(-1)
            except pygame.error:
                pass
        _enabled = True
    except pygame.error:
        _enabled = False

def play(name):
    if not _enabled: return
    sound = _sounds.get(name)
    if sound: sound.play()

def play_button(): play("button")
def set_music_volume(value):
    global _music_volume
    _music_volume = max(0.0, min(1.0, float(value)))
    if pygame.mixer.get_init(): pygame.mixer.music.set_volume(_music_volume)
def set_sfx_volume(value):
    global _sfx_volume
    _sfx_volume = max(0.0, min(1.0, float(value)))
    for sound in _sounds.values(): sound.set_volume(_sfx_volume)
def stop_music():
    if pygame.mixer.get_init(): pygame.mixer.music.stop()
