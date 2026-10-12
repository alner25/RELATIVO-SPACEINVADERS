"""Authentication helpers used by the Pygame screens."""

from db import login_player, register_player


def login(username, password):
    username = str(username or "").strip()
    password = str(password or "")

    if not username:
        return None, "Please enter your username."
    if not password:
        return None, "Please enter your password."

    try:
        result = login_player(username, password)
    except Exception as exc:
        return None, f"Login error: {exc}"

    # Always normalize the result to (player, message).
    if not isinstance(result, tuple) or len(result) != 2:
        return None, "Login failed: invalid authentication response."

    player, message = result
    return player, str(message or "Login failed.")


def register(username, password, confirm_password):
    username = str(username or "").strip()
    password = str(password or "")
    confirm_password = str(confirm_password or "")

    if not username:
        return False, "Please enter a username."
    if not password:
        return False, "Please enter a password."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(username) > 100:
        return False, "Username is too long."
    if len(password) < 4:
        return False, "Password must be at least 4 characters."
    if password != confirm_password:
        return False, "Passwords do not match."

    try:
        result = register_player(username, password)
    except Exception as exc:
        return False, f"Registration error: {exc}"

    if not isinstance(result, tuple) or len(result) != 2:
        return False, "Registration failed: invalid database response."

    return bool(result[0]), str(result[1] or "Registration failed.")
