"""
FRONTEND LAYER  -  frontend/app.py   (main window)

QuizGUI owns the Tk root window, the shared helper methods (header bar, tables, error
handling, charts), the login / registration / profile screens, and hands over to the
role dashboards. After login it calls user.show_dashboard(self) - polymorphism picks
the right dashboard for Admin, Faculty or Student.
"""
import tkinter as tk
from tkinter import messagebox, ttk

from backend.analysis import ScoreAnalysis
from backend.users import User
from exceptions import QuizAppError, ValidationError
from frontend.admin_screen import build_admin_dashboard
from frontend.dialogs import FormDialog
from frontend.faculty_screen import build_faculty_dashboard
from frontend.quiz_screens import show_result, start_quiz
from frontend.student_screen import build_student_dashboard


class QuizGUI:
    def __init__(self, db):
        self.db = db
        self.user = None
        self.root = tk.Tk()
        self.root.title("Online Quiz Application")
        self.root.geometry("1020x660")
        self.root.minsize(900, 560)
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Sub.TLabel", font=("Segoe UI", 10), foreground="#555")
        style.configure("Head.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Treeview", rowheight=24)
        self.root.report_callback_exception = self._on_tk_error
        self.show_login()

    def run(self):
        self.root.mainloop()

    # ---- shared helpers -------------------------------------------------
    def _on_tk_error(self, exc_type, exc, tb):
        if issubclass(exc_type, QuizAppError):
            messagebox.showerror("Error", str(exc))
        else:
            messagebox.showerror("Unexpected error", f"{exc_type.__name__}: {exc}")

    def _clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def _header(self, subtitle):
        bar = ttk.Frame(self.root, padding=(14, 10))
        bar.pack(fill="x")
        left = ttk.Frame(bar)
        left.pack(side="left")
        ttk.Label(left, text="Online Quiz Application", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text=subtitle, style="Sub.TLabel").pack(anchor="w")
        right = ttk.Frame(bar)
        right.pack(side="right")
        ttk.Label(right, text=f"{self.user.full_name} ({self.user.role})").pack(side="left", padx=10)
        ttk.Button(right, text="Profile", command=self.show_profile).pack(side="left", padx=3)
        ttk.Button(right, text="Logout", command=self.logout).pack(side="left", padx=3)
        ttk.Separator(self.root).pack(fill="x")
        body = ttk.Frame(self.root, padding=10)
        body.pack(fill="both", expand=True)
        return body

    def _tree(self, parent, columns, height=12):
        """columns = [(id, heading, width)] -> Treeview inside a scrolling frame."""
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                            height=height, selectmode="browse")
        for cid, heading, width in columns:
            tree.heading(cid, text=heading)
            tree.column(cid, width=width, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    @staticmethod
    def _selected_id(tree, what="item"):
        sel = tree.selection()
        if not sel:
            raise ValidationError(f"Please select a {what} first.")
        return int(sel[0])

    @staticmethod
    def _fill(tree, rows, key, columns):
        selected = tree.selection()          # keep the user's selection across refreshes
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", iid=str(row[key]), values=[row[c] for c in columns])
        still_there = [i for i in selected if tree.exists(i)]
        if still_there:
            tree.selection_set(still_there)

    def _guard(self, func):
        """Wrap a button callback so QuizAppErrors become friendly dialogs."""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except QuizAppError as exc:
                messagebox.showerror("Error", str(exc))
        return wrapper

    def _show_text(self, title, text, width=80, height=26):
        win = tk.Toplevel(self.root)
        win.title(title)
        box = tk.Text(win, width=width, height=height, wrap="word", font=("Consolas", 10))
        box.insert("1.0", text)
        box.configure(state="disabled")
        box.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 8))

    def _show_chart(self, labels, values, title):
        if not values:
            raise ValidationError("There is no data to chart yet.")
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        fig = ScoreAnalysis(self.db).plot_chart(labels, values, title)
        win = tk.Toplevel(self.root)
        win.title(title)
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=6)

    # ---- login / registration --------------------------------------------
    def show_login(self):
        self._clear()
        self.user = None
        outer = ttk.Frame(self.root)
        outer.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(outer, text="Online Quiz Application", style="Title.TLabel").pack(pady=(0, 2))
        ttk.Label(outer, text="with Score Analysis and Database Integration",
                  style="Sub.TLabel").pack(pady=(0, 18))
        form = ttk.Frame(outer)
        form.pack()
        ttk.Label(form, text="Email").grid(row=0, column=0, sticky="e", padx=6, pady=5)
        email = ttk.Entry(form, width=34)
        email.grid(row=0, column=1, pady=5)
        ttk.Label(form, text="Password").grid(row=1, column=0, sticky="e", padx=6, pady=5)
        password = ttk.Entry(form, width=34, show="*")
        password.grid(row=1, column=1, pady=5)
        email.focus()

        @self._guard
        def do_login(_event=None):
            self.user = User.authenticate(self.db, email.get(), password.get())
            self.user.show_dashboard(self)  # polymorphic call

        btns = ttk.Frame(outer)
        btns.pack(pady=14)
        ttk.Button(btns, text="Login", command=do_login).pack(side="left", padx=6)
        ttk.Button(btns, text="Register as Student", command=self.register_student).pack(side="left", padx=6)
        self.root.bind("<Return>", do_login)
        ttk.Label(outer, style="Sub.TLabel", justify="center",
                  text="Demo: admin@quiz.com / admin123   |   faculty@quiz.com / faculty123\n"
                       "student@quiz.com / student123").pack(pady=(10, 0))

    def register_student(self):
        dialog = FormDialog(self.root, "Student Registration", [
            ("Full name", "name", "entry", None), ("Email", "email", "entry", None),
            ("Password (min 6)", "password", "password", None),
            ("Roll number", "roll", "entry", None), ("Class / Grade", "grade", "entry", None)])
        if not dialog.result:
            return
        r = dialog.result
        try:
            User.register(self.db, r["name"], r["email"], r["password"], "Student",
                          roll_no=r["roll"], class_grade=r["grade"])
            messagebox.showinfo("Registered", "Account created. You can now log in.")
        except QuizAppError as exc:
            messagebox.showerror("Error", str(exc))

    def logout(self):
        if self.user:
            self.user.logout()
        self.root.unbind("<Return>")
        self.show_login()

    def show_profile(self):
        dialog = FormDialog(self.root, "My Profile", [
            ("Full name", "name", "entry", None), ("Email", "email", "entry", None),
            ("Current password (only to change it)", "old", "password", None),
            ("New password", "new", "password", None)])
        if not dialog.result:
            return
        r = dialog.result
        try:
            if r["name"] or r["email"]:
                self.user.update_profile(r["name"] or self.user.full_name,
                                         r["email"] or self.user.email)
            if r["new"]:
                self.user.change_password(r["old"], r["new"])
            messagebox.showinfo("Profile", "Profile updated.")
        except QuizAppError as exc:
            messagebox.showerror("Error", str(exc))

    # ---- each role's screens live in their own module -----------------------
    def show_admin_dashboard(self):
        build_admin_dashboard(self)

    def show_faculty_dashboard(self):
        build_faculty_dashboard(self)

    def show_student_dashboard(self):
        build_student_dashboard(self)

    def start_quiz(self, quiz_id, on_done=None):
        start_quiz(self, quiz_id, on_done)

    def show_result(self, result_id):
        show_result(self, result_id)
