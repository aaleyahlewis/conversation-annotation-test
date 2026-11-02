# Validation

## Automated checks

- 13 core tests cover XML/codebook parity, required rules, Unicode offsets, overlapping and cross-message regions, adapter round trips, invalid answers, message IDs, whitespace, URL checks, and serialized-page decoding.
- 7 frontend tests run the actual application JavaScript with a small test DOM and mocked network responses. They cover label selection, region state, answer counts, save acknowledgement, failed saves and retries, in-flight edits, required validation, local feedback, and grouped submission/download controls. They are not browser rendering tests.
- 4 integration tests use the real local HTTP server and Label Studio API. They cover task creation, draft saving, submission, JSON/ZIP export, native result checks, revisions, retries, process restart, required errors, Unicode handling, and local request guards. A temporary app database and a separate fictional-data Label Studio project keep these tests apart from normal app records.

Run commands are in the README. Integration tests require the local Label Studio service. Test data may remain in the dedicated local Label Studio test project; it is not included in the source repository.

## Browser checks performed during development

An isolated test page was used to check label-first highlighting, collapsible Regions, automatic answer saving, refresh recovery, missing-answer focus, and formal submission. Current-work JSON and an eight-file research ZIP were downloaded through the browser and inspected. The submitted copy was verified through the real Label Studio API.

The fixed bottom bar was checked at the default desktop viewport. The last background input remained above the bar, and no horizontal document overflow was observed. Narrow-screen wrapping rules are implemented but have not been independently verified in a mobile browser. Development screenshots are kept locally and excluded from publication.

## Limits

These checks do not establish accessibility conformance, real participant usability, metric validity, or universal ChatGPT format compatibility. No real participant study or public hosting test has been completed. Fictional examples are not research results.

The shared-page decoder uses an undocumented format. WritingBlock tags and Markdown source can appear in extracted text. Shared-page content may differ from the original chat interface. The review step is necessary; a reliable content-normalization policy is still unresolved.

The application is a single-user localhost prototype. Remote authentication, participant separation, and a full study data retention or withdrawal workflow are outside its current scope.
