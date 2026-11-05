"""Loopback-only research prototype. One local test identity; not a multi-user server."""

import csv
import io
import json
import os
import secrets
import sqlite3
import threading
import traceback
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import requests
from app.core import (
    ROOT,
    CODEBOOK,
    FIELDS,
    uid,
    digest,
    normalize_conversation,
    validate_document,
    required_issues,
    IncompleteAnnotation,
    to_ls,
    from_ls,
)
from app.extractor import extract_chatgpt_conversation

LOCAL = Path(os.environ.get("ANNOTATION_DATA", ROOT / ".local")).resolve()
LOCAL.mkdir(parents=True, exist_ok=True)
try:
    LOCAL.chmod(0o700)
except OSError:
    pass
DB = LOCAL / "app.sqlite3"
LOCK = threading.RLock()
CSRF = secrets.token_urlsafe(32)


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    con = sqlite3.connect(DB, timeout=20)
    con.row_factory = sqlite3.Row
    return con


def initialize():
    with connect() as con:
        con.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS previews(id TEXT PRIMARY KEY, data TEXT NOT NULL, demo INTEGER NOT NULL, created_at TEXT NOT NULL, conversation_id TEXT);
        CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, data TEXT NOT NULL, draft TEXT NOT NULL,
          revision INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          task_id INTEGER, annotation_id INTEGER, sync_error TEXT, synced_version INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS submissions(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
          version INTEGER NOT NULL, document TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(conversation_id,version));
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        columns = {row[1] for row in con.execute("PRAGMA table_info(submissions)")}
        if "requirements_version" not in columns:
            con.execute(
                "ALTER TABLE submissions ADD COLUMN requirements_version TEXT NOT NULL DEFAULT 'legacy-optional-v1'"
            )
        # Preview text expires; confirmed source content lives in conversations.
        con.execute(
            "DELETE FROM previews WHERE conversation_id IS NULL AND created_at < ?",
            (
                datetime.fromtimestamp(
                    datetime.now().timestamp() - 86400, timezone.utc
                ).isoformat(),
            ),
        )


def get_record(cid):
    with connect() as con:
        row = con.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    if not row:
        raise LookupError("Conversation not found.")
    return dict(row)


def latest(cid):
    with connect() as con:
        row = con.execute(
            "SELECT * FROM submissions WHERE conversation_id=? ORDER BY version DESC LIMIT 1",
            (cid,),
        ).fetchone()
    return dict(row) if row else None


def public_record(row):
    sub = latest(row["id"])
    data = json.loads(row["data"])
    document = validate_document(json.loads(row["draft"]), data)
    return {
        "id": row["id"],
        "data": data,
        "document": document,
        "revision": row["revision"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "submission_version": sub["version"] if sub else 0,
        "has_changes": sub is None
        or json.loads(sub["document"]) != json.loads(row["draft"]),
        "synced_version": row["synced_version"],
        "sync_error": row["sync_error"],
        "task_id": row["task_id"],
        "annotation_id": row["annotation_id"],
        "requirements_version": sub["requirements_version"] if sub else None,
    }


def ls_config():
    path = LOCAL / "ls_connection.json"
    if not path.exists():
        raise ValueError(
            "Label Studio is not configured. Start it with scripts/start_local.py."
        )
    cfg = json.loads(path.read_text())
    # This prototype never sends source content or its token to a remote host.
    if cfg["url"] != "http://127.0.0.1:8080":
        raise ValueError("Only local Label Studio on port 8080 is supported.")
    return cfg


def ls_request(method, path, payload=None):
    cfg = ls_config()
    try:
        session = requests.Session()
        session.trust_env = False
        try:
            r = session.request(
                method,
                cfg["url"] + path,
                json=payload,
                headers={"Authorization": "Token " + cfg["token"]},
                timeout=(3, 25),
                allow_redirects=False,
            )
        finally:
            session.close()
        if not 200 <= r.status_code < 300:
            # Avoid returning tokens, source text, or full upstream error bodies.
            raise ValueError(
                f"Label Studio returned HTTP {r.status_code}. Check .local/label-studio.log."
            )
        return r.json() if r.content else None
    except requests.RequestException as exc:
        raise ValueError(
            "Cannot reach local Label Studio. Your local data is saved; start Label Studio and retry sync."
        ) from exc


def ls_items(value):
    return (
        value
        if isinstance(value, list)
        else value.get("results", value.get("tasks", []))
    )


def ensure_project():
    with connect() as con:
        saved = con.execute(
            "SELECT value FROM settings WHERE key='project_id'"
        ).fetchone()
    if saved:
        ls_request("GET", f"/api/projects/{int(saved[0])}/")
        return int(saved[0])
    title = os.environ.get("ANNOTATION_LS_PROJECT_TITLE", "Annotation Local Pilot")
    projects = ls_items(ls_request("GET", "/api/projects/?page_size=100"))
    existing = next((p for p in projects if p.get("title") == title), None)
    config = (ROOT / "config/label_config.xml").read_text()
    if existing:
        pid = existing["id"]
    else:
        p = ls_request(
            "POST",
            "/api/projects/",
            {
                "title": title,
                "label_config": config,
                "description": "Local Annotation prototype. Participant identity is TEST01 in app data; API author is the local service account.",
                "enable_empty_annotation": True,
            },
        )
        pid = p["id"]
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO settings VALUES ('project_id',?)", (str(pid),)
        )
    return pid


