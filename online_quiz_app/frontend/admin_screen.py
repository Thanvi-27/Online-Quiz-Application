"""
FRONTEND LAYER  -  frontend/admin_screen.py   (Admin dashboard)

Tabs: Users (add / activate / delete), Quizzes (view / delete), Overall Reports (+ chart).
Every button calls a method of the logged-in Admin object (gui.user).
"""
from tkinter import messagebox, ttk

from frontend.dialogs import FormDialog


def build_admin_dashboard(gui):
    gui._clear()
    gui.root.unbind("<Return>")
    body = gui._header("Administrator dashboard")
    tabs = ttk.Notebook(body)
    tabs.pack(fill="both", expand=True)

    # Users tab
    users_tab = ttk.Frame(tabs, padding=8)
    tabs.add(users_tab, text="Users")
    cols = [("user_id", "ID", 50), ("full_name", "Name", 200), ("email", "Email", 240),
            ("role", "Role", 90), ("status", "Status", 80), ("created_at", "Created", 160)]
    users = gui._tree(users_tab, cols)

    def refresh_users():
        gui._fill(users, gui.user.manage_users(), "user_id", [c[0] for c in cols])

    @gui._guard
    def add_user():
        d = FormDialog(gui.root, "Add User", [
            ("Full name", "name", "entry", None), ("Email", "email", "entry", None),
            ("Password (min 6)", "password", "password", None),
            ("Role", "role", "combo", ["Student", "Faculty", "Admin"]),
            ("Department / Roll no.", "extra1", "entry", None),
            ("Designation / Class", "extra2", "entry", None)])
        if not d.result:
            return
        r = d.result
        extra = ({"department": r["extra1"], "designation": r["extra2"]} if r["role"] == "Faculty"
                 else {"roll_no": r["extra1"], "class_grade": r["extra2"]} if r["role"] == "Student"
                 else {})
        gui.user.add_user(r["name"], r["email"], r["password"], r["role"], **extra)
        refresh_users()

    @gui._guard
    def toggle_status():
        uid = gui._selected_id(users, "user")
        current = users.item(str(uid), "values")[4]
        gui.user.set_user_status(uid, "Inactive" if current == "Active" else "Active")
        refresh_users()

    @gui._guard
    def delete_user():
        uid = gui._selected_id(users, "user")
        if messagebox.askyesno("Delete user", "Delete this user and all their data?"):
            gui.user.delete_user(uid)
            refresh_users()

    row = ttk.Frame(users_tab)
    row.pack(fill="x", pady=6)
    for text, cmd in [("Add User", add_user), ("Activate / Deactivate", toggle_status),
                      ("Delete User", delete_user), ("Refresh", refresh_users)]:
        ttk.Button(row, text=text, command=cmd).pack(side="left", padx=4)
    refresh_users()

    # Quizzes tab
    quiz_tab = ttk.Frame(tabs, padding=8)
    tabs.add(quiz_tab, text="Quizzes")
    qcols = [("quiz_id", "ID", 50), ("title", "Title", 220), ("faculty_name", "Faculty", 160),
             ("subject", "Subject", 110), ("difficulty_level", "Level", 70),
             ("question_count", "Questions", 80), ("total_marks", "Marks", 60),
             ("status", "Status", 80)]
    quizzes = gui._tree(quiz_tab, qcols)

    def refresh_quizzes():
        gui._fill(quizzes, gui.user.manage_quizzes(), "quiz_id", [c[0] for c in qcols])

    @gui._guard
    def delete_quiz():
        qid = gui._selected_id(quizzes, "quiz")
        if messagebox.askyesno("Delete quiz", "Delete this quiz with its questions and results?"):
            gui.user.delete_quiz(qid)
            refresh_quizzes()

    row = ttk.Frame(quiz_tab)
    row.pack(fill="x", pady=6)
    ttk.Button(row, text="Delete Quiz", command=delete_quiz).pack(side="left", padx=4)
    ttk.Button(row, text="Refresh", command=refresh_quizzes).pack(side="left", padx=4)
    refresh_quizzes()

    # Reports tab
    rep_tab = ttk.Frame(tabs, padding=8)
    tabs.add(rep_tab, text="Overall Reports")
    summary = ttk.Label(rep_tab, style="Head.TLabel", justify="left")
    summary.pack(anchor="w", pady=(0, 6))
    ttk.Label(rep_tab, text="Quiz-wise performance").pack(anchor="w")
    rcols = [("title", "Quiz", 300), ("attempts", "Attempts", 90), ("avg_pct", "Average %", 100)]
    rtree = gui._tree(rep_tab, rcols, height=6)
    ttk.Label(rep_tab, text="Student ranking (average %)").pack(anchor="w", pady=(8, 0))
    stree = gui._tree(rep_tab, [("full_name", "Student", 300), ("attempts", "Attempts", 90),
                                 ("avg_pct", "Average %", 100)], height=6)
    state = {"report": None}

    def refresh_reports():
        rep = gui.user.view_overall_reports()
        state["report"] = rep
        summary.config(text=(f"Attempts: {rep['total_attempts']}    Average: {rep['average_score']}%    "
                             f"Highest: {rep['highest_score']}%    Lowest: {rep['lowest_score']}%    "
                             f"Trend: {rep['performance_trend']}"))
        rtree.delete(*rtree.get_children())
        for q in rep["quizzes"]:
            rtree.insert("", "end", values=(q["title"], q["attempts"], q["avg_pct"] or 0))
        stree.delete(*stree.get_children())
        for s in rep["students"]:
            stree.insert("", "end", values=(s["full_name"], s["attempts"], s["avg_pct"]))

    @gui._guard
    def chart():
        rep = state["report"]
        with_data = list(filter(lambda q: q["attempts"], rep["quizzes"]))
        gui._show_chart([q["title"][:16] for q in with_data],
                         [q["avg_pct"] for q in with_data], "Average score by quiz")

    row = ttk.Frame(rep_tab)
    row.pack(fill="x", pady=6)
    ttk.Button(row, text="Show Chart", command=chart).pack(side="left", padx=4)
    ttk.Button(row, text="Refresh", command=refresh_reports).pack(side="left", padx=4)
    refresh_reports()
