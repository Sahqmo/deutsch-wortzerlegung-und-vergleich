import type { Analysis, Decomposition, Morpheme, ScoreBreakdown, TargetResult } from "@/lib/schema";

const LANG_LABEL = { en: "영어", ko: "한국어", ja: "일본어" } as const;
const KIND_LABEL = { compound: "합성어", derived: "파생어", simplex: "단일어", phrase: "구(句)" } as const;
const ORIGIN_LABEL = { native: "고유", sino: "한자어", loan: "외래어", calque: "번역차용", unknown: "불명" } as const;
const RELATION_LABEL = { same: "뜻 같음", related: "뜻 연관", added: "추가됨", missing: "누락" } as const;

/** 그룹 번호 → 색 번호 (정렬된 그룹은 색을 공유, added/missing은 색 없음) */
function groupColors(score: ScoreBreakdown) {
  const de = new Map<number, number>();
  const target = new Map<number, number>();
  score.groups.forEach((g, gi) => {
    if (g.de.length === 0 || g.target.length === 0) return;
    g.de.forEach((i) => de.set(i, gi));
    g.target.forEach((i) => target.set(i, gi));
  });
  return { de, target };
}

function Chip({ m, group, lone }: { m: Morpheme; group?: number; lone?: boolean }) {
  const style = group === undefined ? undefined : ({ "--g": `var(--c${group % 6})` } as React.CSSProperties);
  return (
    <span className={`chip${lone ? " lone" : ""}${m.role === "suffix" || m.role === "prefix" ? " affix" : ""}`} style={style}>
      <span className="chip-main">{m.surface}</span>
      {m.lemma !== m.surface && <span className="chip-sub">{m.lemma}</span>}
      <span className="chip-gloss">{m.gloss}</span>
      <span className={`chip-origin o-${m.origin}`}>{ORIGIN_LABEL[m.origin]}</span>
    </span>
  );
}

function Row({
  label,
  d,
  colors,
  extra,
}: {
  label: string;
  d: Decomposition;
  colors: Map<number, number>;
  extra?: string;
}) {
  return (
    <div className="row">
      <div className="row-label">
        <span>{label}</span>
        <span className="row-word">{d.word}</span>
        <span className="row-kind">{KIND_LABEL[d.kind]}</span>
      </div>
      <div className="chips">
        {d.morphemes.length === 0 && <span className="muted">분해할 요소 없음</span>}
        {d.morphemes.map((m, i) => (
          <Chip key={i} m={m} group={colors.get(i)} lone={!colors.has(i)} />
        ))}
        {extra && <span className="linking">연결요소 -{extra}-</span>}
      </div>
    </div>
  );
}

function Bar({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <div className="bar" title={hint}>
      <div className="bar-head">
        <span>{label}</span>
        <span>{Math.round(value)}</span>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

export function ResultCard({
  de,
  target,
  score,
  rank,
  tied,
}: {
  de: Decomposition;
  target: TargetResult;
  score: ScoreBreakdown;
  rank?: number;
  tied?: boolean;
}) {
  const colors = groupColors(score);
  const tone = score.total >= 80 ? "high" : score.total >= 55 ? "mid" : "low";

  return (
    <article className="card">
      <header className="card-head">
        {rank !== undefined && <span className={`rank${rank === 1 ? " rank-top" : ""}`}>{tied ? "공동 " : ""}{rank}위</span>}
        <h3>{LANG_LABEL[target.lang]}</h3>
        {target.confidence !== "high" && (
          <span className="warn">자동 분석 추정 · 신뢰도 {target.confidence === "medium" ? "보통" : "낮음"}</span>
        )}
      </header>

      {!target.found ? (
        <p className="muted">적절한 대응어를 찾지 못했어요.</p>
      ) : (
        <>
          <div className="score-wrap">
            <div className={`score score-${tone}`}>
              <span className="score-num">{score.total}</span>
              <span className="score-pct">%</span>
            </div>
            <div className="bars">
              <Bar label="구조" value={score.structure} hint="요소 개수·순서가 독일어와 얼마나 같은가" />
              <Bar label="의미" value={score.meaning} hint="요소끼리 뜻이 얼마나 대응하는가" />
              <Bar label="고유도" value={score.origin} hint="외래어가 아니라 그 언어 자체의 조합으로 만들어졌는가" />
            </div>
          </div>

          <Row label="독일어" d={de} colors={colors.de} extra={de.linking.join("/") || undefined} />
          <Row label={LANG_LABEL[target.lang]} d={target.decomposition} colors={colors.target} />

          <ul className="notes">
            {score.groups.map((g, i) => {
              const aligned = g.de.length > 0 && g.target.length > 0;
              const style = aligned ? ({ "--g": `var(--c${i % 6})` } as React.CSSProperties) : undefined;
              return (
                <li key={i} style={style} className={aligned ? "" : "lone"}>
                  <span className={`rel rel-${g.relation}`}>{RELATION_LABEL[g.relation]}</span>
                  <span>{g.note}</span>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {(target.comment || score.structureNotes.length > 0) && (
        <p className="comment">
          {target.comment && <>💬 {target.comment}</>}
          {score.structureNotes.map((n, i) => (
            <span key={i} style={{ display: "block", marginTop: 6, fontSize: "0.9em", opacity: 0.85 }}>
              ▽ {n}
            </span>
          ))}
        </p>
      )}
    </article>
  );
}

export function Summary({ analysis, scores }: { analysis: Analysis; scores: ScoreBreakdown[] }) {
  const found = scores.filter((s) => s.found);
  const best = found.length ? found.reduce((a, b) => (b.total > a.total ? b : a)) : null;
  const tops = best ? found.filter((s) => s.total === best.total) : []; // 공동 1위면 여럿
  const top = best && analysis.targets.find((t) => t.lang === best.lang);
  return (
    <section className="summary">
      <h2>{analysis.de.word || analysis.input}</h2>
      <div className="parts">
        {analysis.de.morphemes.map((m, i) => (
          <span key={i} className="part">
            {m.lemma}
          </span>
        ))}
      </div>
      {top && best && (
        <p className="muted">
          가장 닮은 언어: <strong>{tops.map((s) => LANG_LABEL[s.lang]).join(" · ")}</strong>
          {tops.length > 1 ? " (공동 1위)" : ` (${top.decomposition.word})`} — {best.total}%
        </p>
      )}
    </section>
  );
}
