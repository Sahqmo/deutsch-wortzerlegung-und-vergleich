import type {
  AlignmentGroup,
  Analysis,
  Decomposition,
  Morpheme,
  Origin,
  ScoreBreakdown,
  TargetResult,
} from "./schema";

const ORIGIN_SCORE: Record<Origin, number> = {
  native: 1,
  calque: 1,
  sino: 0.9, // 한자어는 외래어(loan)와 달리 그 언어 안에서 조어력이 있는 일반 어휘라 거의 토박이로 본다
  unknown: 0.5,
  loan: 0.3,
};

const WEIGHTS = { structure: 0.4, meaning: 0.4, origin: 0.2 };
const RELATION_SCORE = { same: 1, related: 0.5, added: 0, missing: 0 } as const;

/** 짝지어진 파생 접미사(-er ↔ 사)가 있을 때 구조 점수에 얹는 가산점 최대치 */
const PARALLEL_SUFFIX_BONUS = 10;

const round = (n: number) => Math.round(n * 10) / 10;

/**
 * 구조 점수 계산용 "단위 수": 어근과 접두사만 센다(접미사는 파생 표지라 제외).
 * 비어 있지 않은데 단위가 0이면 1로 본다.
 */
function unitCount(morphemes: Morpheme[], indices: number[]): number {
  if (indices.length === 0) return 0;
  const n = indices.filter((i) => morphemes[i]?.role !== "suffix").length;
  return Math.max(n, 1);
}

/**
 * LLM이 만든 정렬을 정리한다: 범위를 벗어난 인덱스 제거, 중복 배정 제거,
 * 어느 그룹에도 안 들어간 요소는 missing(독일어 쪽) / added(대응어 쪽) 그룹으로 보충.
 */
export function normalizeAlignment(
  de: Decomposition,
  target: TargetResult,
): AlignmentGroup[] {
  const nDe = de.morphemes.length;
  const nT = target.decomposition.morphemes.length;
  const usedDe = new Set<number>();
  const usedT = new Set<number>();
  const groups: AlignmentGroup[] = [];

  for (const g of target.alignment) {
    const d = [...new Set(g.de)].filter((i) => i >= 0 && i < nDe && !usedDe.has(i));
    const t = [...new Set(g.target)].filter((i) => i >= 0 && i < nT && !usedT.has(i));
    if (d.length === 0 && t.length === 0) continue;
    d.forEach((i) => usedDe.add(i));
    t.forEach((i) => usedT.add(i));
    // 관계 표기가 실제 인덱스와 어긋나면 인덱스를 따른다.
    const relation =
      d.length === 0 ? "added" : t.length === 0 ? "missing" : g.relation === "added" || g.relation === "missing" ? "related" : g.relation;
    groups.push({ de: d, target: t, relation, note: g.note });
  }

  for (let i = 0; i < nDe; i++) {
    if (!usedDe.has(i)) {
      groups.push({ de: [i], target: [], relation: "missing", note: "대응어에 대응하는 요소가 없음" });
    }
  }
  for (let i = 0; i < nT; i++) {
    if (!usedT.has(i)) {
      groups.push({ de: [], target: [i], relation: "added", note: "독일어에는 없는 요소" });
    }
  }
  return groups;
}

/** 정렬된 그룹들이 독일어 순서를 유지하는 정도 (0~1). 쌍 단위 역전 비율. */
function orderScore(groups: AlignmentGroup[]): number {
  const aligned = groups
    .filter((g) => g.de.length > 0 && g.target.length > 0)
    .map((g) => ({ de: Math.min(...g.de), t: Math.min(...g.target) }))
    .sort((a, b) => a.de - b.de);
  if (aligned.length < 2) return 1;
  let pairs = 0;
  let inversions = 0;
  for (let i = 0; i < aligned.length; i++) {
    for (let j = i + 1; j < aligned.length; j++) {
      pairs++;
      if (aligned[i].t > aligned[j].t) inversions++;
    }
  }
  return 1 - inversions / pairs;
}

export function scoreTarget(de: Decomposition, target: TargetResult): ScoreBreakdown {
  const groups = normalizeAlignment(de, target);
  const empty: ScoreBreakdown = {
    lang: target.lang,
    found: target.found,
    structure: 0,
    meaning: 0,
    origin: 0,
    total: 0,
    groups,
  };
  if (!target.found || groups.length === 0) return empty;

  const tm = target.decomposition.morphemes;

  // 구조: 그룹별 단위 수 일치도(added/missing은 0)의 평균 70% + 순서 30%
  const countMatch =
    groups.reduce((sum, g) => {
      if (g.de.length === 0 || g.target.length === 0) return sum;
      const a = unitCount(de.morphemes, g.de);
      const b = unitCount(tm, g.target);
      return sum + Math.min(a, b) / Math.max(a, b);
    }, 0) / groups.length;
  // 파생 접미사의 평행성: 독일어 쪽에 접미사(-er)가 있는 정렬 그룹 중, 대응어 쪽에도 접미사(사)가 있는 비율만큼 가산.
  // (Pfleg+er ↔ 간호+사 는 Pfleg+er ↔ nurse 보다 짜임이 더 닮았다. 접미사가 없는 쪽에는 감점하지 않는다.)
  const hasSuffix = (ms: Morpheme[], idx: number[]) => idx.some((i) => ms[i]?.role === "suffix");
  const deSuffixGroups = groups.filter((g) => g.target.length > 0 && hasSuffix(de.morphemes, g.de));
  const parallel =
    deSuffixGroups.length === 0
      ? 0
      : deSuffixGroups.filter((g) => hasSuffix(tm, g.target)).length / deSuffixGroups.length;
  const structure = Math.min(
    100,
    100 * (0.7 * countMatch + 0.3 * orderScore(groups)) + PARALLEL_SUFFIX_BONUS * parallel,
  );

  // 의미: same 1, related 0.5, added/missing 0 의 평균
  const meaning =
    (100 * groups.reduce((sum, g) => sum + RELATION_SCORE[g.relation], 0)) / groups.length;

  // 고유도: 정렬된 대응어 요소들의 origin 평균
  const alignedT = new Set<number>();
  for (const g of groups) {
    if (g.de.length > 0) g.target.forEach((i) => alignedT.add(i));
  }
  const origin =
    alignedT.size === 0
      ? 0
      : (100 * [...alignedT].reduce((s, i) => s + ORIGIN_SCORE[tm[i].origin], 0)) / alignedT.size;

  const total =
    WEIGHTS.structure * structure + WEIGHTS.meaning * meaning + WEIGHTS.origin * origin;

  return {
    lang: target.lang,
    found: true,
    structure: round(structure),
    meaning: round(meaning),
    origin: round(origin),
    total: Math.round(total),
    groups,
  };
}

export function scoreAnalysis(analysis: Analysis): ScoreBreakdown[] {
  return analysis.targets.map((t) => scoreTarget(analysis.de, t));
}
