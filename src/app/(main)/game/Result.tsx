"use client";

import { useState } from "react";
import type { AnalyzeResponse } from "@/lib/schema";
import { gradeOf, LANG_LABEL, rank } from "./grades";
import { LangCard } from "./LangCard";

export function Result({ data, onAgain }: { data: AnalyzeResponse; onAgain: () => void }) {
  const { analysis, scores, source } = data;
  const ranked = rank(analysis.targets, scores);
  const winners = ranked.filter((r) => r.found);
  const best = winners[0];
  const [copied, setCopied] = useState(false);

  const podium = winners.length >= 3 ? [winners[1], winners[0], winners[2]] : winners.length === 2 ? [winners[1], winners[0]] : winners;

  async function copy() {
    const lines = [
      `독일어 합성어 상성 진단소`,
      `「${analysis.de.word}」 (${analysis.de.morphemes.map((m) => m.lemma).join(" + ")})`,
      ...winners.map((w, i) => `${i + 1}위 ${LANG_LABEL[w.lang]} ${w.decomposition.word} — ${w.score.total}% ${gradeOf(w.score.total).title}`),
      `${location.origin}/?w=${encodeURIComponent(analysis.de.word)}`,
    ];
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("복사해서 공유하세요", lines.join("\n"));
    }
  }

  return (
    <section className="screen result" aria-labelledby="result-title">
      <p className="eyebrow">ERGEBNIS · 진단 완료</p>
      <h2 id="result-title" className="word-title">
        {analysis.de.word}
      </h2>

      <div className="split" aria-label="독일어 분해 결과">
        {analysis.de.morphemes.map((m, i) => (
          <span key={i} className={`piece${m.role !== "root" ? " piece-affix" : ""}`} style={{ animationDelay: `${i * 110}ms`, ["--hue" as string]: (i * 61 + 20) % 360 }}>
            <span className="piece-main">{m.lemma}</span>
            {m.gloss && <span className="piece-gloss">{m.gloss}</span>}
          </span>
        ))}
        {analysis.de.linking.length > 0 && (
          <span className="piece piece-link" title="합성할 때 끼는 연결요소">
            <span className="piece-main">-{analysis.de.linking.join("/")}-</span>
            <span className="piece-gloss">연결요소</span>
          </span>
        )}
      </div>

      {best ? (
        <>
          <div className="winner">
            <span className="winner-crown" aria-hidden="true">
              ★
            </span>
            <p>
              가장 닮은 언어는 <strong>{LANG_LABEL[best.lang]}</strong>
              <span className="winner-word"> {best.decomposition.word}</span>
            </p>
            <p className="winner-grade">
              {best.score.total}% · {gradeOf(best.score.total).title} · {gradeOf(best.score.total).de}
            </p>
          </div>

          <div className="podium" aria-label="순위">
            {podium.map((p) => {
              const r = winners.indexOf(p) + 1;
              return (
                <div key={p.lang} className={`pod pod-${r}`}>
                  <span className="pod-pct">{p.score.total}%</span>
                  <span className="pod-bar" style={{ height: `${[0, 132, 100, 76][r] ?? 76}px` }}>
                    <span className="pod-rank">{r}</span>
                  </span>
                  <span className="pod-name">{LANG_LABEL[p.lang]}</span>
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <p className="alert">세 언어 모두 적절한 대응어를 찾지 못했어요.</p>
      )}

      <div className="cards">
        {ranked.map((t, i) => (
          <LangCard key={t.lang} de={analysis.de} target={t} score={t.score} rank={i + 1} index={i} />
        ))}
      </div>

      <div className="actions">
        <button type="button" className="btn btn-primary" onClick={onAgain}>
          ↺ 다른 단어로 다시
        </button>
        <button type="button" className="btn btn-ghost" onClick={copy}>
          {copied ? "✔ 복사됨!" : "결과 복사"}
        </button>
      </div>

      <p className="fineprint">
        <span className="de-tag">Hinweis</span>{" "}
        {source === "demo" ? "미리 준비된 예시 결과예요. " : ""}
        번역기와 사전 라이브러리로 자동 분석한 재미용 추정치예요. 어원과 분해는 틀릴 수 있어요. 점수는 구조 40% · 의미 40% · 토박이력 20% 가중합입니다.
      </p>
    </section>
  );
}
