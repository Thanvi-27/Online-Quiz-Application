# Online Quiz Application with Score Analysis and Database Integration
Alliance School of Advanced Computing, Micro-Project, Group G_06 (E1CSA348)

Python 3, Tkinter, SQLite, matplotlib (`pip install matplotlib`; tkinter and sqlite3 come with Python).

```
python main.py                          # run the app
python -m unittest tests.test_quiz_app -v   # run the 27 unit tests (from this folder)
```

Demo logins (created on first run): `admin@quiz.com / admin123`, `faculty@quiz.com / faculty123`,
`student@quiz.com / student123`.

## Project structure: three layers

```
online_quiz_app/
  main.py                  starts the app (connect DB, create tables, open GUI)
  exceptions.py            custom exceptions used by all layers

  frontend/                FRONTEND  what the user sees (Tkinter)
    app.py                   main window, login, registration, profile, shared helpers
    dialogs.py               FormDialog: one reusable pop-up form
    admin_screen.py          Admin dashboard
    faculty_screen.py        Faculty dashboard
    student_screen.py        Student dashboard
    quiz_screens.py          quiz attempt window (timer) and result screen

  backend/                 BACKEND  OOP classes and business rules
    users.py                 User (abstract), Admin, Faculty, Student
    quiz.py                  Option, Question, Quiz
    attempt.py               Answer, Attempt, Result (scoring)
    analysis.py              ScoreAnalysis (reports, trends, weak topics, chart)
    security.py              salted PBKDF2 password hashing
    demo_data.py             demo accounts and sample quiz
    utils.py                 now(), DIFFICULTIES

  database/                DATABASE  storage
    db_manager.py            DatabaseManager: the 11 tables + connect/insert/update/delete/fetch

  tests/test_quiz_app.py   27 unit tests
```

Rules between layers (checked while splitting the code):
* `frontend` calls `backend` classes only. It never runs SQL; it just hands the database object to them.
* `backend` has no Tkinter code and no `sqlite3`. It stores data only through `DatabaseManager` methods.
* `database` knows nothing about the other two layers.

## How one action travels through the layers
Student presses **Submit Quiz**:
`frontend/quiz_screens.py` calls `Attempt.submit()` in `backend/attempt.py`, which creates an `Answer` per question,
builds the `Result`, and calls `ScoreAnalysis.generate_analysis()`. All of them save rows with
`DatabaseManager.insert()/update()` in `database/db_manager.py`. The GUI then shows the result.

## Suggested viva split (swap as you like; it matches the action plan in the proposal)
| Member | Part | Files | One-line answer for the viva |
|---|---|---|---|
| Kummithi Thanvi | Backend: users and OOP design | `backend/users.py`, `backend/security.py` | Abstract `User`, three subclasses, polymorphic `show_dashboard()`, private attributes, hashed passwords |
| Allam Krishna Sahithi | Frontend | `frontend/` (all files) | One Tkinter window, one dashboard per role, every button calls a backend method |
| Kasireddy Greeshma | Database and testing | `database/db_manager.py`, `tests/` | 11 SQLite tables with foreign keys; `DatabaseManager` is the only code that touches SQL; 27 unit tests |
| Sattaru Meghana | Backend: quiz and attempt flow | `backend/quiz.py`, `backend/attempt.py` | Quiz, Question, Option rules; `Attempt.submit()` scores and stores the result |
| Kapadam Bhavana | Backend: analysis and validation | `backend/analysis.py`, `exceptions.py` | Student, quiz and overall reports, trend, weak topics, chart; custom exceptions and input validation |
