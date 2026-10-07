"""영어·한국어·일본어 대응어 분해. 각 언어의 라이브러리(wordfreq / Kiwi+hanja / fugashi+UniDic)를 쓴다."""

from __future__ import annotations

import re

import fugashi
from hanja.table import hanja_table
from kiwipiepy import Kiwi
from wordfreq import zipf_frequency

from translator import Translator
from units import Morpheme, Unit

# ───────────────────────── 일본어 (fugashi + UniDic) ─────────────────────────

_ja = fugashi.Tagger()
GOSHU_ORIGIN = {"和": "native", "漢": "sino", "外": "loan", "混": "unknown", "固": "native"}
SKIP_POS1 = {"助詞", "助動詞", "補助記号", "記号", "空白"}
KANJI = re.compile(r"[一-鿿]")
KATAKANA = re.compile(r"^[゠-ヿー]+$")


def _ja_lemma(token) -> str:
    lemma = getattr(token.feature, "lemma", None) or token.surface
    return lemma.split("-")[0] if lemma else token.surface


def _ja_known_single(part: str) -> bool:
    toks = _ja(part)
    return len(toks) == 1 and not toks[0].is_unk and toks[0].surface == part


def _ja_reading(part: str) -> str:
    """가타카나 읽기에서 탁점·반탁점을 뺀 것(연탁 手+袋 = て+ぶくろ 를 같게 보려고). 못 구하면 빈 문자열.
    활용한 모양 그대로의 읽기(kana: 取り=トリ)를 쓴다. 사전형 읽기(lForm: 取り=トル)로 비교하면 오쿠리가나 합성어(取り消し)가 쪼개지지 않는다."""
    import unicodedata

    toks = _ja(part)
    kana = "".join((getattr(t.feature, "kana", None) or getattr(t.feature, "lForm", None) or "") for t in toks)
    return "".join(c for c in unicodedata.normalize("NFD", kana) if c not in "゙゚")


def _is_true_compound(whole: str, a: str, b: str) -> bool:
    """whole 이 a+b 의 실제 합성어인가: 읽기가 부분 읽기의 이어 붙임과 같아야 한다 (今日=きょう 는 今+日 이 아님)."""
    rw, ra, rb = _ja_reading(whole), _ja_reading(a), _ja_reading(b)
    return bool(rw) and rw == ra + rb


def decompose_ja(text: str) -> list[Unit]:
    units: list[Unit] = []
    for t in _ja(text):
        pos1 = getattr(t.feature, "pos1", "") or ""
        # 無害+な 처럼 명사/형용동사에 붙는 어미 な·に(だ의 활용)는 접미사 형태소로 둔다. 독일어 -lich 와 짝지어진다
        if pos1 == "助動詞" and t.surface in ("な", "に") and getattr(t.feature, "lemma", "") == "だ" and units:
            units[-1].morphemes.append(Morpheme(t.surface, f"-{t.surface}", role="suffix", origin="native", lang="ja"))
            units[-1].text += t.surface
            continue
        if pos1 in SKIP_POS1:
            continue
        origin = GOSHU_ORIGIN.get(getattr(t.feature, "goshu", "") or "", "unknown")
        role = "suffix" if pos1 == "接尾辞" else "prefix" if pos1 == "接頭辞" else "root"
        surface = t.surface
        if role == "suffix" and units:
            units[-1].morphemes.append(Morpheme(surface, _ja_lemma(t), role="suffix", origin=origin, lang="ja"))
            units[-1].text += surface
            continue
        # 순수 일본어(和語) 합성어는 한자 단위까지 쪼갠다: 手袋 → 手 + 袋
        if origin in ("native", "unknown") and len(surface) >= 2 and KANJI.search(surface) and pos1 == "名詞":
            for i in range(1, len(surface)):
                a, b = surface[:i], surface[i:]
                if _ja_known_single(a) and _ja_known_single(b) and _is_true_compound(surface, a, b):
                    for part in (a, b):
                        pt = _ja(part)[0]
                        po = GOSHU_ORIGIN.get(getattr(pt.feature, "goshu", "") or "", origin)
                        units.append(Unit(part, [Morpheme(part, _ja_lemma(pt), role="root", origin=po, lang="ja")]))
                    break
            else:
                units.append(Unit(surface, [Morpheme(surface, _ja_lemma(t), role=role, origin=origin, lang="ja")]))
            continue
        units.append(Unit(surface, [Morpheme(surface, _ja_lemma(t), role=role, origin=origin, lang="ja")]))
    return units


