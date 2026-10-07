"""독일어 Wiktionary 어원 문장에서 합성어 분해 사전(lexicon.sqlite)을 만든다.

원본: Hugging Face `yuanxin112/wiktionary-morph` (de) — kaikki.org(wiktextract)가 뽑은 독일어 Wiktionary. CC-BY-SA-4.0.
이 파일로 만든 lexicon.sqlite 는 그 라이선스를 이어받는다(출처 표기 + 동일 조건 공유). 그래서 저장소에는 넣지 않고(.gitignore),
공개 배포 전에는 라이선스를 다시 확인해야 한다.

사용법 (pyarrow 가 필요하다: pip install -r requirements-lexicon.txt):
    python build_lexicon.py            # nlp/data/ 에 원본을 내려받고 nlp/lexicon.sqlite 를 만든다
    python build_lexicon.py --parquet 경로/de.parquet
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import urllib.request
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
DB_PATH = HERE / "lexicon.sqlite"
PARQUET_URL = "https://huggingface.co/datasets/yuanxin112/wiktionary-morph/resolve/main/de/train-00000-of-00001.parquet"
PARQUET_URL_EN = "https://huggingface.co/datasets/yuanxin112/wiktionary-morph/resolve/main/en/train-00000-of-00001.parquet"

LINKS = ["ens", "es", "en", "er", "s", "n", "e"]

# 어원 문장에서 구성요소가 아닌 말(문법 용어)
STOP = set(
    """den dem der des die das ein einem einer eines einen substantiv substantiven substantivs verb verben verbs adjektiv adjektive adjektiven
    adjektivs adverb adverbs stamm stammes substantivierten substantivierte substantivierter verbstamm wortstamm präposition präpositionen pronomen
    partizip zahlwort numerale grundwort bestimmungswort wort wortes worts wörtern nomen nomens zusammengesetzt zusammensetzung sowie und oder
    sowohl als auch mit von zu aus deren kompositum determinativkompositum possessivkompositum kopulativkompositum fugenelement fugenelements
    verbalstamm adjektivstamm erweiterten imperativ infinitiv genitiv plural singular unflektierten grundform erstglied zweitglied bestimmungsglied
    grundglied gebundenen gebundene gebundener lexem lexems präfix präfixes suffix suffixes ohne konfix konfixes affixoid präfixoid suffixoid
    halbpräfix halbsuffix gleitlaut umlaut eigennamen subtraktionsfuge formativ wortgruppe komparativ superlativ indefinitpronomen familiennamen namen
    lexemen neoklassischen lautmalerischen gesteigerten ableitung derivatem ableitungsmorphem erst erste ersten zweiten zweite sich im in bei an auf für über""".split()
)
LINK_PHRASE = re.compile(r"[Ff]ugen(?:element|-)\w*\s*[-‑]?(\w*)")
STEM_QUOTE = re.compile(r"Stamm\s*[„\"][^“\"]*[“\"]")
INTRO = re.compile(r"(?:kompositum|zusammensetzung|zusammenrückung|zusammenbildung|komposition)\b[^.;]*?\b(?:aus|von)\b(.*)", re.I | re.S)


def parse_etymology(text: str | None) -> tuple[list[str], list[str]] | None:
    """어원 문장 → (구성요소 기본형 목록, 연결요소 목록). 합성어로 읽히지 않으면 None."""
    if not text:
        return None
    m = INTRO.search(text)
    if not m:
        return None
    body = m.group(1)
    body = re.split(r"(?<![0-9])\.(?:\s|$)|;|\s+oder\s+", body)[0]
    body = re.sub(r"\([^)]*\)", " ", body)
    body = STEM_QUOTE.sub(" ", body)
    links: list[str] = []

    def grab(mm: re.Match) -> str:
        if mm.group(1):
            links.append(mm.group(1))
        return " "

    body = LINK_PHRASE.sub(grab, body)
    parts: list[str] = []
    for tok in re.findall(r"[-A-Za-zÄÖÜäöüß]+", body):
        if tok.lower() in STOP:
            continue
        tok = tok.strip("-")
        if len(tok) >= 2:
            parts.append(tok)
    if not 2 <= len(parts) <= 4:
        return None
    return parts, links


AFFIX_AFTER_KEYWORD = re.compile(
    r"(?:Derivatem|Präfix|Suffix|Ableitungsmorphem|Derivationsmorphem)(?:\s*\([^)]*\))?\s*(-[A-Za-zäöüß]+|[A-Za-zäöüß]+-)(?![A-Za-zäöüß])"
)


def parse_derivation(text: str | None) -> tuple[list[str], list[str]] | None:
    """파생어 어원 문장 → (접두사들, 접미사들). 문장 형식이 제각각이라 구성요소는 읽지 않고, 하이픈이 붙은 접사 표기(-ung, ver-)만 뽑는다."""
    if not text:
        return None
    prefixes: list[str] = []
    suffixes: list[str] = []
    for m in AFFIX_AFTER_KEYWORD.finditer(text):
        tok = m.group(1)
        if tok.startswith("-"):
            suffixes.append(tok[1:].lower())
        else:
            prefixes.append(tok[:-1].lower())
    prefixes = list(dict.fromkeys(prefixes))
    suffixes = list(dict.fromkeys(suffixes))
    return (prefixes, suffixes) if prefixes or suffixes else None


# ───────────── 표면형 정렬: 어원의 기본형(Grenze, Kranker)을 입력 단어의 조각(Grenz, Kranken)에 맞춘다 ─────────────

def _norm(s: str) -> str:
    return s.lower().translate(str.maketrans("äöüß", "aous")).replace("ss", "s")


def _score(seg: str, lemma: str) -> int:
    """seg(표면 조각)가 lemma 의 어떤 모양과 얼마나 맞는가. 3 = 같음, 2 = 어미·움라우트만 다름, 1 = 어간이 같음, 0 = 안 맞음."""
    s, l = seg.lower(), lemma.lower()
    if s == l:
        return 3
    sn, ln = _norm(seg), _norm(lemma)
    if sn == ln:
        return 3
    for cut in ("e", "en", "n", "er", "s"):
        if ln.endswith(cut) and sn == ln[: -len(cut)]:
            return 2
        if sn.endswith(cut) and ln == sn[: -len(cut)]:
            return 2
    cp = 0
    for a, b in zip(sn, ln):
        if a != b:
            break
        cp += 1
    if cp >= 3 and cp >= min(len(sn), len(ln)) - 1:
        return 1
    return 0


def _best_suffix(remaining: str, lemma: str) -> tuple[int, int]:
    """remaining 의 끝에서 lemma 와 가장 잘 맞는 조각의 (점수, 길이)."""
    best = (0, 0)
    n = len(lemma)
    for length in range(max(3, n - 3), n + 3):
        if length > len(remaining) - 3:
            continue
        sc = _score(remaining[-length:], lemma)
        if sc > best[0] or (sc == best[0] and sc and abs(length - n) < abs(best[1] - n)):
            best = (sc, length)
    return best


def align(word: str, parts: list[str], links: list[str]) -> tuple[list[str], list[str]] | None:
    """단어를 구성요소 기본형에 맞춰 표면 조각으로 자른다. 맞지 않으면 None. → (표면 조각들, 연결요소들)"""
    remaining = word
    surfaces: list[str] = []
    used_links: list[str] = []
    for idx in range(len(parts) - 1, 0, -1):
        sc, length = _best_suffix(remaining, parts[idx])
        if sc == 0 or (idx == len(parts) - 1 and sc < 2 and length != len(parts[idx])):
            return None
        if idx == len(parts) - 1 and _norm(remaining[-length:]) != _norm(parts[idx]) and sc < 3:
            return None  # 핵심어(마지막 요소)는 대개 모양이 바뀌지 않는다
        surfaces.append(remaining[-length:])
        remaining = remaining[:-length]
        # 앞 요소 끝의 연결요소를 떼어 본다. 점수가 가장 높은 후보를 고른다 (Gottes → Gott + es)
        prev = parts[idx - 1]
        candidates = list(dict.fromkeys(links + [""] + LINKS))
        best: tuple[int, int, str] | None = None
        for order, cand in enumerate(candidates):
            if cand and not remaining.lower().endswith(cand):
                continue
            rem2 = remaining[: len(remaining) - len(cand)] if cand else remaining
            if len(rem2) < (2 if idx - 1 == 0 else 3):  # 첫 요소는 Öl 처럼 두 글자일 수 있다
                continue
            if idx - 1 == 0:
                score = _score(rem2, prev)
            else:
                score = _best_suffix(rem2, prev)[0]
            if score == 0:
                continue
            key = (score, -order)
            if best is None or key > best[:2]:
                best = (score, -order, cand)
        if best is None:
            return None
        link = best[2]
        used_links.append(link)
        if link:
            remaining = remaining[: -len(link)]
    surfaces.append(remaining)
    surfaces.reverse()
    used_links.reverse()
    rebuilt = "".join(s + (used_links[i] if i < len(used_links) else "") for i, s in enumerate(surfaces))
    if rebuilt != word:
        return None
    # 단어 가운데에서 잘린 조각은 소문자로 남아 있으니 기본형의 대소문자에 맞춘다 (zeit → Zeit)
    surfaces = [x if i == 0 else (x[:1].upper() + x[1:] if parts[i][:1].isupper() else x.lower()) for i, x in enumerate(surfaces)]
    return surfaces, [l for l in used_links if l]


def align_any(word: str, parts: list[str], links: list[str]) -> tuple[list[str], list[str], list[str]] | None:
    """align 이 안 되면 구성요소 후보에서 문법 용어 찌꺼기(Gleitlaut, Eigennamen …)가 섞인 것으로 보고, 순서를 지킨 부분집합 중 맞는 것을 찾는다."""
    r = align(word, parts, links)
    if r:
        return r[0], r[1], parts
    for size in range(len(parts) - 1, 1, -1):
        for idx in combinations(range(len(parts)), size):
            sub = [parts[i] for i in idx]
            r = align(word, sub, links)
            if r:
                return r[0], r[1], sub
    return None


# 어원 문장이 없거나 못 읽은 단어를 위한 보강. Wiktionary 항목 X 의 '파생어(derived)' 목록에 W 가 있고 W 가 X 로 시작하거나 끝나면,
# X 가 W 의 한 구성요소이고 나머지가 사전 단어일 때 합성어 W = X + 나머지 로 본다 (정답 표에서 추정한 경계는 거의 전부 맞았다).
def add_from_derived_lists(con: sqlite3.Connection, rows: list[dict], seen: set[str]) -> int:
    from german import DERIVATIONAL_TAILS, is_word  # 규칙 쪽의 어휘 검증(wordfreq)을 재사용한다

    parents: dict[str, set[str]] = {}
    for r in rows:
        for w in r["derived"] or []:
            if " " not in w and "-" not in w and len(w) >= 7:
                parents.setdefault(w, set()).add(r["word"])
    added = 0
    for w, ps in parents.items():
        if w in seen or not w.isalpha():
            continue
        lw = w.lower()
        best: tuple[int, list[str], list[str]] | None = None
        for p in ps:
            lp = p.lower()
            if len(p) < 3 or len(p) >= len(w) - 2 or lp in DERIVATIONAL_TAILS:
                continue
            for link in [""] + LINKS:  # 앞 요소가 부모: 부모 + (연결요소) + 나머지
                rest = w[len(p) + len(link):]
                if lw.startswith(lp + link) and len(rest) >= 3 and rest.lower() not in DERIVATIONAL_TAILS and is_word(rest, 3.0):
                    cand = (len(p), [w[: len(p)], rest[:1].upper() + rest[1:] if w[:1].isupper() else rest], [link] if link else [])
                    if best is None or cand[0] > best[0]:
                        best = cand
            if lw.endswith(lp):  # 뒤 요소가 부모: (앞) + (연결요소) + 부모
                front = w[: len(w) - len(p)]
                for link in [""] + LINKS:
                    if link and not front.lower().endswith(link):
                        continue
                    f = front[: len(front) - len(link)] if link else front
                    if len(f) >= 3 and f.lower() not in DERIVATIONAL_TAILS and is_word(f, 3.0):
                        cand = (len(f), [f, p if p.lower() == w[len(w) - len(p):].lower() else w[len(w) - len(p):]], [link] if link else [])
                        if best is None or cand[0] > best[0]:
                            best = cand
        if best:
            _, surfaces, used = best
            con.execute("INSERT INTO compound VALUES (?, ?, ?, ?, ?)", (w, "|".join(surfaces), "|".join(surfaces), ",".join(used), "derived-list"))
            seen.add(w)
            added += 1
    return added


# ───────────── 영어 ─────────────
# 영어판 Wiktionary 어원 문장의 "From fearful + -ness." 와 구조화된 decomposition 필드에서 단어 → 접두사·어근·접미사를 얻는다.

EN_CLAUSE = re.compile(r"\b(?:From|Compound of|Blend of|Derived from|Equivalent to|Formed from)\s+([^.]*?\s\+[^.]*?)(?:\.|$)")


EN_INFLECTION_SUFFIXES = {"-ed", "-s", "-es", "-d", "-n", "-est", "-ing-"}


def _en_clean(s: str) -> str:
    return s.replace("‎", "").replace("‏", "")


def parse_en_etymology(text: str | None) -> list[str] | None:
    """영어 어원 문장 → 토큰 목록(['fearful', '-ness'], ['di-', 'ketone']). 'A + B' 꼴이 아니거나 낱말이 아닌 것이 섞이면 None."""
    for m in EN_CLAUSE.finditer(_en_clean(text or "")):
        toks = [re.sub(r"\s*\(.*?\)", "", t).strip() for t in m.group(1).split("+")]
        if 2 <= len(toks) <= 4 and all(re.fullmatch(r"-?[A-Za-z][A-Za-z'-]*-?", t) for t in toks):
            return toks
    return None


def en_tokens_from_decomposition(d: dict | None) -> list[str] | None:
    """구조화된 decomposition({base, affixes, parts}) → 토큰 목록. 접두사 → 어근 → 접미사 순서."""
    if not d:
        return None
    if d.get("parts") and len(d["parts"]) >= 2:
        return list(d["parts"])
    if d.get("base") and d.get("affixes"):
        pre = [a for a in d["affixes"] if a.endswith("-") and not a.startswith("-")]
        suf = [a for a in d["affixes"] if a.startswith("-") and not a.endswith("-")]
        if pre or suf:
            return pre + [d["base"]] + suf
    return None


def _en_kind(tok: str) -> str:
    if tok.startswith("-") and tok.endswith("-"):
        return "link"
    if tok.endswith("-"):
        return "prefix"
    if tok.startswith("-"):
        return "suffix"
    return "part"


def _en_sim(surface: str, lemma: str) -> int:
    """어근 조각이 기본형과 맞는가: 3 = 같음, 2 = 어미 e/y 탈락·자음 겹침 정도의 차이, 0 = 아님."""
    if surface == lemma:
        return 3
    cp = 0
    for a, b in zip(surface, lemma):
        if a != b:
            break
        cp += 1
    if cp >= 2 and cp >= min(len(surface), len(lemma)) - 2 and abs(len(surface) - len(lemma)) <= 2:
        return 2
    return 0


def align_en(word: str, tokens: list[str]) -> list[list[list[str]]] | None:
    """단어를 토큰에 맞춰 단위(unit)별 형태소 [표면, 기본형, 역할] 로 자른다. 맞지 않으면 None.
    합성어는 어근마다 하나의 단위, 접두사는 뒤 어근의 단위에, 접미사는 앞 어근의 단위에 붙는다."""
    w = word.lower()
    kinds = [(_en_kind(t), t.strip("-").lower()) for t in tokens]
    if any(not t for _, t in kinds) or not any(k == "part" for k, _ in kinds):
        return None
    # 접미사 (오른쪽 끝에서 안쪽으로)
    end = len(w)
    suffixes: list[tuple[str, str]] = []
    i = len(kinds)
    while i > 0 and kinds[i - 1][0] == "suffix":
        t = kinds[i - 1][1]
        if not w[:end].endswith(t) or end - len(t) < 2:
            return None
        end -= len(t)
        suffixes.insert(0, (t, "-" + t))
        i -= 1
    head = kinds[:i]
    # 접두사 (왼쪽 끝에서)
    pos = 0
    prefixes: list[str] = []
    j = 0
    while j < len(head) and head[j][0] == "prefix":
        t = head[j][1]
        if not w.startswith(t, pos) or end - (pos + len(t)) < 2:
            return None
        pos += len(t)
        prefixes.append(t)
        j += 1
    middle = head[j:]
    if not middle or any(k in ("prefix", "suffix") for k, _ in middle) or middle[0][0] != "part" or middle[-1][0] != "part":
        return None
    span = w[pos:end]
    surfaces: list[tuple[str, str]] = []  # (표면, 기본형)
    cur = 0
    n_parts = sum(1 for k, _ in middle if k == "part")
    idx_part = 0
    for k, t in middle:
        if k == "link":
            if span.startswith(t, cur):
                cur += len(t)
            continue
        idx_part += 1
        if idx_part == n_parts:
            piece = span[cur:]
            if len(piece) < 2 or _en_sim(piece, t) == 0:
                return None
            surfaces.append((piece, t))
        else:
            best: tuple[int, int] | None = None
            for length in range(max(2, len(t) - 2), len(t) + 2):
                sc = _en_sim(span[cur : cur + length], t)
                if sc and (best is None or (sc, -abs(length - len(t))) > (best[0], -abs(best[1] - len(t)))):
                    best = (sc, length)
            if best is None:
                return None
            surfaces.append((span[cur : cur + best[1]], t))
            cur += best[1]
    # 단위 만들기
    units: list[list[list[str]]] = [[[sf, lm, "root"]] for sf, lm in surfaces]
    if prefixes:
        units[0] = [[p, p, "prefix"] for p in prefixes] + units[0]
    for sf, lm in suffixes:
        units[-1].append([sf if sf.startswith("-") else "-" + sf, lm, "suffix"])
    return units


def build_english(parquet_path: Path, con: sqlite3.Connection) -> dict:
    import json

    import pyarrow.parquet as pq
    from wordfreq import zipf_frequency

    con.execute("CREATE TABLE en_entry (word TEXT PRIMARY KEY, spec TEXT NOT NULL, source TEXT NOT NULL)")
    rows = pq.read_table(parquet_path, columns=["word", "morph_type", "decomposition", "etymology_text"]).to_pylist()
    stats = {"en_candidates": 0, "en_stored": 0, "en_unaligned": 0, "en_no_tokens": 0}
    affix_counts: dict[tuple[str, str], int] = {}
    chosen: dict[str, tuple[float, list, str]] = {}
    for r in rows:
        if r["morph_type"] == "simple":
            continue
        word = r["word"]
        if not word.isalpha() or len(word) < 4:
            continue
        stats["en_candidates"] += 1
        tokens, source = parse_en_etymology(r["etymology_text"]), "etymology"
        if not tokens:
            tokens, source = en_tokens_from_decomposition(r["decomposition"]), "decomposition"
        if not tokens:
            stats["en_no_tokens"] += 1
            continue
        units = align_en(word, tokens)
        if units is None:
            stats["en_unaligned"] += 1
            continue
        if any(role == "suffix" and lemma in EN_INFLECTION_SUFFIXES for unit in units for _, lemma, role in unit):
            stats["en_inflection_skipped"] = stats.get("en_inflection_skipped", 0) + 1
            continue  # 굴절(-ed, -s …)은 단어 짜임이 아니다
        # 같은 철자의 항목이 여러 개면(resting = rest + -ing / re- + sting) 어근이 더 흔한 단어인 쪽을 고른다
        score = min(zipf_frequency(lm, "en") for unit in units for _, lm, role in unit if role == "root")
        prev = chosen.get(word.lower())
        if prev is None or score > prev[0]:
            chosen[word.lower()] = (score, units, source)
    for w, (_, units, source) in chosen.items():
        con.execute("INSERT INTO en_entry VALUES (?, ?, ?)", (w, json.dumps(units, ensure_ascii=False), source))
        stats["en_stored"] += 1
        for unit in units:
            for _, lemma, role in unit:
                if role in ("prefix", "suffix"):
                    affix_counts[(lemma, role)] = affix_counts.get((lemma, role), 0) + 1
    # 사전에서 배운 접사 목록: 사전에 없는 말을 규칙으로 풀 때 접사 후보로 쓴다
    con.execute("CREATE TABLE en_affix (affix TEXT NOT NULL, role TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (affix, role))")
    for (lemma, role), n in affix_counts.items():
        if n >= 8 and lemma.strip("-").isalpha():
            con.execute("INSERT INTO en_affix VALUES (?, ?, ?)", (lemma.strip("-"), role, n))
    return stats


def build(parquet_path: Path, db_path: Path, parquet_en: Path | None = None) -> None:
    import pyarrow.parquet as pq  # 만들 때만 필요하다

    table = pq.read_table(parquet_path, columns=["word", "morph_type", "etymology_text", "derived"])
    rows = table.to_pylist()
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            sys.exit(f"{db_path} 를 다른 프로세스(실행 중인 분석 서버 등)가 열고 있다. 서버를 끄고 다시 하거나, --out 으로 다른 경로에 만든 뒤 환경변수 LEXICON_PATH 로 지정할 것.")
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE compound (word TEXT PRIMARY KEY, surfaces TEXT NOT NULL, lemmas TEXT NOT NULL, links TEXT NOT NULL, source TEXT NOT NULL)")
    con.execute("CREATE TABLE derivation (word TEXT PRIMARY KEY, prefixes TEXT NOT NULL, suffixes TEXT NOT NULL)")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    stats = {"compound_entries": 0, "unparsed": 0, "unaligned": 0, "stored": 0, "from_derived_lists": 0, "derivation_entries": 0, "derivation_stored": 0}
    seen: set[str] = set()
    for r in rows:
        if r["morph_type"] == "derivation":
            stats["derivation_entries"] += 1
            word = r["word"]
            d = parse_derivation(r["etymology_text"])
            if d and " " not in word and "-" not in word:
                pre, suf = d
                low = word.lower()
                # 단어의 앞·뒤에 실제로 붙어 있는 접사만 인정한다 (움라우트 등으로 모양이 바뀐 것은 버린다)
                pre = [p for p in pre if low.startswith(p) and len(low) - len(p) >= 3]
                suf = [x for x in suf if low.endswith(x) and len(low) - len(x) >= 3]
                if pre or suf:
                    con.execute("INSERT OR IGNORE INTO derivation VALUES (?, ?, ?)", (word, ",".join(pre), ",".join(suf)))
                    stats["derivation_stored"] += 1
            continue
        if r["morph_type"] != "compound":
            continue
        stats["compound_entries"] += 1
        word = r["word"]
        if word in seen or " " in word or "-" in word:
            continue
        parsed = parse_etymology(r["etymology_text"])
        if parsed is None:
            stats["unparsed"] += 1
            continue
        parts, links = parsed
        aligned = align_any(word, parts, links)
        if aligned is None:
            stats["unaligned"] += 1
            continue
        surfaces, used, parts = aligned
        seen.add(word)
        con.execute("INSERT INTO compound VALUES (?, ?, ?, ?, ?)", (word, "|".join(surfaces), "|".join(parts), ",".join(used), "etymology"))
        stats["stored"] += 1
    stats["from_derived_lists"] = add_from_derived_lists(con, rows, seen)
    if parquet_en is not None:
        stats.update(build_english(parquet_en, con))
    con.execute(
        "INSERT INTO meta VALUES ('source', 'Wiktionary (de) via yuanxin112/wiktionary-morph, CC-BY-SA-4.0')"
    )
    con.commit()
    con.close()
    print(stats)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", type=Path, help="이미 받아 둔 de.parquet 경로 (없으면 내려받는다)")
    ap.add_argument("--parquet-en", type=Path, help="영어 en.parquet 경로 (없으면 내려받는다)")
    ap.add_argument("--no-english", action="store_true", help="영어 사전은 만들지 않는다")
    ap.add_argument("--out", type=Path, default=DB_PATH)
    args = ap.parse_args()
    path = args.parquet
    if path is None:
        DATA_DIR.mkdir(exist_ok=True)
        path = DATA_DIR / "de.parquet"
        if not path.exists():
            print("내려받는 중 (약 88MB) …", file=sys.stderr)
            urllib.request.urlretrieve(PARQUET_URL, path)
    path_en = None
    if not args.no_english:
        path_en = args.parquet_en
        if path_en is None:
            DATA_DIR.mkdir(exist_ok=True)
            path_en = DATA_DIR / "en.parquet"
            if not path_en.exists():
                print("영어 원본 내려받는 중 (약 64MB) …", file=sys.stderr)
                urllib.request.urlretrieve(PARQUET_URL_EN, path_en)
    build(path, args.out, path_en)


if __name__ == "__main__":
    main()
