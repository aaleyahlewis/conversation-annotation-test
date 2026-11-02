"""Run both loopback services. Ctrl+C stops only processes started here."""

import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
LOCAL.mkdir(exist_ok=True, mode=0o700)
LOCAL.chmod(0o700)
children = []


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)


def available(port):
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def get(url, token=None):
    req = urllib.request.Request(
        url, headers={"Authorization": "Token " + token} if token else {}
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=2) as r:
        return json.load(r)


def stop(*args):
    for p in children:
        if p.poll() is None:
            p.terminate()
    for p in children:
        try:
            p.wait(timeout=8)
        except subprocess.TimeoutExpired:
            p.kill()


def main():
    credentials_path = LOCAL / "local_credentials.json"
    if credentials_path.exists():
        creds = json.loads(credentials_path.read_text())
    else:
        creds = {
            "email": "researcher@localhost.test",
            "password": secrets.token_urlsafe(24),
            "token": secrets.token_hex(20),
        }
        write_private(credentials_path, creds)
    write_private(
        LOCAL / "ls_connection.json",
        {"url": "http://127.0.0.1:8080", "token": creds["token"]},
    )
    env = dict(os.environ)
    env.update(
        {
            "LABEL_STUDIO_BASE_DATA_DIR": str(LOCAL / "label-studio"),
            "LABEL_STUDIO_USERNAME": creds["email"],
            "LABEL_STUDIO_PASSWORD": creds["password"],
            "LABEL_STUDIO_USER_TOKEN": creds["token"],
            "LABEL_STUDIO_ENABLE_LEGACY_API_TOKEN": "true",
            "LABEL_STUDIO_DISABLE_SIGNUP_WITHOUT_LINK": "true",
            "LABEL_STUDIO_DEBUG": "false",
            "LABEL_STUDIO_COLLECT_ANALYTICS": "false",
            "COLLECT_ANALYTICS": "false",
            "LABEL_STUDIO_SENTRY_DSN": "",
            "LABEL_STUDIO_FRONTEND_SENTRY_DSN": "",
            "ANNOTATION_DATA": str(LOCAL),
            "PYTHONUNBUFFERED": "1",
        }
    )
    try:
        if available(8080):
            log = (LOCAL / "label-studio.log").open("a")
            p = subprocess.Popen(
                [
                    str(ROOT / ".venv/bin/label-studio"),
                    "start",
                    "--no-browser",
                    "--internal-host",
                    "127.0.0.1",
                    "--port",
                    "8080",
                    "--enable-legacy-api-token",
                ],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            children.append(p)
            print(
                "Starting Label Studio; first launch applies database migrations…",
                flush=True,
            )
        else:
            get("http://127.0.0.1:8080/api/projects/", creds["token"])
            print("Reusing the verified local Label Studio service.", flush=True)
        for _ in range(180):
            if children and children[0].poll() is not None:
                raise RuntimeError("Label Studio exited. Read .local/label-studio.log.")
            try:
                get("http://127.0.0.1:8080/api/projects/", creds["token"])
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError(
                "Label Studio did not become ready. Read .local/label-studio.log."
            )
        print("Label Studio API ready on http://localhost:8080", flush=True)
        if not available(8765):
            raise RuntimeError(
                "Port 8765 is already in use. Stop the earlier website before restarting."
            )
        p = subprocess.Popen(
            [str(ROOT / ".venv/bin/python"), "-m", "app.server"], cwd=ROOT, env=env
        )
        children.append(p)
        print(
            "Open http://localhost:8765 — all participant actions stay here.",
            flush=True,
        )
        print(
            "Local researcher credentials are in .local/local_credentials.json (not in Git). Ctrl+C stops both services.",
            flush=True,
        )
        while True:
            for p in children:
                if p.poll() is not None:
                    raise RuntimeError(
                        "A service stopped unexpectedly; check the terminal and local log."
                    )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping local services…", flush=True)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
