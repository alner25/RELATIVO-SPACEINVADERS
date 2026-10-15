
def unlock_audio():
    """Start music after a player interaction when supported."""
    global _enabled, _music_started

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
