"use client";

import type { Entry } from "./history";
import { gradeOf } from "./grades";

// 전광판에 흐르는 합성어 예시 (한 묶음을 두 번 반복해 폭을 충분히 채운다)
const MARQUEE_WORDS = [
  "KUGEL + SCHREIB + ER",
  "ABFAHRT + S + ZEIT",
  "KRANKEN + HAUS",
  "HAND + SCHUH",
  "KUGEL + SCHREIB + ER",
  "ABFAHRT + S + ZEIT",
  "KRANKEN + HAUS",
  "HAND + SCHUH",
];

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
      {/* 한 줄 트랙을 통째로 움직인다: 같은 묶음을 두 번 이어 붙이고 절반(-50%)만큼 이동 → 단어 폭이 달라도 겹치지 않고 끊김 없이 반복 */}
      <div className="marquee" aria-hidden="true">
        <div className="marquee-track">
          {[0, 1].map((copy) => (
            <div className="marquee-group" key={copy}>
              {MARQUEE_WORDS.map((w, i) => (
                <span key={i}>{w}</span>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="hero">
        <p className="eyebrow">WORTLABOR · 말 짜임 궁합 테스트</p>
        <h1 id="title">
          <span className="h1-line">독일어 합성어</span>
          <span className="h1-line pop">상성 진단소</span>
        </h1>
        <p className="lead">
          독일어 단어를 쪼개 놓고, 영어·한국어·일본어 중 <strong>누가 제일 비슷하게 만들어졌는지</strong> 퍼센트로 판정해 드려요.
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
          <span className="de-tag">Eingabe</span>
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
            진단 시작 <span aria-hidden="true">→</span>
          </button>
        </div>
        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}
      </form>

      <div className="stage-pick">
        <p className="mini-title">스테이지 선택 <span className="de-tag">Stufe wählen</span></p>
        <div className="stage-list">
          {examples.map((ex, i) => (
            <button key={ex} type="button" className="btn btn-stage" onClick={() => onStart(ex)}>
              <span className="stage-no">STUFE {i + 1}</span>
              <span className="stage-word">{ex}</span>
            </button>
          ))}
        </div>
      </div>

      {demoMode && (
        <p className="note-bar">
          지금은 데모 모드예요. 분석 서비스가 꺼져 있어서 위 스테이지 단어만 진단돼요. <code>run.bat</code>으로 실행하면 아무 단어나 돼요.
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
            <p className="mini-title">내 도감 <span className="de-tag">Sammlung</span> · {collection.length}종 수집</p>
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
                    <span className="dex-mark" aria-hidden="true">
                      {g.mark}
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

      {/* 이전(심플 카드형) 디자인 페이지로 가는 링크. 루트 레이아웃이 달라서 일반 링크(전체 이동)로 연결한다 */}
      <p className="legacy-link">
        <a href="/old">이전 디자인으로 보기 →</a>
      </p>
    </section>
  );
}
