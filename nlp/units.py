from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Morpheme:
    surface: str
    lemma: str
    gloss: str = ""
    role: str = "root"  # root | prefix | suffix
    origin: str = "unknown"  # native | sino | loan | calque | unknown
    lang: str = ""
    # 번역 조회에 쓸 텍스트/언어 (한국어 한자어는 한자로 조회). 비어 있으면 lemma/lang.
    lookup_text: str = ""
    lookup_lang: str = ""

    def to_dict(self) -> dict:
        return {
            "surface": self.surface,
            "lemma": self.lemma,
            "gloss": self.gloss,
            "role": self.role,
            "origin": self.origin,
        }


@dataclass
class Unit:
    """합성어의 한 요소(독일어의 Abfahrt, 영어 단어 하나, 한국어 한자어 한 단어 …). 형태소들을 묶는다."""

    text: str
    morphemes: list[Morpheme] = field(default_factory=list)
