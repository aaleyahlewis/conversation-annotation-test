# Validation

## Automated checks

- 13 core tests cover XML/codebook parity, required rules, Unicode offsets, overlapping and cross-message regions, adapter round trips, invalid answers, message IDs, whitespace, URL checks, and serialized-page decoding.
- 8 frontend tests run the actual application JavaScript with a small test DOM and mocked network responses. They cover label selection, region state, answer counts, save acknowledgement, failed saves and retries, in-flight edits, required validation, local feedback, and grouped submission/download controls. They are not browser rendering tests.
- 4 integration tests use the real local HTTP server and Label Studio API. They cover task creation, draft saving, submission, JSON/ZIP export, native result checks, revisions, retries, process restart, required errors, Unicode handling, and local request guards. A temporary app database and a separate fictional-data Label Studio project keep these tests apart from normal app records.

Run commands are in the README. Integration tests require the local Label Studio service. Test data may remain in the dedicated local Label Studio test project; it is not included in the source repository.

## Clean installation

Committed source was tested on macOS with Python 3.12.3 in a fresh virtual environment, without existing credentials or databases. Installation from public PyPI, dependency checks, first startup, and all 24 tests passed. An anonymous GitHub read matched the tested source commit. The original local conversation and submission data were unchanged after restoring the original services. A second physical computer and other operating systems have not been verified.

## Browser checks performed during development

An isolated test page was used to check label-first highlighting, collapsible Regions, automatic answer saving, refresh recovery, missing-answer focus, and formal submission. Current-work JSON and an eight-file research ZIP were downloaded through the browser and inspected. The submitted copy was verified through the real Label Studio API.

Navigation from the bottom of Review was checked in a browser: entering Annotate reset page and question-pane scroll positions to zero. The single-line bottom bar measured 59 pixels for both a saved draft and a successful submission at the default desktop viewport. Save, submission, download progress, success, and error feedback share one text status; ZIP guidance is available in the control title and assistive description without taking a visible second row. The fixed bottom bar was checked at the default desktop viewport. Actual JSON and ZIP browser downloads each kept the bar at 59 pixels; the success message replaced the normal status and then automatically reverted. Tests also cover failed downloads, failed saves, and required-answer feedback without a separate footer message row. The last background input remained above the bar, and no horizontal document overflow was observed. Browser viewport checks at widths of 1280, 768, and 375 pixels found no horizontal document overflow and kept all three action buttons within the viewport. Narrow widths intentionally wrap the controls; this is not a physical mobile-device test. Save-retry feedback recovery and late download results after changing conversations are covered by frontend tests. Development screenshots are kept locally and excluded from publication.

## Limits

These checks do not establish accessibility conformance, real participant usability, metric validity, or universal ChatGPT format compatibility. No real participant study or public hosting test has been completed. Fictional examples are not research results.

The shared-page decoder uses an undocumented format. WritingBlock tags and Markdown source can appear in extracted text. Shared-page content may differ from the original chat interface. The review step is necessary; a reliable content-normalization policy is still unresolved.

The application is a single-user localhost prototype. Remote authentication, participant separation, and a full study data retention or withdrawal workflow are outside its current scope.
