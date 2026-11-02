# Annotation export data dictionary

This local prototype uses one test identity, TEST01. Sample annotations are demonstrations, not validated labels or participant research findings.

- `annotations.json`: authoritative app-side latest formal submission for each conversation. Draft changes and previous submission versions are not included. Historical submissions remain in the local database.
- `current-annotations.json`: current saved work, including unsubmitted drafts, with `status` (draft/submitted), `saved_at`, and `latest_submission_version`. This is not restricted to research-ready submissions.
- `requirements_version`: per-entry submission policy. New submissions use `required-per-region-v2`; existing submissions are preserved as `legacy-optional-v1` without inventing missing answers. The exported codebook contains current `required` flags; read each entry's policy before interpreting historical completeness.
- `conversation.dialogue`: frozen, participant-confirmed text. `message_id` is stable; `source_index` is its pre-selection position and `index` is its confirmed display position. `role` is the original user/assistant source, independent of a region's manually chosen `passage_type`.
- `annotation.regions`: each region has a unique ID, a passage type, one or more contiguous message segments, and answers governed by the required-field policy. Draft answers may be incomplete. Multiple regions may overlap. Deleting a region deletes its answers in the draft.
- `segments`: `message_id`, `start`, `end`, and selected `text`. Offsets are **Unicode code points**, start inclusive and end exclusive. Newlines are preserved. Slice the frozen message text, not a Markdown rendering. A cross-message region has a segment for each included message.
- `annotation.context`: the two conversation-wide optional answers; they are not region answers.
- `answers`: text answers are strings; choice answers are arrays of exact codebook option strings. Single-choice answers have zero or one entry. Missing/empty answers are not negative answers and do not establish that a phenomenon was absent. Explicit No, No benefits, Other, uncertainty, and not applicable are distinct from no answer.
- `text_sha256`: SHA-256 of a canonical JSON representation of the confirmed dialogue (sorted object keys, Python JSON default separators, UTF-8, ensure_ascii=False).
- `submission_version`: incremented only when a different document is formally submitted. Submitting an identical document again does not create a new submission. Saves and submits also increment an editing revision used to detect stale edits.
- `submitted_at` / `exported_at`: ISO-8601 UTC timestamps. They are not original ChatGPT message times.
- `label_studio`: remote IDs and last successfully verified synced submission version. API author is a service account, **not** a participant. TEST01 comes from the app's identity record.
- `label_studio_raw.json`: matching latest submitted results retrieved from the local Label Studio API during export, with staff identity fields removed. Label Studio paragraph offsets use browser UTF-16 units. This differs from canonical code-point offsets for some emoji. Only verified matching results are included; read `manifest.json` for any missing/sync warnings.
- `conversations.csv`: one row per submitted conversation, including conversation-level context as JSON.
- `regions.csv`: one row per region; segments and answers are JSON cells to preserve cross-message and multi-select data.
- `region_choices.csv`: one row per selected option (not one observation per participant). Count at an appropriate level for analysis.
- CSV cells that could be interpreted as spreadsheet formulas are prefixed with an apostrophe. Unmodified text is in JSON.
- `manifest.json`: selected scope, sync warnings, counts, and schema/codebook versions. Do not silently treat incomplete remote sync as a complete native export.
- Shared URLs and excluded/redacted original text are not part of research exports. Public sharing is a separate action: editing text in this tool does not change the ChatGPT shared page.

Do not infer identity goals, access labor, real-world success, or metric validity solely from label frequency or model output. Participant explanations are situated evidence. The codebook is a research starting point, not a validated automatic scoring scheme.
