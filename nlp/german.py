"""독일어 합성어 분해: HanTa(형태 분석) → CharSplit(+어휘 검증) → 접두사/접미사 분리."""

from __future__ import annotations

from functools import lru_cache

from compound_split import char_split
from HanTa import HanoverTagger as ht
from wordfreq import zipf_frequency

from lexicon import lookup_compound, lookup_derivation
from units import Morpheme, Unit

_tagger = ht.HanoverTagger("morphmodel_ger.pgz")

LINKS = ["s", "es", "n", "en", "e", "er", "ens"]

# ───────────── 접두사·접미사 데이터 ─────────────
# 분리 가능한 접사를 미리 적어 두고, 쪼갤 수 있는지 판정할 때 쓴다. 접사를 뗀 나머지가 실제 단어(또는 동사 어간)일 때만 인정한다.
# 강한 접두사: 거의 언제나 접두사로 쓰이는 비분리 접두사. 어간이 동사라면 합성어보다 빈도가 높은 단어도 쪼갠다 (verbinden = ver + binden)
STRONG_PREFIXES = ["miss", "ver", "zer", "ent", "emp", "be", "ge", "er", "un", "ur"]
# 약한 접두사: 전치사·분리 접두사. 합성어의 앞 요소와 구별이 어려워서 어간이 충분히 흔하고 전체가 훨씬 더 흔하지 않을 때만 쪼갠다
WEAK_PREFIXES = [
    "zurück", "zusammen", "heraus", "hinaus", "herein", "hinein", "voraus", "wieder", "wider", "unter", "durch", "über",
    "nach", "weg", "vor", "auf", "aus", "bei", "ein", "mit", "her", "hin", "ab", "an", "um", "zu",
]
PREFIXES = sorted(STRONG_PREFIXES + WEAK_PREFIXES, key=len, reverse=True)
# 어간 종류: v = 동사에서(Verbindung ← verbinden), n = 명사·형용사에서(Freundschaft ← Freund), vn = 둘 다. (접미사, 어간 종류)
SUFFIX_DATA = [
    ("schaft", "n"), ("heit", "n"), ("keit", "n"), ("tum", "n"), ("ling", "n"), ("chen", "n"), ("lein", "n"),
    ("nis", "vn"), ("ung", "v"), ("lich", "vn"), ("bar", "vn"), ("sam", "vn"), ("haft", "n"), ("los", "n"),
    ("isch", "n"), ("ig", "n"), ("ler", "n"), ("ei", "n"), ("in", "n"), ("er", "v"),
]
SUFFIX_MIN_STEM = {"ig": 5, "in": 5, "ei": 5}  # 짧은 접미사는 어간이 길 때만 (Termin, Datei 같은 말을 지킨다). 기본은 4
SUFFIXES = sorted(SUFFIX_DATA, key=lambda x: len(x[0]), reverse=True)
# 합성어의 뒷 요소가 아니라 접미사로 다뤄야 하는 것들
DERIVATIONAL_TAILS = {"heit", "keit", "schaft", "ung", "lich", "chen", "lein", "nis", "tum", "ling", "ler", "erin"}
ADJ_TAILS = {"bar", "los", "sam", "haft", "ig", "isch"}  # 소문자로 시작하는 낱말(형용사)에서만 접미사. Cocktailbar 의 Bar 는 합성어 요소
# 파생어처럼 보이지만 어원상 굳은 말
LEXICALIZED = {"nachbar", "zufrieden", "messer", "finger", "zimmer", "wasser", "butter", "mutter", "vater", "bruder", "schwester", "donner",
               "verein", "hammer", "vitamin", "zucker", "schüler", "teller"}
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
    for link in sorted(LINKS, key=len, reverse=True):  # 연결요소를 떼는 쪽을 우선, 긴 것부터 (Abfahrts → Abfahrt, Bundes → Bund+es 이지 Bunde+s 가 아님)
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


def _is_derived_word(w: str) -> bool:
    """사전에 없어도 '흔한 어간 + 파생 접미사'로 설명되는 말인가 (Anwaltschaft = Anwalt + -schaft). 합성어 요소 검증에 쓴다."""
    ms = split_affixes(w)
    stem = [m for m in ms if m.role != "suffix"][-1].lemma.lower()
    # 어간이 짧거나 그 자체가 접미사면 우연일 수 있다 (Bar+schaft, Wissen+Schaft+ler)
    return any(m.role == "suffix" for m in ms) and len(stem) >= 5 and stem not in DERIVATIONAL_TAILS


