"""
Unit tests for the backend and database layers.
Run from the project folder:   python -m unittest tests.test_quiz_app -v
Every test uses a fresh in-memory SQLite database, so nothing touches quiz_app.db.
"""
import unittest

from backend.analysis import ScoreAnalysis
from backend.quiz import Quiz
from backend.security import hash_password, verify_password
from backend.users import Admin, Faculty, Student, User
from database.db_manager import DatabaseManager
from exceptions import AuthenticationError, AuthorizationError, ValidationError


def make_db():
    db = DatabaseManager(":memory:")
    db.connect()
    db.create_tables()
    return db


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        User.register(self.db, "Admin", "a@x.com", "admin123", "Admin")
        User.register(self.db, "Fac", "f@x.com", "faculty1", "Faculty", department="CS")
        User.register(self.db, "Stu", "s@x.com", "student1", "Student", roll_no="R1")
        self.admin = User.authenticate(self.db, "a@x.com", "admin123")
        self.fac = User.authenticate(self.db, "f@x.com", "faculty1")
        self.stu = User.authenticate(self.db, "s@x.com", "student1")

    def tearDown(self):
        self.db.close()

    def make_quiz(self, publish=True, topics=("OOP", "SQL")):
        quiz = self.fac.create_quiz("Quiz", "CS", "Py", "d", "Easy", 0)
        for i, topic in enumerate(topics):
            self.fac.add_question(quiz.quiz_id, f"Q{i}?", "MCQ", topic, 2,
                                  [("right", True), ("wrong", False)])
        if publish:
            self.fac.publish_quiz(quiz.quiz_id)
        return quiz

    def answers(self, quiz, correct=True):
        out = {}
        for q in Quiz.load(self.db, quiz.quiz_id).get_questions():
            opts = q.get_options()
            out[q.question_id] = next(o.option_id for o in opts if o.is_correct == correct)
        return out


class TestSecurityAndLogin(BaseCase):
    def test_password_hash_verifies_only_correct_password(self):
        stored = hash_password("secret1")
        self.assertTrue(verify_password("secret1", stored))
        self.assertFalse(verify_password("Secret1", stored))

    def test_login_returns_role_specific_subclass(self):
        self.assertIsInstance(self.admin, Admin)
        self.assertIsInstance(self.fac, Faculty)
        self.assertIsInstance(self.stu, Student)

    def test_wrong_password_raises_authentication_error(self):
        with self.assertRaises(AuthenticationError):
            User.authenticate(self.db, "s@x.com", "nope")

    def test_inactive_account_cannot_login(self):
        self.admin.set_user_status(self.stu.user_id, "Inactive")
        with self.assertRaises(AuthenticationError):
            User.authenticate(self.db, "s@x.com", "student1")

    def test_user_is_abstract(self):
        with self.assertRaises(TypeError):
            User(self.db, 1, "n", "e@x.com", "Admin")

    def test_polymorphic_dashboard_dispatch(self):
        class FakeGUI:
            calls = []
            show_admin_dashboard = lambda self: self.calls.append("admin")
            show_faculty_dashboard = lambda self: self.calls.append("faculty")
            show_student_dashboard = lambda self: self.calls.append("student")
        gui = FakeGUI()
        for user in (self.admin, self.fac, self.stu):
            user.show_dashboard(gui)
        self.assertEqual(gui.calls, ["admin", "faculty", "student"])


class TestRegistrationValidation(BaseCase):
    def test_duplicate_email_rejected(self):
        with self.assertRaises(ValidationError):
            User.register(self.db, "Dup", "s@x.com", "password1", "Student")

    def test_short_password_rejected(self):
        with self.assertRaises(ValidationError):
            User.register(self.db, "N", "n@x.com", "123", "Student")

    def test_invalid_email_rejected(self):
        with self.assertRaises(ValidationError):
            User.register(self.db, "N", "not-an-email", "password1", "Student")


class TestAuthorization(BaseCase):
    def test_admin_cannot_delete_own_account(self):
        with self.assertRaises(AuthorizationError):
            self.admin.delete_user(self.admin.user_id)

    def test_faculty_cannot_modify_another_faculty_quiz(self):
        quiz = self.make_quiz()
        User.register(self.db, "F2", "f2@x.com", "faculty2", "Faculty")
        other = User.authenticate(self.db, "f2@x.com", "faculty2")
        with self.assertRaises(AuthorizationError):
            other.delete_quiz(quiz.quiz_id)

    def test_student_cannot_view_another_students_result(self):
        quiz = self.make_quiz()
        result = self.stu.start_attempt(quiz.quiz_id).submit(self.answers(quiz))
        User.register(self.db, "S2", "s2@x.com", "student2", "Student")
        other = User.authenticate(self.db, "s2@x.com", "student2")
        with self.assertRaises(AuthorizationError):
            other.view_result(result.result_id)


