"use client";

import { useEffect, useState } from "react";

const STEPS = [
  { ko: "단어를 분해하는 중", de: "Zerlegen" },
  { ko: "번역기로 대응어를 가져오는 중", de: "Übersetzen" },
  { ko: "요소 블록을 짝 맞추는 중", de: "Zuordnen" },
  { ko: "궁합 점수를 계산하는 중", de: "Bewerten" },
];

export function Loading({ word }: { word: string }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 700);
    return () => clearInterval(t);
  }, []);

  return (
    <section className="screen loading" aria-live="polite" aria-busy="true">
      <p className="eyebrow">PRÜFUNG LÄUFT…</p>

      <div className="specimen" data-size={word.length > 16 ? "xs" : word.length > 11 ? "sm" : "md"}>
        <span className="specimen-label">
          검체 <span className="de-tag">Probe</span>
        </span>
        <div className="specimen-word" aria-label={word}>
          <span aria-hidden="true">{word}</span>
          <i className="scan" aria-hidden="true" />
        </div>
        <div className="ruler" aria-hidden="true" />
      </div>

      <ol className="steps">
        {STEPS.map((s, i) => {
          const state = i < step ? "done" : i === step ? "active" : "todo";
          return (
            <li key={s.de} className={`step step-${state}`} aria-current={state === "active" ? "step" : undefined}>
              <span className="step-mark" aria-hidden="true">
                {state === "done" ? "✓" : i + 1}
              </span>
              <span className="step-ko">
                {s.ko}
                {state === "active" && <span className="dots" aria-hidden="true" />}
              </span>
              <span className="step-de">{s.de}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
