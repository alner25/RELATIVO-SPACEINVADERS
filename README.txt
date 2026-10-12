SPACE INVADERS - FINAL COMPATIBLE BUILD

1. Install Python 3.12+ (Python 3.14 is also supported by pygame-ce if available).
2. Open this folder in VS Code.
3. Create/activate a virtual environment:
   python -m venv venv
   .\venv\Scripts\activate
4. Install packages:
   pip install -r requirements.txt
5. Open XAMPP and START MySQL.
6. Run:
   python main.py

The database name is space_invaders_relativo.
The program automatically creates the database and required tables.
Existing players/scores are preserved; an avatar column is added automatically.

Main compatibility fixes:
- login() always returns (player, message)
- profile DB functions are present
- leaderboard DB function is present
- avatar storage is supported
- MySQL database is created automatically
- main.py passes gameplay events to GameManager.update(events)
- no call is made to a nonexistent GameManager.handle_event()
- Enemy.get_rect() exists in the supplied Enemy class
