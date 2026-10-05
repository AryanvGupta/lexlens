import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

MAX_WORDS = 300  # ~400 tokens, under bge-small's 512 limit
OVERLAP_WORDS = 40
SEC_RE = re.compile(r"<!-- itempath:[^>]*?/Sec\. ([^>]+?) -->")


@dataclass
class Chunk:
    id: str
    source_id: str
    title: str
    section: str
    url: str
    text: str
    char_start: int
    char_end: int


def parse_sections(html: str) -> list[tuple[str, str, list[str], int, int]]:
    """Return (section_number, heading, paragraphs, start, end) per section."""
    marks = list(SEC_RE.finditer(html))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(html)
        block = html[m.start() : end]
        a = block.find("<!-- field-start:statute -->")
        b = block.find("<!-- field-end:statute -->")
        if a < 0 or b < 0:
            continue
        head = BeautifulSoup(block, "lxml").select_one("h3.section-head")
        paras = [
            p.get_text(" ", strip=True)
            for p in BeautifulSoup(block[a:b], "lxml").find_all("p")
        ]
        paras = [p for p in paras if p]
        if paras:
            heading = head.get_text(" ", strip=True) if head else ""
            out.append((m.group(1).strip(), heading, paras, m.start(), end))
    return out


def split_words(paras: list[str]) -> list[str]:
    """Pack paragraphs into <=MAX_WORDS chunks; overlap carries trailing words."""
    chunks, cur = [], []
    for p in paras:
        words = p.split()
        step = MAX_WORDS - OVERLAP_WORDS  # leave room for the carried overlap
        for i in range(0, len(words), step):  # oversize paragraph: hard split
            piece = words[i : i + step]
            if cur and len(cur) + len(piece) > MAX_WORDS:
                chunks.append(" ".join(cur))
                cur = cur[-OVERLAP_WORDS:]
            cur.extend(piece)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def chunk_source(source: dict, html: str) -> list[Chunk]:
    out = []
    for sec, heading, paras, start, end in parse_sections(html):
        for n, text in enumerate(split_words(paras)):
            out.append(
                Chunk(
                    id=f"{source['id']}:{sec}:{n}",
                    source_id=source["id"],
                    title=heading,
                    section=sec,
                    url=source["url"],
                    text=text,
                    char_start=start,
                    char_end=end,
                )
            )
    return out