def _charsplit(word: str) -> tuple[str, str, str] | None:
    """CharSplit 후보 중 어휘 검증을 통과한 최고 점수 분해 → (앞, 뒤, 연결요소)."""
    best: tuple[float, str, str, str] | None = None
    for score, a, b in char_split.split_compound(word)[:8]:
        if score < -0.9 or len(a) < 3 or len(b) < 3:
            continue
        if b.lower() in DERIVATIONAL_TAILS or (b.lower() in ADJ_TAILS and word[:1].islower()):
            continue  # -lich, -schaft, 형용사의 -bar·-los 같은 파생 접미사는 합성어의 뒷 요소가 아니라 접미사로 다룬다
        sl = strip_link(a)
        if sl is None or not (is_word(b, 2.6) or (len(a) >= 4 and _is_derived_word(b))):
            continue
        stem, link = sl
        value = score + 0.15 * (min(zipf(stem), 6) + min(zipf(b), 6)) - (0.4 if link else 0)
        if best is None or value > best[0]:
            best = (value, stem, b, link)
    return (best[1], best[2], best[3]) if best else None


def _split_by_lexicon(word: str, depth: int, hints: dict[str, str]) -> tuple[list[str], list[str]] | None:
    """Wiktionary 어원에서 만든 분해 사전을 먼저 조회한다. 있으면 각 조각을 다시 조회해 더 쪼갠다 (Bundesanwaltschaft → Bund + Anwaltschaft).
    조각의 사전 기본형(Grenzkosten 의 Grenz → Grenze)은 hints 에 모아 둔다."""
    entry = lookup_compound(word)
    if entry is None or depth > 3:
        return None
    out: list[str] = []
    links: list[str] = list(entry.links)
    for surface, lemma in zip(entry.surfaces, entry.lemmas):
        sub = _split_by_lexicon(surface, depth + 1, hints) or (_split_by_lexicon(lemma, depth + 1, hints) if lemma != surface else None)
        if sub:
            out.extend(sub[0])
            links.extend(sub[1])
        else:
            out.append(surface)
            hints[surface] = lemma
    return out, links


