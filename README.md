# Conversation annotation

A local research tool for importing and annotating ChatGPT conversations. Users can review messages, highlight passages, and answer questions about communication and accessibility. All annotation happens on the custom website. A local Label Studio API stores a copy of submitted annotations.

This is a single-user research prototype. It uses the test identity `TEST01`. It does not include participant accounts or online study hosting.

## Run locally

Tested on macOS with Python 3.12. Install [Python 3.12](https://www.python.org/downloads/) first if `python3.12 --version` is not available. Docker and a ChatGPT API key are not needed.

Open a terminal in the project folder and run:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
./start.sh
```

Installation needs internet access. The first launch creates the local databases and credentials, so wait for the website address to appear. Open [http://localhost:8765](http://localhost:8765) and keep the terminal open. Press Control+C to stop.

For later runs, use `./start.sh` without reinstalling. If it reports Permission denied, use `sh start.sh`. If a port is already in use, stop the previous app instance; ports 8765 and 8080 must be free.

A clean installation from committed source was verified with a new virtual environment and new databases: startup and all 24 tests passed. Other operating systems have not been verified. For a quick check, load a fictional example, annotate it, refresh to check saving, then submit and download the research ZIP.

Each person runs their own copy and has their own local data. Publishing code to GitHub does not create a shared online workspace.

## Basic workflow

1. Paste a public ChatGPT shared link, or import a conversation JSON file. You can also load the fictional example.
2. Review the extracted messages. Exclude messages or edit sensitive details before confirming.
3. Choose **my text** or **AI's text**, then highlight a passage. Choose a label again for each new highlight. Whole-message selection is also available.
4. Answer the questions for that highlight. Answers save automatically as local drafts. Regions can overlap, and the Regions list can be collapsed.
5. Use the fixed bottom bar to submit or download data. Required questions are checked on submission. Only questions or sections marked optional can be skipped.

For my-text regions, the Other description is optional. For AI regions, the role selection is optional; the separate role explanation and other answers are required. Conversation-level background is optional.

Try [the manual test guide](docs/SELF_TEST.md) with `fixtures/practice-extension.json`. All bundled example conversations are fictional; they are not participant data or validated annotations. Some original demo labels deliberately differ from source-message roles.

## Where the data goes

- Drafts and formal submissions are stored in `.local/app.sqlite3`.
- Submitted annotations are also copied to local Label Studio at [http://localhost:8080](http://localhost:8080).
- **Download current JSON** includes current saved work, even before submission, and labels it draft or submitted.
- **Download research ZIP** includes the latest formal submission, not newer draft changes. It contains JSON, CSVs, the codebook, a data dictionary, and verified Label Studio results when available.
- The collapsed researcher export on the home page downloads all submitted local conversations.

Submitting does not send data to a researcher or GitHub. `.local/`, virtual environments, database files, logs, development screenshots, and standard export filenames are ignored by Git. Keep other research files outside the source folder. Ignore rules do not protect files that someone explicitly force-adds or manually uploads.

Stop both services before backing up the whole `.local/` folder to a private location outside the repository. Restarting keeps saved work.

Local credentials are generated on first startup and saved in `.local/local_credentials.json`. They are not included in the repository. Participants do not need to sign in to Label Studio.

## Current limitations

The app listens on loopback addresses and is meant to run on one computer. Uploading this repository to GitHub does not host a working website. Remote research use would need a separate deployment plan, participant access controls, and a data handling plan.

Shared-page extraction depends on an undocumented ChatGPT page format. Always check the preview. WritingBlock wrappers and Markdown syntax currently remain in extracted text. A shared page may also differ from the original chat interface. Formatting cleanup and rules for these differences are not yet implemented. Text-only extraction does not fully represent images, attachments, or tool interactions.

The interface is not a claim of full accessibility conformance. Real participant and assistive technology testing are still needed. The codebook is a research starting point, not a validated automatic metric.

## Development checks

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_core.py' -v
node --check app/static/app.js
node --test tests/test_frontend.cjs
.venv/bin/python tests/test_integration.py
python3 scripts/check_publication.py
```

Node is only needed for frontend developer checks. Integration tests require the local Label Studio service from `./start.sh`. They use port 8766, a temporary app database, and a separate fictional-data Label Studio project.

To check extraction with a public test link you choose:

```sh
.venv/bin/python scripts/check_shared_link.py "https://chatgpt.com/share/YOUR-SHARE-ID"
```

The script prints a message count, not conversation text. No real shared link is bundled.

## More details

- [Implementation notes](docs/IMPLEMENTATION_PLAN.md)
- [Export data dictionary](docs/data_dictionary.md)
- [Validation and limitations](docs/VALIDATION.md)

No project license has been selected. Public visibility alone is not an open-source license. Dependency licenses still apply; this project uses Label Studio as an installed dependency rather than bundling its source.
