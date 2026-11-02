# Run the app locally

These steps are for macOS, where this version was tested. Use Python 3.12 and keep ports 8765 and 8080 free. You do not need Docker, a ChatGPT API key, or a hosted Label Studio account.

## First-time setup

Download or clone this repository, then open a terminal in its folder. The commands below assume you are already in the project folder, which contains `start.sh`.

Check that Python 3.12 is installed:

```sh
python3.12 --version
```

If the command is missing, install Python 3.12 from [python.org](https://www.python.org/downloads/) and reopen the terminal.

Create a virtual environment and install the dependencies:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
```

The install needs internet access and may take a few minutes. `requirements.lock.txt` pins the tested dependency versions. Installation on other systems has not been verified.

## Start

```sh
./start.sh
```

If you get Permission denied, run:

```sh
sh start.sh
```

Wait for the terminal to print the website address, then open [http://localhost:8765](http://localhost:8765). The first launch also sets up the local Label Studio database, so it may take longer.

Keep this terminal open while using the app. On later runs, just open the project folder in a terminal and run `./start.sh` again. You do not need to reinstall dependencies each time.

## Try it

Click **Load example conversation**, review it, and confirm. Choose a label before highlighting. Fill in the questions and wait for **All changes saved**. Use **Submit annotations** in the bottom bar when you are ready to create a formal submission.

**Download current JSON** can export a draft. **Download research ZIP** becomes available after a formal submission. Editing a submitted conversation saves a new draft; submit again to include those changes in the research ZIP.

For a longer practice run, follow [SELF_TEST.md](docs/SELF_TEST.md).

## Stop and keep your work

Press **Control+C** in the startup terminal. Closing the browser does not stop the server. Restarting does not delete saved work.

Your conversations, drafts, submissions, local credentials, and Label Studio data live in `.local/`. Keep this folder private. To make a consistent backup, stop both services first and copy the whole `.local/` folder to a private location outside the repository. Do not upload it to GitHub.

## Common problems

- **Port already in use:** stop the previous copy with Control+C. Do not start a second copy in another terminal.
- **Shared link cannot be imported:** check that the link is public, retry later, or use the JSON import option. The app does not bypass login or access restrictions.
- **Label Studio copy is pending:** your formal submission stays in the local app database. Open **Researcher: storage status** and retry the copy after Label Studio is available.
- **Need the researcher Label Studio UI:** open [http://localhost:8080](http://localhost:8080). Existing local login details are in `.local/local_credentials.json`; do not share that file.
- **Check startup errors:** look at the terminal and `.local/label-studio.log`. Logs may contain local information, so do not upload them without reviewing them.

This setup runs on your computer. GitHub stores the source code; it does not run this Python and SQLite application through GitHub Pages.