def ensure_task(cid):
    row = get_record(cid)
    if row["task_id"]:
        return row["task_id"]
    pid = ensure_project()
    # Reconcile ambiguous timeouts before retrying creation.
    found = None
    page = 1
    while True:
        response = ls_request(
            "GET", f"/api/tasks/?project={pid}&page={page}&page_size=100"
        )
        items = ls_items(response)
        found = next(
            (t for t in items if t.get("data", {}).get("conversation_id") == cid), None
        )
        if found or len(items) < 100:
            break
        page += 1
        if page > 100:
            raise ValueError("Too many local tasks to reconcile safely.")
    if not found:
        found = ls_request(
            "POST", "/api/tasks/", {"project": pid, "data": json.loads(row["data"])}
        )
    tid = found["id"]
    with connect() as con:
        con.execute(
            "UPDATE conversations SET task_id=?,sync_error=NULL WHERE id=?", (tid, cid)
        )
    return tid


def sync(cid):
    with LOCK:
        try:
            tid = ensure_task(cid)
            sub = latest(cid)
            if not sub:
                return
            row = get_record(cid)
            if row["synced_version"] == sub["version"]:
                return
            results = to_ls(json.loads(sub["document"]), json.loads(row["data"]))
            aid = row["annotation_id"]
            if not aid:
                task = ls_request("GET", f"/api/tasks/{tid}/")
                existing = next(
                    (
                        a
                        for a in task.get("annotations", [])
                        if a.get("unique_id") == cid
                    ),
                    None,
                )
                aid = existing["id"] if existing else None
            payload = {"result": results, "was_cancelled": False, "ground_truth": False}
            if aid:
                ls_request("PATCH", f"/api/annotations/{aid}/", payload)
            else:
                payload["unique_id"] = cid
                aid = ls_request("POST", f"/api/tasks/{tid}/annotations/", payload)[
                    "id"
                ]
            fetched = ls_request("GET", f"/api/tasks/{tid}/")
            returned = next(
                (a for a in fetched.get("annotations", []) if a["id"] == aid), None
            )
            if not returned or digest(returned["result"]) != digest(results):
                raise ValueError(
                    "Label Studio round-trip verification failed. Local submission is intact."
                )
            with connect() as con:
                con.execute(
                    "UPDATE conversations SET annotation_id=?,synced_version=?,sync_error=NULL WHERE id=?",
                    (aid, sub["version"], cid),
                )
        except ValueError as exc:
            with connect() as con:
                con.execute(
                    "UPDATE conversations SET sync_error=? WHERE id=?", (str(exc), cid)
                )


