import copy
import json
import unittest
from unittest.mock import patch
from app.core import (
    ROOT,
    CODEBOOK,
    normalize_conversation,
    validate_document,
    to_ls,
    from_ls,
    u16,
    from_u16,
    required_issues,
)
from app.extractor import valid_url, parse_html, extract_chatgpt_conversation


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / "fixtures/demo.json").read_text())
        self.data = normalize_conversation(self.fixture)

    def test_all_fields_match_xml(self):
        import xml.etree.ElementTree as ET

        root = ET.fromstring((ROOT / "config/label_config.xml").read_text())
        controls = [x for x in root.iter() if x.tag in ("TextArea", "Choices")]
        self.assertEqual(len(controls), len(CODEBOOK["fields"]))
        self.assertEqual(
            {x.get("name") for x in controls}, {f["name"] for f in CODEBOOK["fields"]}
        )
        for x in controls:
            f = next(f for f in CODEBOOK["fields"] if f["name"] == x.get("name"))
            self.assertEqual(f["required"], x.get("required") == "true")
            if f["type"] == "text":
                self.assertEqual(f["rows"], int(x.get("rows", "1")))
            else:
                self.assertEqual(
                    x.get("choice"),
                    "single-radio" if f["type"] == "single" else "multiple",
                )
            self.assertEqual(
                f["options"], [c.get("value") for c in x if c.tag == "Choice"]
            )

    def test_provided_five_regions_roundtrip(self):
        doc = from_ls(self.fixture["results"], self.data)
        self.assertEqual(len(doc["regions"]), 5)
        # Preserve the original manually chosen label, even on assistant source text.
        self.assertEqual(doc["regions"][2]["passage_type"], "my text")
        roundtrip = from_ls(to_ls(doc, self.data), self.data)
        for document in (doc, roundtrip):
            for region in document["regions"]:
                region["answers"] = {
                    name: value
                    for name, value in region["answers"].items()
                    if not name.startswith("legacy_")
                }
        self.assertEqual(doc, roundtrip)

    def test_unicode_overlap_multimessage_roundtrip(self):
        data = normalize_conversation(
            {
                "messages": [
                    {"role": "user", "content": "A😀e\u0301\nHi"},
                    {"role": "assistant", "content": "Next 😀 text"},
                ]
            }
        )
        a, b = data["dialogue"]
        doc = {
            "regions": [
                {
                    "id": "one",
                    "passage_type": "my text",
                    "segments": [
                        {
                            "message_id": a["message_id"],
                            "start": 1,
                            "end": len(a["text"]),
                        },
                        {"message_id": b["message_id"], "start": 0, "end": 6},
                    ],
                    "answers": {"user_why": "My context"},
                },
                {
                    "id": "overlap",
                    "passage_type": "my text",
                    "segments": [{"message_id": a["message_id"], "start": 1, "end": 2}],
                    "answers": {},
                },
            ],
            "context": {"conversation_additional_context": "Not visible 😀"},
        }
        canonical = validate_document(doc, data)
        self.assertEqual(canonical, from_ls(to_ls(canonical, data), data))
        self.assertEqual(u16(a["text"], 2), 3)
        self.assertEqual(from_u16(a["text"], 3), 2)
        with self.assertRaises(ValueError):
            from_u16(a["text"], 2)

    def test_required_answers_only_block_submission_not_draft_validation(self):
        doc = from_ls(self.fixture["results"], self.data)
        self.assertTrue(required_issues(doc))
        self.assertEqual(validate_document(doc, self.data), doc)
        by_name = {f["name"]: f for f in CODEBOOK["fields"]}
        for region in doc["regions"]:
            group = "user" if region["passage_type"] == "my text" else "ai"
            for name, field in by_name.items():
                if field["group"] == group and field["required"]:
                    region["answers"][name] = (
                        "Test explanation"
                        if field["type"] == "text"
                        else [field["options"][0]]
                    )
        for field in CODEBOOK["fields"]:
            if field["group"] == "conversation" and field["required"]:
                doc["context"][field["name"]] = "Required context"
        self.assertEqual(required_issues(doc), [])
        doc["regions"][0]["answers"]["ai_behavior_explanation"] = "  "
        self.assertEqual(required_issues(doc)[0]["field"], "ai_behavior_explanation")

    def test_reject_misaligned_text_and_bad_choices(self):
        doc = from_ls(self.fixture["results"], self.data)
        doc["regions"][0]["segments"][0]["text"] = "wrong"
        with self.assertRaises(ValueError):
            validate_document(doc, self.data)
        doc = from_ls(self.fixture["results"], self.data)
        doc["regions"][0]["answers"]["ai_role"] = ["invented"]
        with self.assertRaises(ValueError):
            validate_document(doc, self.data)

    def test_single_choice_and_group_validation(self):
        doc = from_ls(self.fixture["results"], self.data)
        doc["regions"][0]["answers"]["ai_followup_adjustment"] = ["Yes", "No"]
        with self.assertRaises(ValueError):
            validate_document(doc, self.data)
        doc["regions"][0]["answers"] = {"user_why": "wrong group"}
        with self.assertRaises(ValueError):
            validate_document(doc, self.data)

    def test_optional_empty_and_global_only(self):
        for doc in [
            {"regions": [], "context": {}},
            {
                "regions": [],
                "context": {"conversation_accessibility_context": "My goals"},
            },
        ]:
            clean = validate_document(doc, self.data)
            self.assertEqual(clean, from_ls(to_ls(clean, self.data), self.data))
        incomplete = validate_document({"regions": [], "context": {}}, self.data)
        self.assertEqual(
            {issue["field"] for issue in required_issues(incomplete)},
            {
                field["name"]
                for field in CODEBOOK["fields"]
                if field["group"] == "conversation"
            },
        )

    def test_existing_draft_answers_are_preserved_outside_new_questions(self):
        message = self.data["dialogue"][0]
        old = {
            "regions": [
                {
                    "id": "old-region",
                    "passage_type": "my text",
                    "segments": [
                        {
                            "message_id": message["message_id"],
                            "start": 0,
                            "end": 6,
                        }
                    ],
                    "answers": {
                        "user_how_strategy": [
                            "Adjusting language or linguistic expression"
                        ],
                        "user_where": ["Professional / Workplace"],
                        "user_how_site": ["Interacting through AI"],
                        "user_strategy_explanation": "Previously saved explanation",
                    },
                }
            ],
            "context": {},
        }
        migrated = validate_document(old, self.data)
        answers = migrated["regions"][0]["answers"]
        self.assertEqual(
            answers["legacy_user_how_strategy"],
            ["Adjusting language or linguistic expression"],
        )
        self.assertEqual(answers["legacy_user_where"], ["Professional / Workplace"])
        self.assertEqual(answers["legacy_user_how_site"], ["Interacting through AI"])
        self.assertEqual(
            answers["legacy_user_strategy_explanation"],
            "Previously saved explanation",
        )
        self.assertNotIn("user_how_strategy", answers)
        self.assertFalse(any(x["from_name"].startswith("legacy_") for x in to_ls(migrated, self.data)))

    def test_preserve_whitespace_and_reject_duplicate_ids(self):
        data = normalize_conversation(
            {"messages": [{"role": "user", "content": "  text\n "}]}
        )
        self.assertEqual(data["dialogue"][0]["text"], "  text\n ")
        self.data["dialogue"][1]["message_id"] = self.data["dialogue"][0]["message_id"]
        with self.assertRaises(ValueError):
            normalize_conversation(self.data)

    def test_reject_gapped_segments(self):
        doc = from_ls(self.fixture["results"], self.data)
        r = doc["regions"][0]
        r["segments"].append(
            {
                "message_id": self.data["dialogue"][3]["message_id"],
                "start": 0,
                "end": 10,
            }
        )
        with self.assertRaises(ValueError):
            validate_document(doc, self.data)


