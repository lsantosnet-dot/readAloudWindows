from readaloud.textproc import MAX_SEGMENT_CHARS, clean_for_speech, make_title, split_segments


def test_clean_markdown():
    md = """# Título

Um **texto** com [link](https://exemplo.com) e `código`.

- item um
- item dois

> citação

![figura](img.png) https://site.com/pagina
"""
    cleaned = clean_for_speech(md)
    for junk in ("#", "**", "](", "`", "https", "> ", "- item"):
        assert junk not in cleaned
    assert "Título" in cleaned
    assert "Um texto com link e código." in cleaned
    assert "item um" in cleaned


def test_segments_respect_max_size_and_keep_words():
    text = ("Esta é uma frase de teste. " * 60) + ("palavra " * 200)
    segments = split_segments(text)
    assert len(segments) > 1
    assert all(len(s) <= MAX_SEGMENT_CHARS for s in segments)
    assert sum(s.count("palavra") for s in segments) == 200


def test_list_lines_become_sentences():
    assert split_segments("Compras\nleite\npão") == ["Compras. leite. pão."]


def test_no_readable_text():
    assert split_segments("``` \n --- \n ***") == []


def test_title():
    assert make_title("\n\n## Olá mundo\nresto") == "Olá mundo"
    assert make_title("x" * 200).endswith("…")
