"""Text length in "words" for English and Chinese (CJK) text alike.

Chinese and Japanese are written without spaces, so `len(text.split())`
counts a whole Chinese paragraph as one or a few words. Here each CJK
character counts as 1 / CJK_CHARS_PER_WORD of a word, and everything else is
counted by whitespace-separated words as before. English-only text gets
exactly the same count as `len(text.split())`, so the thresholds in config.py
(FULL_TEXT_MIN_WORDS, MAX_CONTENT_WORDS) keep their meaning and apply to
Chinese text at roughly the same amount of content.
"""

import re

# About 1.5 Chinese characters carry as much content as one English word
CJK_CHARS_PER_WORD = 1.5

# CJK ideographs (incl. extension A and compatibility), Japanese kana, Korean
_CJK = r"㐀-䶿一-鿿豈-﫿぀-ヿ가-힯"
_CJK_CHAR = re.compile(f"[{_CJK}]")
# One token: a single CJK character, or a run of other non-space characters
_TOKEN = re.compile(f"[{_CJK}]|[^\\s{_CJK}]+")


def has_cjk(text: str | None) -> bool:
    return bool(text and _CJK_CHAR.search(text))


def text_length(text: str | None) -> int:
    """Length in English-word equivalents (rounded down)."""
    if not text:
        return 0
    units = 0.0
    for token in _TOKEN.finditer(text):
        units += 1 / CJK_CHARS_PER_WORD if _CJK_CHAR.fullmatch(token.group()) else 1
    return int(units)


def truncate_text(text: str, max_words: int) -> str:
    """The start of `text` up to `max_words` (as counted by text_length()).

    English-only text is returned as its first `max_words` words joined by
    single spaces, as before; text with CJK characters keeps its original
    spacing up to the cut.
    """
    if not has_cjk(text):
        return " ".join(text.split()[:max_words])

    units = 0.0
    for token in _TOKEN.finditer(text):
        units += 1 / CJK_CHARS_PER_WORD if _CJK_CHAR.fullmatch(token.group()) else 1
        if units > max_words:
            return text[:token.start()].rstrip()
    return text
