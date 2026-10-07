"use client";

import { useEffect, useState } from "react";
import type { AnalyzeResponse } from "@/lib/schema";
import { ResultCard, Summary } from "./ResultCard";

const EXAMPLES = ["Kugelschreiber", "Abfahrtszeit", "Krankenhaus", "Handschuh"];

export default function Home() {
  const [word, setWord] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    fetch("/api/analyze")
      .then((r) => r.json())
      .then((d: { demoMode: boolean }) => setDemoMode(d.demoMode))
      .catch(() => {});
  }, []);

  async function run(w: string) {
    const target = w.trim();
    if (!target || loading) return;
    setWord(target);
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ word: target }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "알 수 없는 오류가 났어요.");
        setResult(null);
      } else {
        setResult(data as AnalyzeResponse);
      }
    } catch {
      setError("서버에 연결하지 못했어요.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const analysis = result?.analysis;

  return (
    <main className="wrap">
      <header className="hero">
        <h1>독일어 합성어 상성 진단소</h1>
        <p>
          독일어 합성어를 분해하고, 영어·한국어·일본어의 대응어와 <strong>짜임이 얼마나 닮았는지</strong> 퍼센트로 진단해요.
        </p>
      </header>

      <form
        className="search"
        onSubmit={(e) => {
          e.preventDefault();
          run(word);
        }}
      >
        <input
          value={word}
          onChange={(e) => setWord(e.target.value)}
          placeholder="독일어 단어를 입력 (예: Kugelschreiber)"
          aria-label="독일어 단어"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          maxLength={40}
        />
        <button type="submit" disabled={loading || !word.trim()}>
          {loading ? "진단 중…" : "진단하기"}
        </button>
      </form>

      <div className="examples">
        {EXAMPLES.map((ex) => (
          <button key={ex} type="button" className="ex" onClick={() => run(ex)} disabled={loading}>
            {ex}
          </button>
        ))}
      </div>

      {demoMode && (
        <p className="banner">
          데모 모드: 분석 서비스(Python)가 꺼져 있어 위 예시 단어 4개만 진단할 수 있어요. <code>run.bat</code>으로 실행하면 아무 단어나 진단해요.
        </p>
      )}

      {loading && <p className="status" role="status">단어를 쪼개고 번역기로 대응어를 찾는 중이에요… (처음 보는 단어는 몇 초 걸려요)</p>}
      {error && <p className="error" role="alert">{error}</p>}

      {analysis && !loading && (
        <>
          {!analysis.isGermanWord ? (
            <p className="error">‘{analysis.input}’은(는) 독일어 단어로 보기 어려워요.</p>
          ) : (
            <>
              <Summary analysis={analysis} scores={result.scores} />
              <div className="cards">
                {analysis.targets
                  .flatMap((t) => {
                    const score = result.scores.find((s) => s.lang === t.lang);
                    return score ? [{ t, score }] : [];
                  })
                  // 가장 유사한 언어부터. 대응어를 못 찾은 언어는 맨 뒤. 동점이면 en·ko·ja 순서 유지.
                  .sort((a, b) => Number(b.t.found) - Number(a.t.found) || b.score.total - a.score.total)
                  .map(({ t, score }, i) => (
                    <ResultCard key={t.lang} de={analysis.de} target={t} score={score} rank={t.found ? i + 1 : undefined} />
                  ))}
              </div>
              <p className="legend">
                같은 색 칩끼리 서로 대응하는 요소예요. 점선 칩은 상대 언어에 대응이 없는 요소예요. 출처:{" "}
                {result.source === "live" ? "방금 자동 분석" : "미리 준비된 예시"}
              </p>
            </>
          )}
        </>
      )}

      <footer className="foot">
        재미용 도구예요. 번역기와 사전 라이브러리로 자동 분석한 추정치라 어원과 분해가 틀릴 수 있어요. 점수는 구조 40% · 의미 40% · 고유도 20% 가중합입니다.
      </footer>
    </main>
  );
}
