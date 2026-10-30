"""
FRONTEND LAYER  -  frontend/student_screen.py   (Student dashboard)

Tabs: Available Quizzes (start a quiz), My Results (history + details) and
Performance Analysis (topic accuracy, trend, chart).
"""
from tkinter import ttk


def build_student_dashboard(gui):
    gui._clear()
    gui.root.unbind("<Return>")
    body = gui._header(f"Student dashboard - Roll no. {gui.user.roll_no or 'N/A'}")
    tabs = ttk.Notebook(body)
    tabs.pack(fill="both", expand=True)

    # Available quizzes
    avail_tab = ttk.Frame(tabs, padding=8)
    tabs.add(avail_tab, text="Available Quizzes")
    cols = [("quiz_id", "ID", 50), ("title", "Title", 230), ("subject", "Subject", 110),
            ("faculty_name", "Faculty", 150), ("difficulty_level", "Level", 70),
            ("question_count", "Questions", 80), ("total_marks", "Marks", 60),
            ("time_limit", "Mins", 55)]
    tree = gui._tree(avail_tab, cols)

    def refresh_quizzes():
        gui._fill(tree, gui.user.view_available_quizzes(), "quiz_id", [c[0] for c in cols])

    @gui._guard
    def start():
        gui.start_quiz(gui._selected_id(tree, "quiz"), on_done=refresh_all)

    row = ttk.Frame(avail_tab)
    row.pack(fill="x", pady=6)
    ttk.Button(row, text="Start Quiz", command=start).pack(side="left", padx=4)
    ttk.Button(row, text="Refresh", command=refresh_quizzes).pack(side="left", padx=4)

    # Results history
    res_tab = ttk.Frame(tabs, padding=8)
    tabs.add(res_tab, text="My Results")
    hcols = [("result_id", "ID", 50), ("title", "Quiz", 220), ("total_score", "Score", 60),
             ("percentage", "%", 60), ("correct_count", "Correct", 65),
             ("incorrect_count", "Wrong", 60), ("time_taken", "Secs", 55),
             ("generated_at", "Date", 150)]
    htree = gui._tree(res_tab, hcols)

    # Performance
    perf_tab = ttk.Frame(tabs, padding=8)
    tabs.add(perf_tab, text="Performance Analysis")
    summary = ttk.Label(perf_tab, style="Head.TLabel", justify="left")
    summary.pack(anchor="w")
    ttk.Label(perf_tab, text="Topic accuracy (weakest first)").pack(anchor="w", pady=(10, 0))
    tcols = [("topic", "Topic", 240), ("correct", "Correct", 80), ("total", "Answered", 80),
             ("acc", "Accuracy %", 100), ("flag", "Verdict", 140)]
    ttree = gui._tree(perf_tab, tcols, height=8)
    pstate = {"report": None}

    def refresh_perf():
        rep = gui.user.view_performance()
        pstate["report"] = rep
        summary.config(text=(
            f"Attempts: {rep['total_attempts']}    Average: {rep['average_score']}%    "
            f"Highest: {rep['highest_score']}%    Lowest: {rep['lowest_score']}%\n"
            f"Correct answers: {rep['correct_total']}    Incorrect: {rep['incorrect_total']}    "
            f"Trend: {rep['performance_trend']}"))
        ttree.delete(*ttree.get_children())
        for topic, correct, total, acc in rep["weak_topics"]:
            verdict = "Needs improvement" if acc < 60 else "Good" if acc < 85 else "Strong"
            ttree.insert("", "end", values=(topic, correct, total, acc, verdict))

    def refresh_history():
        rep = gui.user.view_performance()
        gui._fill(htree, rep["history"], "result_id", [c[0] for c in hcols])

    def refresh_all():
        refresh_quizzes()
        refresh_history()
        refresh_perf()

    @gui._guard
    def view_detail():
        gui.show_result(gui._selected_id(htree, "result"))

    @gui._guard
    def chart():
        rep = pstate["report"]
        gui._show_chart(rep["trend_labels"], rep["trend_values"], "My score trend")

    row = ttk.Frame(res_tab)
    row.pack(fill="x", pady=6)
    ttk.Button(row, text="View Details", command=view_detail).pack(side="left", padx=4)
    htree.bind("<Double-1>", lambda e: view_detail())
    row = ttk.Frame(perf_tab)
    row.pack(fill="x", pady=6)
    ttk.Button(row, text="Show Score Trend Chart", command=chart).pack(side="left", padx=4)
    ttk.Button(row, text="Refresh", command=refresh_perf).pack(side="left", padx=4)
    refresh_all()
