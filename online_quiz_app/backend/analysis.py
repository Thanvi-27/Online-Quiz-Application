"""
BACKEND LAYER  -  backend/analysis.py   (score analysis)

Class: ScoreAnalysis. Builds student-wise, quiz-wise and overall reports, performance
trend (Up / Down / Stable), weak topics, and the matplotlib chart figure. Results are
also stored in the score_analysis table.

Explain in viva: all scores are analysed as percentages, how the trend is decided, and
the functional-style code (map, filter, zip, sorted, lambda, comprehensions).
"""
from backend.utils import now


class ScoreAnalysis:
    """All scores are analysed as percentages so quizzes with different totals compare fairly."""

    def __init__(self, db):
        self._db = db

    # ---- helpers -----------------------------------------------------
    @staticmethod
    def _trend(percentages):
        if len(percentages) < 2:
            return "Stable"
        delta = percentages[-1] - percentages[-2]
        return "Up" if delta > 2 else "Down" if delta < -2 else "Stable"

    @staticmethod
    def _summarise(rows):
        pcts = [r["percentage"] for r in rows]
        if not pcts:
            return {"total_attempts": 0, "average_score": 0.0, "highest_score": 0.0,
                    "lowest_score": 0.0, "performance_trend": "Stable"}
        return {"total_attempts": len(pcts),
                "average_score": round(sum(pcts) / len(pcts), 2),
                "highest_score": max(pcts), "lowest_score": min(pcts),
                "performance_trend": ScoreAnalysis._trend(pcts)}

    def identify_weak_topics(self, student_id=None):
        """Topics sorted weakest-first: (topic, correct, total, accuracy%)."""
        sql = ("SELECT q.topic AS topic, SUM(a.is_correct) AS correct, COUNT(*) AS total "
               "FROM answers a JOIN attempts t ON a.attempt_id = t.attempt_id "
               "JOIN questions q ON a.question_id = q.question_id "
               "WHERE t.status = 'Submitted' AND q.topic IS NOT NULL AND q.topic != '' ")
        params = ()
        if student_id is not None:
            sql += "AND t.student_id = ? "
            params = (student_id,)
        rows = self._db.fetch_all(sql + "GROUP BY q.topic", params)
        stats = [(r["topic"], r["correct"], r["total"], round(r["correct"] / r["total"] * 100, 1))
                 for r in rows]
        return sorted(stats, key=lambda s: s[3])

    def _weak_topic_name(self, student_id=None):
        weak = list(filter(lambda s: s[3] < 60, self.identify_weak_topics(student_id)))
        return weak[0][0] if weak else "None"

    # ---- stored analysis (score_analysis table) ------------------------
    def _store(self, analysis_type, student_id, quiz_id, stats, weak_topic):
        record = {"analysis_type": analysis_type, "student_id": student_id, "quiz_id": quiz_id,
                  **stats, "weak_topic": weak_topic, "generated_at": now()}
        existing = self._db.fetch_one(
            "SELECT analysis_id FROM score_analysis "
            "WHERE analysis_type = ? AND student_id IS ? AND quiz_id IS ?",
            (analysis_type, student_id, quiz_id))
        if existing:
            self._db.update("score_analysis", record, "analysis_id = ?", (existing["analysis_id"],))
        else:
            self._db.insert("score_analysis", record)

    def generate_analysis(self, student_id, quiz_id):
        per_student = self._db.fetch_all(
            "SELECT * FROM results WHERE student_id = ? AND quiz_id = ? ORDER BY result_id",
            (student_id, quiz_id))
        per_quiz = self._db.fetch_all(
            "SELECT * FROM results WHERE quiz_id = ? ORDER BY result_id", (quiz_id,))
        overall = self._db.fetch_all("SELECT * FROM results ORDER BY result_id")
        self._store("Student", student_id, quiz_id, self._summarise(per_student),
                    self._weak_topic_name(student_id))
        self._store("Quiz", None, quiz_id, self._summarise(per_quiz), self._weak_topic_name())
        self._store("Overall", None, None, self._summarise(overall), self._weak_topic_name())

    # ---- reports -------------------------------------------------------
    def get_student_report(self, student_id):
        rows = self._db.fetch_all(
            "SELECT r.*, q.title FROM results r JOIN quizzes q ON r.quiz_id = q.quiz_id "
            "WHERE r.student_id = ? ORDER BY r.result_id", (student_id,))
        report = self._summarise(rows)
        report.update({
            "history": list(reversed(rows)),
            "correct_total": sum(map(lambda r: r["correct_count"], rows)),
            "incorrect_total": sum(map(lambda r: r["incorrect_count"], rows)),
            "weak_topics": self.identify_weak_topics(student_id),
            "trend_labels": [f"#{i} {r['title'][:12]}" for i, r in enumerate(rows, 1)],
            "trend_values": [r["percentage"] for r in rows],
        })
        return report

    def get_quiz_report(self, quiz_id):
        rows = self._db.fetch_all(
            "SELECT r.*, u.full_name FROM results r "
            "JOIN students s ON r.student_id = s.student_id "
            "JOIN users u ON s.user_id = u.user_id WHERE r.quiz_id = ? ORDER BY r.percentage DESC",
            (quiz_id,))
        report = self._summarise(rows)
        report["rows"] = rows
        return report

    def get_overall_report(self):
        rows = self._db.fetch_all("SELECT * FROM results ORDER BY result_id")
        report = self._summarise(rows)
        quizzes = self._db.fetch_all(
            "SELECT q.quiz_id, q.title, COUNT(r.result_id) AS attempts, "
            "ROUND(AVG(r.percentage), 2) AS avg_pct FROM quizzes q "
            "LEFT JOIN results r ON q.quiz_id = r.quiz_id GROUP BY q.quiz_id ORDER BY q.quiz_id")
        students = self._db.fetch_all(
            "SELECT u.full_name, COUNT(r.result_id) AS attempts, "
            "ROUND(AVG(r.percentage), 2) AS avg_pct FROM students s "
            "JOIN users u ON s.user_id = u.user_id JOIN results r ON r.student_id = s.student_id "
            "GROUP BY s.student_id ORDER BY avg_pct DESC")
        report.update({"quizzes": quizzes, "students": students,
                       "weak_topics": self.identify_weak_topics()})
        return report

    def get_trends(self, student_id):
        report = self.get_student_report(student_id)
        deltas = [b - a for a, b in zip(report["trend_values"], report["trend_values"][1:])]
        return report["performance_trend"], deltas

    def plot_chart(self, labels, values, title, ylabel="Percentage (%)"):
        from matplotlib.figure import Figure  # imported lazily so backend works headless
        fig = Figure(figsize=(7, 4), dpi=100)
        ax = fig.add_subplot(111)
        colours = ["#2e9e5b" if v >= 60 else "#e0a030" if v >= 40 else "#d9534f" for v in values]
        ax.bar(range(len(values)), values, color=colours)
        ax.plot(range(len(values)), values, color="#333", marker="o", linewidth=1)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
        ax.set_ylim(0, 105)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        for i, v in enumerate(values):
            ax.text(i, v + 1.5, f"{v:g}", ha="center", fontsize=8)
        fig.tight_layout()
        return fig
