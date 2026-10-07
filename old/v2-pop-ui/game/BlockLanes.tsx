import type { Decomposition, Morpheme, ScoreBreakdown } from "@/lib/schema";
import { RELATION } from "./grades";

const ORIGIN_LABEL = { native: "토박이", sino: "한자어", loan: "외래어", calque: "번역차용", unknown: "불명" } as const;

function Block({ m }: { m: Morpheme }) {
  const affix = m.role !== "root";
  return (
    <span className={`blk${affix ? " blk-affix" : ""}`}>
      <span className="blk-main">{m.surface}</span>
      {m.lemma !== m.surface && <span className="blk-sub">{m.lemma}</span>}
      {m.gloss && <span className="blk-gloss">{m.gloss}</span>}
      {m.origin === "loan" && <span className="blk-tag">{ORIGIN_LABEL.loan}</span>}
      {m.origin === "sino" && <span className="blk-tag blk-tag-soft">{ORIGIN_LABEL.sino}</span>}
    </span>
  );
}

/** 정렬 그룹마다 한 줄기(lane): 위에 독일어 블록, 아래에 대응어 블록, 가운데에 관계 스티커. */
export function BlockLanes({ de, target, score }: { de: Decomposition; target: Decomposition; score: ScoreBreakdown }) {
  return (
    <div className="lanes" role="list" aria-label="요소 짝 맞추기">
      {score.groups.map((g, i) => {
        const rel = RELATION[g.relation];
        const top = g.de.map((idx) => de.morphemes[idx]).filter(Boolean);
        const bottom = g.target.map((idx) => target.morphemes[idx]).filter(Boolean);
        return (
          <div
            key={i}
            role="listitem"
            className={`lane lane-${g.relation}`}
            style={{ ["--lane" as string]: `var(--c${i % 6})`, animationDelay: `${i * 90}ms` }}
          >
            <div className="lane-row">
              {top.length ? top.map((m, k) => <Block key={k} m={m} />) : <span className="blk blk-empty">독일어엔 없음</span>}
            </div>
            <div className="lane-link" title={g.note}>
              <span className="lane-line" aria-hidden="true" />
              <span className="sticker" aria-label={rel.label}>
                {rel.sign} {rel.label}
              </span>
              <span className="lane-line" aria-hidden="true" />
            </div>
            <div className="lane-row">
              {bottom.length ? bottom.map((m, k) => <Block key={k} m={m} />) : <span className="blk blk-empty">대응 없음</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
