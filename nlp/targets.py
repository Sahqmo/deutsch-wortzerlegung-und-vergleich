"""영어·한국어·일본어 대응어 분해. 각 언어의 라이브러리(wordfreq / Kiwi+hanja / fugashi+UniDic)를 쓴다."""

from __future__ import annotations

import re

import fugashi
from hanja.table import hanja_table
from kiwipiepy import Kiwi
from wordfreq import zipf_frequency

from lexicon import english_affixes, lookup_english
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


def decompose_ja(text: str, split_chars: bool = False) -> list[Unit]:
    """split_chars: 띄어쓰기 없는 한 단어이고 한자 2~3글자의 한어(漢語)면 한자 한 글자씩 나눈다 (病院 → 病 | 院). 한국어와 같은 정책.
    한국어 한자어의 단어 경계를 얻는 데 쓸 때는 끄고 부른다 (진공청소기의 真空 이 쪼개지면 안 되므로)."""
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
    if split_chars and units and len(units) == 1:
        root, *rest = units[0].morphemes
        # 無害+な 처럼 한자가 아닌 어미(な·に)가 붙어도 어근이 한어 2~3글자면 글자별로 나눈다. 冷蔵+庫 같은 한자 접미사는 단어 단위로 둔다
        if (
            root.origin == "sino"
            and root.role == "root"
            and 2 <= len(root.surface) <= 3
            and all(KANJI.match(c) for c in root.surface)
            and all(m.role == "suffix" and not KANJI.search(m.surface) for m in rest)
        ):
            out = [Unit(c, [Morpheme(c, c, role="root", origin="sino", lang="ja")]) for c in root.surface]
            out[-1].morphemes.extend(rest)
            out[-1].text += "".join(m.surface for m in rest)
            return out
    return units


# ───────────────────────── 영어 (wordfreq) ─────────────────────────

EN_SUFFIXES = ["ation", "tion", "sion", "ment", "ness", "less", "ful", "able", "ible", "ous", "ish", "ive", "ize", "ic", "ity", "ure", "ance", "ence", "ing", "er", "or", "al",
               "ison", "ion", "ism", "ist", "ify", "ary", "ory", "ent", "ant"]

# 이 접미사들은 뗀 어간이 '접두사+어근' 구조일 때만 인정한다 (million → mill+ion, student → stud+ent 방지)
EN_SUFFIXES_NEED_PREFIX = {"ison", "ion", "ent", "ant"}

# 라틴어 어근의 파생형 어간 → 기본형 (description → describe, conclusion → conclude)
EN_STEM_ALT = [("script", "scribe"), ("duct", "duce"), ("cept", "ceive"), ("sumpt", "sume"), ("clus", "clude"),
               ("fus", "fuse"), ("vers", "vert"), ("divis", "divide"), ("solut", "solve"), ("volut", "volve"),
               ("press", "press"), ("ject", "ject")]


EN_SUFFIX_WORDS = {"less", "ful", "able", "ness", "ment", "ish"}


def _en(w: str) -> float:
    return zipf_frequency(w, "en")


def _en_base(stem: str) -> str | None:
    """접미사를 뗀 어간에서 원래 단어(기본형)를 복원한다. 흔한 영단어면 채택.
    ① 그대로(import+ance) ② 끝의 e 가 빠진 경우(clos+ure → close) ③ -er/-re 의 e 가 자리를 바꾼 경우(entr+ance → enter, centr+al → center)."""
    candidates = [stem, stem + "e"]
    candidates += [stem[: -len(a)] + b for a, b in EN_STEM_ALT if stem.endswith(a) and a != b]
    if stem.endswith("i"):  # happi+ness → happy
        candidates.append(stem[:-1] + "y")
    if len(stem) >= 3 and stem[-1] in "rl" and stem[-2] not in "aeiouy":
        candidates.append(stem[:-1] + "e" + stem[-1])
    return next((c for c in candidates if _en(c) >= 3.4), None)


