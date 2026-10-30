
"""
FRONTEND LAYER - frontend/quiz_screens.py
Attempt and result screens with multithreaded countdown timer.
"""
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import queue

from backend.quiz import Quiz
from backend.attempt import Result
from exceptions import QuizAppError


def start_quiz(gui, quiz_id, on_done=None):
    attempt = gui.user.start_attempt(quiz_id)
    quiz = Quiz.load(gui.db, quiz_id)
    questions = quiz.get_questions()

    win = tk.Toplevel(gui.root)
    win.title(f"Quiz - {quiz.title}")
    win.geometry("780x600")
    win.transient(gui.root)

    try:
        win.grab_set()
    except tk.TclError:
        pass

    top = ttk.Frame(win, padding=8)
    top.pack(fill="x")
    ttk.Label(top, text=quiz.title, style="Head.TLabel").pack(side="left")
    timer = ttk.Label(top, text="")
    timer.pack(side="right")

    holder = ttk.Frame(win)
    holder.pack(fill="both", expand=True)
    canvas = tk.Canvas(holder, highlightthickness=0)
    scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)

    inner.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=inner, anchor="nw", width=730)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    choices = {}

    for number, q in enumerate(questions, 1):
        box = ttk.LabelFrame(
            inner,
            text=f"Q{number} ({q.marks} mark{'s' if q.marks > 1 else ''})"
                 f"{' - ' + q.topic if q.topic else ''}",
            padding=8
        )
        box.pack(fill="x", padx=8, pady=5)

        ttk.Label(
            box,
            text=q.question_text,
            wraplength=680,
            justify="left"
        ).pack(anchor="w")

        var = tk.IntVar(value=0)
        choices[q.question_id] = var

        for opt in q.get_options():
            ttk.Radiobutton(
                box,
                text=opt.option_text,
                variable=var,
                value=opt.option_id
            ).pack(anchor="w", padx=14, pady=1)

    state = {"done": False, "left": quiz.time_limit * 60}
    stop_timer = threading.Event()
    timer_queue = queue.Queue()

    def countdown_worker():
        remaining = quiz.time_limit * 60

        while remaining > 0 and not stop_timer.wait(1):
            remaining -= 1
            timer_queue.put(remaining)

    if quiz.time_limit:
        threading.Thread(
            target=countdown_worker,
            daemon=True
        ).start()

    def finish(auto=False):
        if state["done"]:
            return

        selections = {
            qid: (var.get() or None)
            for qid, var in choices.items()
        }

        unanswered = sum(
            1 for v in selections.values() if v is None
        )

        if not auto and unanswered and not messagebox.askyesno(
            "Submit quiz",
            f"{unanswered} question(s) unanswered. Submit anyway?",
            parent=win
        ):
            return

        state["done"] = True
        stop_timer.set()

        try:
            result = attempt.submit(selections)
        except QuizAppError as exc:
            state["done"] = False
            messagebox.showerror("Error", str(exc), parent=win)
            return

        gui.show_result(result.result_id)

        if on_done:
            on_done()

        win.destroy()

    def tick():
        if state["done"] or not win.winfo_exists():
            return

        if quiz.time_limit:
            try:
                while True:
                    state["left"] = timer_queue.get_nowait()
            except queue.Empty:
                pass

            mins, secs = divmod(state["left"], 60)
            timer.config(text=f"Time left: {mins:02d}:{secs:02d}")

            if state["left"] <= 0:
                messagebox.showinfo(
                    "Time up",
                    "Time is up - submitting your answers.",
                    parent=win
                )
                finish(auto=True)
                return
        else:
            timer.config(text="No time limit")

        win.after(200, tick)

    def on_close():
        if messagebox.askyesno(
            "Leave quiz",
            "Leave without submitting? Your answers will be lost.",
            parent=win
        ):
            state["done"] = True
            stop_timer.set()
            win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)

    ttk.Button(
        win,
        text="Submit Quiz",
        command=finish
    ).pack(pady=8)

    tick()


def show_result(gui, result_id):
    summary, review = Result.load_details(gui.db, result_id)

    lines = [
        f"Quiz        : {summary['title']}",
        f"Score       : {summary['total_score']} / {summary['total_marks']}",
        f"Percentage  : {summary['percentage']}%",
        f"Correct     : {summary['correct_count']}",
        f"Incorrect   : {summary['incorrect_count']} "
        f"(of {summary['total_questions']} questions)",
        f"Time taken  : {summary['time_taken']} seconds",
        "",
        "-" * 60,
        ""
    ]

    for i, r in enumerate(review, 1):
        mark = "CORRECT" if r["is_correct"] else "WRONG"

        lines.append(
            f"Q{i}. {r['question_text']} "
            f"[{mark}, {r['marks_awarded']}/{r['marks']}]"
        )

        lines.append(
            f"     Your answer   : {r['chosen'] or '(not answered)'}"
        )

        if not r["is_correct"]:
            lines.append(
                f"     Correct answer: {r['correct_text']}"
            )

        lines.append("")

    gui._show_text(
        f"Result - {summary['title']}",
        "\n".join(lines),
        width=84,
        height=28
    )
