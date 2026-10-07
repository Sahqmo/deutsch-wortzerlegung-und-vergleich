"use client";

import { useId, useState } from "react";
import type { Decomposition, ScoreBreakdown, TargetResult } from "@/lib/schema";
import { BlockLanes } from "./BlockLanes";
import { gradeOf, LANG_CODE, LANG_LABEL, STATS } from "./grades";
import { useCountUp } from "./useCountUp";

function ScoreRing({ total, delay }: { total: number; delay: number }) {
  const shown = useCountUp(total, 1200, delay);
  const R = 52;
  const C = 2 * Math.PI * R;
  return (
    <div className="ring" role="img" aria-label={`궁합 ${total}퍼센트`}>
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <circle className="ring-bg" cx="60" cy="60" r={R} />
        <circle
          className="ring-fg"
          cx="60"
          cy="60"
          r={R}
          strokeDasharray={C}
          strokeDashoffset={C * (1 - shown / 100)}
          transform="rotate(-90 60 60)"
        />
      </svg>
      <span className="ring-num">
        {shown}
        <small>%</small>
      </span>
      <span className="ring-cap" aria-hidden="true">
        GEPRÜFT
      </span>
    </div>
  );
}

function StatBar({ label, hint, value, delay }: { label: string; hint: string; value: number; delay: number }) {
  const shown = useCountUp(Math.round(value), 900, delay);
  const tipId = useId();
  return (
    <div className="stat">
      {/* 마우스를 올리거나 키보드·터치로 포커스하면 위쪽에 말풍선 설명이 뜬다 */}
      <span className="stat-label" tabIndex={0} aria-describedby={tipId}>
        {label}
        <span className="tip" id={tipId} role="tooltip">
          <strong>{label}</strong>
          {hint}
        </span>
      </span>
      <span className="stat-track">
        <span className="stat-fill" style={{ width: `${shown}%` }} />
      </span>
      <span className="stat-num">{shown}</span>
    </div>
  );
}

export function LangCard({
  de,
  target,
  score,
  rank,
  index,
}: {
  de: Decomposition;
  target: TargetResult;
  score: ScoreBreakdown;
  rank: number;
  index: number;
}) {
  const [open, setOpen] = useState(rank === 1);
  const grade = gradeOf(score.total);
  const found = target.found;
  const delay = 250 + index * 150;

  return (
    <article className={`lcard tone-${found ? grade.tone : "gray"}${open ? " is-open" : ""}`} style={{ animationDelay: `${index * 120}ms` }}>
      <button type="button" className="lcard-head" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className={`rank-badge${rank === 1 && found ? " rank-1" : ""}`}>{found ? `${rank}위` : "—"}</span>
        <span className="lcard-lang">
          <span className="lang-code">{LANG_CODE[target.lang]}</span>
          <span className="lang-name">{LANG_LABEL[target.lang]}</span>
        </span>
        <span className="lcard-word">{found ? target.decomposition.word : "대응어 없음"}</span>
        <span className="lcard-pct">{found ? `${score.total}%` : "-"}</span>
        <span className="chev" aria-hidden="true">
          {open ? "▴" : "▾"}
        </span>
      </button>

      {open && (
        <div className="lcard-body">
          {!found ? (
            <p className="muted">번역기가 적절한 대응어를 찾지 못했어요.</p>
          ) : (
            <>
              <div className="verdict">
                <ScoreRing total={score.total} delay={delay} />
                <div className="verdict-text">
                  <span className="grade-mark" aria-hidden="true">
                    {grade.mark}
                  </span>
                  <h3 className="grade-title">{grade.title}</h3>
                  <p className="grade-de">{grade.de}</p>
                  <p className="grade-line">{grade.line}</p>
                  {target.confidence !== "high" && (
                    <p className="conf">⚠ 자동 추정 · 신뢰도 {target.confidence === "medium" ? "보통" : "낮음"}</p>
                  )}
                </div>
              </div>

              <div className="stats">
                {STATS.map((s, i) => (
                  <StatBar key={s.key} label={s.label} hint={s.hint} value={score[s.key]} delay={delay + 150 + i * 120} />
                ))}
              </div>

              <p className="board-title">블록 맞추기 <span className="de-tag">Bausteine</span> · 위: 독일어 / 아래: {LANG_LABEL[target.lang]}</p>
              <BlockLanes de={de} target={target.decomposition} score={score} />

              {target.comment && <p className="bubble">{target.comment}</p>}

              <details className="why">
                <summary>왜 이렇게 나왔어?</summary>
                <ul>
                  {score.groups.map((g, i) => (
                    <li key={i} style={{ ["--lane" as string]: `var(--c${i % 6})` }}>
                      {g.note}
                    </li>
                  ))}
                </ul>
              </details>
            </>
          )}
        </div>
      )}
    </article>
  );
}
