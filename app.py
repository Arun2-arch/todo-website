"""A small to-do list website built with Flask + SQLite.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""
import os
import sqlite3
from flask import Flask, g, redirect, render_template, request, url_for

app = Flask(__name__)
DATABASE = os.path.join(os.path.dirname(__file__), "todos.db")


# ---------- database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DATABASE) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS todos (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   title TEXT NOT NULL,
                   done INTEGER NOT NULL DEFAULT 0,
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )


# ---------- routes ----------
@app.route("/")
def index():
    view = request.args.get("view", "all")
    query = "SELECT * FROM todos"
    if view == "active":
        query += " WHERE done = 0"
    elif view == "done":
        query += " WHERE done = 1"
    query += " ORDER BY done ASC, id DESC"

    db = get_db()
    todos = db.execute(query).fetchall()
    counts = db.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(done), 0) AS done FROM todos"
    ).fetchone()
    return render_template(
        "index.html",
        todos=todos,
        view=view,
        total=counts["total"],
        done=counts["done"],
        left=counts["total"] - counts["done"],
    )


@app.post("/add")
def add():
    title = request.form.get("title", "").strip()
    if title:
        db = get_db()
        db.execute("INSERT INTO todos (title) VALUES (?)", (title[:200],))
        db.commit()
    return redirect(url_for("index", view=request.form.get("view", "all")))


@app.post("/toggle/<int:todo_id>")
def toggle(todo_id):
    db = get_db()
    db.execute("UPDATE todos SET done = 1 - done WHERE id = ?", (todo_id,))
    db.commit()
    return redirect(url_for("index", view=request.form.get("view", "all")))


@app.post("/edit/<int:todo_id>")
def edit(todo_id):
    title = request.form.get("title", "").strip()
    if title:
        db = get_db()
        db.execute("UPDATE todos SET title = ? WHERE id = ?", (title[:200], todo_id))
        db.commit()
    return redirect(url_for("index", view=request.form.get("view", "all")))


@app.post("/delete/<int:todo_id>")
def delete(todo_id):
    db = get_db()
    db.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    db.commit()
    return redirect(url_for("index", view=request.form.get("view", "all")))


@app.post("/clear-done")
def clear_done():
    db = get_db()
    db.execute("DELETE FROM todos WHERE done = 1")
    db.commit()
    return redirect(url_for("index", view=request.form.get("view", "all")))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
