"""Check lxml's system libraries and document behavior inside UBI images."""

from __future__ import annotations

import re
import subprocess
from io import BytesIO
from pathlib import Path

from docx import Document
from lxml import etree


def verify_runtime() -> None:
    """Reject bundled XML libraries and exercise the installed document stack."""
    linkage = subprocess.check_output(["ldd", etree.__file__], text=True)  # noqa: S603, S607
    libraries = dict(re.findall(r"^\s*(lib(?:xml2|xslt)\.so\.\d+)\s+=>\s+(\S+)", linkage, re.MULTILINE))
    system_directory = Path("/usr/lib64").resolve()
    for name in ("libxml2.so.2", "libxslt.so.1"):
        library = libraries.get(name)
        if library is None or Path(library).resolve().parent != system_directory:
            msg = f"lxml must use the system {name}\n{linkage}"
            raise RuntimeError(msg)

    root = etree.fromstring(b"<root><value>42</value></root>")
    if root.xpath("string(value)") != "42":
        msg = "lxml XML parsing or XPath evaluation failed"
        raise RuntimeError(msg)
    stylesheet = etree.XML(
        b'<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
        b'<xsl:template match="/"><result><xsl:value-of select="root/value"/></result>'
        b"</xsl:template></xsl:stylesheet>"
    )
    if etree.XSLT(stylesheet)(root).getroot().text != "42":
        msg = "lxml XSLT evaluation failed"
        raise RuntimeError(msg)

    document = Document()
    document.add_paragraph("lxml runtime check")
    stream = BytesIO()
    document.save(stream)
    stream.seek(0)
    if Document(stream).paragraphs[0].text != "lxml runtime check":
        msg = "DOCX serialization failed"
        raise RuntimeError(msg)
    print(f"lxml runtime checks passed with libxml2 {etree.LIBXML_VERSION} and libxslt {etree.LIBXSLT_VERSION}")


if __name__ == "__main__":
    verify_runtime()
