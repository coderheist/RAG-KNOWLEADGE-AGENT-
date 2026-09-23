"""Decompression-bomb probe for DocxParser: a .docx whose decompressed XML is
huge must not hang or crash the process (replaces test_zip_bomb.py script).

Uses a 50MB decompressed payload rather than the original 500MB to keep this
fast enough for CI. No live services required — imports the parser directly.
"""
import io
import time
import zipfile

from app.services.parsers.docx_parser import DocxParser

_CONTENT_TYPES = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    b'<Default Extension="xml" ContentType="application/xml"/>'
    b'<Override PartName="/word/document.xml" '
    b'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    b"</Types>"
)
_RELS = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    b'<Relationship Id="rId1" '
    b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    b'Target="word/document.xml"/></Relationships>'
)


def _make_decompression_bomb(decompressed_mb: int) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        xml = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b"<w:body><w:p><w:r><w:t>" + b"A" * (decompressed_mb * 1024 * 1024) + b"</w:t></w:r></w:p></w:body>"
            b"</w:document>"
        )
        zf.writestr("word/document.xml", xml)
    return out.getvalue()


def test_decompression_bomb_does_not_hang_or_crash() -> None:
    bomb = _make_decompression_bomb(50)
    parser = DocxParser()

    start = time.time()
    try:
        result = parser.parse(bomb, "bomb.docx")
        assert len(result.full_text) > 0
    except ValueError:
        pass  # a rejected oversized document is an acceptable outcome
    elapsed = time.time() - start

    # ponytail: no explicit decompressed-size guard in DocxParser yet — this only
    # proves the parser doesn't hang; add a MAX_DECOMPRESSED_SIZE check if this ever
    # creeps past a few seconds for 50MB.
    assert elapsed < 30, f"parsing a 50MB decompression bomb took {elapsed:.1f}s — needs a size guard"
