"""Real local HTTP + Label Studio integration. Run after ./start.sh.
Uses an isolated temporary app database and a separate fake-data LS project.
"""

import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from app.core import ROOT, CODEBOOK, from_ls, normalize_conversation


def complete_test_answers(document):
    """Populate fake responses only in integration fixtures, never in the app."""
    document = copy.deepcopy(document)
    for field in CODEBOOK["fields"]:
        if (
            field["group"] == "conversation"
            and field.get("required")
            and not document["context"].get(field["name"])
        ):
            document["context"][field["name"]] = "Integration test context"
    for region in document["regions"]:
        group = "user" if region["passage_type"] == "my text" else "ai"
        for field in CODEBOOK["fields"]:
            if (
                field["group"] == group
                and field.get("required")
                and not region["answers"].get(field["name"])
            ):
                region["answers"][field["name"]] = (
                    "Integration test explanation"
                    if field["type"] == "text"
                    else [field["options"][0]]
                )
    return document


class LocalIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="annotation-test-")
        cls.local = Path(cls.tmp.name)
        cls.cfg = json.loads((ROOT / ".local/ls_connection.json").read_text())
        (cls.local / "ls_connection.json").write_text(json.dumps(cls.cfg))
        cls.env = dict(
            os.environ,
            ANNOTATION_DATA=str(cls.local),
            ANNOTATION_PORT="8766",
            ANNOTATION_LS_PROJECT_TITLE="Annotation Automated Tests",
        )
        cls.session = requests.Session()
        cls.session.trust_env = False
        cls.start()

    @classmethod
    def start(cls):
        cls.log = (cls.local / "app.log").open("a")
        cls.proc = subprocess.Popen(
            [sys.executable, "-m", "app.server"],
            cwd=ROOT,
            env=cls.env,
            stdout=cls.log,
            stderr=cls.log,
        )
        for _ in range(60):
            try:
                b = cls.session.get("http://127.0.0.1:8766/api/bootstrap", timeout=1)
                b.raise_for_status()
                cls.csrf = b.json()["csrf"]
                return
            except requests.RequestException:
                time.sleep(0.1)
        raise RuntimeError(
            "Test server did not start: " + (cls.local / "app.log").read_text()
        )

    @classmethod
    def stop(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.log.close()

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.session.close()
        cls.tmp.cleanup()

    def get(self, path):
        return self.session.get("http://127.0.0.1:8766" + path, timeout=35)

    def post(self, path, body, expected=200, headers=None):
        h = {"X-Annotation-CSRF": self.csrf}
        h.update(headers or {})
        r = self.session.post(
            "http://127.0.0.1:8766" + path, json=body, headers=h, timeout=35
        )
        self.assertEqual(r.status_code, expected, r.text[:400])
        return r.json()

    def confirm(self, p, subset=None):
        return self.post(
            "/api/confirm",
            {
                "preview_id": p["preview_id"],
                "messages": subset or p["data"]["dialogue"],
            },
            201,
        )

    def test_full_lifecycle(self):
        p = self.post("/api/preview", {"kind": "annotated_demo"})
        c = self.confirm(p)
        cid = c["id"]
        path = "/api/conversations/" + cid
        self.assertIsNotNone(c["task_id"])
        self.assertFalse(c["sync_error"])
        self.assertEqual(len(c["document"]["regions"]), 5)
        # Confirmation retries reuse the same conversation.
        again = self.post(
            "/api/confirm",
            {"preview_id": p["preview_id"], "messages": p["data"]["dialogue"]},
        )
        self.assertEqual(again["id"], cid)
        doc = complete_test_answers(c["document"])
        doc["context"][
            "conversation_additional_context"
        ] = "Test 😀 e\u0301\nLocal context"
        c = self.post(path + "/save", {"revision": c["revision"], "document": doc})
        self.post(path + "/save", {"revision": c["revision"] - 1, "document": doc}, 409)
        self.assertEqual(self.get(path).json()["document"], doc)
        c = self.post(path + "/submit", {"revision": c["revision"], "document": doc})
        self.assertEqual(c["submission_version"], 1)
        self.assertEqual(c["synced_version"], 1)
        self.assertFalse(c["sync_error"])
        c = self.post(path + "/submit", {"revision": c["revision"], "document": doc})
        self.assertEqual(c["submission_version"], 1)
        z = self.get(path + "/export.zip")
        self.assertEqual(z.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(z.content)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["sync_warnings"], [])
            self.assertEqual(manifest["verified_raw_task_count"], 1)
            raw = json.loads(archive.read("label_studio_raw.json"))
            restored = from_ls(raw[0]["annotations"][0]["result"], c["data"])
            for document in (restored, doc):
                for region in document["regions"]:
                    region["answers"] = {
                        name: value
                        for name, value in region["answers"].items()
                        if not name.startswith("legacy_")
                    }
            self.assertEqual(restored, doc)
            self.assertIn("region_choices.csv", archive.namelist())
        # Unsubmitted edits must not leak into the research export.
        draft = copy.deepcopy(doc)
        draft["context"]["conversation_additional_context"] = "UNSUBMITTED"
        c = self.post(path + "/save", {"revision": c["revision"], "document": draft})
        exported = self.get(path + "/export.json").json()["conversations"][0]
        self.assertNotEqual(
            exported["annotation"]["context"]["conversation_additional_context"],
            "UNSUBMITTED",
        )
        # Durable across process restart; restore draft and formal submission separately.
        self.stop()
        self.start()
        c = self.get(path).json()
        self.assertEqual(c["document"], draft)
        self.assertTrue(c["has_changes"])
        # Simulate LS downtime by withholding only the isolated connection configuration.
        (self.local / "ls_connection.json").rename(self.local / "ls_connection.saved")
        c = self.post(path + "/submit", {"revision": c["revision"], "document": draft})
        self.assertEqual(c["submission_version"], 2)
        self.assertEqual(c["synced_version"], 1)
        self.assertTrue(c["sync_error"])
        exported = self.get(path + "/export.json").json()
        self.assertEqual(exported["conversations"][0]["annotation"], draft)
        self.assertTrue(exported["sync_warnings"])
        (self.local / "ls_connection.saved").rename(self.local / "ls_connection.json")
        c = self.post(path + "/sync", {})
        self.assertEqual(c["synced_version"], 2)
        self.assertFalse(c["sync_error"])
        self.assertEqual(
            c["annotation_id"],
            exported["conversations"][0]["label_studio"]["annotation_id"],
        )

    def test_unicode_real_api_and_redaction(self):
        obj = {
            "messages": [
                {"role": "user", "content": "Private name 😀 repeated repeated\nHi"},
                {"role": "assistant", "content": "Reply 😀 e\u0301\nDone"},
                {"role": "user", "content": "Excluded secret"},
            ]
        }
        p = self.post("/api/preview", {"kind": "json", "conversation": obj})
        messages = p["data"]["dialogue"][:2]
        messages[0]["text"] = messages[0]["text"].replace("Private name", "[name]")
        c = self.confirm(p, messages)
        data = c["data"]
        self.assertEqual(len(data["dialogue"]), 2)
        self.assertEqual(
            data["dialogue"][0]["message_id"], p["data"]["dialogue"][0]["message_id"]
        )
        a, b = data["dialogue"]
        doc = {
            "regions": [
                {
                    "id": "unicode",
                    "passage_type": "AI's text",
                    "segments": [
                        {
                            "message_id": b["message_id"],
                            "start": 6,
                            "end": 7,
                            "text": "😀",
                        }
                    ],
                    "answers": {
                        "ai_behavior": ["Modified my language or expression"],
                        "ai_behavior_explanation": "Both roles preserved",
                    },
                }
            ],
            "context": {},
        }
        doc = complete_test_answers(doc)
        c = self.post(
            "/api/conversations/" + c["id"] + "/submit",
            {"revision": 0, "document": doc},
        )
        self.assertEqual(c["synced_version"], 1)
        self.assertFalse(c["sync_error"])
        z = self.get("/api/conversations/" + c["id"] + "/export.zip")
        with zipfile.ZipFile(io.BytesIO(z.content)) as archive:
            raw = json.loads(archive.read("label_studio_raw.json"))
            self.assertNotIn(
                "Excluded secret", archive.read("annotations.json").decode()
            )
            self.assertNotIn("Private name", archive.read("annotations.json").decode())
            self.assertEqual(
                raw[0]["annotations"][0]["result"][0]["value"]["endOffset"], 8
            )
            self.assertEqual(
                from_ls(raw[0]["annotations"][0]["result"], c["data"]), c["document"]
            )

    def test_draft_json_empty_research_exports_and_required_submission(self):
        preview = self.post("/api/preview", {"kind": "demo"})
        c = self.confirm(preview)
        base = "/api/conversations/" + c["id"]
        current = self.get(base + "/current.json")
        self.assertEqual(current.status_code, 200)
        current = current.json()["conversations"][0]
        self.assertEqual(current["status"], "draft")
        self.assertEqual(len(current["conversation"]["dialogue"]), 7)
        for ext in ("json", "zip"):
            response = self.get(base + "/export." + ext)
            self.assertEqual(response.status_code, 400)
            self.assertIn("No submitted", response.json()["error"])
            self.assertNotIn("Content-Disposition", response.headers)
        m = c["data"]["dialogue"][0]
        doc = {
            "regions": [
                {
                    "id": "required_test",
                    "passage_type": "my text",
                    "segments": [{"message_id": m["message_id"], "start": 0, "end": 6}],
                    "answers": {"user_why": "Draft explanation"},
                }
            ],
            "context": {},
        }
        c = self.post(base + "/save", {"revision": c["revision"], "document": doc})
        error = self.post(
            base + "/submit",
            {"revision": c["revision"], "document": c["document"]},
            400,
        )
        self.assertTrue(error["issues"])
        self.assertNotIn("user_where_other", [x["field"] for x in error["issues"]])
        self.assertEqual(self.get(base).json()["submission_version"], 0)
        self.assertEqual(
            self.get(base + "/current.json").json()["conversations"][0]["annotation"][
                "regions"
            ][0]["answers"]["user_why"],
            "Draft explanation",
        )
        c = self.post(
            base + "/submit",
            {
                "revision": c["revision"],
                "document": complete_test_answers(c["document"]),
            },
        )
        self.assertEqual(c["requirements_version"], CODEBOOK["requirements_version"])
        self.assertEqual(
            self.get(base + "/export.json").json()["conversations"][0][
                "requirements_version"
            ],
            CODEBOOK["requirements_version"],
        )
        self.assertEqual(
            self.get(base + "/current.json").json()["conversations"][0]["status"],
            "submitted",
        )

    def test_local_origin_protection(self):
        self.post(
            "/api/preview", {"kind": "demo"}, 403, {"Origin": "https://evil.test"}
        )
        self.post("/api/preview", {"kind": "demo"}, 403, {"X-Annotation-CSRF": "wrong"})
        r = self.session.get(
            "http://127.0.0.1:8766/api/bootstrap",
            headers={"Host": "evil.test"},
            timeout=3,
        )
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    if "--serve-ui" in sys.argv:
        LocalIntegration.setUpClass()
        print(
            "Isolated browser test: http://localhost:8766 (temporary database; Ctrl+C to stop)",
            flush=True,
        )
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            LocalIntegration.tearDownClass()
    else:
        unittest.main(verbosity=2)
