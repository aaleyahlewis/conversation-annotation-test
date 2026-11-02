"""Shared-page parser adapted from the supplied Colab converter.
No scripts from shared pages are executed. The serialization decoder is experimental.
"""

import json
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


def valid_url(url):
    p = urlparse(url)
    if (
        p.scheme != "https"
        or p.hostname != "chatgpt.com"
        or p.port not in (None, 443)
        or p.username
        or p.password
        or not re.fullmatch(r"/share/[A-Za-z0-9-]+/?", p.path)
    ):
        raise ValueError(
            "Use a public https://chatgpt.com/share/... conversation link."
        )
    return url


def extract_chatgpt_conversation(url):
    valid_url(url)
    session = requests.Session()
    session.trust_env = False
    try:
        for _ in range(4):
            valid_url(url)
            r = session.get(
                url,
                timeout=(10, 30),
                allow_redirects=False,
                headers={"User-Agent": "Mozilla/5.0"},
                stream=True,
            )
            if r.is_redirect:
                from urllib.parse import urljoin

                next_url = urljoin(url, r.headers.get("Location", ""))
                r.close()
                url = valid_url(next_url)
                continue
            if r.status_code in (401, 403, 429):
                r.close()
                raise ValueError(
                    "ChatGPT blocked this request or the link is not public. Try again later or import conversation JSON; no login or access checks are bypassed."
                )
            r.raise_for_status()
            buf = bytearray()
            try:
                for chunk in r.iter_content(65536):
                    buf.extend(chunk)
                    if len(buf) > 12_000_000:
                        raise ValueError("Shared page is too large (12 MB limit).")
            finally:
                r.close()
            return parse_html(buf.decode("utf-8"), url)
        raise ValueError("Too many redirects.")
    except requests.RequestException as exc:
        raise ValueError(
            "Could not fetch the shared conversation. Check the link or import JSON."
        ) from exc
    finally:
        session.close()


def parse_html(html, source_url=""):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""

    # Extract serialized React Router stream chunks.
    chunks = []
    pattern = r"streamController\.enqueue\((\"(?:\\.|[^\"\\])*\")\)"

    for script in soup.find_all("script"):
        script_text = script.string or script.get_text()
        if not script_text or "streamController.enqueue" not in script_text:
            continue

        for match in re.finditer(pattern, script_text, re.DOTALL):
            try:
                chunks.append(json.loads(match.group(1)))
            except json.JSONDecodeError:
                continue

    if not chunks:
        raise ValueError("No React Router stream chunks found.")

    # Parse the first chunk, which contains the serialized data table.
    try:
        raw = json.loads(chunks[0])
    except json.JSONDecodeError as exc:
        raise ValueError("Could not parse the first stream chunk.") from exc

    if not isinstance(raw, list):
        raise ValueError(f"Unexpected serialized payload type: {type(raw).__name__}")

    # Experimental reference-table decoder.
    cache = {}
    resolving = set()

    def resolve(index):
        if not isinstance(index, int):
            return index

        if index < 0:
            return None

        if index >= len(raw):
            return index

        if index in cache:
            return cache[index]

        if index in resolving:
            return None

        resolving.add(index)
        item = raw[index]

        try:
            if isinstance(item, dict):
                result = {}
                cache[index] = result

                for key, value in item.items():
                    match = re.fullmatch(r"_(\d+)", key)
                    key_name = (
                        raw[int(match.group(1))]
                        if match and int(match.group(1)) < len(raw)
                        else key
                    )

                    if isinstance(key_name, str):
                        result[key_name] = resolve(value)

                return result

            if isinstance(item, list):
                result = []
                cache[index] = result
                result.extend(resolve(value) for value in item)
                return result

            return item

        finally:
            resolving.discard(index)

    decoded = resolve(0)

    # Find mappings without recursion or revisiting circular references.
    def find_mappings(root):
        stack = [root]
        visited = set()
        found = []

        while stack:
            obj = stack.pop()

            if not isinstance(obj, (dict, list)):
                continue

            obj_id = id(obj)
            if obj_id in visited:
                continue
            visited.add(obj_id)

            if isinstance(obj, dict):
                if isinstance(obj.get("mapping"), dict):
                    found.append(obj)
                stack.extend(obj.values())
            else:
                stack.extend(obj)

        return found

    candidates = find_mappings(decoded)

    def extract_text(content):
        if not isinstance(content, dict):
            return ""

        parts = content.get("parts", [])
        if not isinstance(parts, list):
            return ""

        result = []
        for part in parts:
            if isinstance(part, str):
                result.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    result.append(text)

        return "\n".join(result)

    for candidate in candidates:
        mapping = candidate["mapping"]
        current_node = candidate.get("current_node")

        if not isinstance(current_node, str):
            continue

        # Follow the active branch from the current node to the root.
        ordered_nodes = []
        visited_nodes = set()
        node_id = current_node

        while isinstance(node_id, str) and node_id not in visited_nodes:
            visited_nodes.add(node_id)
            node = mapping.get(node_id)

            if not isinstance(node, dict):
                raise ValueError(
                    "Conversation branch is incomplete; please use JSON import instead."
                )

            ordered_nodes.append(node)
            node_id = node.get("parent")

        if isinstance(node_id, str):
            raise ValueError(
                "Conversation branch contains a cycle; extraction was stopped."
            )
        ordered_nodes.reverse()
        messages = []

        for node in ordered_nodes:
            message = node.get("message")
            if not isinstance(message, dict):
                continue

            author = message.get("author", {})
            role = author.get("role") if isinstance(author, dict) else None

            if role not in ("user", "assistant"):
                continue

            content = extract_text(message.get("content"))
            if content:
                messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

        if messages:
            return {
                "url": source_url,
                "title": title,
                "messages": messages,
            }

    raise ValueError(
        "Could not extract conversation messages. "
        "The embedded stream's serialization format needs a verified decoder."
    )
