import type { Lang, ScoreBreakdown } from "@/lib/schema";

export const LANG_LABEL: Record<Lang, string> = { en: "영어", ko: "한국어", ja: "일본어" };
export const LANG_CODE: Record<Lang, string> = { en: "EN", ko: "KO", ja: "JA" };

export const STATS: { key: "structure" | "meaning" | "origin"; label: string; hint: string }[] = [
  { key: "structure", label: "구조력", hint: "요소 개수와 순서가 독일어와 얼마나 같은가" },
  { key: "meaning", label: "의미력", hint: "요소끼리 뜻이 얼마나 짝지어지는가" },
  { key: "origin", label: "토박이력", hint: "외래어를 빌리지 않고 그 언어의 말로 만들었는가" },
];

export type Tone = "gold" | "pink" | "mint" | "sky" | "lilac" | "gray";

export interface Grade {
  title: string;
  emoji: string;
  tone: Tone;
  line: string;
}

export function gradeOf(total: number): Grade {
  if (total >= 90) return { title: "쌍둥이 단어", emoji: "👯", tone: "gold", line: "거의 복사해서 붙인 수준이에요." };
  if (total >= 75) return { title: "찰떡궁합", emoji: "💘", tone: "pink", line: "짜임이 놀랄 만큼 잘 맞아요." };
  if (total >= 60) return { title: "꽤 닮은 사이", emoji: "😎", tone: "mint", line: "닮은 구석이 확실히 있어요." };
  if (total >= 45) return { title: "썸 타는 사이", emoji: "🫣", tone: "sky", line: "비슷한 듯 아닌 듯 애매해요." };
  if (total >= 30) return { title: "먼 사촌", emoji: "🧐", tone: "lilac", line: "뿌리는 달라도 한두 군데는 통해요." };
  return { title: "생판 남", emoji: "🧊", tone: "gray", line: "발상 자체가 달라요." };
}

export const RELATION: Record<string, { sign: string; label: string }> = {
  same: { sign: "=", label: "같음" },
  related: { sign: "≈", label: "비슷" },
  added: { sign: "+", label: "추가" },
  missing: { sign: "−", label: "없음" },
};

export interface Ranked {
  lang: Lang;
  found: boolean;
  total: number;
  score: ScoreBreakdown;
}

/** 가장 유사한 언어부터. 대응어를 못 찾은 언어는 맨 뒤. 동점이면 en·ko·ja 순서 유지. */
export function rank<T extends { lang: Lang; found: boolean }>(items: T[], scores: ScoreBreakdown[]): (T & { score: ScoreBreakdown })[] {
  return items
    .flatMap((t) => {
      const score = scores.find((s) => s.lang === t.lang);
      return score ? [{ ...t, score }] : [];
    })
    .sort((a, b) => Number(b.found) - Number(a.found) || b.score.total - a.score.total);
}
