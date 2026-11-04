import pytest

from triagedesk.chunking import chunk_article, load_articles, parse_article

DOC = (
    """---
id: TST-01
title: Test article
category: webhooks
updated: 2026-10-01
---
# Test article

Short intro sentence for the article.

## Setting up

Step one is to open the dashboard and add an endpoint. """
    + "word " * 60
    + """

## Code

```python
# this is a comment, not a heading
print("hi")
```

Some text after the code block that explains the snippet in enough words to stand alone here.
It keeps going with more explanation
so the section is long enough and it keeps going with more explanation so the section is long
enough. 

### Details

Tiny.

## Still need help?

Contact support.
"""
)


def test_parse_frontmatter():
    a = parse_article(DOC)
    assert (a.id, a.title, a.category) == ("TST-01", "Test article", "webhooks")
    assert a.body.startswith("# Test article")


def test_missing_frontmatter_rejected():
    with pytest.raises(ValueError, match="frontmatter"):
        parse_article("# no frontmatter")
    with pytest.raises(ValueError, match="missing"):
        parse_article("---\nid: X\n---\nbody")


def test_heading_paths_and_code_fences():
    chunks = chunk_article(parse_article(DOC))
    headings = [c.heading for c in chunks]
    assert headings[0] == "Test article > Setting up"
    assert "Short intro sentence" in chunks[0].content  # tiny intro merged forward
    assert any(h == "Test article > Code" for h in headings)
    # '#' inside the code fence must not start a new section
    assert not any("this is a comment" in h for h in headings)
    code = next(c for c in chunks if c.heading.endswith("Code"))
    assert "```python" in code.content and code.content.count("```") % 2 == 0


def test_small_sections_merged_into_previous():
    chunks = chunk_article(parse_article(DOC))
    assert not any(c.heading.endswith("Still need help?") for c in chunks)
    assert any("Contact support." in c.content for c in chunks)


def test_long_sections_split_on_paragraphs():
    long_body = DOC.replace("## Code", "\n\n".join(["Paragraph " + "x " * 70] * 4) + "\n\n## Code")
    chunks = chunk_article(parse_article(long_body), max_words=100)
    assert all(len(c.content.split()) <= 160 for c in chunks)
    assert sum(1 for c in chunks if c.heading.endswith("Setting up")) >= 2


def test_real_kb_chunks(settings):
    articles = load_articles(settings.kb_dir)
    assert len(articles) >= 40
    chunks = [c for a in articles for c in chunk_article(a)]
    assert all(c.content.strip() for c in chunks)
    assert {a.category for a in articles} == {
        "refunds",
        "failed_payments",
        "settlements",
        "payouts",
        "disputes",
        "kyc",
        "account_access",
        "api_keys",
        "webhooks",
        "checkout",
        "billing",
    }