# ───────────────────────── 영어 (wordfreq) ─────────────────────────

EN_SUFFIXES = ["ation", "tion", "sion", "ment", "ness", "less", "ful", "able", "ible", "ous", "ish", "ive", "ize", "ic", "ity", "ure", "ance", "ence", "ing", "er", "or", "al"]


EN_SUFFIX_WORDS = {"less", "ful", "able", "ness", "ment", "ish"}


def _en(w: str) -> float:
    return zipf_frequency(w, "en")


def _en_base(stem: str) -> str | None:
    """접미사를 뗀 어간에서 원래 단어(기본형)를 복원한다. 흔한 영단어면 채택.
    ① 그대로(import+ance) ② 끝의 e 가 빠진 경우(clos+ure → close) ③ -er/-re 의 e 가 자리를 바꾼 경우(entr+ance → enter, centr+al → center)."""
    candidates = [stem, stem + "e"]
    if stem.endswith("i"):  # happi+ness → happy
        candidates.append(stem[:-1] + "y")
    if len(stem) >= 3 and stem[-1] in "rl" and stem[-2] not in "aeiouy":
        candidates.append(stem[:-1] + "e" + stem[-1])
    return next((c for c in candidates if _en(c) >= 3.4), None)


LATIN_PREFIXES = sorted(
    ["trans", "inter", "super", "anti", "sub", "pre", "pro", "con", "com", "dis", "mis", "non", "ex", "de", "re", "un"],
    key=len,
    reverse=True,
)


def _split_latin_prefix(word: str) -> tuple[str, str] | None:
    """depart → (de, part). 독일어 ab+fahr 처럼 접두사+어근 깊이로 맞추기 위함.
    남는 부분이 흔한 영단어이고, 전체는 굳어진 흔한 단어(report, detail …)가 아닐 때만 쪼갠다."""
    if len(word) < 6 or _en(word) >= 4.5:
        return None
    for p in LATIN_PREFIXES:
        rest = word[len(p):]
        if word.startswith(p) and len(rest) >= 3 and _en(rest) >= 4.0:
            return p, rest
    return None


def decompose_en(text: str) -> list[Unit]:
    units: list[Unit] = []
    for word in re.findall(r"[A-Za-z]+", text):
        low = word.lower()
        # 붙여 쓴 합성어: 두 부분이 모두 흔한 단어이고 전체는 상대적으로 드물 때만 쪼갠다 (carpet 은 그대로, ballpoint 는 쪼갬)
        split = None
        if len(low) >= 7:
            for i in range(3, len(low) - 2):
                a, b = low[:i], low[i:]
                if b in EN_SUFFIX_WORDS:  # use+less 는 합성어가 아니라 접미사 -less (아래 접미사 규칙이 처리)
                    continue
                if _en(a) >= 4.0 and _en(b) >= 4.0 and _en(low) < min(_en(a), _en(b)) - 1.2:
                    if split is None or _en(a) + _en(b) > _en(split[0]) + _en(split[1]):
                        split = (a, b)
        if split:
            for part in split:
                units.append(Unit(part, [Morpheme(part, part, role="root", origin="native", lang="en")]))
            continue
        morphs: list[Morpheme] = []
        for s in EN_SUFFIXES:
            if low.endswith(s) and len(low) - len(s) >= 4:
                stem = low[: -len(s)]
                base = _en_base(stem)
                if base:
                    morphs = [
                        Morpheme(stem, base, role="root", origin="native", lang="en"),
                        Morpheme(f"-{s}", f"-{s}", role="suffix", origin="native", lang="en"),
                    ]
                    break
        if not morphs:
            morphs = [Morpheme(low, low, role="root", origin="native", lang="en")]
        pre = _split_latin_prefix(morphs[0].lemma)
        if pre:
            p, rest = pre
            morphs[0:1] = [
                Morpheme(p, p, role="prefix", origin="native", lang="en"),
                Morpheme(rest, rest, role="root", origin="native", lang="en"),
            ]
        units.append(Unit(low, morphs))
    return units


# ───────────────────────── 한국어 (Kiwi + hanja + 번역기 단서) ─────────────────────────

_kiwi = Kiwi()
HANGUL_BASE = 0xAC00
LAX_INITIALS = {"ㄴ", "ㄹ", "ㅇ"}  # 두음법칙으로 달라질 수 있는 초성
CHOSEONG = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")


