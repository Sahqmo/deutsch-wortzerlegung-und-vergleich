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


def build(parquet_path: Path, db_path: Path) -> None:
    import pyarrow.parquet as pq  # 만들 때만 필요하다

    table = pq.read_table(parquet_path, columns=["word", "morph_type", "etymology_text"])
    rows = table.to_pylist()
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE compound (word TEXT PRIMARY KEY, surfaces TEXT NOT NULL, lemmas TEXT NOT NULL, links TEXT NOT NULL)")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    stats = {"compound_entries": 0, "unparsed": 0, "unaligned": 0, "stored": 0}
    seen: set[str] = set()
    for r in rows:
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
        con.execute("INSERT INTO compound VALUES (?, ?, ?, ?)", (word, "|".join(surfaces), "|".join(parts), ",".join(used)))
        stats["stored"] += 1
    con.execute(
        "INSERT INTO meta VALUES ('source', 'Wiktionary (de) via yuanxin112/wiktionary-morph, CC-BY-SA-4.0')"
    )
    con.commit()
    con.close()
    print(stats)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", type=Path, help="이미 받아 둔 de.parquet 경로 (없으면 내려받는다)")
    ap.add_argument("--out", type=Path, default=DB_PATH)
    args = ap.parse_args()
    path = args.parquet
    if path is None:
        DATA_DIR.mkdir(exist_ok=True)
        path = DATA_DIR / "de.parquet"
        if not path.exists():
            print("내려받는 중 (약 88MB) …", file=sys.stderr)
            urllib.request.urlretrieve(PARQUET_URL, path)
    build(path, args.out)


if __name__ == "__main__":
    main()
