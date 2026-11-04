"""Heading-aware chunking of markdown help-center articles.

Each chunk is one section (heading path + its text). Small sections are merged into the
previous chunk; long sections are split on paragraph boundaries. Fenced code blocks are never
split and '#' lines inside them are not treated as headings.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


# Bump when chunking logic or defaults change, so ingest re-chunks unchanged articles.
CHUNKER_VERSION = "heading-v1:max180:min40"
MAX_WORDS = 180
MIN_WORDS = 40


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    category: str
    updated: str
    body: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(f"{CHUNKER_VERSION}\n{self.title}\n{self.category}\n{self.body}".encode()).hexdigest()


@dataclass(frozen=True)
class Chunk:
    article_id: str
    chunk_index: int
    heading: str  # "Title > Section > Subsection"
    content: str

    @property
    def embedding_text(self) -> str:
        return f"{self.heading}\n{self.content}"


def parse_article(text: str, source: str = "<string>") -> Article:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{source}: missing YAML frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    missing = {"id", "title", "category"} - meta.keys()
    if missing:
        raise ValueError(f"{source}: frontmatter missing {sorted(missing)}")
    return Article(
        id=str(meta["id"]),
        title=str(meta["title"]),
        category=str(meta["category"]),
        updated=str(meta.get("updated", "")),
        body=text[m.end() :].strip(),
    )


def load_articles(kb_dir: Path) -> list[Article]:
    articles = [parse_article(p.read_text(encoding="utf-8"), str(p)) for p in sorted(kb_dir.glob("*.md"))]
    ids = [a.id for a in articles]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate article ids in knowledge base")
    return articles


def _sections(article: Article) -> list[tuple[list[str], str]]:
    """Split the body into (heading path, text) sections."""
    path: list[str] = [article.title]
    sections: list[tuple[list[str], list[str]]] = [(list(path), [])]
    in_code = False
    for line in article.body.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else _HEADING_RE.match(line)
        if m:
            level, title = len(m.group(1)), m.group(2).strip()
            if level == 1:
                path = [title]
            else:
                path = path[: level - 1] + [title]
            sections.append((list(path), []))
        else:
            sections[-1][1].append(line)
    return [(p, "\n".join(lines).strip()) for p, lines in sections if "\n".join(lines).strip()]


def _split_long(text: str, max_words: int) -> list[str]:
    paras = re.split(r"\n\s*\n", text)
    # Re-join paragraphs that were split inside a code fence.
    merged: list[str] = []
    for p in paras:
        if merged and merged[-1].count("```") % 2 == 1:
            merged[-1] += "\n\n" + p
        else:
            merged.append(p)
    parts: list[str] = []
    cur: list[str] = []
    for p in merged:
        if cur and len(" ".join(cur + [p]).split()) > max_words:
            parts.append("\n\n".join(cur))
            cur = []
        cur.append(p)
    if cur:
        parts.append("\n\n".join(cur))
    return parts


def chunk_article(article: Article, *, max_words: int = MAX_WORDS, min_words: int = MIN_WORDS) -> list[Chunk]:
    pieces: list[tuple[str, str]] = []
    for path, text in _sections(article):
        heading = " > ".join(path)
        for part in _split_long(text, max_words):
            if pieces and len(part.split()) < min_words and len(pieces[-1][1].split()) < max_words:
                prev_heading, prev_text = pieces[-1]
                sub = path[-1]
                pieces[-1] = (prev_heading, f"{prev_text}\n\n{sub}:\n{part}")
            else:
                pieces.append((heading, part))
    if len(pieces) > 1 and len(pieces[0][1].split()) < min_words:
        intro = pieces.pop(0)[1]
        pieces[0] = (pieces[0][0], f"{intro}\n\n{pieces[0][1]}")
    return [Chunk(article.id, i, h, t) for i, (h, t) in enumerate(pieces)]
