"""Validation and lossless adapters. Canonical offsets are Unicode code points."""

import copy
import hashlib
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEBOOK = json.loads((ROOT / "config/codebook.json").read_text())
FIELDS = {f["name"]: f for f in CODEBOOK["fields"]}
LEGACY_FIELDS = {f["name"]: f for f in CODEBOOK["legacy_fields"]}
LEGACY_SOURCES = {
    source: field["name"]
    for field in CODEBOOK["legacy_fields"]
    for source in field["source_names"]
}
LABELS = ["my text", "AI's text"]


def uid():
    return uuid.uuid4().hex


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def normalize_conversation(obj):
    if isinstance(obj, list):
        if len(obj) != 1:
            raise ValueError("Import one conversation at a time.")
        obj = obj[0]
    if not isinstance(obj, dict):
        raise ValueError("Expected a conversation JSON object.")
    data = obj.get("data", obj)
    if not isinstance(data, dict):
        raise ValueError("Conversation data must be an object.")
    messages = data.get("dialogue", data.get("messages"))
    if not isinstance(messages, list) or not messages or len(messages) > 1000:
        raise ValueError("Provide 1–1000 text messages in messages or data.dialogue.")
    result = []
    seen = set()
    for i, m in enumerate(messages):
        if not isinstance(m, dict):
            raise ValueError("Each message must be an object.")
        role = m.get("role")
        text = m.get("text", m.get("content"))
        if (
            role not in ("user", "assistant")
            or not isinstance(text, str)
            or not text.strip()
        ):
            raise ValueError(
                f"Message {i + 1}: expected user/assistant role and nonempty text."
            )
        if len(text) > 200000:
            raise ValueError("A message exceeds the 200,000 character limit.")
        mid = m.get("message_id") or uid()
        if not isinstance(mid, str) or mid in seen:
            raise ValueError("Message IDs must be unique strings.")
        seen.add(mid)
        result.append(
            {
                "message_id": mid,
                "source_index": m.get("source_index", i),
                "index": i,
                "role": role,
                "author": "You" if role == "user" else "ChatGPT",
                "text": text,
            }
        )
    return {
        "title": str(data.get("title") or "Imported conversation")[:300],
        "dialogue": result,
        "codebook_version": CODEBOOK["version"],
    }


def validate_document(doc, data):
    if (
        not isinstance(doc, dict)
        or not isinstance(doc.get("regions"), list)
        or len(doc["regions"]) > 1000
    ):
        raise ValueError("Invalid annotation document.")
    result = {"regions": [], "context": {}, "offset_unit": "unicode_code_point"}
    mids = {m["message_id"]: m for m in data["dialogue"]}
    indexes = {m["message_id"]: i for i, m in enumerate(data["dialogue"])}
    ids = set()

    def answers(values, group):
        if not isinstance(values, dict):
            raise ValueError("Answers must be an object.")
        cleaned = {}
        for name, value in values.items():
            f = FIELDS.get(name)
            legacy_name = (
                LEGACY_SOURCES.get(name)
                if not f and name not in LEGACY_FIELDS
                else None
            )
            if legacy_name:
                name = legacy_name
                f = LEGACY_FIELDS[name]
            elif name in LEGACY_FIELDS:
                f = LEGACY_FIELDS[name]
            elif f and f["type"] in ("multiple", "single"):
                valid = (
                    isinstance(value, list)
                    and len(value) == len(set(value))
                    and all(v in f["options"] for v in value)
                    and (f["type"] != "single" or len(value) <= 1)
                )
                if not valid and f.get("legacy_name"):
                    legacy_name = f["legacy_name"]
                    old_field = LEGACY_FIELDS[legacy_name]
                    old_valid = (
                        isinstance(value, list)
                        and len(value) == len(set(value))
                        and all(v in old_field["options"] for v in value)
                        and (
                            old_field["type"] != "single" or len(value) <= 1
                        )
                    )
                    if not old_valid:
                        raise ValueError(f"Invalid choices: {name}")
                    cleaned[legacy_name] = value
                    continue
            if not f or f["group"] != group:
                raise ValueError(f"Unexpected answer field: {name}")
            if f["type"] == "text":
                if not isinstance(value, str) or len(value) > 50000:
                    raise ValueError(f"Invalid text answer: {name}")
            else:
                if (
                    not isinstance(value, list)
                    or len(value) != len(set(value))
                    or any(v not in f["options"] for v in value)
                ):
                    raise ValueError(f"Invalid choices: {name}")
                if f["type"] == "single" and len(value) > 1:
                    raise ValueError(f"Choose one answer: {name}")
            cleaned[name] = value
        return cleaned

    result["context"] = answers(doc.get("context", {}), "conversation")
    for r in doc["regions"]:
        if not isinstance(r, dict):
            raise ValueError("Every region must be an object.")
        rid = r.get("id")
        if not isinstance(rid, str) or not rid or len(rid) > 100 or rid in ids:
            raise ValueError("Region IDs must be nonempty and unique.")
        ids.add(rid)
        if r.get("passage_type") not in LABELS:
            raise ValueError("Choose my text or AI’s text.")
        segs = r.get("segments")
        if not isinstance(segs, list) or not segs:
            raise ValueError("Select text for every region.")
        cleaned = []
        previous = None
        for seg in segs:
            if not isinstance(seg, dict):
                raise ValueError("Every segment must be an object.")
            m = mids.get(seg.get("message_id"))
            a, b = seg.get("start"), seg.get("end")
            if (
                not m
                or type(a) is not int
                or type(b) is not int
                or not 0 <= a < b <= len(m["text"])
            ):
                raise ValueError(
                    "Region offsets do not match the confirmed conversation."
                )
            idx = indexes[m["message_id"]]
            if previous is not None and (
                idx != previous[0] + 1
                or previous[1] != len(data["dialogue"][previous[0]]["text"])
                or a != 0
            ):
                raise ValueError("Cross-message selections must be a contiguous range.")
            previous = (idx, b)
            selected = m["text"][a:b]
            if seg.get("text", selected) != selected:
                raise ValueError("Selected text does not match its offsets.")
            cleaned.append(
                {"message_id": m["message_id"], "start": a, "end": b, "text": selected}
            )
        result["regions"].append(
            {
                "id": rid,
                "passage_type": r["passage_type"],
                "segments": cleaned,
                "answers": answers(
                    r.get("answers", {}),
                    "user" if r["passage_type"] == "my text" else "ai",
                ),
            }
        )
    return result