# 라틴어·그리스어 접두사. 자음 앞에서 모양이 바뀌는 것(ad→ac/ap/at, com→col/cor, in→im/il, ob→oc/op, sub→sup …)도 따로 넣는다
LATIN_PREFIXES = sorted(
    [
        # 라틴어
        "trans", "inter", "intro", "super", "circum", "contra", "extra", "retro", "ultra", "subter",
        "pre", "pro", "con", "com", "col", "cor", "dis", "dif", "mis", "non", "ex", "ef", "de", "re", "un", "in", "im", "il", "ir",
        "ab", "abs", "ad", "ac", "af", "ag", "al", "ap", "as", "at", "ob", "oc", "of", "op", "per", "post", "sub", "suc", "suf", "sup", "sus",
        "se", "ante", "co",
        # 그리스어
        "anti", "auto", "apo", "cata", "dia", "dys", "epi", "hyper", "hypo", "meta", "para", "peri", "syn", "sym", "tele", "micro", "macro",
        "mono", "poly", "geo", "bio",
    ],
    key=len,
    reverse=True,
)

# 자유 단어가 아닌 라틴어·그리스어 어근(굳어진 결합형). 접두사 뒤에 이것이 오면 쪼갠다: com+pare, de+scribe, re+ceive, tele+graph …
# (port, part, form 처럼 자유 단어이기도 한 것은 여기 넣지 않는다. 아래 '자유 단어' 규칙이 굳어진 흔한 단어를 걸러 준다)
BOUND_ROOTS = {
    "pare", "par", "press", "side", "tract", "spect", "ject", "pel", "mit", "fer", "ceive", "cept", "sist", "tain", "tin", "cur", "cure", "pose",
    "vert", "verse", "scribe", "script", "struct", "vise", "voke", "voc", "fect", "flect", "gress", "duce", "duct", "pend", "tend",
    "sume", "cede", "ceed", "claim", "clude", "cline", "dict", "gen", "grade", "lect", "mand", "nounce", "ply", "pute", "quire",
    "rect", "rupt", "serve", "sult", "sign", "tribute", "vent", "volve", "fuse", "cide", "cise", "stitute", "solve", "vide", "ject",
    "pear", "cept", "fine", "tect", "plain", "plore", "mote", "mark", "ride", "cord", "cover", "ceal", "tend",
    "logy", "graph", "graphy", "phone", "scope", "meter", "metry", "nomy", "cracy", "thesis",
}


# 모양이 바뀐 접두사·짧은 접두사는 어근이 결합형일 때만 쓴다 (import 를 im+port 로 쪼개지 않으려고). 나머지는 자유 단어 어근에도 쓴다
BOUND_ONLY_PREFIXES = {"in", "im", "il", "ir", "col", "cor", "dif", "ef", "ab", "abs", "ad", "ac", "af", "ag", "al", "ap", "as", "at",
                       "ob", "oc", "of", "op", "per", "post", "suc", "suf", "sup", "sus", "se", "ante", "co", "intro", "circum",
                       "contra", "extra", "retro", "ultra", "subter"}


def _split_latin_prefix(word: str) -> tuple[str, str] | None:
    """depart → (de, part), compare → (com, pare). 독일어 ab+fahr 처럼 접두사+어근 깊이로 맞추기 위함.
    남는 부분이 ① 라틴어·그리스어 결합형 어근(BOUND_ROOTS)이거나 ② 흔한 영단어이면서 전체는 굳어진 흔한 단어(report, detail …)가 아닐 때만 쪼갠다."""
    if len(word) < 5:
        return None
    singular = word[:-1] if word.endswith("s") and len(word) > 5 else word
    if word in NO_PREFIX_SPLIT or singular in NO_PREFIX_SPLIT:
        return None
    zw = max(_en(word), _en(singular))  # 복수형(exchanges)은 단수형의 빈도도 본다
    for p in LATIN_PREFIXES:
        rest = word[len(p):]
        if not word.startswith(p) or len(rest) < 3:
            continue
        if rest in BOUND_ROOTS:
            return p, rest
        if p not in BOUND_ONLY_PREFIXES and len(word) >= 6 and zw < 4.5 and _en(rest) >= 4.0:
            return p, rest
    return None


