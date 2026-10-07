"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { AnalyzeResponse } from "@/lib/schema";
import { Intro } from "./game/Intro";
import { Loading } from "./game/Loading";
import { Result } from "./game/Result";
import { clearCollection, loadCollection, saveEntry, type Entry } from "./game/history";
import { LANG_CODE, rank } from "./game/grades";

const EXAMPLES = ["Kugelschreiber", "Abfahrtszeit", "Krankenhaus", "Handschuh"];
const MIN_LOADING_MS = 1800; // 로딩 연출이 보일 최소 시간

type Stage = { name: "intro" } | { name: "loading"; word: string } | { name: "result"; data: AnalyzeResponse };

export default function Home() {
  const [stage, setStage] = useState<Stage>({ name: "intro" });
  const [word, setWord] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [collection, setCollection] = useState<Entry[]>([]);
  const busy = useRef(false);

  const start = useCallback(async (raw: string) => {
    const w = raw.trim();
    if (!w || busy.current) return;
    busy.current = true;
    setWord(w);
    setError(null);
    setStage({ name: "loading", word: w });
    window.scrollTo({ top: 0 });
    try {
      const started = Date.now();
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ word: w }),
      });
      const body = await res.json();
      // 오류(예: 쪼갤 수 없는 단일 단어)는 로딩 연출을 기다리지 않고 바로 메인으로 돌아간다
      if (!res.ok) throw new Error(body.error ?? "알 수 없는 오류가 났어요.");
      const rest = MIN_LOADING_MS - (Date.now() - started);
      if (rest > 0) await new Promise((r) => setTimeout(r, rest));
      const data = body as AnalyzeResponse;
      if (!data.analysis.isGermanWord) throw new Error(`‘${data.analysis.input}’은(는) 독일어 단어로 보기 어려워요. 다른 단어를 넣어 주세요!`);

      const best = rank(data.analysis.targets, data.scores).find((r) => r.found);
      if (best) {
        setCollection(
          saveEntry({
            word: data.analysis.de.word,
            lang: LANG_CODE[best.lang],
            target: best.decomposition.word,
            total: best.score.total,
            at: Date.now(),
          }),
        );
      }
      history.replaceState(null, "", `/?w=${encodeURIComponent(data.analysis.de.word)}`);
      setStage({ name: "result", data });
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError(e instanceof Error ? e.message : "서버에 연결하지 못했어요.");
      setStage({ name: "intro" });
    } finally {
      busy.current = false;
    }
  }, []);

  useEffect(() => {
    setCollection(loadCollection());
    fetch("/api/analyze")
      .then((r) => r.json())
      .then((d: { demoMode: boolean }) => setDemoMode(d.demoMode))
      .catch(() => {});
    const shared = new URLSearchParams(window.location.search).get("w");
    if (shared) void start(shared);
  }, [start]);

  function again() {
    history.replaceState(null, "", "/");
    setWord("");
    setError(null);
    setStage({ name: "intro" });
    window.scrollTo({ top: 0 });
  }

  return (
    <main className="app">
      <div className="bg" aria-hidden="true">
        <i className="blob b1" />
        <i className="blob b2" />
        <i className="blob b3" />
      </div>
      <div className="frame">
        {stage.name === "intro" && (
          <Intro
            word={word}
            onWord={setWord}
            onStart={start}
            examples={EXAMPLES}
            collection={collection}
            onClearCollection={() => {
              clearCollection();
              setCollection([]);
            }}
            demoMode={demoMode}
            error={error}
          />
        )}
        {stage.name === "loading" && <Loading word={stage.word} />}
        {stage.name === "result" && <Result data={stage.data} onAgain={again} />}
      </div>
    </main>
  );
}
