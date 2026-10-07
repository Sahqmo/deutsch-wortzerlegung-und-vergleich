"""독일어 요소 ↔ 대응어 요소 정렬. 번역기 후보(직접 번역·역번역·영어 피벗)로 뜻 일치를 판정한다."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from translator import Translator
from units import Morpheme, Unit


def norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", s.lower())


def _safe(tr: Translator, text: str, src: str, dst: str) -> list[str]:
    try:
        return tr.lookup(text, src, dst)
    except Exception:  # noqa: BLE001  보조 조회 실패는 신호가 없는 것으로 취급
        return []


@dataclass
class Item:
    """정렬 대상 하나: 독일어 요소(unit) 또는 대응어의 요소/형태소."""

    text: str
    lang: str
    indices: list[int]  # 평탄화된 morphemes 인덱스
    ref: str = ""  # 번역 조회용 텍스트(없으면 text)
    ref_lang: str = ""
    direct: list[str] = field(default_factory=list)  # 대상 언어 쪽 후보
    en: list[str] = field(default_factory=list)  # 영어 피벗 후보
    head: bool = False  # 합성어의 핵심어(마지막 요소) 자리인가


def _unit_item(unit: Unit, base: int, lang: str) -> Item:
    return Item(unit.text, lang, list(range(base, base + len(unit.morphemes))))


def _morph_item(m: Morpheme, index: int, fallback_lang: str) -> Item:
    return Item(m.surface, fallback_lang, [index], ref=m.lookup_text or m.lemma, ref_lang=m.lookup_lang or fallback_lang)


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _fetch_signals(tr: Translator, de_items: list[Item], t_items: list[Item], lang: str, banned: str) -> None:
    jobs: list[tuple[Item, str, str, str, str]] = []  # (item, 필드, 텍스트, src, dst)
    for it in de_items:
        jobs.append((it, "direct", it.text, "de", lang))
        jobs.append((it, "en", it.text, "de", "en"))
    for it in t_items:
        src = it.ref_lang or lang
        jobs.append((it, "direct", it.ref or it.text, src, "de"))
        if src == "en":
            it.en = [it.ref or it.text]
        else:
            jobs.append((it, "en", it.ref or it.text, src, "en"))

    def run(job):
        item, fld, text, src, dst = job
        res = [x for x in _safe(tr, text, src, dst) if banned not in norm(x)]
        return item, fld, res[:6]

    with ThreadPoolExecutor(max_workers=6) as pool:
        for item, fld, res in pool.map(run, jobs):
            setattr(item, fld, res)


def _shared_senses(d: Item, t: Item) -> list[str]:
    """독일어 요소와 대응어 요소의 영어 번역 후보가 겹치는 단어들(독일어 후보 순서). 뜻풀이의 의미(sense)를 고르는 증거."""
    t_set = {norm(x) for x in t.en}
    return [x for x in d.en if norm(x) in t_set]


def _score(d: Item, t: Item, lang: str) -> int:
    """0=무관, 1=연관, 2=같음"""
    d_norm, t_norm = norm(d.text), norm(t.ref if t.ref_lang == lang and t.ref else t.text)
    t_to_de = [norm(x) for x in t.direct]
    d_to_t = [norm(x) for x in d.direct]
    t_to_de_set, d_to_t_set = set(t_to_de), set(d_to_t)

    if t_norm and t_norm in d_to_t[:2]:
        return 2
    if d_norm in t_to_de[:2]:
        return 2
    d_en, t_en = [norm(x) for x in d.en], [norm(x) for x in t.en]
    if d_en and t_en:
        common = set(d_en) & set(t_en)
        if common and (d_en[0] in common or t_en[0] in common or (set(d_en[:2]) & set(t_en[:2]))):
            return 2
        if common:
            return 1
    if t_norm and t_norm in d_to_t_set:
        return 1
    if d_norm in t_to_de_set:
        return 1
    for cand in t_to_de + d_to_t:
        if len(cand) >= 4 and _common_prefix(d_norm, cand) >= max(4, min(len(d_norm), len(cand)) - 2):
            return 1
    return 0


def align(de_units: list[Unit], t_units: list[Unit], lang: str, tr: Translator, word: str) -> tuple[list[dict], bool, dict[int, list[str]]]:
    """(정렬 그룹 리스트, 위치 기반 추정을 썼는지, 독일어 형태소 인덱스 → 뜻 증거 단어들)"""
    de_items, base = [], 0
    for u in de_units:
        de_items.append(_unit_item(u, base, "de"))
        base += len(u.morphemes)
    t_items, base = [], 0
    for u in t_units:
        t_items.append(_unit_item(u, base, lang))
        t_items[-1].ref, t_items[-1].ref_lang = u.text, lang
        # 한자어·외래어는 번역기가 더 잘 아는 표기(한자/가타카나, 일본어)로 조회한다: 기 → 機
        if u.morphemes and all(m.lookup_text and m.lookup_lang for m in u.morphemes) and len({m.lookup_lang for m in u.morphemes}) == 1:
            t_items[-1].ref = "".join(m.lookup_text for m in u.morphemes)
            t_items[-1].ref_lang = u.morphemes[0].lookup_lang
        base += len(u.morphemes)

    if de_items:
        de_items[-1].head = True
    if t_items:
        t_items[-1].head = True
    flat_t = [m for u in t_units for m in u.morphemes]
    # 한자어처럼 형태소가 여럿인 대응어 요소는 형태소 단위 후보도 준비
    sub_items: dict[int, list[Item]] = {}
    for ti, u in enumerate(t_units):
        roots = [i for i, m in enumerate(u.morphemes) if m.role != "suffix"]
        if len(roots) >= 2:
            first = t_items[ti].indices[0]
            sub_items[ti] = [_morph_item(u.morphemes[i], first + i, lang) for i in roots]
            sub_items[ti][-1].head = ti == len(t_units) - 1

    all_t = t_items + [s for subs in sub_items.values() for s in subs]
    _fetch_signals(tr, de_items, all_t, lang, norm(word))

    groups: list[dict] = []
    used_de: set[int] = set()
    used_t: set[int] = set()  # t_items 인덱스
    used_sub: set[tuple[int, int]] = set()  # (t_items 인덱스, 형태소 인덱스)
    fallback_used = False
    senses: dict[int, list[str]] = {}

    def evidence(d: Item, t: Item) -> None:
        if len(d.indices) == 1:
            senses.setdefault(d.indices[0], []).extend(_shared_senses(d, t))

    def add(de_idx: list[int], t_idx: list[int], relation: str, note: str) -> None:
        groups.append({"de": de_idx, "target": t_idx, "relation": relation, "note": note})

    # 1) 요소 단위 매칭
    pairs = sorted(
        ((_score(d, t, lang), i, j) for i, d in enumerate(de_items) for j, t in enumerate(t_items)),
        key=lambda x: (-x[0], abs(x[1] / max(len(de_items), 1) - x[2] / max(len(t_items), 1))),
    )
    for score, i, j in pairs:
        if score < 1 or i in used_de or j in used_t:
            continue
        used_de.add(i)
        used_t.add(j)
        d, t = de_items[i], t_items[j]
        evidence(d, t)
        if score == 2:
            add(d.indices, t.indices, "same", f"{d.text} ≈ {t.text}")
        else:
            add(d.indices, t.indices, "related", f"{d.text} ~ {t.text} (뜻이 연관됨)")

    # 2) 남은 한자어 등을 형태소 단위로 매칭
    sub_pairs = sorted(
        (
            (_score(d, s, lang), i, ti, k)
            for i, d in enumerate(de_items)
            if i not in used_de
            for ti, subs in sub_items.items()
            if ti not in used_t
            for k, s in enumerate(subs)
        ),
        key=lambda x: -x[0],
    )
    for score, i, ti, k in sub_pairs:
        if score < 1 or i in used_de or (ti, k) in used_sub:
            continue
        used_de.add(i)
        used_sub.add((ti, k))
        d, s = de_items[i], sub_items[ti][k]
        evidence(d, s)
        add(d.indices, s.indices, "same" if score == 2 else "related", f"{d.text} ≈ {s.text}({flat_t[s.indices[0]].lemma})")

    # 3) 남은 항목: 위치(핵심어 자리) 기반 추정
    left_de = [i for i in range(len(de_items)) if i not in used_de]
    left_t: list[Item] = []
    for ti, it in enumerate(t_items):
        if ti in used_t:
            continue
        if ti in sub_items and any((ti, k) in used_sub for k in range(len(sub_items[ti]))):
            left_t.extend(s for k, s in enumerate(sub_items[ti]) if (ti, k) not in used_sub)
        else:
            left_t.append(it)

    if left_de and left_t:
        if not groups and len(left_t) == 1 and len(left_de) >= 2:
            fallback_used = True
            t = left_t[0]
            add(sum((de_items[i].indices for i in left_de), []), t.indices, "related",
                f"독일어의 여러 요소가 '{t.text}' 하나로 합쳐짐")
            left_de, left_t = [], []
        elif not groups and len(left_de) == 1 and len(left_t) >= 2:
            # 독일어는 한 단어이고 대응어가 여러 요소: 대응어 전체가 곧 그 단어의 번역이므로 뜻은 같다(짜임만 다름)
            fallback_used = True
            add(de_items[left_de[0]].indices, sum((t.indices for t in left_t), []), "same",
                f"독일어 '{de_items[left_de[0]].text}'가 대응어에서는 여러 요소로 나뉨 (뜻은 같음)")
            left_de, left_t = [], []
        else:
            # 위치 기반 추정: 핵심어(마지막 요소)는 핵심어끼리, 수식어는 수식어끼리만 짝짓는다.
            # (수식어 Staub 가 핵심어 자리의 '기'와 짝지어지는 엉뚱한 대응을 막는다)
            for want_head, label in ((True, "핵심어"), (False, "수식어")):
                while True:
                    di = next((i for i in reversed(left_de) if de_items[i].head == want_head), None)
                    tj = next((k for k in range(len(left_t) - 1, -1, -1) if left_t[k].head == want_head), None)
                    if di is None or tj is None:
                        break
                    fallback_used = True
                    left_de.remove(di)
                    t = left_t.pop(tj)
                    d = de_items[di]
                    add(d.indices, t.indices, "related", f"{d.text} ~ {t.text} ({label} 자리 기준 추정, 어원·뜻은 다를 수 있음)")

    for i in left_de:
        add(de_items[i].indices, [], "missing", f"'{de_items[i].text}'에 해당하는 요소가 없음")
    for t in left_t:
        add([], t.indices, "added", f"독일어에는 없는 요소 '{t.text}'")

    # 한 단어(세탁)의 글자 중 일부만 짝이 지어지고 나머지가 '추가'로 남았으면, 그 단어 전체가 한 요소이므로 같은 그룹으로 합친다
    for ti, subs in sub_items.items():
        unit_idx = set(t_items[ti].indices)
        for g in [g for g in groups if g["relation"] == "added" and len(g["target"]) == 1 and g["target"][0] in unit_idx]:
            host = next((h for h in groups if h is not g and h["de"] and any(i in unit_idx for i in h["target"])), None)
            if host:
                host["target"] = sorted(set(host["target"]) | set(g["target"]))
                groups.remove(g)

    groups.sort(key=lambda g: (min(g["de"]) if g["de"] else 10**6, min(g["target"]) if g["target"] else 0))
    return groups, fallback_used, senses
