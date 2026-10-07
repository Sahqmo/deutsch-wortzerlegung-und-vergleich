import { scoreTarget } from "./score";
import type { Analysis, Selection, TargetResult } from "./schema";

/**
 * 기본 분석보다 이만큼(점) 높아야 다른 후보를 고른다.
 * 점수를 최대화하면 잘게 쪼개서 짝을 많이 만드는 쪽으로 쏠리기 쉬워서, 기본 분석(분해 정책)을 우대한다.
 */
export const DEFAULT_MARGIN = 3;

/**
 * 언어별로 분석 후보(기본 분석 + candidates)를 같은 점수 공식으로 채점하고 가장 잘 맞는 것을 고른다.
 * 단, 쪼개지 않은 한 덩어리 후보는 고르지 않는다(위 excluded).
 * 고른 후보가 target 자리를 대신하고(화면은 그대로 쓴다), 무엇을 골랐는지는 selection 에 남는다.
 */
export function selectBestTargets(analysis: Analysis, margin = DEFAULT_MARGIN): Analysis {
  const targets = analysis.targets.map((t): TargetResult => {
    const alts = t.candidates ?? [];
    const { candidates: _drop, selection: _s, ...base } = t;
    void _drop;
    void _s;
    if (!t.found || alts.length === 0) return base;

    const options = [base, ...alts];
    const totals = options.map((o) => scoreTarget(analysis.de, { ...o }).total);
    // 쪼개지 않은 한 덩어리(형태소 1개) 후보는 고르지 않는다. 독일어 요소 전체와 대응어 전체를 '같은 뜻' 한 그룹으로 묶으면
    // 단어 전체의 번역이 같다는 사실만으로 만점에 가까워서, 짜임을 비교한 점수가 아니기 때문이다 (Mehrheit ↔ 다수).
    const excluded = options.map((o, i) => i > 0 && analysis.de.morphemes.length > 1 && o.decomposition.morphemes.length <= 1);
    let best = 0;
    for (let i = 1; i < options.length; i++) {
      if (!excluded[i] && totals[i] > totals[best]) best = i;
    }
    if (best !== 0 && totals[best] < totals[0] + margin) best = 0;

    const labelOf = (o: { label?: string; decomposition: { word: string } }) => o.label ?? o.decomposition.word;
    const selection: Selection = {
      label: labelOf(options[best]),
      isDefault: best === 0,
      defaultLabel: labelOf(base),
      defaultTotal: totals[0],
      options: options.map((o, i) => ({ label: labelOf(o), total: totals[i], chosen: i === best, ...(excluded[i] ? { excluded: true } : {}) })),
    };
    const { candidates: _c, ...chosen } = options[best] as TargetResult;
    void _c;
    return { ...chosen, selection };
  });
  return { ...analysis, targets };
}
