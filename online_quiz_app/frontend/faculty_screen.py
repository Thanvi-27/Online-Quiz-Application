"""
FRONTEND LAYER  -  frontend/faculty_screen.py   (Faculty dashboard)

Tabs: My Quizzes (create, add questions, view, publish, delete) and Student Performance.
Every button calls a method of the logged-in Faculty object (gui.user).
"""
from tkinter import messagebox, ttk

from backend.quiz import Quiz
from backend.utils import DIFFICULTIES
from exceptions import ValidationError
from frontend.dialogs import FormDialog


def build_faculty_dashboard(gui):
    gui._clear()
    gui.root.unbind("<Return>")
    body = gui._header(f"Faculty dashboard - {gui.user.department or 'Faculty'}")
    tabs = ttk.Notebook(body)
    tabs.pack(fill="both", expand=True)

    quiz_tab = ttk.Frame(tabs, padding=8)
    tabs.add(quiz_tab, text="My Quizzes")
    cols = [("quiz_id", "ID", 50), ("title", "Title", 240), ("subject", "Subject", 120),
            ("difficulty_level", "Level", 70), ("question_count", "Questions", 80),
            ("total_marks", "Marks", 60), ("time_limit", "Mins", 55), ("status", "Status", 80)]
    tree = gui._tree(quiz_tab, cols)

    def refresh():
        gui._fill(tree, gui.user.my_quizzes(), "quiz_id", [c[0] for c in cols])

    @gui._guard
    def new_quiz():
        d = FormDialog(gui.root, "Create Quiz", [
            ("Title", "title", "entry", None), ("Subject", "subject", "entry", None),
            ("Topic", "topic", "entry", None), ("Description", "desc", "text", None),
            ("Difficulty", "diff", "combo", DIFFICULTIES),
            ("Time limit (minutes, 0 = none)", "time", "entry", None)])
        if not d.result:
            return
        r = d.result
        gui.user.create_quiz(r["title"], r["subject"], r["topic"], r["desc"], r["diff"],
                              r["time"] or 0)
        refresh()

    @gui._guard
    def add_question():
        qid = gui._selected_id(tree, "quiz")
        d = FormDialog(gui.root, "Add Question", [
            ("Question", "text", "text", None), ("Topic (for weak-area analysis)", "topic", "entry", None),
            ("Type", "type", "combo", ["MCQ", "TrueFalse"]), ("Marks", "marks", "entry", None),
            ("Option A (True for True/False)", "a", "entry", None),
            ("Option B (False for True/False)", "b", "entry", None),
            ("Option C (MCQ only)", "c", "entry", None), ("Option D (MCQ only)", "d", "entry", None),
            ("Correct answer", "correct", "combo", ["A", "B", "C", "D"])])
        if not d.result:
            return
        r = d.result
        if r["type"] == "TrueFalse":
            texts = ["True", "False"]
            if r["correct"] not in ("A", "B"):
                raise ValidationError("For True/False choose A (True) or B (False).")
        else:
            texts = [r["a"], r["b"], r["c"], r["d"]]
        options = [(t, "ABCD"[i] == r["correct"]) for i, t in enumerate(texts)]
        if r["type"] == "MCQ" and not texts["ABCD".index(r["correct"])].strip():
            raise ValidationError("The correct answer cannot be an empty option.")
        gui.user.add_question(qid, r["text"], r["type"], r["topic"], r["marks"] or 1, options)
        refresh()
        messagebox.showinfo("Question added", "Question saved.")

    @gui._guard
    def view_questions():
        qid = gui._selected_id(tree, "quiz")
        quiz = Quiz.load(gui.db, qid)
        lines = []
        for i, q in enumerate(quiz.get_questions(), 1):
            lines.append(f"Q{i}. {q.question_text}  [{q.topic}] ({q.marks} mark)")
            for letter, opt in zip("ABCD", q.get_options()):
                lines.append(f"    {letter}. {opt.option_text}" + ("   <-- correct" if opt.is_correct else ""))
            lines.append("")
        gui._show_text(f"Questions - {quiz.title}", "\n".join(lines) or "No questions yet.")

    @gui._guard
    def toggle_publish():
        qid = gui._selected_id(tree, "quiz")
        status = tree.item(str(qid), "values")[7]
        (gui.user.unpublish_quiz if status == "Published" else gui.user.publish_quiz)(qid)
        refresh()

    @gui._guard
    def delete_quiz():
        qid = gui._selected_id(tree, "quiz")
        if messagebox.askyesno("Delete quiz", "Delete this quiz with its questions and results?"):
            gui.user.delete_quiz(qid)
            refresh()

    row = ttk.Frame(quiz_tab)
    row.pack(fill="x", pady=6)
    for text, cmd in [("New Quiz", new_quiz), ("Add Question", add_question),
                      ("View Questions", view_questions), ("Publish / Unpublish", toggle_publish),
                      ("Delete Quiz", delete_quiz)]:
        ttk.Button(row, text=text, command=cmd).pack(side="left", padx=4)
    refresh()

    perf_tab = ttk.Frame(tabs, padding=8)
    tabs.add(perf_tab, text="Student Performance")
    pcols = [("full_name", "Student", 180), ("title", "Quiz", 200), ("total_score", "Score", 60),
             ("percentage", "%", 60), ("correct_count", "Correct", 65),
             ("incorrect_count", "Wrong", 60), ("generated_at", "Date", 150)]
    ptree = gui._tree(perf_tab, pcols)
    pstate = {"rows": []}
    summary = ttk.Label(perf_tab, style="Head.TLabel")
    summary.pack(anchor="w", pady=4)

    def refresh_perf():
        rows = gui.user.view_student_performance()
        pstate["rows"] = rows
        ptree.delete(*ptree.get_children())
        for r in rows:
            ptree.insert("", "end", values=[r[c[0]] for c in pcols])
        pcts = [r["percentage"] for r in rows]
        summary.config(text=(f"Attempts: {len(pcts)}   Average: {round(sum(pcts)/len(pcts), 2)}%   "
                             f"Highest: {max(pcts)}%   Lowest: {min(pcts)}%") if pcts
                       else "No attempts on your quizzes yet.")

    @gui._guard
    def chart():
        rows = pstate["rows"]
        by_quiz = {}
        for r in rows:
            by_quiz.setdefault(r["title"], []).append(r["percentage"])
        labels = sorted(by_quiz)
        values = [round(sum(by_quiz[t]) / len(by_quiz[t]), 2) for t in labels]
        gui._show_chart([t[:16] for t in labels], values, "Average score per quiz")

    row = ttk.Frame(perf_tab)
    row.pack(fill="x", pady=6)
    ttk.Button(row, text="Show Chart", command=chart).pack(side="left", padx=4)
    ttk.Button(row, text="Refresh", command=refresh_perf).pack(side="left", padx=4)
    refresh_perf()