# 사전에서 배운 접사(빈도순)로 푼다. 사전에 없는 드문 말(unspectral, pseudoscorpion, cannonry)을 위한 규칙이라
# 남는 부분이 자유 단어일 때만 쪼갠다. 흔한 단어는 굳어진 것으로 보고 그대로 둔다.
# 사전 파일 없이도 쓰는 정적 접두사 목록(라틴·그리스·게르만계). 남는 부분이 자유 단어일 때만, 흔한 단어가 아닐 때만 쪼갠다.
# 사전에서 배운 접두사(english_affixes)는 이 목록에 없는 것만 보태 쓴다.
STATIC_PREFIXES = [
    # 라틴계: re-, con-/com-, dis- 등
    "re", "con", "com", "dis", "de", "ex", "pre", "pro", "post", "sub", "super", "trans", "inter", "intra", "intro", "extra", "ultra",
    "contra", "counter", "circum", "ante", "ambi", "mal", "tri", "uni", "multi", "semi", "omni", "non", "un",
    # 그리스계
    "anti", "auto", "bio", "geo", "micro", "macro", "mono", "poly", "hyper", "hypo", "meta", "para", "peri", "syn", "tele", "neo", "pseudo",
    "electro", "photo", "neuro", "arch", "pan",
    # 게르만계
    "over", "under", "out", "mis", "fore", "mid", "self", "half",
]
# 짧아서 우연히 맞기 쉬운 접두사 (남는 부분이 더 흔한 단어여야 한다)
SHORT_PREFIXES = {"re", "de", "ex", "un", "mid"}
# 접두사처럼 보이지만 어원상 굳은 말
NO_PREFIX_SPLIT = {"comfort", "parasite", "sublime", "constable", "comfortable", "bishop", "uniform", "section", "parasite", "exchange", "represent"}
# in-/im- 은 우연한 일치가 많아서(inch, image, import) 정적 목록에 넣지 않는다. 사전에서 배운 경우에도 짧은 접두사라 쓰지 않는다


def _learned_prefix(word: str) -> tuple[str, str] | None:
    singular = word[:-1] if word.endswith("s") and len(word) > 5 else word
    if word in NO_PREFIX_SPLIT or singular in NO_PREFIX_SPLIT:
        return None
    zw = max(_en(word), _en(singular))  # 복수형(exchanges, uniforms)은 단수형의 빈도도 본다
    learned = dict(english_affixes()[0])
    inventory = {p: 100 for p in STATIC_PREFIXES}
    for p, n in learned.items():
        if n >= 12 and p not in inventory:
            inventory[p] = n
    static = set(STATIC_PREFIXES)
    # 긴 접두사부터 (under 를 un 보다 먼저)
    for p, n in sorted(inventory.items(), key=lambda kv: (-len(kv[0]), -kv[1])):
        rest = word[len(p):]
        if not word.startswith(p) or len(rest) < 4:
            continue
        guard = 5.0 if p in ("un", "non") else 4.5
        if zw >= guard:
            continue
        if p in static:
            # 합성적인 짜임이면 전체가 남는 부분보다 훨씬 흔하지 않다 (extraordinary 4.36 ≤ ordinary 4.42 + 0.3)
            need = 3.0 if p in ("un", "non") and zw < 3.8 else 3.7 if p in SHORT_PREFIXES else 3.3
            if _en(rest) >= need and zw <= _en(rest) + 0.3:
                return p, rest
            continue
        # 사전에서만 배운 접두사: 짧은 것은 re/de/co 만, 흔한 접두사(n≥40)가 붙은 드문 말은 남는 부분이 조금 드물어도 쪼갠다
        if len(p) <= 2 and p not in ("co",):
            continue
        need = 4.2 if len(p) <= 2 else 2.8 if (n >= 40 and zw < 3.8) else 3.6
        if _en(rest) >= need:
            return p, rest
    return None


# 굴절 어미와, 고유명사(julian, romanian)·우연한 일치가 많은 짧은 접미사는 학습한 접미사에서 뺀다
LEARNED_SUFFIX_EXCLUDE = {"ed", "s", "es", "d", "n", "est", "en", "an", "ian", "ie", "ite", "ee", "le", "man", "ally", "ies"}