class TestQuizManagement(BaseCase):
    def test_empty_quiz_title_rejected(self):
        with self.assertRaises(ValidationError):
            self.fac.create_quiz("  ", "s", "t", "d", "Easy", 0)

    def test_question_needs_two_options(self):
        quiz = self.fac.create_quiz("Q", "s", "t", "d", "Easy", 0)
        with self.assertRaises(ValidationError):
            self.fac.add_question(quiz.quiz_id, "Q?", "MCQ", "t", 1, [("only", True)])

    def test_question_needs_exactly_one_correct_option(self):
        quiz = self.fac.create_quiz("Q", "s", "t", "d", "Easy", 0)
        with self.assertRaises(ValidationError):
            self.fac.add_question(quiz.quiz_id, "Q?", "MCQ", "t", 1, [("a", True), ("b", True)])

    def test_total_marks_recalculated_when_questions_added(self):
        quiz = self.make_quiz(publish=False, topics=("A", "B", "C"))
        self.assertEqual(Quiz.load(self.db, quiz.quiz_id).total_marks, 6)

    def test_cannot_publish_quiz_without_questions(self):
        quiz = self.fac.create_quiz("Q", "s", "t", "d", "Easy", 0)
        with self.assertRaises(ValidationError):
            self.fac.publish_quiz(quiz.quiz_id)

    def test_student_cannot_start_draft_quiz(self):
        quiz = self.make_quiz(publish=False)
        with self.assertRaises(ValidationError):
            self.stu.start_attempt(quiz.quiz_id)


class TestScoring(BaseCase):
    def test_all_correct_gives_100_percent(self):
        quiz = self.make_quiz()
        r = self.stu.start_attempt(quiz.quiz_id).submit(self.answers(quiz))
        self.assertEqual((r.total_score, r.percentage, r.correct_count), (4, 100.0, 2))

    def test_unanswered_question_counts_as_incorrect(self):
        quiz = self.make_quiz()
        sel = self.answers(quiz)
        first = next(iter(sel))
        sel[first] = None
        r = self.stu.start_attempt(quiz.quiz_id).submit(sel)
        self.assertEqual((r.total_score, r.percentage, r.incorrect_count), (2, 50.0, 1))

    def test_all_wrong_gives_zero(self):
        quiz = self.make_quiz()
        r = self.stu.start_attempt(quiz.quiz_id).submit(self.answers(quiz, correct=False))
        self.assertEqual((r.total_score, r.percentage), (0, 0.0))

    def test_attempt_cannot_be_submitted_twice(self):
        quiz = self.make_quiz()
        attempt = self.stu.start_attempt(quiz.quiz_id)
        attempt.submit(self.answers(quiz))
        with self.assertRaises(ValidationError):
            attempt.submit(self.answers(quiz))


class TestAnalysisAndPersistence(BaseCase):
    def test_retake_keeps_every_attempt_in_history(self):
        quiz = self.make_quiz()
        self.stu.start_attempt(quiz.quiz_id).submit(self.answers(quiz, correct=False))
        self.stu.start_attempt(quiz.quiz_id).submit(self.answers(quiz))
        report = self.stu.view_performance()
        self.assertEqual(report["total_attempts"], 2)
        self.assertEqual(report["performance_trend"], "Up")
        self.assertEqual((report["highest_score"], report["lowest_score"]), (100.0, 0.0))

    def test_trend_detection(self):
        self.assertEqual(ScoreAnalysis._trend([40, 80]), "Up")
        self.assertEqual(ScoreAnalysis._trend([80, 40]), "Down")
        self.assertEqual(ScoreAnalysis._trend([70, 71]), "Stable")
        self.assertEqual(ScoreAnalysis._trend([70]), "Stable")

    def test_weak_topic_is_the_one_answered_worst(self):
        quiz = self.make_quiz(topics=("OOP", "SQL"))
        sel = self.answers(quiz)
        sql_q = Quiz.load(self.db, quiz.quiz_id).get_questions()[1]
        sel[sql_q.question_id] = next(o.option_id for o in sql_q.get_options() if not o.is_correct)
        self.stu.start_attempt(quiz.quiz_id).submit(sel)
        weakest = ScoreAnalysis(self.db).identify_weak_topics(self.stu.student_id)[0]
        self.assertEqual((weakest[0], weakest[3]), ("SQL", 0.0))

    def test_analysis_rows_are_stored_in_database(self):
        quiz = self.make_quiz()
        self.stu.start_attempt(quiz.quiz_id).submit(self.answers(quiz))
        kinds = {r["analysis_type"] for r in self.db.fetch_all("SELECT * FROM score_analysis")}
        self.assertEqual(kinds, {"Student", "Quiz", "Overall"})

    def test_deleting_user_cascades_to_results(self):
        quiz = self.make_quiz()
        self.stu.start_attempt(quiz.quiz_id).submit(self.answers(quiz))
        self.admin.delete_user(self.stu.user_id)
        self.assertEqual(self.db.fetch_one("SELECT COUNT(*) AS c FROM results")["c"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
