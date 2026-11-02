# Source publication review

## Scope

The review covers the files selected by `git ls-files --cached --others --exclude-standard`. It does not publish anything. At preparation time, the repository had no tracked files, commits, or configured remotes, so there was no existing commit history to sanitize.

## Changes made

- Removed the machine-specific home directory from the README.
- Removed the concrete ChatGPT shared-link default from the extraction check. It now requires a URL supplied at runtime.
- Rewrote the setup and implementation notes in English and translated the manual practice guide.
- Replaced Chinese test strings with English text while keeping emoji and combining-character coverage.
- Excluded development screenshots from Git. They remain on the local computer.
- Expanded ignore rules for local service data, credentials, environment files, databases, exports, logs, backups, editor state, and temporary files.
- Added `scripts/check_publication.py`, which lists candidate files and reports matching categories without printing secret values.

## Findings

The prepared source files contain no detected personal home-directory paths, concrete shared-conversation URLs, Chinese characters, common credential patterns, or exact matches to the generated local password and token. A separate search found no known local owner or original staff identifiers in the publishable text. Bundled conversations are fictional examples.

The local conversation database, Label Studio database, credentials, and logs are inside the ignored `.local/` directory. They were not removed or copied into the source. Export buttons download files; they do not publish them to GitHub.

The current source includes the annotation codebook and XML configuration, as well as fictional conversations. Those are part of what becomes visible if the code repository is public.

## Verify before pushing

From the project folder, run:

```sh
python3 scripts/check_publication.py
git status --short
git diff --cached --stat
```

Inspect the list. Do not force-add ignored files. Do not manually upload the whole working directory through a browser: browser uploads do not use Git ignore rules. Keep new participant files outside the source folder.

Before the first commit, review the Git author name and email. Use your GitHub username and the exact noreply address supplied by GitHub if you do not want a personal email in public commits. This file review cannot choose your account identity for you.

## Limits

Pattern scans are not proof that no sensitive content can exist. New files, later edits, commit metadata, manually uploaded data, and future history need their own review. A later switch to private does not erase copies downloaded while public or make existing public forks private.

No license was chosen, no commit was created, and no GitHub repository was created or pushed during this preparation. The local application remains a localhost tool; publishing source does not deploy a remote study service.
