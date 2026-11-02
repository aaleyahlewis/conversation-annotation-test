"""Check shared-page extraction without printing conversation content."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.extractor import extract_chatgpt_conversation

if len(sys.argv) != 2:
    print('Usage: python scripts/check_shared_link.py "https://chatgpt.com/share/YOUR-SHARE-ID"')
    sys.exit(2)
url = sys.argv[1]

try:
    result = extract_chatgpt_conversation(url)
    print(
        "SUCCESS: extracted",
        len(result["messages"]),
        "text messages. Conversation text was not printed.",
    )
except ValueError as exc:
    print("NOT EXTRACTED:", str(exc))
    sys.exit(2)