def export_data(cid=None, include_raw=False):
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM conversations"
            + (" WHERE id=?" if cid else "")
            + " ORDER BY created_at",
            (cid,) if cid else (),
        ).fetchall()
    conversations = []
    raw = []
    failures = []
    for row in rows:
        sub = latest(row["id"])
        if not sub:
            continue
        data = json.loads(row["data"])
        document = json.loads(sub["document"])
        entry = {
            "conversation_id": row["id"],
            "participant_id": "TEST01",
            "conversation": data,
            "submission_id": sub["id"],
            "submission_version": sub["version"],
            "requirements_version": sub["requirements_version"],
            "submitted_at": sub["created_at"],
            "annotation": document,
            "text_sha256": digest(data["dialogue"]),
            "label_studio": {
                "task_id": row["task_id"],
                "annotation_id": row["annotation_id"],
                "synced_version": row["synced_version"],
            },
        }
        conversations.append(entry)
        if row["synced_version"] != sub["version"]:
            failures.append(
                {
                    "conversation_id": row["id"],
                    "reason": "Latest submission is not synced to Label Studio.",
                }
            )
        elif include_raw:
            try:
                task = ls_request("GET", f"/api/tasks/{row['task_id']}/")
                annotation = next(
                    a
                    for a in task.get("annotations", [])
                    if a["id"] == row["annotation_id"]
                )
                if digest(annotation["result"]) != digest(to_ls(document, data)):
                    raise ValueError(
                        "Remote annotation was modified; local submitted version is authoritative."
                    )
                # Restrict raw export to app-owned submitted annotation and remove staff metadata.
                raw.append(
                    {
                        "id": task["id"],
                        "data": task["data"],
                        "annotations": [
                            {"id": annotation["id"], "result": annotation["result"]}
                        ],
                        "provenance": {
                            "api_author": "local-service-account",
                            "participant_id": "TEST01",
                        },
                    }
                )
            except (ValueError, StopIteration):
                failures.append(
                    {
                        "conversation_id": row["id"],
                        "reason": "Could not verify or retrieve matching Label Studio results.",
                    }
                )
    if not conversations:
        raise ValueError(
            "No submitted annotations are available. Submit this conversation first, or download its current JSON."
        )
    return {
        "schema_version": "1.0",
        "exported_at": now(),
        "codebook_version": CODEBOOK["version"],
        "selection": "latest submitted version per conversation; drafts excluded",
        "participant_mode": "single local TEST01 identity; not a recruited participant sample",
        "conversations": conversations,
        "sync_warnings": failures,
    }, raw


def current_export(cid):
    row = get_record(cid)
    data = json.loads(row["data"])
    document = json.loads(row["draft"])
    submission = latest(cid)
    is_submitted = (
        submission is not None and json.loads(submission["document"]) == document
    )
    return {
        "schema_version": "1.0",
        "exported_at": now(),
        "codebook_version": CODEBOOK["version"],
        "requirements_version": CODEBOOK["requirements_version"],
        "selection": "current saved work; may include unsubmitted draft answers",
        "conversations": [
            {
                "conversation_id": cid,
                "participant_id": data.get("participant_id", "TEST01"),
                "status": "submitted" if is_submitted else "draft",
                "conversation": data,
                "annotation": document,
                "saved_at": row["updated_at"],
                "latest_submission_version": submission["version"] if submission else 0,
                "requirements_version": (
                    submission["requirements_version"]
                    if is_submitted
                    else CODEBOOK["requirements_version"]
                ),
                "text_sha256": digest(data["dialogue"]),
            }
        ],
    }


