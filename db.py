"""MySQL database layer for the Space Invaders project.

Requires XAMPP/MariaDB/MySQL to be running.  The database itself and all
required tables are created/migrated automatically.
"""

import hashlib
from typing import Any

import mysql.connector
from mysql.connector import Error

DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = ""
DB_NAME = "space_invaders_relativo"

AVATARS = {
    "astronaut", "alien", "robot", "pilot",
    "commander", "galaxy", "gamer", "explorer",
}


def _connect_server():
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
        )
    except Error as exc:
        print("MySQL server connection error:", exc)
        return None


def get_connection():
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
        )
    except Error as exc:
        print("Database connection error:", exc)
        return None


def hash_password(password):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def _table_columns(connection, table):
    cursor = connection.cursor()
    try:
        cursor.execute(f"SHOW COLUMNS FROM `{table}`")
        return {row[0] for row in cursor.fetchall()}
    finally:
        cursor.close()


def get_players_id_column(connection):
    try:
        columns = _table_columns(connection, "players")
    except Error:
        return None
    if "id" in columns:
        return "id"
    if "player_id" in columns:
        return "player_id"
    return None


def initialize_database():
    """Create the database/tables and migrate old installations."""
    server = _connect_server()
    if server is None:
        return False

    try:
        cursor = server.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        server.commit()
        cursor.close()
    except Error as exc:
        print("Could not create database:", exc)
        try:
            server.close()
        except Exception:
            pass
        return False
    finally:
        try:
            server.close()
        except Exception:
            pass

    connection = get_connection()
    if connection is None:
        return False

    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INT AUTO_INCREMENT PRIMARY KEY,
                player_name VARCHAR(100) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                avatar VARCHAR(30) NOT NULL DEFAULT 'astronaut',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)
        connection.commit()
        cursor.close()

        # Migrate an older players table that did not have avatar.
        columns = _table_columns(connection, "players")
        if "avatar" not in columns:
            cursor = connection.cursor()
            cursor.execute(
                "ALTER TABLE players ADD COLUMN avatar VARCHAR(30) "
                "NOT NULL DEFAULT 'astronaut'"
            )
            connection.commit()
            cursor.close()

        player_id_column = get_players_id_column(connection)
        if player_id_column is None:
            print("Database error: players table has no ID column.")
            return False

        cursor = connection.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS scores (
                id INT AUTO_INCREMENT PRIMARY KEY,
                player_id INT NOT NULL,
                score INT NOT NULL DEFAULT 0,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_scores_player (player_id),
                INDEX idx_scores_score (score),
                CONSTRAINT fk_scores_player
                    FOREIGN KEY (player_id)
                    REFERENCES players(`{player_id_column}`)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
            ) ENGINE=InnoDB
        """)
        connection.commit()
        cursor.close()
        print("Database initialized:", DB_NAME)
        return True
    except Error as exc:
        print("Database initialization error:", exc)
        return False
    finally:
        try:
            connection.close()
        except Exception:
            pass


def register_player(player_name, password):
    name = str(player_name or "").strip()
    if not name:
        return False, "Username cannot be empty."

    connection = get_connection()
    if connection is None:
        return False, "Database connection failed. Start MySQL in XAMPP."

    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT 1 FROM players WHERE player_name = %s LIMIT 1",
            (name,),
        )
        if cursor.fetchone():
            cursor.close()
            return False, "Username already exists."

        cursor.execute(
            "INSERT INTO players (player_name, password_hash, avatar) "
            "VALUES (%s, %s, %s)",
            (name, hash_password(password), "astronaut"),
        )
        connection.commit()
        cursor.close()
        return True, "Registration successful."
    except Error as exc:
        print("Registration error:", exc)
        try:
            connection.rollback()
        except Exception:
            pass
        return False, "Registration failed. Check the database."
    finally:
        connection.close()


def login_player(player_name, password):
    name = str(player_name or "").strip()
    connection = get_connection()
    if connection is None:
        return None, "Database connection failed. Start MySQL in XAMPP."

    try:
        player_id_column = get_players_id_column(connection)
        if player_id_column is None:
            return None, "Players table has no ID column."

        columns = _table_columns(connection, "players")
        avatar_sql = "avatar" if "avatar" in columns else "NULL"
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT `{player_id_column}`, player_name, {avatar_sql} "
            "FROM players WHERE player_name = %s AND password_hash = %s",
            (name, hash_password(password)),
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None, "Invalid username or password."

        avatar = row[2] if row[2] in AVATARS else "astronaut"
        player = {
            "id": row[0],
            "player_id": row[0],
            "player_name": row[1],
            "username": row[1],
            "avatar": avatar,
        }
        return player, "Login successful."
    except Error as exc:
        print("Login error:", exc)
        return None, "Login failed. Check the database."
    finally:
        connection.close()


def add_player(player_name):
    connection = get_connection()
    if connection is None:
        return None
    try:
        pid_col = get_players_id_column(connection)
        if not pid_col:
            return None
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT `{pid_col}` FROM players WHERE player_name = %s",
            (str(player_name).strip(),),
        )
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else None
    except Error as exc:
        print("add_player error:", exc)
        return None
    finally:
        connection.close()


def save_score(player_id, score):
    if player_id is None:
        return False
    connection = get_connection()
    if connection is None:
        return False
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO scores (player_id, score) VALUES (%s, %s)",
            (int(player_id), max(0, int(score))),
        )
        connection.commit()
        cursor.close()
        return True
    except (Error, ValueError) as exc:
        print("save_score error:", exc)
        try:
            connection.rollback()
        except Exception:
            pass
        return False
    finally:
        connection.close()


def get_high_scores(limit=10):
    connection = get_connection()
    if connection is None:
        return []
    try:
        pid_col = get_players_id_column(connection)
        if not pid_col:
            return []
        limit = max(1, min(100, int(limit)))
        cursor = connection.cursor()
        cursor.execute(f"""
            SELECT p.player_name, s.score, s.played_at
            FROM scores s
            JOIN players p ON s.player_id = p.`{pid_col}`
            ORDER BY s.score DESC, s.played_at ASC
            LIMIT {limit}
        """)
        rows = cursor.fetchall()
        cursor.close()
        return rows
    except (Error, ValueError) as exc:
        print("get_high_scores error:", exc)
        return []
    finally:
        connection.close()


def _resolve_player_id(connection, player_ref):
    if player_ref is None:
        return None
    try:
        if isinstance(player_ref, int) or str(player_ref).isdigit():
            return int(player_ref)
    except Exception:
        pass
    pid_col = get_players_id_column(connection)
    if not pid_col:
        return None
    cursor = connection.cursor()
    cursor.execute(
        f"SELECT `{pid_col}` FROM players WHERE player_name = %s",
        (str(player_ref),),
    )
    row = cursor.fetchone()
    cursor.close()
    return row[0] if row else None


def get_player(player_ref):
    connection = get_connection()
    if connection is None:
        return None
    try:
        pid_col = get_players_id_column(connection)
        if not pid_col:
            return None
        columns = _table_columns(connection, "players")
        avatar_sql = "avatar" if "avatar" in columns else "NULL"
        pid = _resolve_player_id(connection, player_ref)
        if pid is None:
            return None
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT `{pid_col}`, player_name, {avatar_sql}, created_at "
            "FROM players WHERE " + f"`{pid_col}` = %s",
            (pid,),
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        avatar = row[2] if row[2] in AVATARS else "astronaut"
        return {
            "id": row[0],
            "player_id": row[0],
            "player_name": row[1],
            "username": row[1],
            "avatar": avatar,
            "created_at": row[3],
        }
    except Error as exc:
        print("get_player error:", exc)
        return None
    finally:
        connection.close()


def get_player_scores(player_ref):
    connection = get_connection()
    if connection is None:
        return []
    try:
        pid_col = get_players_id_column(connection)
        if not pid_col:
            return []
        pid = _resolve_player_id(connection, player_ref)
        if pid is None:
            return []
        cursor = connection.cursor()
        cursor.execute(
            "SELECT score, played_at FROM scores "
            "WHERE player_id = %s ORDER BY score DESC, played_at DESC",
            (pid,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    except Error as exc:
        print("get_player_scores error:", exc)
        return []
    finally:
        connection.close()


def get_player_high_score(player_ref):
    scores = get_player_scores(player_ref)
    if not scores:
        return 0
    try:
        return max(int(row[0]) for row in scores)
    except Exception:
        return 0


def get_leaderboard(limit=50):
    connection = get_connection()
    if connection is None:
        return []
    try:
        pid_col = get_players_id_column(connection)
        if not pid_col:
            return []
        limit = max(1, min(200, int(limit)))
        columns = _table_columns(connection, "players")
        avatar_sql = "p.avatar" if "avatar" in columns else "'astronaut'"
        cursor = connection.cursor(dictionary=True)
        cursor.execute(f"""
            SELECT
                p.`{pid_col}` AS player_id,
                p.player_name AS player_name,
                {avatar_sql} AS avatar,
                MAX(s.score) AS score,
                COUNT(s.id) AS games_played
            FROM players p
            JOIN scores s ON s.player_id = p.`{pid_col}`
            GROUP BY p.`{pid_col}`, p.player_name, {avatar_sql}
            ORDER BY score DESC, games_played ASC, p.player_name ASC
            LIMIT {limit}
        """)
        rows = cursor.fetchall()
        cursor.close()
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
            if row.get("avatar") not in AVATARS:
                row["avatar"] = "astronaut"
        return rows
    except (Error, ValueError) as exc:
        print("get_leaderboard error:", exc)
        return []
    finally:
        connection.close()


def update_player_profile(player_id, new_username, new_password=None, avatar="astronaut"):
    connection = get_connection()
    if connection is None:
        return False
    try:
        pid_col = get_players_id_column(connection)
        if not pid_col:
            return False
        name = str(new_username or "").strip()
        if not name:
            return False
        avatar = avatar if avatar in AVATARS else "astronaut"
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT 1 FROM players WHERE player_name = %s AND `{pid_col}` != %s",
            (name, player_id),
        )
        if cursor.fetchone():
            cursor.close()
            return False

        if new_password:
            cursor.execute(
                f"UPDATE players SET player_name=%s, password_hash=%s, avatar=%s "
                f"WHERE `{pid_col}`=%s",
                (name, hash_password(new_password), avatar, player_id),
            )
        else:
            cursor.execute(
                f"UPDATE players SET player_name=%s, avatar=%s "
                f"WHERE `{pid_col}`=%s",
                (name, avatar, player_id),
            )
        if cursor.rowcount == 0:
            cursor.close()
            return False
        connection.commit()
        cursor.close()
        return True
    except Error as exc:
        print("update_player_profile error:", exc)
        try:
            connection.rollback()
        except Exception:
            pass
        return False
    finally:
        connection.close()


def delete_player(player_id):
    connection = get_connection()
    if connection is None:
        return False
    try:
        pid_col = get_players_id_column(connection)
        if not pid_col:
            return False
        cursor = connection.cursor()
        cursor.execute(
            f"DELETE FROM players WHERE `{pid_col}` = %s",
            (player_id,),
        )
        deleted = cursor.rowcount > 0
        connection.commit()
        cursor.close()
        return deleted
    except Error as exc:
        print("delete_player error:", exc)
        try:
            connection.rollback()
        except Exception:
            pass
        return False
    finally:
        connection.close()


# Compatibility alias used by older code.
def login(player_name, password):
    return login_player(player_name, password)


if __name__ == "__main__":
    print("Database ready:", initialize_database())
