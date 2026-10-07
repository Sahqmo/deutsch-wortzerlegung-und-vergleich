"use client";

import type { Entry } from "./history";
import { gradeOf } from "./grades";

const STEPS = [
  { n: "1", title: "단어 투입", text: "독일어 합성어를 넣어요" },
  { n: "2", title: "블록 분해", text: "lemma 단위로 쪼개요" },
  { n: "3", title: "궁합 판정", text: "영·한·일과 짜임을 맞춰 봐요" },
];

export function Intro({
  word,
  onWord,
  onStart,
  examples,
  collection,
  onClearCollection,
  demoMode,
  error,
}: {
  word: string;
  onWord: (w: string) => void;
  onStart: (w: string) => void;
  examples: string[];
  collection: Entry[];
  onClearCollection: () => void;
  demoMode: boolean;
  error: string | null;
}) {
  return (
    <section className="screen intro" aria-labelledby="title">
      <div className="marquee" aria-hidden="true">
        <span>KUGEL + SCHREIB + ER</span>
        <span>ABFAHRT + S + ZEIT</span>
        <span>KRANKEN + HAUS</span>
        <span>HAND + SCHUH</span>
        <span>KUGEL + SCHREIB + ER</span>
        <span>ABFAHRT + S + ZEIT</span>
      </div>

      <div className="hero">
        <p className="eyebrow">WORD LAB · 말 짜임 궁합 테스트</p>
        <h1 id="title">
          <span className="h1-line">독일어 합성어</span>
          <span className="h1-line pop">상성 진단소</span>
        </h1>
        <p className="lead">
          독일어 단어를 쪼개 놓고, 영어·한국어·일본어 중 <strong>누가 제일 비슷하게 만들었는지</strong> 퍼센트로 판정해 드려요.
        </p>
      </div>

      <form
        className="slot"
        onSubmit={(e) => {
          e.preventDefault();
          onStart(word);
        }}
      >
        <label htmlFor="word" className="slot-label">
          <span className="slot-dot" aria-hidden="true" /> 단어 투입구
        </label>
        <div className="slot-row">
          <input
            id="word"
            value={word}
            onChange={(e) => onWord(e.target.value)}
            placeholder="예: Kugelschreiber"
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            maxLength={40}
          />
          <button type="submit" className="btn btn-primary" disabled={!word.trim()}>
            진단 시작 <span aria-hidden="true">▶</span>
          </button>
        </div>
        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}
      </form>

      <div className="stage-pick">
        <p className="mini-title">▶ 스테이지 선택 (바로 해보기)</p>
        <div className="stage-list">
          {examples.map((ex, i) => (
            <button key={ex} type="button" className="btn btn-stage" onClick={() => onStart(ex)}>
              <span className="stage-no">STAGE {i + 1}</span>
              <span className="stage-word">{ex}</span>
            </button>
          ))}
        </div>
      </div>

      {demoMode && (
        <p className="note-bar">
          🔌 지금은 데모 모드예요. 분석 서비스가 꺼져 있어서 위 스테이지 단어만 진단돼요. <code>run.bat</code>으로 실행하면 아무 단어나 돼요.
        </p>
      )}

      <ol className="how">
        {STEPS.map((s) => (
          <li key={s.n}>
            <span className="how-n">{s.n}</span>
            <strong>{s.title}</strong>
            <span>{s.text}</span>
          </li>
        ))}
      </ol>

      {collection.length > 0 && (
        <div className="dex">
          <div className="dex-head">
            <p className="mini-title">📒 내 도감 · {collection.length}종 수집</p>
            <button type="button" className="link-btn" onClick={onClearCollection}>
              비우기
            </button>
          </div>
          <ul className="dex-list">
            {collection.map((e) => {
              const g = gradeOf(e.total);
              return (
                <li key={e.word}>
                  <button type="button" className={`dex-item tone-${g.tone}`} onClick={() => onStart(e.word)} title={`${e.target} · ${g.title}`}>
                    <span className="dex-emoji" aria-hidden="true">
                      {g.emoji}
                    </span>
                    <span className="dex-word">{e.word}</span>
                    <span className="dex-score">{e.total}%</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
