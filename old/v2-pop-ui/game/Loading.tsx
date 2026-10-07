"use client";

import { useEffect, useState } from "react";

const MESSAGES = [
  "단어를 블록으로 쪼개는 중…",
  "번역기에서 대응어를 데려오는 중…",
  "영어·한국어·일본어 블록을 맞춰 보는 중…",
  "궁합 점수를 계산하는 중…",
];

export function Loading({ word }: { word: string }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, MESSAGES.length - 1)), 1100);
    return () => clearInterval(t);
  }, []);

  return (
    <section className="screen loading" aria-live="polite">
      <p className="eyebrow">ANALYZING…</p>
      <div className="tiles" data-long={word.length > 10} aria-label={word}>
        {[...word].map((ch, i) => (
          <span key={i} className="tile" style={{ animationDelay: `${i * 70}ms`, ["--hue" as string]: (i * 47) % 360 }}>
            {ch}
          </span>
        ))}
      </div>
      <p className="loading-msg">{MESSAGES[step]}</p>
      <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={MESSAGES.length} aria-valuenow={step + 1}>
        <span style={{ width: `${((step + 1) / MESSAGES.length) * 100}%` }} />
      </div>
    </section>
  );
}
