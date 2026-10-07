"""독일어 단어 하나 → Analysis JSON (프론트의 zod 스키마와 같은 모양). LLM 없이 번역기 + 각 언어 라이브러리로 만든다."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from align import align
from german import _tagger, cap, decompose_de, is_plausible_german
from targets import decompose_en, decompose_ja, decompose_ko, ja_candidates, ko_candidates
from wordfreq import zipf_frequency
from affixes import SUFFIX_GLOSS
from translator import Translator
from units import Morpheme, Unit

LANGS = ("en", "ko", "ja")

PREFIX_GLOSS = {
    # 독일어 접두사
    "zurück": "back", "unter": "under", "durch": "through", "über": "over / above", "nach": "after", "weg": "away",
    "vor": "before", "ver": "away / wrongly", "zer": "apart", "ent": "away / un-", "auf": "up / open", "aus": "out",
    "bei": "along / near", "ein": "in", "mit": "with / along", "her": "toward here", "hin": "toward there",
    "ab": "away / off", "an": "on / to", "be": "(verb prefix)", "er": "out / up (result)", "ge": "(collective / result)",
    "um": "around / re-", "un": "not", "zu": "to / shut",
    # 영어 접두사
    "de": "off / down", "re": "again / back", "pre": "before", "pro": "forth / for", "con": "together", "com": "together",
    "dis": "apart / not", "trans": "across", "inter": "between", "sub": "under", "ex": "out / former", "anti": "against",
    "non": "not", "mis": "wrongly", "super": "above / beyond",
    # 독일어 접두사 (추가)
    "emp": "(verb prefix)", "miss": "wrongly", "ur": "original", "zusammen": "together", "heraus": "out", "hinaus": "out (away)",
    "herein": "in (here)", "hinein": "in (there)", "voraus": "ahead", "wieder": "again", "wider": "against",
    # 영어 라틴·그리스계 접두사 (자음 앞에서 모양이 바뀐 것 포함)
    "in": "in / not", "im": "in / not", "il": "in / not", "ir": "in / not", "ad": "to", "ac": "to", "af": "to", "ag": "to", "al": "to",
    "ap": "to", "as": "to", "at": "to", "ob": "against", "oc": "against", "of": "against", "op": "against", "per": "through",
    "post": "after", "suc": "under", "suf": "under", "sup": "under", "sus": "under", "se": "apart", "ante": "before", "co": "together",
    "col": "together", "cor": "together", "intro": "into", "circum": "around", "contra": "against", "extra": "beyond", "retro": "back",
    "ultra": "beyond", "subter": "under", "dif": "apart", "ef": "out", "abs": "away", "apo": "away", "cata": "down", "dia": "through",
    "dys": "bad", "epi": "upon", "hyper": "over", "hypo": "under", "meta": "beyond", "para": "beside", "peri": "around",
    "syn": "together", "sym": "together", "tele": "far", "micro": "small", "macro": "large", "mono": "one", "poly": "many",
    "geo": "earth", "bio": "life", "auto": "self",
}

# 번역기는 전치사·불변화사를 문맥 없이 번역하면 엉뚱한 뜻을 낸다(Ein → 'A', Um → 'Um'). 합성어 앞요소로 흔한 말은 직접 적어 둔다.
PARTICLE_GLOSS = {
    "ein": "in / into", "aus": "out (of)", "an": "at / on / to", "auf": "on / up", "ab": "away / off / down",
    "um": "around / about", "über": "over / above / across", "unter": "under / among", "vor": "before / in front of",
    "nach": "after / toward", "zu": "to / closed", "mit": "with", "bei": "at / near", "durch": "through",
    "hin": "toward there", "her": "toward here", "gegen": "against", "ohne": "without", "für": "for", "von": "of / from",
    "zwischen": "between", "hinter": "behind", "neben": "beside", "rück": "back", "zurück": "back", "wider": "against",
}


def _affix_gloss(m: Morpheme) -> str | None:
    if m.role == "suffix":
        return SUFFIX_GLOSS.get(m.lemma)
    if m.role == "prefix":
        return PREFIX_GLOSS.get(m.lemma)
    return None


def _lookup(tr: Translator, text: str, src: str, dst: str) -> list[str]:
    try:
        return tr.lookup(text, src, dst)[:6]
    except Exception:  # noqa: BLE001
        return []


def _lookup_pos(tr: Translator, text: str, src: str, dst: str) -> dict[str, list[str]]:
    try:
        return tr.lookup_pos(text, src, dst)
    except Exception:  # noqa: BLE001
        return {}


def _german_pos(lemma: str) -> str | None:
    """독일어 요소의 품사(번역기의 사전 품사 이름으로): noun / verb / adjective / adverb."""
    try:
        tag = _tagger.analyze(lemma, taglevel=1)[1]
    except Exception:  # noqa: BLE001
        return None
    if tag.startswith("N"):
        return "noun"
    if tag.startswith("V"):
        return "verb"
    if tag.startswith("ADJ"):
        return "adjective"
    if tag.startswith("ADV"):
        return "adverb"
    return None


def _fill_gloss(units: list[Unit], tr: Translator, lang: str) -> None:
    """대응어 형태소마다 짧은 영어 뜻풀이. 영어 단어는 그 자체가 영어라 비워 둔다(문법 접미사 표지는 한국어)."""
    todo: list[Morpheme] = []
    for u in units:
        for m in u.morphemes:
            glossed = _affix_gloss(m)
            if glossed is not None:
                m.gloss = glossed
            elif m.lang != "en":
                todo.append(m)

    def run(m: Morpheme) -> None:
        text, src = (m.lookup_text or m.lemma), (m.lookup_lang or m.lang or lang)
        nouns = _lookup_pos(tr, text, src, "en").get("noun")  # 합성어 구성 요소는 명사가 대부분이라 명사 뜻을 우선
        if nouns:
            m.gloss = nouns[0].lower()
            return
        cands = _lookup(tr, text, src, "en")
        if cands:
            m.gloss = cands[0].lower()

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(run, todo))


def _fill_de_gloss(units: list[Unit], tr: Translator, evidence: dict[int, list[str]]) -> None:
    """독일어 형태소의 영어 뜻풀이. 번역기는 단어 하나만 주면 흔하지 않은 뜻부터 내놓는다(Kugel → bullet).
    ① 전치사·불변화사는 직접 적은 표에서, ② 세 언어 정렬에서 대응어와 영어 번역이 겹친 뜻(ball)을 우선,
    ③ 증거가 없으면 영어에서 더 흔한 뜻을 고른다."""
    flat = [m for u in units for m in u.morphemes]

    def run(item: tuple[int, Morpheme]) -> None:
        idx, m = item
        glossed = _affix_gloss(m)
        if glossed is not None:
            m.gloss = glossed
            return
        particle = PARTICLE_GLOSS.get(m.lemma.lower())
        if particle:
            m.gloss = particle
            return
        # 요소의 품사와 같은 사전 항목만 후보로 쓴다 (번역기의 문장 번역 결과 'A', 'Um' 같은 잡음이 빠진다)
        pos = _german_pos(m.lemma)
        in_pos = _lookup_pos(tr, m.lemma, "de", "en").get(pos, []) if pos else []
        en = in_pos or _lookup(tr, m.lemma, "de", "en")
        if not en:
            m.gloss = ""
            return
        low = [w.lower() for w in en]
        votes: dict[str, int] = {}
        for w in evidence.get(idx, []):
            if w.lower() in low:  # 품사가 맞는 후보에 들어 있는 증거만 인정
                votes[w.lower()] = votes.get(w.lower(), 0) + 1
        order = {w: r for r, w in enumerate(low)}
        if votes:
            m.gloss = min(votes, key=lambda w: (-votes[w], order[w]))
        else:
            # 영어 빈도가 높은 뜻을 좋아하되, 사전이 앞에 둔(관련도 높은) 후보에도 점수를 준다
            weight = 0.5 if in_pos else 0.3
            m.gloss = max(low[:5], key=lambda w: zipf_frequency(w, "en") - weight * order[w])

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(run, enumerate(flat)))


def _kind(units: list[Unit]) -> str:
    roots = sum(1 for u in units for m in u.morphemes if m.role != "suffix")
    total = sum(len(u.morphemes) for u in units)
    return "compound" if roots >= 2 else "derived" if total >= 2 else "simplex"


def _flat(units: list[Unit]) -> list[Morpheme]:
    return [m for u in units for m in u.morphemes]


def _decomposition(word: str, units: list[Unit], links: list[str]) -> dict:
    return {
        "word": word,
        "kind": _kind(units),
        "morphemes": [m.to_dict() for m in _flat(units)],
        "linking": links,
    }


def _comment(lang: str, found: bool, units: list[Unit], groups: list[dict], de_units: list[Unit]) -> str:
    if not found:
        return "번역기가 독일어 단어를 그대로 돌려줘서 적절한 대응어를 찾지 못했어요."
    flat = _flat(units)
    if len(units) == 1 and len(flat) == 1 and len(de_units) > 1:
        return "대응어가 하나로 굳은 단일어라 독일어처럼 요소를 쌓아 만든 말이 아니에요."
    loans = [m for m in flat if m.origin == "loan"]
    if loans and len(loans) == len([m for m in flat if m.role != "suffix"]):
        return "조합 방식은 닮아도 재료가 모두 외래어라, 그 언어 자체의 말 만들기는 아니에요."
    sino = [m for m in flat if m.origin == "sino"]
    if sino and len(sino) == len(flat):
        return "한자 형태소로 쪼개 보면 독일어처럼 뜻 요소를 쌓은 말이에요."
    if any(g["relation"] == "added" for g in groups):
        return "독일어에는 없는 요소가 하나 더 붙어 있어요."
    if all(g["relation"] == "same" for g in groups):
        return "요소끼리 뜻이 일대일로 대응해요."
    return "일부 요소는 뜻이 달라서 짜임이 완전히 같지는 않아요."


def _confidence(found: bool, groups: list[dict], fallback: bool, units: list[Unit]) -> str:
    if not found or not groups:
        return "low"
    unaligned = sum(1 for g in groups if g["relation"] in ("added", "missing"))
    if unaligned * 2 > len(groups):
        return "low"
    unknown = [m for m in _flat(units) if m.origin == "unknown"]
    if fallback or unknown:
        return "medium"
    return "high"


def _empty_target(lang: str) -> dict:
    return {"lang": lang, "found": False, "decomposition": {"word": "", "kind": "simplex", "morphemes": [], "linking": []},
            "alignment": [], "confidence": "low", "comment": ""}


def _is_noun(lower: str) -> bool:
    """소문자 단어가 명사인가. 첫 글자를 대문자로 했을 때 명사(NN)이고, 소문자 그대로는 동사·형용사·부사가 아닐 때 (schreiben 은 명사가 아니다)."""
    try:
        if _tagger.analyze(cap(lower), taglevel=1)[1] != "NN":
            return False
        return not _tagger.analyze(lower, taglevel=1)[1].startswith(("V", "ADJ", "ADV"))
    except Exception:  # noqa: BLE001
        return False


def normalize_input(word: str) -> str:
    """대소문자를 품사에 맞춘다. 전부 대문자(KRANKENHAUS)면 명사는 앞 글자만 대문자, 그 밖에는 전부 소문자로.
    전부 소문자로 쓴 명사(krankenhaus)도 앞 글자를 대문자로. 이미 섞여 있으면(Krankenhaus, e-Mail …) 손대지 않는다."""
    word = word.strip()
    if len(word) > 1 and word.isupper():
        base = word.lower()
    elif word.islower():
        base = word
    else:
        return word
    return cap(base) if _is_noun(base) else base


def analyze(word_in: str, tr: Translator) -> dict:
    word = normalize_input(word_in)
    de_units, links = decompose_de(word)
    de_ok = is_plausible_german(word, de_units)
    de_dec = _decomposition(word, de_units, links)
    if not de_ok:
        return {"input": word, "isGermanWord": False, "de": {**de_dec, "morphemes": []}, "targets": [_empty_target(l) for l in LANGS]}
    if len(_flat(de_units)) < 2:
        # 더 쪼갤 수 없는 단일 단어: 비교할 짜임이 없어서 어느 언어든 100% 가 되므로 번역기를 부르지 않고 멈춘다
        return {"input": word, "isGermanWord": True, "de": de_dec, "targets": [_empty_target(l) for l in LANGS]}

    def make(lang: str, main: str, units: list[Unit], found: bool) -> tuple[dict, dict[int, list[str]]]:
        groups: list[dict] = []
        fallback = False
        senses: dict[int, list[str]] = {}
        if found:
            groups, fallback, senses = align(de_units, units, lang, tr, word)
            _fill_gloss(units, tr, lang)
        return {
            "lang": lang,
            "found": found,
            "label": " | ".join(u.text for u in units),
            "decomposition": _decomposition(main if found else main or "", units, []),
            "alignment": groups,
            "confidence": _confidence(found, groups, fallback, units),
            "comment": _comment(lang, found, units, groups, de_units),
        }, senses

    def build(lang: str) -> tuple[dict, dict[int, list[str]]]:
        main = (tr.lookup(word, "de", lang) or [""])[0]
        if lang == "en" and main[:1].isupper() and main[1:] == main[1:].lower():
            main = main[:1].lower() + main[1:]
        found = bool(main) and main.lower() != word.lower()
        if not found:
            units: list[Unit] = []
        elif lang == "en":
            units = decompose_en(main)
        elif lang == "ja":
            units = decompose_ja(main, split_chars=True)
        else:
            units = decompose_ko(main, tr)
        found = found and bool(units)
        target, senses = make(lang, main, units, found)
        # 분석 후보: 한자어는 경계 조합마다 정렬을 해 두고, 화면 쪽(점수 공식이 있는 곳)에서 가장 잘 맞는 것을 고른다
        if found and lang in ("ko", "ja"):
            alts = ko_candidates(main, tr) if lang == "ko" else ja_candidates(main)
            seen = {tuple(u.text for u in units)}
            candidates = []
            for alt in alts:
                key = tuple(u.text for u in alt)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(make(lang, main, alt, True)[0])
            target["candidates"] = candidates
        return target, senses

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(build, LANGS))
    targets = [r[0] for r in results]

    # 세 언어의 정렬에서 모은 뜻 증거로 독일어 형태소의 뜻풀이를 고른다
    evidence: dict[int, list[str]] = {}
    for _, sn in results:
        for idx, words in sn.items():
            evidence.setdefault(idx, []).extend(words)
    _fill_de_gloss(de_units, tr, evidence)
    return {"input": word, "isGermanWord": True, "de": _decomposition(word, de_units, links), "targets": targets}
