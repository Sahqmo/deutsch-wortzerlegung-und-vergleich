"""독일어 합성어 분해 사전 조회. build_lexicon.py 가 만든 lexicon.sqlite(Wiktionary 어원 기반)를 읽는다.

파일이 없으면 조용히 비활성화되어, 호출하는 쪽은 규칙 기반 분해로 넘어간다.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path(__file__).parent / "lexicon.sqlite"


@dataclass(frozen=True)
class CompoundEntry:
    surfaces: tuple[str, ...]  # 입력 단어의 조각 (연결요소 제외): Abfahrt, Zeit
    lemmas: tuple[str, ...]  # 사전의 기본형: Abfahrt, Zeit (Grenzkosten → Grenze, Kosten)
    links: tuple[str, ...]  # 연결요소: s


_lock = threading.Lock()
_con: sqlite3.Connection | None = None
_checked = False


def _connection() -> sqlite3.Connection | None:
    global _con, _checked
    if _checked:
        return _con
    with _lock:
        if not _checked:
            if DB_PATH.exists():
                _con = sqlite3.connect(DB_PATH, check_same_thread=False)
            _checked = True
    return _con


def available() -> bool:
    return _connection() is not None


def lookup_compound(word: str) -> CompoundEntry | None:
    """단어(표면형)가 사전에 합성어로 있으면 분해를 돌려준다. 대소문자는 구별하되 첫 글자만 바꿔서도 찾아 본다."""
    con = _connection()
    if con is None:
        return None
    for key in dict.fromkeys([word, word[:1].upper() + word[1:], word[:1].lower() + word[1:]]):
        row = con.execute("SELECT surfaces, lemmas, links FROM compound WHERE word = ?", (key,)).fetchone()
        if row:
            surfaces, lemmas, links = row
            return CompoundEntry(tuple(surfaces.split("|")), tuple(lemmas.split("|")), tuple(l for l in links.split(",") if l))
    return None


def lookup_derivation(word: str) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """파생어 사전: Wiktionary 어원에 적힌 (접두사들, 접미사들). 구성요소는 읽지 않고 접사만 쓴다. 없으면 None."""
    con = _connection()
    if con is None:
        return None
    for key in dict.fromkeys([word, word[:1].upper() + word[1:], word[:1].lower() + word[1:]]):
        row = con.execute("SELECT prefixes, suffixes FROM derivation WHERE word = ?", (key,)).fetchone()
        if row:
            return tuple(x for x in row[0].split(",") if x), tuple(x for x in row[1].split(",") if x)
    return None
