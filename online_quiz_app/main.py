"""
Online Quiz Application with Score Analysis and Database Integration
Alliance School of Advanced Computing - Micro-Project (Group G_06)

Run:   python main.py

Layers
  frontend/  Tkinter screens (what the user sees)
  backend/   OOP classes and business rules (what the app does)
  database/  SQLite access (where the data is stored)

Demo logins (created on first run)
  Admin   : admin@quiz.com    / admin123
  Faculty : faculty@quiz.com  / faculty123
  Student : student@quiz.com  / student123
"""
import os

from backend.demo_data import seed_demo_data
from database.db_manager import DatabaseManager
from exceptions import QuizAppError
from frontend.app import QuizGUI

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quiz_app.db")


def main():
    db = DatabaseManager(DB_FILE)
    try:
        db.connect()
        db.create_tables()
        seed_demo_data(db)
    except QuizAppError as exc:
        print(f"Startup failed: {exc}")
        return
    try:
        QuizGUI(db).run()
    finally:
        db.close()


if __name__ == "__main__":
    main()
