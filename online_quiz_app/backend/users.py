"""
BACKEND LAYER  -  backend/users.py   (users and roles)

Classes: User (abstract), Admin, Faculty, Student.

OOP concepts shown here:
  * Abstraction   - User is an ABC with the abstract method show_dashboard()
  * Inheritance   - Admin, Faculty and Student extend User
  * Polymorphism  - show_dashboard() does something different in each subclass
  * Encapsulation - private attributes (__user_id, __email ...) exposed via properties
  * Factory       - User.authenticate() / User.from_row() build the right subclass
"""
import re
from abc import ABC, abstractmethod

from backend.analysis import ScoreAnalysis
from backend.attempt import Attempt, Result
from backend.quiz import Question, Quiz
from backend.security import hash_password, verify_password
from backend.utils import now
from exceptions import AuthenticationError, AuthorizationError, DatabaseError, ValidationError


class User(ABC):
    def __init__(self, db, user_id, full_name, email, role, status="Active", created_at=None):
        self._db = db
        self.__user_id = user_id
        self.__full_name = full_name
        self.__email = email
        self.__role = role
        self.__status = status
        self.__created_at = created_at
        self.__logged_in = False

    # encapsulated attributes exposed read-only
    user_id = property(lambda self: self.__user_id)
    full_name = property(lambda self: self.__full_name)
    email = property(lambda self: self.__email)
    role = property(lambda self: self.__role)
    status = property(lambda self: self.__status)

    def login(self):
        self.__logged_in = self.__status == "Active"
        return self.__logged_in

    def logout(self):
        self.__logged_in = False

    def update_profile(self, full_name, email):
        full_name, email = full_name.strip(), email.strip().lower()
        if not full_name:
            raise ValidationError("Name cannot be empty.")
        User.validate_email(email)
        clash = self._db.fetch_one("SELECT user_id FROM users WHERE email = ? AND user_id != ?",
                                   (email, self.__user_id))
        if clash:
            raise ValidationError("That email is already in use.")
        self._db.update("users", {"full_name": full_name, "email": email},
                        "user_id = ?", (self.__user_id,))
        self.__full_name, self.__email = full_name, email

    def change_password(self, old_password, new_password):
        row = self._db.fetch_one("SELECT password_hash FROM users WHERE user_id = ?",
                                 (self.__user_id,))
        if not verify_password(old_password, row["password_hash"]):
            raise AuthenticationError("Current password is incorrect.")
        User.validate_password(new_password)
        self._db.update("users", {"password_hash": hash_password(new_password)},
                        "user_id = ?", (self.__user_id,))

    @abstractmethod
    def show_dashboard(self, gui):
        """Each role opens its own dashboard (polymorphism)."""

    # ---- validation / factory helpers ----------------------------------
    @staticmethod
    def validate_email(email):
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValidationError("Enter a valid email address.")

    @staticmethod
    def validate_password(password):
        if len(password) < 6:
            raise ValidationError("Password must be at least 6 characters.")

    @staticmethod
    def register(db, full_name, email, password, role, **extra):
        full_name, email = full_name.strip(), email.strip().lower()
        if not full_name:
            raise ValidationError("Name cannot be empty.")
        User.validate_email(email)
        User.validate_password(password)
        if role not in ("Admin", "Faculty", "Student"):
            raise ValidationError("Invalid role.")
        if db.fetch_one("SELECT 1 AS x FROM users WHERE email = ?", (email,)):
            raise ValidationError("An account with this email already exists.")
        roll_no = (extra.get("roll_no") or "").strip() or None
        if roll_no and db.fetch_one("SELECT 1 AS x FROM students WHERE roll_no = ?", (roll_no,)):
            raise ValidationError("That roll number is already registered.")
        uid = db.insert("users", {"full_name": full_name, "email": email,
                                  "password_hash": hash_password(password), "role": role,
                                  "status": "Active", "created_at": now()})
        try:
            if role == "Admin":
                db.insert("admins", {"user_id": uid, "permissions": "ALL"})
            elif role == "Faculty":
                db.insert("faculty", {"user_id": uid, "department": extra.get("department", ""),
                                      "designation": extra.get("designation", "")})
            else:
                db.insert("students", {"user_id": uid, "roll_no": roll_no,
                                       "class_grade": extra.get("class_grade", "")})
        except DatabaseError:
            db.delete("users", "user_id = ?", (uid,))
            raise
        return uid

    @staticmethod
    def authenticate(db, email, password):
        row = db.fetch_one("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
        if not row or not verify_password(password, row["password_hash"]):
            raise AuthenticationError("Invalid email or password.")
        if row["status"] != "Active":
            raise AuthenticationError("This account is inactive. Contact the administrator.")
        user = User.from_row(db, row)
        user.login()
        return user

    @staticmethod
    def from_row(db, row):
        base = (db, row["user_id"], row["full_name"], row["email"], row["role"],
                row["status"], row["created_at"])
        table = {"Admin": ("admins", Admin), "Faculty": ("faculty", Faculty),
                 "Student": ("students", Student)}[row["role"]]
        detail = db.fetch_one(f"SELECT * FROM {table[0]} WHERE user_id = ?", (row["user_id"],))
        if not detail:
            raise AuthenticationError("Account profile is incomplete.")
        return table[1](*base, detail)


class Admin(User):
    def __init__(self, db, user_id, full_name, email, role, status, created_at, detail):
        super().__init__(db, user_id, full_name, email, role, status, created_at)
        self.admin_id = detail["admin_id"]
        self.permissions = detail["permissions"]

    def show_dashboard(self, gui):
        gui.show_admin_dashboard()

    def manage_users(self):
        return self._db.fetch_all(
            "SELECT user_id, full_name, email, role, status, created_at FROM users ORDER BY user_id")

    def add_user(self, full_name, email, password, role, **extra):
        return User.register(self._db, full_name, email, password, role, **extra)

    def set_user_status(self, user_id, status):
        if user_id == self.user_id:
            raise AuthorizationError("You cannot change your own status.")
        self._db.update("users", {"status": status}, "user_id = ?", (user_id,))

    def delete_user(self, user_id):
        if user_id == self.user_id:
            raise AuthorizationError("You cannot delete your own account.")
        self._db.delete("users", "user_id = ?", (user_id,))

    def manage_quizzes(self):
        return self._db.fetch_all(
            "SELECT q.*, u.full_name AS faculty_name, "
            "(SELECT COUNT(*) FROM questions WHERE quiz_id = q.quiz_id) AS question_count "
            "FROM quizzes q JOIN faculty f ON q.faculty_id = f.faculty_id "
            "JOIN users u ON f.user_id = u.user_id ORDER BY q.quiz_id")

    def delete_quiz(self, quiz_id):
        Quiz.load(self._db, quiz_id).delete_quiz()

    def view_overall_reports(self):
        return ScoreAnalysis(self._db).get_overall_report()


class Faculty(User):
    def __init__(self, db, user_id, full_name, email, role, status, created_at, detail):
        super().__init__(db, user_id, full_name, email, role, status, created_at)
        self.faculty_id = detail["faculty_id"]
        self.department = detail["department"]
        self.designation = detail["designation"]

    def show_dashboard(self, gui):
        gui.show_faculty_dashboard()

    def _owned_quiz(self, quiz_id):
        quiz = Quiz.load(self._db, quiz_id)
        if quiz.faculty_id != self.faculty_id:
            raise AuthorizationError("You can only modify your own quizzes.")
        return quiz

    def create_quiz(self, title, subject, topic, description, difficulty, time_limit):
        quiz = Quiz(self._db, faculty_id=self.faculty_id, title=title, subject=subject,
                    topic=topic, description=description, difficulty_level=difficulty,
                    time_limit=time_limit)
        quiz.save()
        return quiz

    def my_quizzes(self):
        return self._db.fetch_all(
            "SELECT q.*, (SELECT COUNT(*) FROM questions WHERE quiz_id = q.quiz_id) "
            "AS question_count FROM quizzes q WHERE faculty_id = ? ORDER BY quiz_id",
            (self.faculty_id,))

    def add_question(self, quiz_id, text, qtype, topic, marks, options):
        return self._owned_quiz(quiz_id).add_question(text, qtype, topic, marks, options)

    def add_option(self, question_id, text, is_correct=False):
        q = self._db.fetch_one("SELECT quiz_id FROM questions WHERE question_id = ?", (question_id,))
        if not q:
            raise ValidationError("Question not found.")
        self._owned_quiz(q["quiz_id"])
        row = self._db.fetch_one("SELECT * FROM questions WHERE question_id = ?", (question_id,))
        return Question.from_row(self._db, row).add_option(text, is_correct)

    def publish_quiz(self, quiz_id):
        self._owned_quiz(quiz_id).publish()

    def unpublish_quiz(self, quiz_id):
        self._owned_quiz(quiz_id).unpublish()

    def delete_quiz(self, quiz_id):
        self._owned_quiz(quiz_id).delete_quiz()

    def view_student_performance(self):
        return self._db.fetch_all(
            "SELECT r.*, u.full_name, q.title FROM results r "
            "JOIN students s ON r.student_id = s.student_id JOIN users u ON s.user_id = u.user_id "
            "JOIN quizzes q ON r.quiz_id = q.quiz_id WHERE q.faculty_id = ? "
            "ORDER BY r.result_id DESC", (self.faculty_id,))


class Student(User):
    def __init__(self, db, user_id, full_name, email, role, status, created_at, detail):
        super().__init__(db, user_id, full_name, email, role, status, created_at)
        self.student_id = detail["student_id"]
        self.roll_no = detail["roll_no"]
        self.class_grade = detail["class_grade"]

    def show_dashboard(self, gui):
        gui.show_student_dashboard()

    def view_available_quizzes(self):
        return self._db.fetch_all(
            "SELECT q.*, u.full_name AS faculty_name, "
            "(SELECT COUNT(*) FROM questions WHERE quiz_id = q.quiz_id) AS question_count "
            "FROM quizzes q JOIN faculty f ON q.faculty_id = f.faculty_id "
            "JOIN users u ON f.user_id = u.user_id WHERE q.status = 'Published' "
            "AND question_count > 0 ORDER BY q.quiz_id")

    def start_attempt(self, quiz_id):
        return Attempt(self._db, self.student_id, quiz_id).start()

    def view_result(self, result_id):
        summary, review = Result.load_details(self._db, result_id)
        if summary["student_id"] != self.student_id:
            raise AuthorizationError("You can only view your own results.")
        return summary, review

    def view_performance(self):
        return ScoreAnalysis(self._db).get_student_report(self.student_id)