def _learned_suffix_candidates() -> list[str]:
    known = set(EN_SUFFIXES)
    return [s for s, n in english_affixes()[1] if len(s) >= 2 and n >= 30 and s not in known and s not in LEARNED_SUFFIX_EXCLUDE]


def _en_lexicon_units(word: str, depth: int = 0) -> list[Unit] | None:
    """영어판 Wiktionary 어원에서 만든 분해 사전을 조회한다. 어근이 다시 파생어·합성어이고 그 안의 어근이 자유 단어면 한 번 더 풀어서
    안쪽 접사까지 찾는다 (fearful + -ness → fear + -ful + -ness). 사전에 없으면 None → 규칙으로."""
    entry = lookup_english(word)
    if entry is None or depth > 3:
        return None
    roots = [lm for spec in entry for _, lm, role in spec if role == "root"]
    # 흔한 단어인데 어근이 자유 단어가 아니면(happy = hap + -y, report = re + porto) 쪼개지 않는다. 굳어진 흔한 단어는 그대로 둔다
    if depth == 0 and _en(word) >= 4.0 and any(_en(r) < 3.5 for r in roots):
        return None
    # 현재분사·동명사형(resting)인데 사전 항목이 다른 짜임(re- + sting)을 말하면 -ing 로 읽는 규칙 쪽을 따른다
    if depth == 0 and word.endswith("ing") and not any(lm == "-ing" for spec in entry for _, lm, _ in spec) and _en_base(word[:-3]):
        return None
    # 굳어진 흔한 단어에 붙은 접두사(report = re + port)도 규칙과 같은 정책으로 쪼개지 않는다
    if depth == 0 and _en(word) >= 4.7 and any(role == "prefix" for spec in entry for _, _, role in spec):
        return None
    out: list[Unit] = []
    for spec in entry:
        morphs = [Morpheme(sf, lm, role=role, origin="native", lang="en") for sf, lm, role in spec]
        root_idx = next((i for i, m in enumerate(morphs) if m.role == "root"), None)
        if root_idx is not None and morphs[root_idx].lemma.isalpha() and morphs[root_idx].lemma.lower() != word.lower():
            sub = _en_lexicon_units(morphs[root_idx].lemma, depth + 1)
            sub_roots = [m.lemma for u in sub or [] for m in u.morphemes if m.role == "root"]
            sub_affixes = [m.surface.strip("-") for u in sub or [] for m in u.morphemes if m.role != "root"]
            # 안쪽으로 풀 때는 어근이 흔한 자유 단어이고 접사가 두 글자 이상일 때만 (a- + maze, hap + -y, see + -n 같은 건 풀지 않는다)
            if sub and all(_en(r) >= 4.0 for r in sub_roots) and all(len(a) >= 2 for a in sub_affixes):
                if len(sub) == 1:  # 어근이 파생어면 그 형태소들로 갈아 끼운다 (접두사·접미사는 그대로 바깥에 남는다)
                    morphs[root_idx : root_idx + 1] = sub[0].morphemes
                else:  # 어근이 합성어면 단위를 나눈다 (접두사는 첫 단위, 접미사는 마지막 단위에)
                    before, after = morphs[:root_idx], morphs[root_idx + 1 :]
                    sub[0].morphemes[:0] = before
                    sub[-1].morphemes.extend(after)
                    for u in sub:
                        u.text = "".join(m.surface.strip("-") for m in u.morphemes)
                    out.extend(sub)
                    continue
        # 사전의 어근에 라틴·그리스계 접두사가 붙어 있으면 규칙 표로 한 번 더 뗀다 (describe → de + scribe)
        if not any(m.role == "prefix" for m in morphs):
            for i, m in enumerate(morphs):
                if m.role == "root":
                    pre = _split_latin_prefix(m.lemma)
                    if pre and m.surface.startswith(pre[0]) and len(m.surface) > len(pre[0]):
                        morphs[i : i + 1] = [
                            Morpheme(pre[0], pre[0], role="prefix", origin="native", lang="en"),
                            Morpheme(m.surface[len(pre[0]):], pre[1], role="root", origin="native", lang="en"),
                        ]
                    break
        out.append(Unit("".join(m.surface.strip("-") for m in morphs), morphs))
    return out


