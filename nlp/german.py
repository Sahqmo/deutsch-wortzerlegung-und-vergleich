"""독일어 합성어 분해: HanTa(형태 분석) → CharSplit(+어휘 검증) → 접두사/접미사 분리."""

from __future__ import annotations

from compound_split import char_split
from HanTa import HanoverTagger as ht
from wordfreq import zipf_frequency

from units import Morpheme, Unit

_tagger = ht.HanoverTagger("morphmodel_ger.pgz")

LINKS = ["s", "es", "n", "en", "e", "er", "ens"]
PREFIXES = [
    "zurück", "unter", "durch", "über", "nach", "weg", "vor", "ver", "zer", "ent", "auf", "aus", "bei", "ein",
    "mit", "her", "hin", "ab", "an", "be", "er", "ge", "um", "un", "zu",
]
VERB_SUFFIXES = ["ung", "er"]
ADJ_SUFFIXES = ["schaft", "keit", "heit", "lich", "chen", "lein", "nis"]
DERIVATIONAL_TAILS = {"heit", "keit", "schaft", "ung", "lich", "chen", "lein", "nis"}
# 파생 접미사로 쓰이는 것들 중 단어 빈도가 낮은 어간(Geselle)도 받아들이는 접미사 (구별력이 높다)
STRONG_SUFFIXES = {"schaft", "keit", "heit", "lich", "nis"}


def zipf(w: str) -> float:
    return zipf_frequency(w.lower(), "de")


def is_word(w: str, minimum: float = 3.0) -> bool:
    """사전(빈도 목록)에 있는 단어인가. 3글자 이하는 더 엄격하게."""
    if len(w) < 3:
        return False
    return zipf(w) >= (minimum + 0.8 if len(w) == 3 else minimum)


def cap(w: str) -> str:
    return w[:1].upper() + w[1:]


def is_verb(infinitive: str) -> bool:
    try:
        return _tagger.analyze(infinitive, taglevel=1)[1].startswith("V")
    except Exception:  # noqa: BLE001
        return False


def strip_link(part: str) -> tuple[str, str] | None:
    """합성어 앞 요소 → (어간, 연결요소). 어간이 사전에 없으면 None."""
    low = part.lower()
    for link in LINKS:  # 연결요소를 떼는 쪽을 우선 (Abfahrts → Abfahrt)
        if low.endswith(link) and len(low) - len(link) >= 3 and is_word(low[: -len(link)], 3.3):
            if not is_word(low, 4.6) or link in ("s", "es"):
                return part[: -len(link)], link
    if is_word(low, 3.0):
        return part, ""
    return None


def _hanta_split(word: str) -> tuple[list[str], list[str]] | None:
    """HanTa 합성어 분석 → (요소, 연결요소). 분해되지 않거나 의심스러우면 None."""
    try:
        parts = _tagger.analyze(word, taglevel=3)[1]
    except Exception:  # noqa: BLE001
        return None
    content = [(l, p) for l, p in parts if not p.startswith(("FUGE", "SUF"))]
    links = [l for l, p in parts if p.startswith("FUGE") or p.startswith("SUF")]
    if len(content) < 2 or not all(is_word(l, 3.0) for l, _ in content):
        return None
    return [cap(l) if p.startswith("N") else l for l, p in content], links


def _charsplit(word: str) -> tuple[str, str, str] | None:
    """CharSplit 후보 중 어휘 검증을 통과한 최고 점수 분해 → (앞, 뒤, 연결요소)."""
    best: tuple[float, str, str, str] | None = None
    for score, a, b in char_split.split_compound(word)[:8]:
        if score < -0.9 or len(a) < 3 or len(b) < 3:
            continue
        if b.lower() in DERIVATIONAL_TAILS:  # -lich, -schaft 같은 파생 접미사는 합성어의 뒷 요소가 아니라 접미사로 다룬다
            continue
        sl = strip_link(a)
        if sl is None or not is_word(b, 2.6):
            continue
        stem, link = sl
        value = score + 0.15 * (min(zipf(stem), 6) + min(zipf(b), 6)) - (0.4 if link else 0)
        if best is None or value > best[0]:
            best = (value, stem, b, link)
    return (best[1], best[2], best[3]) if best else None


