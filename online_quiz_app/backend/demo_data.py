"""
BACKEND LAYER  -  backend/demo_data.py

Creates the demo admin, faculty, student and the sample "Python Basics" quiz the first
time the app runs (only when the users table is empty).
"""
from backend.users import User


def seed_demo_data(db):
    if db.fetch_one("SELECT 1 AS x FROM users LIMIT 1"):
        return
    User.register(db, "System Admin", "admin@quiz.com", "admin123", "Admin")
    User.register(db, "Demo Faculty", "faculty@quiz.com", "faculty123", "Faculty",
                  department="Computer Science", designation="Assistant Professor")
    User.register(db, "Demo Student", "student@quiz.com", "student123", "Student",
                  roll_no="CS001", class_grade="B.Tech 2nd Year")
    faculty = User.authenticate(db, "faculty@quiz.com", "faculty123")
    quiz = faculty.create_quiz("Python Basics", "Programming", "Python",
                               "Fundamentals of Python.", "Easy", 10)
    bank = [
        ("Which keyword defines a function in Python?", "Functions",
         ["def", "func", "define", "lambda"], 0),
        ("What is the output of len([1, 2, 3])?", "Lists", ["2", "3", "4", "Error"], 1),
        ("Which of these is immutable?", "Data Types", ["list", "dict", "tuple", "set"], 2),
        ("Which keyword is used to handle exceptions?", "Exceptions",
         ["catch", "try", "handle", "error"], 1),
        ("Inheritance lets a class...", "OOP",
         ["hide data", "reuse another class's members", "run faster", "open files"], 1),
    ]
    for text, topic, opts, correct in bank:
        faculty.add_question(quiz.quiz_id, text, "MCQ", topic, 1,
                             [(o, i == correct) for i, o in enumerate(opts)])
    faculty.publish_quiz(quiz.quiz_id)