def decompose_en(text: str) -> list[Unit]:
    units: list[Unit] = []
    for word in re.findall(r"[A-Za-z]+", text):
        low = word.lower()
        from_lexicon = _en_lexicon_units(low)
        if from_lexicon:
            units.extend(from_lexicon)
            continue
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
        for s in EN_SUFFIXES + _learned_suffix_candidates():
            if s not in EN_SUFFIXES and _en(low) >= 4.5:
                continue  # 학습한 접미사는 드문 말에만 쓴다
            if low.endswith(s) and len(low) - len(s) >= (4 if s in EN_SUFFIXES else 5):
                stem = low[: -len(s)]
                base = _en_base(stem)
                if base and s in EN_SUFFIXES_NEED_PREFIX and not _split_latin_prefix(base):
                    base = None
                if base:
                    morphs = [
                        Morpheme(stem, base, role="root", origin="native", lang="en"),
                        Morpheme(f"-{s}", f"-{s}", role="suffix", origin="native", lang="en"),
                    ]
                    break
        if not morphs:
            morphs = [Morpheme(low, low, role="root", origin="native", lang="en")]
        pre = _split_latin_prefix(morphs[0].lemma) or _learned_prefix(morphs[0].lemma)
        if pre:
            p, rest = pre
            surface = morphs[0].surface
            rest_surface = surface[len(p):] if surface.startswith(p) and len(surface) > len(p) else rest
            morphs[0:1] = [
                Morpheme(p, p, role="prefix", origin="native", lang="en"),
                Morpheme(rest_surface, rest, role="root", origin="native", lang="en"),
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


def _sino_units(form: str, cand: str, split_chars: bool = False) -> list[Unit]:
    """한자어 한 덩어리를 단어 단위로 나눈다. 단어 경계는 일치한 한자 표기(cand)를 일본어 분석기로 끊어 얻고,
    한자 한 글자 = 한글 한 음절로 대응시킨다. 여러 단어가 이어진 말은 형태소가 글자가 아니라 '단어'다. (진공청소기 → 진공 | 청소 | 기)
    다만 입력 전체가 띄어쓰기 없는 한 단어이고 2~3글자면(split_chars) 한자 한 글자씩 나눈다. (병원 → 병 | 원)"""
    ja_units = decompose_ja(cand)
    ok = bool(ja_units) and sum(len(u.text) for u in ja_units) == len(cand) and all(
        sum(len(m.surface) for m in u.morphemes) == len(u.text) for u in ja_units
    )
    if not ok:
        ja_units = [Unit(cand, [Morpheme(cand, cand, role="root", origin="sino", lang="ja")])]
    if split_chars and len(ja_units) == 1 and len(ja_units[0].morphemes) == 1 and 2 <= len(form) <= 3 and len(cand) == len(form):
        return [
            Unit(f, [Morpheme(f, k, role="root", origin="sino", lang="ko", lookup_text=k, lookup_lang="ja")])
            for f, k in zip(form, cand)
        ]
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


def _find_hanja(form: str, tr: Translator, with_zh: bool = True) -> str | None:
    """일본어/중국어(번체) 번역 후보 중 음이 글자별로 맞는 한자 표기(病院)."""
    try:
        candidates = list(tr.lookup(form, "ko", "ja")[:5])
        if with_zh:
            candidates += tr.lookup(form, "ko", "zh-TW")[:3]
    except RuntimeError:
        return None
    for cand in candidates:
        if hanja_reading_matches(form, cand):
            return cand
    return None


def _try_sino(form: str, tr: Translator, with_zh: bool = True, split_chars: bool = False) -> list[Unit] | None:
    """일본어/중국어(번체) 번역 후보 중 음이 글자별로 맞는 한자어가 있으면 한자 형태소 단위들로."""
    cand = _find_hanja(form, tr, with_zh)
    return _sino_units(form, cand, split_chars) if cand else None


# ───────── 분석 후보: 한자어의 경계 조합 ─────────
# 한자어 하나를 어떻게 끊을지(한 덩어리 / 한 글자씩 / 단어 단위 / 그 사이)에 따라 짝짓기와 점수가 달라진다 (냉장 | 고 ↔ 냉 | 장고).
# 한자 n 글자의 경계 조합을 전부 만들어(2^(n-1) 개) 후보로 돌려주면, 화면 쪽에서 점수가 가장 높은 것을 고른다.
MAX_CANDIDATE_CHARS = 4


def _compositions(n: int) -> list[list[tuple[int, int]]]:
    """0..n 을 연속한 구간으로 나누는 모든 방법: n=3 → [(0,3)], [(0,1),(1,3)], [(0,2),(2,3)], [(0,1),(1,2),(2,3)]."""
    out: list[list[tuple[int, int]]] = []
    for mask in range(1 << (n - 1)):
        cuts = [i + 1 for i in range(n - 1) if mask >> i & 1]
        bounds = [0, *cuts, n]
        out.append([(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)])
    return out


def ko_candidates(text: str, tr: Translator) -> list[list[Unit]]:
    """띄어쓰기 없는 한국어 한자어(2~4글자)의 경계 조합 후보 단위 목록. 한자어로 확인되지 않으면 빈 목록."""
    text = text.strip()
    if not HANGUL_WORD.match(text) or not 2 <= len(text) <= MAX_CANDIDATE_CHARS:
        return []
    cand = _find_hanja(text, tr)
    if not cand or len(cand) != len(text):
        return []
    return [
        [
            Unit(text[a:b], [Morpheme(text[a:b], cand[a:b], role="root", origin="sino", lang="ko", lookup_text=cand[a:b], lookup_lang="ja")])
            for a, b in comp
        ]
        for comp in _compositions(len(text))
    ]


def ja_candidates(text: str) -> list[list[Unit]]:
    """띄어쓰기 없는 일본어 한어(한자 2~4글자)의 경계 조합 후보 단위 목록."""
    text = text.strip()
    if not 2 <= len(text) <= MAX_CANDIDATE_CHARS or not all(KANJI.match(c) for c in text):
        return []
    return [
        [Unit(text[a:b], [Morpheme(text[a:b], text[a:b], role="root", origin="sino", lang="ja")]) for a, b in comp]
        for comp in _compositions(len(text))
    ]


HANGUL_WORD = re.compile(r"^[가-힣]{2,}$")


def decompose_ko(text: str, tr: Translator) -> list[Unit]:
    units: list[Unit] = []
    chunks = text.split()
    for chunk in chunks:
        # 띄어쓰기 단위 통째로 한자어 매칭을 먼저 시도 (대학교, 운전면허증처럼 형태소 분석기가 끊어 버리는 말도 살림)
        # 입력 전체가 띄어쓰기 없는 한 단어일 때만 한자 한 글자씩 나눈다 (출발 시간 → 출발 | 시간)
        if HANGUL_WORD.match(chunk):
            sino = _try_sino(chunk, tr, split_chars=len(chunks) == 1)
            if sino:
                units.extend(sino)
                continue
        units.extend(_decompose_ko_chunk(chunk, tr, split_chars=len(chunks) == 1))
    return units


def _decompose_ko_chunk(text: str, tr: Translator, split_chars: bool = False) -> list[Unit]:
    units: list[Unit] = []
    tokens = _kiwi.tokenize(text)
    # 불쾌+한 처럼 내용어가 하나뿐이고 뒤에 용언화·형용사화 어미(XSA/XSV)만 붙으면, 어근이 2~3글자 한자어일 때 한자 한 글자씩 나눈다
    # (-적 같은 명사 파생 접미사는 일본어 的 처럼 한자 접미사라서 단어 단위 그대로)
    content = [t for t in tokens if t.tag.startswith(("NN", "XR", "VV", "VA", "NR", "SL"))]
    split_chars = split_chars and len(content) == 1 and not any(t.tag == "XSN" for t in tokens)
    for tok in tokens:
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
            sino = _try_sino(form, tr, split_chars=split_chars)
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