def _jamo(syllable: str) -> tuple[str, int, int] | None:
    code = ord(syllable) - HANGUL_BASE
    if not 0 <= code < 11172:
        return None
    return CHOSEONG[code // 588], (code % 588) // 28, code % 28


def _syllable_match(a: str, b: str) -> bool:
    if a == b:
        return True
    ja_, jb = _jamo(a), _jamo(b)
    return bool(ja_ and jb and ja_[0] in LAX_INITIALS and jb[0] in LAX_INITIALS and ja_[1:] == jb[1:])


SHINJITAI_COLLISION = {"証": "證", "芸": "藝", "弁": "辯", "台": "臺", "欠": "缺"}


def hanja_reading_matches(korean: str, kanji: str) -> list[str] | None:
    """한글 단어와 한자(일본 신자체 포함) 단어의 음이 글자별로 맞으면 한자 리스트를 돌려준다."""
    if len(korean) != len(kanji) or not all(KANJI.match(c) for c in kanji):
        return None
    out: list[str] = []
    for k, c in zip(korean, kanji):
        # 일본 신자체가 다른 옛 글자와 겹치는 경우(証=정 ≠ 證=증)는 옛 글자의 음도 확인한다
        readings = [hanja_table.get(c)] + ([hanja_table.get(SHINJITAI_COLLISION[c])] if c in SHINJITAI_COLLISION else [])
        if not any(r and _syllable_match(k, r) for r in readings):
            return None
        out.append(c)
    return out



_KO_INITIAL_CLASS = {"ㄱ": "k", "ㅋ": "k", "ㄲ": "k", "ㄷ": "t", "ㅌ": "t", "ㄸ": "t", "ㅂ": "p", "ㅍ": "p", "ㅃ": "p",
                     "ㅅ": "s", "ㅆ": "s", "ㅈ": "c", "ㅊ": "c", "ㅉ": "c", "ㅎ": "h", "ㅁ": "m", "ㄴ": "n", "ㄹ": "r"}


def _ko_skeleton(word: str) -> str:
    out = []
    for ch in word:
        j = _jamo(ch)
        if j and j[0] in _KO_INITIAL_CLASS:
            out.append(_KO_INITIAL_CLASS[j[0]])
    return "".join(out)


def _kana_skeleton(kana: str) -> str:
    import unicodedata

    out = []
    for ch in kana:
        try:
            name = unicodedata.name(ch)
        except ValueError:
            continue
        if "LETTER" not in name or "SMALL" in name:
            continue
        syl = name.split()[-1].lower()
        for prefix, cls in (("ch", "c"), ("sh", "s"), ("ts", "t"), ("j", "c"), ("k", "k"), ("g", "k"), ("t", "t"), ("d", "t"),
                            ("p", "p"), ("b", "p"), ("f", "p"), ("v", "p"), ("s", "s"), ("z", "c"), ("h", "h"), ("m", "m"),
                            ("n", "n"), ("r", "r"), ("l", "r")):
            if syl.startswith(prefix):
                out.append(cls)
                break
    return "".join(out)


def _lcs(a: str, b: str) -> int:
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            dp[i + 1][j + 1] = dp[i][j] + 1 if x == y else max(dp[i][j + 1], dp[i + 1][j])
    return dp[-1][-1]


def looks_like_transliteration(korean: str, katakana: str) -> bool:
    """한국어 외래어와 가타카나 표기의 자음 뼈대가 (순서대로) 거의 다 겹치는가."""
    ks = _ko_skeleton(korean)
    return bool(ks) and _lcs(ks, _kana_skeleton(katakana)) >= len(ks)


def _split_loan(korean: str, katakana: str) -> list[tuple[str, str]]:
    """한국어 외래어를 일본어 가타카나 분절(ボール|ペン)의 비율로 나눈다 → [(한국어 조각, 가타카나 조각)]. 못 나누면 통째로."""
    toks = [t.surface for t in _ja(katakana) if t.surface]
    n = len(toks)
    if n < 2 or len(korean) < n:
        return [(korean, katakana)]
    weights = [max(len(t.replace("ー", "").replace("ッ", "")), 1) for t in toks]
    total = sum(weights)
    cuts, acc = [], 0
    for w in weights[:-1]:
        acc += w
        cuts.append(max(1, min(len(korean) - 1, round(acc / total * len(korean)))))
    if sorted(set(cuts)) != cuts:
        return [(korean, katakana)]
    bounds = [0, *cuts, len(korean)]
    return [(korean[bounds[i]:bounds[i + 1]], toks[i]) for i in range(n)]


def _sino_units(form: str, cand: str) -> list[Unit]:
    """한자어 한 덩어리를 단어 단위로 나눈다. 단어 경계는 일치한 한자 표기(cand)를 일본어 분석기로 끊어 얻고,
    한자 한 글자 = 한글 한 음절로 대응시킨다. 형태소는 글자가 아니라 '단어'다. (진공청소기 → 진공 | 청소 | 기)"""
    ja_units = decompose_ja(cand)
    ok = bool(ja_units) and sum(len(u.text) for u in ja_units) == len(cand) and all(
        sum(len(m.surface) for m in u.morphemes) == len(u.text) for u in ja_units
    )
    if not ok:
        ja_units = [Unit(cand, [Morpheme(cand, cand, role="root", origin="sino", lang="ja")])]
    out: list[Unit] = []
    pos = 0
    for u in ja_units:
        morphs: list[Morpheme] = []
        start = pos
        for m in u.morphemes:
            part = form[pos:pos + len(m.surface)]
            morphs.append(
                Morpheme(part, m.surface, role=m.role, origin="sino", lang="ko", lookup_text=m.surface, lookup_lang="ja")
            )
            pos += len(m.surface)
        out.append(Unit(form[start:pos], morphs))
    return out


def _try_sino(form: str, tr: Translator, with_zh: bool = True) -> list[Unit] | None:
    """일본어/중국어(번체) 번역 후보 중 음이 글자별로 맞는 한자어가 있으면 한자 형태소 단위들로."""
    try:
        candidates = list(tr.lookup(form, "ko", "ja")[:5])
        if with_zh:
            candidates += tr.lookup(form, "ko", "zh-TW")[:3]
    except RuntimeError:
        return None
    for cand in candidates:
        hanjas = hanja_reading_matches(form, cand)
        if hanjas:
            return _sino_units(form, cand)
    return None


HANGUL_WORD = re.compile(r"^[가-힣]{2,}$")


def decompose_ko(text: str, tr: Translator) -> list[Unit]:
    units: list[Unit] = []
    for chunk in text.split():
        # 띄어쓰기 단위 통째로 한자어 매칭을 먼저 시도 (대학교, 운전면허증처럼 형태소 분석기가 끊어 버리는 말도 살림)
        if HANGUL_WORD.match(chunk):
            sino = _try_sino(chunk, tr)
            if sino:
                units.extend(sino)
                continue
        units.extend(_decompose_ko_chunk(chunk, tr))
    return units


def _decompose_ko_chunk(text: str, tr: Translator) -> list[Unit]:
    units: list[Unit] = []
    for tok in _kiwi.tokenize(text):
        # 무해+한(하+ㄴ), 부정+적 처럼 명사 뒤의 파생 접미사는 접미사 형태소로. 어미까지 이어지는 부분을 표면형으로 삼는다
        if tok.tag in ("XSA", "XSV", "XSN") and units and units[-1].morphemes[-1].role != "suffix":
            surface = text[tok.start:] if tok.tag in ("XSA", "XSV") else tok.form
            units[-1].morphemes.append(Morpheme(surface, f"-{surface}", role="suffix", origin="native", lang="ko"))
            units[-1].text += surface
            continue
        if not tok.tag.startswith(("NN", "XR", "VV", "VA", "NR", "SL")):
            continue
        form = tok.form
        is_verb = tok.tag.startswith(("VV", "VA"))
        lemma_form = form + "다" if is_verb else form

        # ① 한자어
        if not is_verb:
            sino = _try_sino(form, tr)
            if sino:
                units.extend(sino)
                continue

        try:
            ja_all = tr.lookup(form, "ko", "ja")[:5]
        except RuntimeError:
            ja_all = []
        ja = ja_all[0] if ja_all else ""

        # ② 외래어: 가타카나 번역 후보와 발음 뼈대가 겹치면 외래어로 보고 가타카나 분절에 맞춰 나눈다
        kata = next((c for c in ja_all if KATAKANA.match(c) and looks_like_transliteration(form, c)), None)
        if kata:
            for part, kana in _split_loan(form, kata):
                units.append(Unit(part, [Morpheme(part, part, role="root", origin="loan", lang="ko", lookup_text=kana, lookup_lang="ja")]))
            continue

        # ③ 그 외: 단일 형태소. 일본어 대응어가 순수 일본어(和語)면 고유어로 추정
        origin = "unknown"
        if ja:
            gos = {getattr(t.feature, "goshu", "") for t in _ja(ja) if (getattr(t.feature, "pos1", "") or "") not in SKIP_POS1}
            if gos == {"和"}:
                origin = "native"
        units.append(Unit(form, [Morpheme(form, lemma_form, role="root", origin=origin, lang="ko")]))
    return units