class ExtractorTests(unittest.TestCase):
    def test_url_allowlist(self):
        valid_url("https://chatgpt.com/share/abc-123")
        for url in [
            "http://chatgpt.com/share/a",
            "https://evil.test/share/a",
            "https://chatgpt.com.evil.test/share/a",
            "https://chatgpt.com:8888/share/a",
            "https://u:p@chatgpt.com/share/a",
            "https://chatgpt.com/share/../a",
        ]:
            with self.assertRaises(ValueError):
                valid_url(url)

    def test_bad_html_fails_loudly(self):
        with self.assertRaises(ValueError):
            parse_html("<html>Login required</html>")

    def test_extract_serialized_fixture(self):
        # Reference table matching the supplied parser's supported format.
        raw = [
            {"mapping": 1, "current_node": 2},
            {"node": 3},
            "node",
            {"message": 4, "parent": -1},
            {"author": 5, "content": 6},
            {"role": 7},
            {"parts": 8},
            "user",
            [9],
            "  Hello 😀\n",
        ]
        chunk = json.dumps(json.dumps(raw))
        html = f"<html><title>Test</title><script>streamController.enqueue({chunk})</script></html>"
        out = parse_html(html)
        self.assertEqual(out["messages"], [{"role": "user", "content": "  Hello 😀\n"}])

    def test_fetch_rejects_private_redirect(self):
        class R:
            is_redirect = True
            headers = {"Location": "http://127.0.0.1/private"}

            def close(self):
                pass

        with patch("app.extractor.requests.Session") as sess:
            sess.return_value.get.return_value = R()
            with self.assertRaises(ValueError):
                extract_chatgpt_conversation("https://chatgpt.com/share/test")
            self.assertEqual(sess.return_value.get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
