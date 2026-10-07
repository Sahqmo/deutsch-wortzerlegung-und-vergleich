"""번역기 어댑터. 독일어 단어 → 대응어를 가져오는 부분만 외부 번역기에 맡긴다.

기본 구현은 키가 필요 없는 비공식 Google 번역 엔드포인트(개인 프로토타입용; 약관상 공개 서비스에는 부적합).
공개 배포 시에는 Translator 프로토콜을 만족하는 공식 Cloud Translation 구현으로 교체하면 된다.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Protocol

import requests

CACHE_PATH = Path(__file__).parent / "translations.sqlite"


class Translator(Protocol):
    def lookup(self, text: str, src: str, dst: str) -> list[str]:
        """text 를 dst 언어로 번역한 후보 목록. 첫 번째가 대표 번역. 실패하면 빈 리스트."""
        ...

    def lookup_pos(self, text: str, src: str, dst: str) -> dict[str, list[str]]:
        """사전형 번역 후보를 품사별로 묶은 것 ({"noun": [...], "verb": [...]}). 사전 항목이 없으면 빈 dict."""
        ...


class GtxTranslator:
    URL = "https://translate.googleapis.com/translate_a/single"

    def __init__(self, cache_path: Path = CACHE_PATH, min_interval: float = 0.05):
        self._db = sqlite3.connect(str(cache_path), check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS tr (src TEXT, dst TEXT, text TEXT, result TEXT, PRIMARY KEY (src, dst, text))"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS trpos (src TEXT, dst TEXT, text TEXT, result TEXT, PRIMARY KEY (src, dst, text))"
        )
        self._lock = threading.Lock()
        self._last = 0.0
        self._min_interval = min_interval
        self._session = requests.Session()

    # ───────── 캐시 ─────────

    def _cached(self, text: str, src: str, dst: str) -> list[str] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT result FROM tr WHERE src=? AND dst=? AND text=?", (src, dst, text)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def _store(self, text: str, src: str, dst: str, result: list[str]) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO tr VALUES (?,?,?,?)", (src, dst, text, json.dumps(result, ensure_ascii=False))
            )
            self._db.commit()

    def _cached_pos(self, text: str, src: str, dst: str) -> dict[str, list[str]] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT result FROM trpos WHERE src=? AND dst=? AND text=?", (src, dst, text)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def _store_pos(self, text: str, src: str, dst: str, groups: dict[str, list[str]]) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO trpos VALUES (?,?,?,?)", (src, dst, text, json.dumps(groups, ensure_ascii=False))
            )
            self._db.commit()

    # ───────── 요청과 해석 ─────────

    @staticmethod
    def _parse(data: list) -> tuple[list[str], dict[str, list[str]]]:
        """gtx 응답 → (평탄한 후보 목록, 품사별 사전 후보). 대표 번역(문장 번역기 결과)은 평탄 목록 맨 앞에만 들어간다."""
        main = "".join(seg[0] for seg in (data[0] or []) if seg and seg[0]).strip()
        out: list[str] = [main] if main else []
        groups: dict[str, list[str]] = {}
        for pos in (data[1] or []) if len(data) > 1 else []:  # 사전형 후보
            alts = [a for a in pos[1] if isinstance(a, str)]
            out.extend(alts)
            if alts:
                groups.setdefault(str(pos[0]).lower(), []).extend(alts)
        for item in (data[5] or []) if len(data) > 5 else []:  # 대체 번역
            for alt in item[2] or []:
                if alt and isinstance(alt[0], str):
                    out.append(alt[0])
        seen: set[str] = set()
        return [x for x in out if not (x.lower() in seen or seen.add(x.lower()))], groups

    def _fetch(self, text: str, src: str, dst: str) -> tuple[list[str], dict[str, list[str]]]:
        with self._lock:  # 요청 간 최소 간격
            wait = self._min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                r = self._session.get(
                    self.URL,
                    params={"client": "gtx", "sl": src, "tl": dst, "dt": ["t", "bd", "at"], "q": text},
                    timeout=15,
                )
                r.raise_for_status()
                return self._parse(r.json())
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(0.4 * (attempt + 1))
        raise RuntimeError(f"translate failed: {last_err}")

    # ───────── 공개 메서드 ─────────

    def lookup(self, text: str, src: str, dst: str) -> list[str]:
        text = text.strip()
        if not text:
            return []
        hit = self._cached(text, src, dst)
        if hit is not None:
            return hit
        flat, groups = self._fetch(text, src, dst)
        self._store(text, src, dst, flat)
        self._store_pos(text, src, dst, groups)
        return flat

    def lookup_pos(self, text: str, src: str, dst: str) -> dict[str, list[str]]:
        text = text.strip()
        if not text:
            return {}
        hit = self._cached_pos(text, src, dst)
        if hit is not None:
            return hit
        flat, groups = self._fetch(text, src, dst)
        self._store(text, src, dst, flat)
        self._store_pos(text, src, dst, groups)
        return groups
