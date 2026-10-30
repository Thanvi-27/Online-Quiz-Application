"""
BACKEND LAYER  -  backend/quiz.py   (quiz content)

Classes: Option, Question, Quiz.
A Quiz has many Questions, a Question has many Options and exactly one correct Option.
Quiz.total_marks is recalculated (with functools.reduce) whenever questions change.

Explain in viva: validation rules (>= 2 options, exactly one correct), publish() rules,
and how these classes save themselves through the DatabaseManager they are given.
"""
from functools import reduce

from backend.utils import DIFFICULTIES, now
from exceptions import ValidationError


class Option:
    def __init__(self, db, option_id, question_id, option_text, is_correct):
        self._db = db
        self.option_id = option_id
        self.question_id = question_id
        self.option_text = option_text
        self.is_correct = bool(is_correct)

    def set_correct(self):
        self._db.update("options", {"is_correct": 1}, "option_id = ?", (self.option_id,))
        self.is_correct = True

    def set_incorrect(self):
        self._db.update("options", {"is_correct": 0}, "option_id = ?", (self.option_id,))
        self.is_correct = False


class Question:
    def __init__(self, db, question_id, quiz_id, question_text, question_type="MCQ",
                 topic="", marks=1, created_at=None):
        self._db = db
        self.question_id = question_id
        self.quiz_id = quiz_id
        self.question_text = question_text
        self.question_type = question_type
        self.topic = topic
        self.marks = marks
        self.created_at = created_at

    @classmethod
    def from_row(cls, db, row):
        return cls(db, **row)

    @classmethod
    def create(cls, db, quiz_id, text, qtype, topic, marks, options):
        """options = list of (option_text, is_correct) tuples."""
        text = text.strip()
        if not text:
            raise ValidationError("Question text cannot be empty.")
        try:
            marks = int(marks)
        except (TypeError, ValueError):
            raise ValidationError("Marks must be a whole number.")
        if marks < 1:
            raise ValidationError("Marks must be at least 1.")
        options = [(t.strip(), c) for t, c in options if t.strip()]
        if len(options) < 2:
            raise ValidationError("A question needs at least two options.")
        if sum(1 for _, correct in options if correct) != 1:
            raise ValidationError("Exactly one option must be marked correct.")
        qid = db.insert("questions", {
            "quiz_id": quiz_id, "question_text": text, "question_type": qtype,
            "topic": topic.strip(), "marks": marks, "created_at": now()})
        question = cls(db, qid, quiz_id, text, qtype, topic.strip(), marks)
        for opt_text, correct in options:
            question.add_option(opt_text, correct)
        return question

    def add_option(self, text, is_correct=False):
        oid = self._db.insert("options", {
            "question_id": self.question_id, "option_text": text, "is_correct": int(is_correct)})
        return Option(self._db, oid, self.question_id, text, is_correct)

    def update_question(self, **fields):
        allowed = {"question_text", "topic", "marks", "question_type"}
        data = {k: v for k, v in fields.items() if k in allowed}
        if data:
            self._db.update("questions", data, "question_id = ?", (self.question_id,))

    def delete_question(self):
        self._db.delete("questions", "question_id = ?", (self.question_id,))

    def get_options(self):
        rows = self._db.fetch_all(
            "SELECT * FROM options WHERE question_id = ? ORDER BY option_id", (self.question_id,))
        return [Option(self._db, **r) for r in rows]

    def get_correct_option(self):
        return next(filter(lambda o: o.is_correct, self.get_options()), None)


class Quiz:
    def __init__(self, db, quiz_id=None, faculty_id=None, title="", subject="", topic="",
                 description="", difficulty_level="Easy", total_marks=0, time_limit=0,
                 status="Draft", created_at=None):
        self._db = db
        self.quiz_id = quiz_id
        self.faculty_id = faculty_id
        self.title = title
        self.subject = subject
        self.topic = topic
        self.description = description
        self.difficulty_level = difficulty_level
        self.total_marks = total_marks
        self.time_limit = time_limit
        self.status = status
        self.created_at = created_at

    @classmethod
    def load(cls, db, quiz_id):
        row = db.fetch_one("SELECT * FROM quizzes WHERE quiz_id = ?", (quiz_id,))
        if not row:
            raise ValidationError("Quiz not found.")
        return cls(db, **row)

    def save(self):
        if not self.title.strip():
            raise ValidationError("Quiz title cannot be empty.")
        if self.difficulty_level not in DIFFICULTIES:
            raise ValidationError("Difficulty must be Easy, Medium or Hard.")
        try:
            self.time_limit = int(self.time_limit or 0)
        except ValueError:
            raise ValidationError("Time limit must be a number of minutes.")
        self.created_at = self.created_at or now()
        self.quiz_id = self._db.insert("quizzes", {
            "faculty_id": self.faculty_id, "title": self.title.strip(),
            "subject": self.subject.strip(), "topic": self.topic.strip(),
            "description": self.description.strip(), "difficulty_level": self.difficulty_level,
            "total_marks": 0, "time_limit": self.time_limit, "status": "Draft",
            "created_at": self.created_at})
        return self.quiz_id

    def get_questions(self):
        rows = self._db.fetch_all(
            "SELECT * FROM questions WHERE quiz_id = ? ORDER BY question_id", (self.quiz_id,))
        return [Question.from_row(self._db, r) for r in rows]

    def _recalculate_total(self):
        total = reduce(lambda acc, q: acc + q.marks, self.get_questions(), 0)
        self._db.update("quizzes", {"total_marks": total}, "quiz_id = ?", (self.quiz_id,))
        self.total_marks = total

    def add_question(self, text, qtype, topic, marks, options):
        question = Question.create(self._db, self.quiz_id, text, qtype, topic, marks, options)
        self._recalculate_total()
        return question

    def update_quiz(self, **fields):
        allowed = {"title", "subject", "topic", "description", "difficulty_level", "time_limit"}
        data = {k: v for k, v in fields.items() if k in allowed}
        if data:
            self._db.update("quizzes", data, "quiz_id = ?", (self.quiz_id,))

    def delete_question(self, question_id):
        self._db.delete("questions", "question_id = ? AND quiz_id = ?", (question_id, self.quiz_id))
        self._recalculate_total()

    def delete_quiz(self):
        self._db.delete("quizzes", "quiz_id = ?", (self.quiz_id,))

    def publish(self):
        if not self.get_questions():
            raise ValidationError("Add at least one question before publishing.")
        self._db.update("quizzes", {"status": "Published"}, "quiz_id = ?", (self.quiz_id,))
        self.status = "Published"

    def unpublish(self):
        self._db.update("quizzes", {"status": "Draft"}, "quiz_id = ?", (self.quiz_id,))
        self.status = "Draft"
