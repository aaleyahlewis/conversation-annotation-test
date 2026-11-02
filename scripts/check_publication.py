"""Review Git's publishable files without printing secrets or local data.

This is a small guard for this repository, not a complete secret scanner.
It never stages, commits, uploads, or modifies files.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    paths = sorted(set(p.decode('utf-8') for p in git(
        'ls-files', '--cached', '--others', '--exclude-standard', '-z'
    ).split(b'\0') if p))
    deleted = {p.decode('utf-8') for p in git('ls-files', '--deleted', '-z').split(b'\0') if p}
    paths = [name for name in paths if name not in deleted]
    issues = []
    rules = {
        'personal home-directory path': r'/(?:Users|home)/[A-Za-z0-9_.-]+/',
        'temporary computer path': r'/(?:private/)?var/folders/[A-Za-z0-9/_.-]+',
        'Windows home-directory path': r'[A-Za-z]:\\Users\\[A-Za-z0-9_.-]+',
        'Chinese characters': r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]',
        'possible GitHub credential': r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
        'possible API credential': r'\bsk-[A-Za-z0-9_-]{20,}',
        'private key material': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'concrete shared conversation URL': r'https://chatgpt\.com/share/[a-fA-F0-9]{8}-[a-fA-F0-9-]{20,}',
    }
    forbidden_roots = {'.local', '.venv', '.git', '.codex', '.agents', 'tmp', 'exports', 'backups', 'data'}
    credentials = []
    private_file = ROOT / '.local/local_credentials.json'
    if private_file.exists():
        values = json.loads(private_file.read_text())
        credentials = [str(values[k]) for k in ('password', 'token') if values.get(k)]
    for name in paths:
        p = ROOT / name
        if p.parts and Path(name).parts[0] in forbidden_roots:
            issues.append((name, 'local-only folder is tracked or publishable'))
        if re.search(r'\.(?:sqlite3?|db)(?:-|$)|\.(?:log|pem|key|zip)$', name):
            issues.append((name, 'possible runtime data or credential file'))
        if name.startswith('docs/') and p.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
            issues.append((name, 'development screenshot is publishable'))
        if p.is_symlink():
            issues.append((name, 'symbolic link needs manual review'))
            continue
        if not p.exists():
            issues.append((name, 'tracked path is missing'))
            continue
        try:
            text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            issues.append((name, 'binary file needs manual review'))
            continue
        for reason, pattern in rules.items():
            if re.search(pattern, text):
                issues.append((name, reason))
        if any(value in text for value in credentials):
            issues.append((name, 'matches an actual local credential'))
    probes = [
        '.local/app.sqlite3', '.local/local_credentials.json', '.local/ls_connection.json',
        '.local/label-studio/label_studio.sqlite3', '.venv/bin/python', '.env',
        'exports/research.json', 'annotation-data.zip', 'current-annotations.json',
        'docs/local-workspace.png', 'tmp/debug.json',
    ]
    for probe in probes:
        result = subprocess.run(['git', 'check-ignore', '--no-index', '-q', probe], cwd=ROOT)
        if result.returncode != 0:
            issues.append((probe, 'ignore rule is missing'))
    print(f'Reviewed {len(paths)} publishable files.')
    for name in paths:
        print(f'  {name}')
    if issues:
        print('\nREVIEW FAILED (matching values are not printed):')
        for name, reason in issues:
            print(f'  {name}: {reason}')
        return 1
    print('\nPASS: configured privacy, language, and ignore checks passed.')
    print('This check does not review commit author identity, hidden Git objects, or all possible sensitive content.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