def safe_csv(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    value = "" if value is None else str(value)
    # Prevent formulas when exported research text is opened in a spreadsheet.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def csv_text(headers, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([safe_csv(v) for v in row])
    return "\ufeff" + stream.getvalue()


def zip_export(cid=None):
    export, raw = export_data(cid, True)
    if not export["conversations"]:
        raise ValueError(
            "Submit at least one conversation before exporting research data."
        )
    convrows = []
    regionrows = []
    choicerows = []
    for item in export["conversations"]:
        c = item["conversation"]
        d = item["annotation"]
        cid = item["conversation_id"]
        convrows.append(
            [
                cid,
                item["participant_id"],
                c["title"],
                item["submission_version"],
                item["submitted_at"],
                len(c["dialogue"]),
                d["context"],
            ]
        )
        for r in d["regions"]:
            regionrows.append(
                [cid, r["id"], r["passage_type"], r["segments"], r["answers"]]
            )
            for name, value in r["answers"].items():
                if isinstance(value, list):
                    for choice in value:
                        choicerows.append([cid, r["id"], name, choice])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("annotations.json", json.dumps(export, ensure_ascii=False, indent=2))
        z.writestr(
            "label_studio_raw.json", json.dumps(raw, ensure_ascii=False, indent=2)
        )
        z.writestr("codebook.json", json.dumps(CODEBOOK, ensure_ascii=False, indent=2))
        z.writestr(
            "conversations.csv",
            csv_text(
                [
                    "conversation_id",
                    "participant_id",
                    "title",
                    "submission_version",
                    "submitted_at",
                    "message_count",
                    "context_answers_json",
                ],
                convrows,
            ),
        )
        z.writestr(
            "regions.csv",
            csv_text(
                [
                    "conversation_id",
                    "region_id",
                    "passage_type",
                    "segments_json",
                    "answers_json",
                ],
                regionrows,
            ),
        )
        z.writestr(
            "region_choices.csv",
            csv_text(["conversation_id", "region_id", "field", "choice"], choicerows),
        )
        z.writestr(
            "manifest.json",
            json.dumps(
                {k: v for k, v in export.items() if k != "conversations"}
                | {
                    "conversation_count": len(convrows),
                    "region_count": len(regionrows),
                    "verified_raw_task_count": len(raw),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        z.write(ROOT / "docs/data_dictionary.md", "data_dictionary.md")
    return buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = "AnnotationLocal/1.0"

    def log_message(self, fmt, *args):
        # No request URLs, body text or credentials in access logs.
        pass

    def guard(self, mutation=False):
        host = self.headers.get("Host", "").split(":")[0]
        if host not in ("localhost", "127.0.0.1"):
            raise PermissionError("Localhost requests only.")
        origin = self.headers.get("Origin")
        if origin and origin not in (
            f"http://localhost:{self.server.server_port}",
            f"http://127.0.0.1:{self.server.server_port}",
        ):
            raise PermissionError("Cross-origin requests are not allowed.")
        if mutation and self.headers.get("X-Annotation-CSRF") != CSRF:
            raise PermissionError(
                "Reload the page before saving (local session changed)."
            )

    def send(self, status, obj, ctype="application/json; charset=utf-8", filename=None):
        body = (
            json.dumps(obj, ensure_ascii=False).encode()
            if ctype.startswith("application/json")
            else (obj.encode() if isinstance(obj, str) else obj)
        )
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        if filename:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{filename}"'
            )
        self.end_headers()
        self.wfile.write(body)

    def error(self, exc):
        status = (
            403
            if isinstance(exc, PermissionError)
            else (
                404
                if isinstance(exc, LookupError)
                else (
                    409
                    if isinstance(exc, Conflict)
                    else (
                        400
                        if isinstance(exc, (ValueError, KeyError, TypeError))
                        else 500
                    )
                )
            )
        )
        if status == 500:
            traceback.print_exc()
        self.send(
            status,
            {
                "error": (
                    str(exc)
                    if status != 500
                    else "Unexpected server error. Check the local server log."
                ),
                **(
                    {"issues": exc.issues}
                    if isinstance(exc, IncompleteAnnotation)
                    else {}
                ),
            },
        )

    def do_GET(self):
        try:
            self.guard()
            path = urlparse(self.path).path
            if path == "/api/bootstrap":
                configured = (LOCAL / "ls_connection.json").exists()
                return self.send(
                    200,
                    {
                        "csrf": CSRF,
                        "codebook": CODEBOOK,
                        "participant": "TEST01",
                        "label_studio_configured": configured,
                    },
                )
            if path == "/api/conversations":
                with connect() as con:
                    rows = con.execute(
                        "SELECT * FROM conversations ORDER BY created_at DESC"
                    ).fetchall()
                return self.send(200, [public_record(dict(r)) for r in rows])
            if path == "/api/health":
                return self.send(200, {"ok": True, "mode": "localhost-single-user"})
            if path == "/api/export.zip":
                return self.send(
                    200, zip_export(), "application/zip", "annotation-data.zip"
                )
            if path.startswith("/api/conversations/"):
                parts = path.strip("/").split("/")
                cid = parts[2]
                get_record(cid)
                if len(parts) == 3:
                    return self.send(200, public_record(get_record(cid)))
                if parts[3] == "export.zip":
                    return self.send(
                        200,
                        zip_export(cid),
                        "application/zip",
                        "annotation-data.zip",
                    )
                if parts[3] == "current.json":
                    return self.send(
                        200, current_export(cid), filename="current-annotations.json"
                    )
                if parts[3] == "export.json":
                    return self.send(
                        200,
                        export_data(cid)[0],
                        filename="annotations.json",
                    )
            assets = {
                "/": "index.html",
                "/app.js": "app.js",
                "/styles.css": "styles.css",
            }
            if path in assets:
                name = assets[path]
                ct = {"html": "text/html", "js": "text/javascript", "css": "text/css"}[
                    name.split(".")[-1]
                ] + "; charset=utf-8"
                return self.send(200, (ROOT / "app/static" / name).read_bytes(), ct)
            raise LookupError("Page not found.")
        except Exception as exc:
            self.error(exc)

    def do_POST(self):
        try:
            self.guard(True)
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("JSON body required.")
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 6_000_000:
                raise ValueError("Request exceeds size limit or is empty.")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("JSON request must be an object.")
            path = urlparse(self.path).path
            if path == "/api/preview":
                kind = body.get("kind")
                demo = 0
                if kind in ("demo", "annotated_demo"):
                    fixture = json.loads((ROOT / "fixtures/demo.json").read_text())
                    data = normalize_conversation(fixture)
                    demo = int(kind == "annotated_demo")
                elif kind == "url":
                    data = normalize_conversation(
                        extract_chatgpt_conversation(body.get("url", ""))
                    )
                elif kind == "json":
                    data = normalize_conversation(body.get("conversation"))
                else:
                    raise ValueError("Choose shared link, JSON, or demo import.")
                pid = uid()
                with connect() as con:
                    con.execute(
                        "INSERT INTO previews VALUES (?,?,?,?,NULL)",
                        (pid, json.dumps(data), demo, now()),
                    )
                return self.send(
                    200,
                    {
                        "preview_id": pid,
                        "data": data,
                        "demo_annotations": bool(demo),
                        "warning": "Text-only extraction. Check message order and content. Attachments, images, and tool actions may not be represented.",
                    },
                )
            if path == "/api/confirm":
                with LOCK:
                    with connect() as con:
                        p = con.execute(
                            "SELECT * FROM previews WHERE id=?", (body["preview_id"],)
                        ).fetchone()
                    if not p:
                        raise LookupError("Preview expired or not found. Import again.")
                    if p["conversation_id"]:
                        return self.send(
                            200, public_record(get_record(p["conversation_id"]))
                        )
                    original = json.loads(p["data"])
                    source = {m["message_id"]: m for m in original["dialogue"]}
                    selected = body.get("messages", [])
                    messages = []
                    used = set()
                    if not isinstance(selected, list):
                        raise ValueError("Messages must be a list.")
                    for s in selected:
                        mid = s["message_id"]
                        if mid not in source or mid in used:
                            raise ValueError("Invalid or duplicate message ID.")
                        used.add(mid)
                        m = dict(source[mid])
                        m["text"] = s["text"]
                        messages.append(m)
                    if [m["source_index"] for m in messages] != sorted(
                        m["source_index"] for m in messages
                    ):
                        raise ValueError("Keep source message order.")
                    data = normalize_conversation(
                        {
                            "title": body.get("title", original["title"]),
                            "dialogue": messages,
                        }
                    )
                    cid = uid()
                    data.update(
                        {
                            "participant_id": "TEST01",
                            "conversation_id": cid,
                            "conversation_version": 1,
                        }
                    )
                    document = {"regions": [], "context": {}}
                    if p["demo"] and data["dialogue"] == original["dialogue"]:
                        document = from_ls(
                            json.loads((ROOT / "fixtures/demo.json").read_text())[
                                "results"
                            ],
                            data,
                        )
                    document = validate_document(document, data)
                    with connect() as con:
                        con.execute(
                            "INSERT INTO conversations(id,data,draft,created_at,updated_at) VALUES (?,?,?,?,?)",
                            (cid, json.dumps(data), json.dumps(document), now(), now()),
                        )
                        # Delete unselected source text from persistent preview after confirmation.
                        con.execute(
                            "UPDATE previews SET conversation_id=?,data=?,demo=0 WHERE id=?",
                            (cid, "{}", p["id"]),
                        )
                sync(cid)
                return self.send(201, public_record(get_record(cid)))
            if path.startswith("/api/conversations/"):
                parts = path.strip("/").split("/")
                cid = parts[2]
                action = parts[3]
                if action == "sync":
                    get_record(cid)
                    sync(cid)
                    return self.send(200, public_record(get_record(cid)))
                if action in ("save", "submit"):
                    with LOCK:
                        row = get_record(cid)
                        if body.get("revision") != row["revision"]:
                            raise Conflict(
                                "This conversation changed in another tab. Reload before editing."
                            )
                        data = json.loads(row["data"])
                        doc = validate_document(body["document"], data)
                        if action == "submit":
                            issues = required_issues(doc)
                            if issues:
                                raise IncompleteAnnotation(issues)
                        sub = latest(cid)
                        with connect() as con:
                            con.execute(
                                "UPDATE conversations SET draft=?,revision=revision+1,updated_at=? WHERE id=?",
                                (json.dumps(doc), now(), cid),
                            )
                            if action == "submit" and (
                                not sub or json.loads(sub["document"]) != doc
                            ):
                                con.execute(
                                    "INSERT INTO submissions(id,conversation_id,version,document,created_at,requirements_version) VALUES (?,?,?,?,?,?)",
                                    (
                                        uid(),
                                        cid,
                                        (sub["version"] + 1) if sub else 1,
                                        json.dumps(doc),
                                        now(),
                                        CODEBOOK["requirements_version"],
                                    ),
                                )
                    if action == "submit":
                        sync(cid)
                    return self.send(200, public_record(get_record(cid)))
            raise LookupError("Endpoint not found.")
        except Exception as exc:
            self.error(exc)


class Conflict(Exception):
    pass


def main():
    initialize()
    port = int(os.environ.get("ANNOTATION_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Annotation local website: http://localhost:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
