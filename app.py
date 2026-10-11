import json, os, threading, uuid
from flask import Flask, Response, jsonify, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Todo List</title>
<style>
  :root { --bg:#f5f5f0; --card:#fff; --text:#1f2933; --muted:#7b8794; --accent:#2f7d6d; --line:#e4e7eb; --danger:#c0392b; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#14181c; --card:#1d2329; --text:#e6e9ec; --muted:#8793a0; --accent:#4cb8a3; --line:#2c343c; --danger:#e57373; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif; }
  main { max-width:560px; margin:6vh auto; padding:0 16px; }
  h1 { font-size:2rem; margin:0 0 16px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:14px; overflow:hidden; }
  form { display:flex; border-bottom:1px solid var(--line); }
  input[type=text] { flex:1; border:0; padding:16px; font-size:1rem; background:transparent; color:inherit; outline:none; }
  button { font:inherit; cursor:pointer; border:0; background:none; color:var(--muted); }
  form button { padding:0 20px; background:var(--accent); color:#fff; font-weight:600; }
  ul { list-style:none; margin:0; padding:0; }
  li { display:flex; align-items:center; gap:12px; padding:12px 16px; border-bottom:1px solid var(--line); }
  li input { width:20px; height:20px; accent-color:var(--accent); }
  li span { flex:1; word-break:break-word; }
  li.done span { text-decoration:line-through; color:var(--muted); }
  li .del { font-size:1.3rem; line-height:1; }
  li .del:hover { color:var(--danger); }
  footer { display:flex; justify-content:space-between; align-items:center; padding:10px 16px; font-size:.875rem; color:var(--muted); }
  .filters button { padding:4px 8px; border-radius:6px; }
  .filters button.active { color:var(--accent); background:color-mix(in srgb,var(--accent) 12%,transparent); font-weight:600; }
  .empty { padding:24px; text-align:center; color:var(--muted); }
  #error { color:var(--danger); font-size:.875rem; margin-top:8px; min-height:1.2em; }
</style>
</head>
<body>
<main>
  <h1>Todo List</h1>
  <div class="card">
    <form id="form">
      <input type="text" id="title" placeholder="What needs doing?" maxlength="200" autocomplete="off" autofocus>
      <button type="submit">Add</button>
    </form>
    <ul id="list"></ul>
    <footer>
      <span id="count"></span>
      <span class="filters">
        <button data-f="all" class="active">All</button>
        <button data-f="active">Active</button>
        <button data-f="done">Done</button>
      </span>
      <button id="clear">Clear done</button>
    </footer>
  </div>
  <div id="error"></div>
</main>
<script>
let todos = [], filter = "all";
const $ = id => document.getElementById(id);

async function api(path, method = "GET", body) {
  const res = await fetch("/api/todos" + path, {
    method, headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || "Request failed");
  return res.status === 204 ? null : res.json();
}

async function refresh() {
  try { todos = await api(""); $("error").textContent = ""; }
  catch (e) { $("error").textContent = e.message; }
  render();
}

function render() {
  const shown = todos.filter(t => filter === "all" || (filter === "done") === t.done);
  const list = $("list");
  list.innerHTML = "";
  if (!shown.length) list.innerHTML = '<div class="empty">Nothing here yet.</div>';
  for (const t of shown) {
    const li = document.createElement("li");
    li.className = t.done ? "done" : "";
    const cb = Object.assign(document.createElement("input"), { type: "checkbox", checked: t.done });
    cb.onchange = () => act(() => api("/" + t.id, "PATCH", { done: cb.checked }));
    const span = document.createElement("span");
    span.textContent = t.title;
    const del = Object.assign(document.createElement("button"), { className: "del", textContent: "×", title: "Delete" });
    del.onclick = () => act(() => api("/" + t.id, "DELETE"));
    li.append(cb, span, del);
    list.append(li);
  }
  const left = todos.filter(t => !t.done).length;
  $("count").textContent = `${left} item${left === 1 ? "" : "s"} left`;
}

async function act(fn) {
  try { await fn(); await refresh(); }
  catch (e) { $("error").textContent = e.message; }
}

$("form").onsubmit = e => {
  e.preventDefault();
  const title = $("title").value.trim();
  if (!title) return;
  $("title").value = "";
  act(() => api("", "POST", { title }));
};
$("clear").onclick = () => act(() => api("", "DELETE"));
document.querySelectorAll(".filters button").forEach(b => b.onclick = () => {
  filter = b.dataset.f;
  document.querySelectorAll(".filters button").forEach(x => x.classList.toggle("active", x === b));
  render();
});

refresh();
</script>
</body>
</html>
"""

# --- Storage -----------------------------------------------------------
# DATABASE_URL set (Neon Postgres, added via Vercel)  -> Postgres
# otherwise                                            -> local JSON file
DB_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
lock = threading.Lock()


class PgStore:
    """One row per todo. A new connection per request suits serverless."""

    _ready = False

    def _conn(self):
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(DB_URL, row_factory=dict_row, autocommit=True, connect_timeout=10)
        if not PgStore._ready:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS todos (
                       id TEXT PRIMARY KEY,
                       title TEXT NOT NULL,
                       done BOOLEAN NOT NULL DEFAULT FALSE,
                       created_at TIMESTAMPTZ NOT NULL DEFAULT now())"""
            )
            PgStore._ready = True
        return conn

    @staticmethod
    def _row(r):
        return {"id": r["id"], "title": r["title"], "done": bool(r["done"])}

    def all(self):
        with self._conn() as c:
            rows = c.execute("SELECT id, title, done FROM todos ORDER BY created_at, id").fetchall()
        return [self._row(r) for r in rows]

    def add(self, title):
        todo_id = uuid.uuid4().hex
        with self._conn() as c:
            c.execute("INSERT INTO todos (id, title) VALUES (%s, %s)", (todo_id, title))
        return {"id": todo_id, "title": title, "done": False}

    def update(self, todo_id, done=None, title=None):
        with self._conn() as c:
            r = c.execute(
                "UPDATE todos SET done = COALESCE(%s, done), title = COALESCE(%s, title) "
                "WHERE id = %s RETURNING id, title, done",
                (done, title, todo_id),
            ).fetchone()
        return self._row(r) if r else None

    def delete(self, todo_id):
        with self._conn() as c:
            c.execute("DELETE FROM todos WHERE id = %s", (todo_id,))

    def clear_done(self):
        with self._conn() as c:
            c.execute("DELETE FROM todos WHERE done")


class FileStore:
    """Local development fallback (data/todos.json)."""

    def __init__(self):
        self.path = os.path.join(BASE_DIR, "data", "todos.json")
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        except OSError:
            self.path = "/tmp/todos.json"

    def _load(self):
        try:
            with open(self.path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self, todos):
        with open(self.path, "w") as f:
            json.dump(todos, f, indent=2)

    def all(self):
        return self._load()

    def add(self, title):
        todo = {"id": uuid.uuid4().hex, "title": title, "done": False}
        with lock:
            todos = self._load()
            todos.append(todo)
            self._save(todos)
        return todo

    def update(self, todo_id, done=None, title=None):
        with lock:
            todos = self._load()
            for t in todos:
                if t["id"] == todo_id:
                    if done is not None:
                        t["done"] = done
                    if title:
                        t["title"] = title
                    self._save(todos)
                    return t
        return None

    def delete(self, todo_id):
        with lock:
            self._save([t for t in self._load() if t["id"] != todo_id])

    def clear_done(self):
        with lock:
            self._save([t for t in self._load() if not t["done"]])


store = PgStore() if DB_URL else FileStore()


# --- Routes ------------------------------------------------------------
@app.get("/")
def index():
    return Response(PAGE, mimetype="text/html")


@app.get("/api/todos")
def list_todos():
    return jsonify(store.all())


@app.post("/api/todos")
def add_todo():
    title = (request.get_json(silent=True) or {}).get("title", "").strip()
    if not title:
        return jsonify(error="Title is required"), 400
    return jsonify(store.add(title[:200])), 201


@app.patch("/api/todos/<todo_id>")
def update_todo(todo_id):
    body = request.get_json(silent=True) or {}
    done = bool(body["done"]) if "done" in body else None
    title = (body.get("title") or "").strip()[:200] or None
    todo = store.update(todo_id, done, title)
    return (jsonify(todo), 200) if todo else (jsonify(error="Not found"), 404)


@app.delete("/api/todos/<todo_id>")
def delete_todo(todo_id):
    store.delete(todo_id)
    return "", 204


@app.delete("/api/todos")
def clear_completed():
    store.clear_done()
    return "", 204


@app.errorhandler(Exception)
def on_error(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return jsonify(error=e.description), e.code
    app.logger.exception("Unhandled error")
    return jsonify(error="Server error - check the logs"), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