def required_issues(document):
    """Drafts may be incomplete. Enforce required answers at submission."""
    issues = []
    for field in CODEBOOK["fields"]:
        if field["group"] != "conversation" or not field.get("required"):
            continue
        value = document["context"].get(field["name"])
        if not value or not value.strip():
            issues.append(
                {
                    "region_id": "",
                    "region_number": None,
                    "field": field["name"],
                    "prompt": field["prompt"],
                }
            )
    for index, region in enumerate(document["regions"]):
        group = "user" if region["passage_type"] == "my text" else "ai"
        for field in CODEBOOK["fields"]:
            if field["group"] != group or not field.get("required", False):
                continue
            value = region["answers"].get(field["name"])
            missing = not value.strip() if isinstance(value, str) else not value
            if missing:
                issues.append(
                    {
                        "region_id": region["id"],
                        "region_number": index + 1,
                        "field": field["name"],
                        "prompt": field["prompt"],
                    }
                )
    return issues


class IncompleteAnnotation(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__(
            f"Complete {len(issues)} required answer(s) before submitting."
        )


def u16(text, index):
    return len(text[:index].encode("utf-16-le")) // 2


def from_u16(text, index):
    try:
        return len(text.encode("utf-16-le")[: index * 2].decode("utf-16-le"))
    except UnicodeDecodeError as exc:
        raise ValueError("Offset splits a Unicode character.") from exc


def to_ls(doc, data):
    """Paragraphs editor uses JS string offsets (UTF-16). Test with pinned LS."""
    messages = data["dialogue"]
    indexes = {m["message_id"]: i for i, m in enumerate(messages)}
    results = []
    for r in doc["regions"]:
        first, last = r["segments"][0], r["segments"][-1]
        a, b = indexes[first["message_id"]], indexes[last["message_id"]]
        value = {
            "start": str(a),
            "end": str(b),
            "startOffset": u16(messages[a]["text"], first["start"]),
            "endOffset": u16(messages[b]["text"], last["end"]),
            "text": "\n".join(s["text"] for s in r["segments"]),
        }

        def emit(name, typ, answer):
            v = copy.deepcopy(value)
            v.update(answer)
            results.append(
                {
                    "id": r["id"],
                    "from_name": name,
                    "to_name": "dialogue",
                    "type": typ,
                    "value": v,
                }
            )

        emit(
            "passage_type", "paragraphlabels", {"paragraphlabels": [r["passage_type"]]}
        )
        for name, answer in r["answers"].items():
            if answer and name in FIELDS:
                emit(
                    name,
                    "textarea" if FIELDS[name]["type"] == "text" else "choices",
                    (
                        {"text": [answer]}
                        if FIELDS[name]["type"] == "text"
                        else {"choices": answer}
                    ),
                )
    for name, answer in doc["context"].items():
        if answer:
            results.append(
                {
                    "id": "context_" + name,
                    "from_name": name,
                    "to_name": "dialogue",
                    "type": "textarea",
                    "value": {"text": [answer]},
                }
            )
    return results


def from_ls(results, data):
    doc = {"regions": [], "context": {}}
    regions = {}
    for r in results:
        if r["type"] == "paragraphlabels":
            v = r["value"]
            a, b = int(v["start"]), int(v["end"])
            segments = []
            for i in range(a, b + 1):
                m = data["dialogue"][i]
                x = from_u16(m["text"], v["startOffset"]) if i == a else 0
                y = from_u16(m["text"], v["endOffset"]) if i == b else len(m["text"])
                if x < y:
                    segments.append(
                        {
                            "message_id": m["message_id"],
                            "start": x,
                            "end": y,
                            "text": m["text"][x:y],
                        }
                    )
            region = {
                "id": r["id"],
                "passage_type": v["paragraphlabels"][0],
                "segments": segments,
                "answers": {},
            }
            regions[r["id"]] = region
            doc["regions"].append(region)
    for r in results:
        name = r["from_name"]
        if name not in FIELDS:
            continue
        v = r["value"]
        answer = (
            "\n".join(v.get("text", []))
            if r["type"] == "textarea"
            else v.get("choices", [])
        )
        if FIELDS[name]["group"] == "conversation":
            doc["context"][name] = answer
        elif r["id"] in regions:
            regions[r["id"]]["answers"][name] = answer
    return validate_document(doc, data)