def split_compound(word: str, depth: int = 0) -> tuple[list[str], list[str]]:
    """합성어 → (요소 표면형 리스트, 연결요소 리스트)."""
    if depth > 3 or len(word) < 6:
        return [word], []
    if depth > 0 and len(word) < 10:  # 하위 요소는 충분히 길 때만 다시 쪼갠다 (Schreiber → Sch+Reiber 방지)
        return [word], []
    h = _hanta_split(word)
    if h:
        out: list[str] = []
        links = list(h[1])
        for p in h[0]:
            sub, sub_links = split_compound(p, depth + 1)
            out.extend(sub)
            links.extend(sub_links)
        return out, links
    c = _charsplit(word)
    if c:
        a, b, link = c
        left, l1 = split_compound(a, depth + 1)
        right, l2 = split_compound(b, depth + 1)
        return left + right, ([link] if link else []) + l1 + l2
    return [word], []


def _suffix_base(stem: str, minimum: float) -> str | None:
    """접미사를 뗀 어간에서 원래 단어를 복원한다: 그대로(Freund) · +e(Gesell → Geselle) · 움라우트 풀기(gefähr → Gefahr)."""
    plain = stem.translate(str.maketrans("äöü", "aou"))
    candidates = [stem, stem + "e"] + ([plain, plain + "e"] if plain != stem else [])
    for c in candidates:
        if is_word(c, minimum):
            return _cased_lemma(c)
    return None


def _cased_lemma(word: str) -> str:
    """대소문자만 바로잡는다: 명사면 대문자(geselle → Geselle), 형용사·동사면 소문자(gemein). 다른 낱말로 바꾸지는 않는다."""
    try:
        lemma, tag = _tagger.analyze(cap(word), taglevel=1)
        if tag.startswith("NN") and lemma.lower() == word.lower():
            return lemma
        lemma = _tagger.analyze(word.lower(), taglevel=1)[0]
        return lemma if lemma.lower() == word.lower() else word.lower()
    except Exception:  # noqa: BLE001
        return word


def split_affixes(part: str) -> list[Morpheme]:
    """한 요소(Abfahrt, Schreiber …)를 접두사/어근/접미사로. 확실할 때만 쪼갠다."""
    low = part.lower()
    prefix = ""
    root = part
    for p in PREFIXES:
        rest = low[len(p):]
        if low.startswith(p) and len(rest) >= 4 and zipf(rest) >= 3.6 and zipf(low) < zipf(rest) + 1.5:
            prefix, root = p, part[len(p):]
            if part[:1].isupper():  # 명사는 접두사를 떼도 명사: Abfahrt → ab + Fahrt
                root = cap(root)
            break

    suffix = ""
    lemma = root
    rlow = root.lower()
    for s_ in VERB_SUFFIXES + ADJ_SUFFIXES:
        if not rlow.endswith(s_) or len(rlow) - len(s_) < 3:
            continue
        stem = rlow[: -len(s_)]
        if s_ in VERB_SUFFIXES:
            inf = stem + "en"
            if is_word(inf, 3.2) and is_verb(inf) and zipf(rlow) <= zipf(inf) + 0.3:
                suffix, lemma, root = s_, inf, root[: -len(s_)]
                break
        else:
            base = _suffix_base(stem, 3.0 if s_ in STRONG_SUFFIXES else 3.4)
            if base:
                suffix, lemma, root = s_, base, root[: -len(s_)]
                break

    out: list[Morpheme] = []
    if prefix:
        out.append(Morpheme(prefix, prefix, role="prefix", origin="native", lang="de"))
    out.append(Morpheme(root, lemma, role="root", origin="native", lang="de"))
    if suffix:
        out.append(Morpheme(f"-{suffix}", f"-{suffix}", role="suffix", origin="native", lang="de"))
    return out


def decompose_de(word: str) -> tuple[list[Unit], list[str]]:
    parts, links = split_compound(word)
    units: list[Unit] = []
    for p in parts:
        # HanTa/CharSplit 가 접미사를 독립 요소로 떼어낸 경우(Gesund+heit)엔 앞 요소에 붙인다.
        if units and p.lower() in DERIVATIONAL_TAILS:
            units[-1].morphemes.append(Morpheme(f"-{p.lower()}", f"-{p.lower()}", role="suffix", origin="native", lang="de"))
            units[-1].text += p.lower()
            continue
        units.append(Unit(text=p, morphemes=split_affixes(p)))
    return units, links


def is_plausible_german(word: str, units: list[Unit]) -> bool:
    return len(units) > 1 or zipf(word) > 0
