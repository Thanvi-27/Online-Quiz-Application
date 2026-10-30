"""
BACKEND LAYER  -  backend/attempt.py   (taking a quiz and scoring it)

Classes: Answer, Result, Attempt.
Attempt.submit() is the heart of the project: it creates one Answer per question,
checks each one, builds the Result (score, percentage, counts) and then asks
ScoreAnalysis to refresh the analysis tables.

Explain in viva: the submit() flow, why unanswered questions count as incorrect, and
the use of filter / reduce / lambda in Result.calculate_score().
"""
from datetime import datetime
from functools import reduce

from backend.analysis import ScoreAnalysis
from backend.quiz import Quiz
from backend.utils import now
from exceptions import ValidationError


class Answer:
    def __init__(self, db, attempt_id, question_id, selected_option_id=None):
        self._db = db
        self.attempt_id = attempt_id
        self.question_id = question_id
        self.selected_option_id = selected_option_id
        self.is_correct = False
        self.marks_awarded = 0

    def check_answer(self):
        if self.selected_option_id is None:
            return False
        row = self._db.fetch_one(
            "SELECT is_correct FROM options WHERE option_id = ? AND question_id = ?",
            (self.selected_option_id, self.question_id))
        return bool(row and row["is_correct"])

    def submit_answer(self):
        self.is_correct = self.check_answer()
        if self.is_correct:
            q = self._db.fetch_one("SELECT marks FROM questions WHERE question_id = ?",
                                   (self.question_id,))
            self.marks_awarded = q["marks"]
        self._db.insert("answers", {
            "attempt_id": self.attempt_id, "question_id": self.question_id,
            "selected_option_id": self.selected_option_id, "is_correct": int(self.is_correct),
            "marks_awarded": self.marks_awarded, "answered_at": now()})
        return self


class Result:
    def __init__(self, db, attempt_id, student_id, quiz_id, result_id=None):
        self._db = db
        self.result_id = result_id
        self.attempt_id = attempt_id
        self.student_id = student_id
        self.quiz_id = quiz_id
        self.total_questions = 0
        self.correct_count = 0
        self.incorrect_count = 0
        self.total_score = 0
        self.max_marks = 0
        self.percentage = 0.0
        self.time_taken = 0

    def calculate_score(self, answers, max_marks, time_taken):
        self.total_questions = len(answers)
        self.correct_count = len(list(filter(lambda a: a.is_correct, answers)))
        self.incorrect_count = self.total_questions - self.correct_count
        self.total_score = reduce(lambda acc, a: acc + a.marks_awarded, answers, 0)
        self.max_marks = max_marks
        self.time_taken = time_taken
        self.percentage = self.get_percentage()

    def get_percentage(self):
        return round(self.total_score / self.max_marks * 100, 2) if self.max_marks else 0.0

    def save_result(self):
        self.result_id = self._db.insert("results", {
            "attempt_id": self.attempt_id, "student_id": self.student_id,
            "quiz_id": self.quiz_id, "total_questions": self.total_questions,
            "correct_count": self.correct_count, "incorrect_count": self.incorrect_count,
            "total_score": self.total_score, "percentage": self.percentage,
            "time_taken": self.time_taken, "generated_at": now()})
        return self.result_id

    @staticmethod
    def load_details(db, result_id):
        """Return (summary dict, per-question review list) for a stored result."""
        summary = db.fetch_one(
            "SELECT r.*, q.title, q.total_marks FROM results r "
            "JOIN quizzes q ON r.quiz_id = q.quiz_id WHERE r.result_id = ?", (result_id,))
        if not summary:
            raise ValidationError("Result not found.")
        review = db.fetch_all(
            "SELECT qs.question_text, qs.topic, qs.marks, a.is_correct, a.marks_awarded, "
            "so.option_text AS chosen, "
            "(SELECT option_text FROM options o WHERE o.question_id = qs.question_id "
            " AND o.is_correct = 1) AS correct_text "
            "FROM answers a JOIN questions qs ON a.question_id = qs.question_id "
            "LEFT JOIN options so ON a.selected_option_id = so.option_id "
            "WHERE a.attempt_id = ? ORDER BY a.answer_id", (summary["attempt_id"],))
        return summary, review


class Attempt:
    def __init__(self, db, student_id, quiz_id, attempt_id=None):
        self._db = db
        self.attempt_id = attempt_id
        self.student_id = student_id
        self.quiz_id = quiz_id
        self.started_at = None
        self.status = "New"

    def start(self):
        quiz = Quiz.load(self._db, self.quiz_id)
        if quiz.status != "Published":
            raise ValidationError("This quiz is not available.")
        if not quiz.get_questions():
            raise ValidationError("This quiz has no questions yet.")
        self.started_at = now()
        self.status = "InProgress"
        self.attempt_id = self._db.insert("attempts", {
            "student_id": self.student_id, "quiz_id": self.quiz_id,
            "started_at": self.started_at, "status": "InProgress"})
        return self

    def get_answers(self):
        return self._db.fetch_all("SELECT * FROM answers WHERE attempt_id = ?", (self.attempt_id,))

    def submit(self, selections):
        """selections = {question_id: selected_option_id or None}"""
        if self.status != "InProgress":
            raise ValidationError("This attempt is already submitted.")
        quiz = Quiz.load(self._db, self.quiz_id)
        questions = quiz.get_questions()
        answers = [Answer(self._db, self.attempt_id, q.question_id,
                          selections.get(q.question_id)).submit_answer() for q in questions]
        submitted = now()
        self._db.update("attempts", {"submitted_at": submitted, "status": "Submitted"},
                        "attempt_id = ?", (self.attempt_id,))
        self.status = "Submitted"
        elapsed = int((datetime.strptime(submitted, "%Y-%m-%d %H:%M:%S")
                       - datetime.strptime(self.started_at, "%Y-%m-%d %H:%M:%S")).total_seconds())
        max_marks = reduce(lambda acc, q: acc + q.marks, questions, 0)
        result = Result(self._db, self.attempt_id, self.student_id, self.quiz_id)
        result.calculate_score(answers, max_marks, elapsed)
        result.save_result()
        ScoreAnalysis(self._db).generate_analysis(self.student_id, self.quiz_id)
        return result
