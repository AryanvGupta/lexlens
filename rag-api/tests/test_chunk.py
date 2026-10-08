from app.ingest.chunk import MAX_WORDS, OVERLAP_WORDS, chunk_source, split_words

SRC = {"id": "usc-x", "url": "http://example/x"}


def html(sec, head, paras):
    body = "".join(f"<p>{p}</p>" for p in paras)
    return (
        f"<!-- itempath:/10/CHAPTER 1/Sec. {sec} -->\n"
        f'<h3 class="section-head">&sect;{sec}. {head}</h3>\n'
        f"<!-- field-start:statute -->{body}<!-- field-end:statute -->\n"
    )


def test_sections_and_metadata():
    doc = html("1", "One", ["alpha beta"]) + html("2", "Two", ["gamma"])
    cs = chunk_source(SRC, doc)
    assert [c.id for c in cs] == ["usc-x:1:0", "usc-x:2:0"]
    assert cs[0].title == "§1. One" and cs[0].text == "alpha beta"
    assert cs[0].char_end <= cs[1].char_start


def test_section_without_body_skipped():
    doc = "<!-- itempath:/10/Sec. 9 -->\n<h3>repealed</h3>\n" + html("2", "Two", ["x"])
    assert [c.section for c in chunk_source(SRC, doc)] == ["2"]


def test_split_respects_limit_and_overlaps():
    paras = [" ".join(f"w{i}_{j}" for j in range(200)) for i in range(3)]
    chunks = split_words(paras)
    assert len(chunks) > 1
    assert all(len(c.split()) <= MAX_WORDS for c in chunks)
    tail = chunks[0].split()[-OVERLAP_WORDS:]
    assert chunks[1].split()[:OVERLAP_WORDS] == tail


def test_oversize_paragraph_hard_split():
    chunks = split_words([" ".join(["w"] * (MAX_WORDS * 2 + 10))])
    assert all(len(c.split()) <= MAX_WORDS for c in chunks) and len(chunks) >= 3


def test_zero_overlap_does_not_repeat_text(monkeypatch):
    import app.ingest.chunk as c

    monkeypatch.setattr(c, "MAX_WORDS", 10)
    monkeypatch.setattr(c, "OVERLAP_WORDS", 0)
    words = [f"w{i}" for i in range(35)]
    chunks = c.split_words([" ".join(words[:12]), " ".join(words[12:])])
    assert " ".join(chunks).split() == words
