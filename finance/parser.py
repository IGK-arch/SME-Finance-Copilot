"""Bounded text-only PDF parser subprocess; never executes embedded scripts."""

import base64
import io
import sys

from pypdf import PdfReader


def main() -> None:
    content = base64.b64decode(sys.stdin.read(700001), validate=True)
    if not content.startswith(b"%PDF-") or len(content) > 500000:
        raise ValueError("Unsupported PDF")
    reader = PdfReader(io.BytesIO(content), strict=True)
    if reader.is_encrypted or len(reader.pages) > 30:
        raise ValueError("Encrypted or oversized PDF")
    texts: list[str] = []
    for i, page in enumerate(reader.pages, 1):
        contents = page.get_contents()
        if contents is not None and len(contents.get_data()) > 2000000:
            raise ValueError("Page too large")
        text = page.extract_text() or ""
        if sum(map(len, texts)) + len(text) > 200000:
            raise ValueError("Text limit exceeded")
        texts.append(f"Page {i}\n{text}")
    sys.stdout.buffer.write("\n".join(texts).encode("utf-8"))


if __name__ == "__main__":
    main()