def split_compound(word: str, depth: int = 0, hints: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """합성어 → (요소 표면형 리스트, 연결요소 리스트). 사전(있으면) → 규칙 순서. hints 를 주면 사전의 기본형을 거기에 채운다."""
    if word.lower() not in LEXICALIZED:
        found = _split_by_lexicon(word, depth, hints if hints is not None else {})
        if found:
            return found
    if depth > 3 or len(word) < 6 or word.lower() in LEXICALIZED:
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


@lru_cache(maxsize=4096)
def _verb_inf(stem: str) -> str | None:
    """동사 어간 → 부정형(binden ← bind, wickeln ← wickl, wandern ← wander, hoffen ← hoffn). 실제 동사의 부정형일 때만."""
    cands = [stem + "en", stem + "n"]
    if stem and stem[-1] in "lr" and len(stem) >= 3:
        cands.append(stem[:-1] + "e" + stem[-1] + "n")
    if stem.endswith("n"):
        cands.append(stem[:-1] + "en")
    for c in cands:
        if not is_word(c, 3.2):
            continue
        try:
            lemma, tag = _tagger.analyze(c, taglevel=1)[0], _tagger.analyze(c, taglevel=1)[1]
        except Exception:  # noqa: BLE001
            continue
        if tag.startswith("V") and lemma.lower() == c.lower():  # fingen → fangen 처럼 다른 동사의 활용형은 제외
            return c
    return None


def _noun_adj_base(stem: str, minimum: float) -> str | None:
    base = _suffix_base(stem, minimum)
    if base is None and stem.endswith("s") and len(stem) >= 5:  # 연결 -s-: Hoffnungs → Hoffnung
        base = _suffix_base(stem[:-1], minimum)
    return base


def _resolve(stem: str, kind: str, minimum: float, depth: int = 0) -> tuple[list[str], str] | None:
    """접미사를 뗀 어간이 '(접두사들) + 실제 단어'로 설명되는가. 설명되면 (접두사 목록, 어근 기본형).
    접두사를 먼저 떼어 본다: unverbindlich 의 verbind → ver + binden."""
    low = stem.lower()
    if low in LEXICALIZED:
        return [], low
    if depth < 3:
        for p in PREFIXES:
            rest = low[len(p):]
            if not low.startswith(p) or len(rest) < 3:
                continue
            strong = p in STRONG_PREFIXES
            if p == "ge" and any(c in "äöü" for c in rest):
                continue  # Gefährlich 의 fähr 처럼 움라우트 어간에 붙은 ge- 는 우연한 일치가 많다
            if not strong and not (zipf(rest) >= 3.6 and zipf(low) < zipf(rest) + 1.5):
                continue
            sub = _resolve(rest, kind, minimum, depth + 1)
            if sub is None:
                continue
            # erlaub+nis: 통째로 동사(erlauben)인데 어간만 명사(Laub)로 설명되는 우연한 일치는 쪼개지 않는다
            if not (sub[1][:1].islower() and sub[1].endswith("n")) and _verb_inf(low):
                continue
            if strong and p in ("ge", "be", "er", "ver", "zer", "ent", "emp") and not sub[0] and sub[1] == rest and len(rest) < 5:
                continue  # 짧은 명사·형용사 어간에 붙은 우연한 일치(Beet, Verein …)는 제외
            return [p, *sub[0]], sub[1]
    if kind in ("v", "vn"):
        inf = _verb_inf(low)
        if inf:
            return [], inf
    if kind in ("n", "vn") and len(low) >= 4:
        base = _noun_adj_base(low, minimum)
        if base:
            return [], base
    return None


TRIVIAL_SUFFIXES = {"e", "en", "n", "s", "t", "es"}  # 어미 수준이라 형태소로 떼지 않는다 (Frage = frag + -e 로 만들지 않는다)


def _split_by_derivation_lexicon(part: str) -> list[Morpheme] | None:
    """파생어 사전(Wiktionary 어원)이 '이 단어에는 이 접사가 있다'고 한 것을 먼저 적용한다. 외래 접사(-ismus, -ation, -ator …)나
    규칙이 놓치는 말(tödlich = Tod + -lich)을 잡는다. 접사를 뗀 어간은 다시 규칙으로 풀어 더 안쪽 접사도 찾는다 (Wissenschaftler → Wissen + -schaft + -ler)."""
    entry = lookup_derivation(part)
    if entry is None:
        return None
    low = part.lower()
    pre = [p for p in entry[0] if low.startswith(p)]
    suf = [x for x in entry[1] if x not in TRIVIAL_SUFFIXES and low.endswith(x)]
    stem = low
    used_pre: list[str] = []
    for p in pre:
        if stem.startswith(p) and len(stem) - len(p) >= 3:
            used_pre.append(p)
            stem = stem[len(p):]
    used_suf: list[str] = []
    for x in suf:
        if stem.endswith(x) and len(stem) - len(x) >= 3:
            used_suf.append(x)
            stem = stem[: -len(x)]
    if not used_pre and not used_suf:
        return None
    start = sum(len(p) for p in used_pre)
    root_surface = part[start : len(part) - sum(len(x) for x in used_suf)]
    if part[:1].isupper() and used_pre:
        root_surface = cap(root_surface)
    inner = split_affixes(root_surface) if len(root_surface) >= 5 else [Morpheme(root_surface, root_surface, role="root", origin="native", lang="de")]
    if len(inner) == 1 and inner[0].lemma == inner[0].surface:
        # 어간의 기본형 복원 (Gesell → Geselle). 접미사가 아는 종류(-schaft 는 명사 어간 …)면 그 종류로, 아니면 동사·명사 모두
        kind = dict(SUFFIX_DATA).get(used_suf[-1], "vn") if used_suf else "vn"
        resolved = _resolve(root_surface.lower(), kind, 3.0)
        if resolved and not resolved[0] and resolved[1].lower() != root_surface.lower():
            inner[0].lemma = resolved[1]
    out = [Morpheme(p, p, role="prefix", origin="native", lang="de") for p in used_pre] + inner
    out += [Morpheme(f"-{x}", f"-{x}", role="suffix", origin="native", lang="de") for x in reversed(used_suf)]
    return out


def split_affixes(part: str) -> list[Morpheme]:
    """한 요소(Abfahrt, Verbindung, unverbindlich …)를 접두사들 / 어근 / 접미사들로. 확실할 때만 쪼갠다.
    접미사를 안쪽으로 한두 겹 벗기고(Lehrerin = Lehr + -er + -in), 남은 어간에서 접두사를 벗긴다(un + ver + bind)."""
    low = part.lower()
    if low in LEXICALIZED:
        return [Morpheme(part, part, role="root", origin="native", lang="de")]
    from_lexicon = _split_by_derivation_lexicon(part)
    if from_lexicon:
        return from_lexicon
    stem = low
    suffixes: list[str] = []
    resolved: tuple[list[str], str] | None = None
    for _ in range(2):
        if stem in LEXICALIZED:
            break
        for suf, kind in SUFFIXES:
            if suf in ADJ_TAILS and part[:1].isupper() and not suffixes and suf in ("bar",):
                pass  # 명사로 쓰인 낱말의 -bar 도 접미사로 본다 (Dankbarkeit 안의 dankbar 처럼 대문자로 시작해도 되도록 둔다)
            if not stem.endswith(suf) or len(stem) - len(suf) < SUFFIX_MIN_STEM.get(suf, 4):
                continue
            sub = stem[: -len(suf)]
            r = _resolve(sub, kind, 3.0 if suf in STRONG_SUFFIXES else 3.4)
            if r is None:
                continue
            if suf == "er" and sub.endswith("er"):  # Lehrer + in 같은 겹침은 위에서 처리
                continue
            suffixes.append(suf)
            stem, resolved = sub, r
            break
        else:
            break
    if resolved is None:
        resolved = _resolve(stem, "vn", 3.4) if len(stem) >= 5 else None
        if resolved is not None and not resolved[0]:
            resolved = None  # 접두사가 없으면 쪼갤 것이 없다
    prefixes, lemma = resolved if resolved else ([], part[: len(stem)])
    pre_len = sum(len(p) for p in prefixes)
    root = part[pre_len : len(stem)]
    if part[:1].isupper() and not prefixes:
        pass
    elif part[:1].isupper():  # 명사는 접두사를 떼도 명사: Abfahrt → ab + Fahrt
        root = cap(root)
    if not resolved or lemma.lower() == root.lower():
        lemma = root
    out: list[Morpheme] = []
    pos = 0
    for p in prefixes:
        out.append(Morpheme(p, p, role="prefix", origin="native", lang="de"))
        pos += len(p)
    out.append(Morpheme(root, lemma, role="root", origin="native", lang="de"))
    for suf in reversed(suffixes):
        out.append(Morpheme(f"-{suf}", f"-{suf}", role="suffix", origin="native", lang="de"))
    return out


def _hint_lemma(surface: str, lemma: str) -> str:
    """사전 기본형을 형태소 기본형으로: Gäns → Gans, Grenz → Grenze. 형용사 명사화형(Kranker)에서 온 어간은 형용사로(krank)."""
    if lemma.lower().startswith(surface.lower()) and lemma.lower().endswith(("er", "es", "en")) and len(lemma) - len(surface) == 2:
        return surface.lower()
    return lemma


def decompose_de(word: str) -> tuple[list[Unit], list[str]]:
    hints: dict[str, str] = {}
    parts, links = split_compound(word, hints=hints)
    units: list[Unit] = []
    for p in parts:
        low = p.lower()
        # HanTa/CharSplit 가 접미사를 독립 요소로 떼어낸 경우(Gesund+heit)엔 앞 요소에 붙인다.
        if units and (low in DERIVATIONAL_TAILS or (low in ADJ_TAILS and word[:1].islower())):
            units[-1].morphemes.append(Morpheme(f"-{low}", f"-{low}", role="suffix", origin="native", lang="de"))
            units[-1].text += low
            continue
        morphs = split_affixes(p)
        if len(morphs) == 1 and p in hints and morphs[0].lemma == morphs[0].surface:
            morphs[0].lemma = _hint_lemma(p, hints[p])
        units.append(Unit(text=p, morphemes=morphs))
    # 합성어 분해가 접두사를 따로 떼어낸 경우(Ver|Gleich, Vor|Sicht)엔 뒤 요소에 접두사로 붙인다: ver + gleich
    merged: list[Unit] = []
    i = 0
    while i < len(units):
        u = units[i]
        low = u.text.lower()
        if low in PREFIXES and len(u.morphemes) == 1 and i + 1 < len(units):
            nxt = units[i + 1]
            nxt.morphemes.insert(0, Morpheme(low, low, role="prefix", origin="native", lang="de"))
            nxt.text = u.text + nxt.text
            i += 1
            continue
        merged.append(u)
        i += 1
    return merged, links


def is_plausible_german(word: str, units: list[Unit]) -> bool:
    return len(units) > 1 or zipf(word) > 0
