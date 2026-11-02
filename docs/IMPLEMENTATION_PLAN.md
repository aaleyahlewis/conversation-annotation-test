# Implementation notes

## Scope

One local website handles import, review, highlighting, answers, submission, and export. A separate local Label Studio process stores a submitted copy through its API. The current app uses one test identity, TEST01, without participant accounts, invitations, or public hosting.

## Files and services

- `app/static/`: buildless JavaScript and CSS for the participant interface.
- `app/extractor.py`: bounded public shared-page fetching and experimental serialized-page decoding. It does not execute shared-page scripts.
- `app/core.py`: conversation validation, region validation, and Label Studio result adapters.
- `app/server.py`: localhost HTTP API, SQLite persistence, submission snapshots, sync, and export.
- `config/codebook.json`: 18 answer fields, option lists, and required rules.
- `config/label_config.xml`: matching local Label Studio configuration.
- `scripts/start_local.py`: starts the app on port 8765 and Label Studio on port 8080.
- `fixtures/`: fictional examples only.

## Data flow

1. Extract a public shared conversation or import JSON.
2. Show a review page where messages can be excluded or edited.
3. Confirm and freeze the text; create a corresponding Label Studio task.
4. Create labelled regions with stable message IDs and text offsets.
5. Save partial drafts automatically, using editing revisions to reject stale writes.
6. Check required answers, store an immutable submission, and sync the latest version to Label Studio.
7. Download current work as JSON or the latest formal submission as a research ZIP.

Canonical region offsets use Unicode code points. The Label Studio adapter converts them to browser UTF-16 offsets. Newlines and selected text are checked against the frozen messages. Message source role and manually chosen passage label are separate values. Overlapping and contiguous cross-message regions are supported.

## Interface

Users select my text or AI's text before highlighting. The label disarms after each new region. Regions start collapsed and can be reopened. Answers save automatically; a retry control appears after a failed save. There is no separate Add or Save answer step.

The fixed bottom bar contains submission status, save status, downloads, and Submit annotations. Its height is measured so it does not cover the last inputs. Errors appear close to their controls. Label-selection hints appear by the labels.

Required rules are enforced in both frontend and backend at submission. Partial drafts are allowed. Optional fields retain their wording without extra badges. Current requirements use `required-per-region-v2`; older submissions keep their recorded legacy policy.

## Storage and sync

The app database is authoritative. Label Studio is a verified mirror of the latest submission, not the draft. The generated service account is the API author, not a participant identity. A sync failure does not remove the local submission. Retries reconcile remote IDs before creating new records. Research exports verify native results and report missing or mismatched copies.

Shared URLs are not stored in confirmed research exports. Confirmation removes unselected and unredacted preview text from the saved preview. Unconfirmed previews expire. This is not a claim of forensic deletion from SQLite pages or existing private backups.

## Local boundaries

Services listen on loopback. Host, Origin, and CSRF checks protect local writes. API credentials stay on the backend. Text is displayed as text rather than executed as HTML. CSV exports protect spreadsheet users from formula execution. These controls do not replace participant authentication for a future remote deployment.

WritingBlock wrappers, Markdown rendering, and differences between the original chat and its shared version remain open issues. No automatic cleanup policy has been applied.
