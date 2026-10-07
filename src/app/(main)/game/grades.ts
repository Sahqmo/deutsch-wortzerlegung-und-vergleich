import { competitionRanks, tiedFlags } from "@/lib/rank";
import type { Lang, ScoreBreakdown } from "@/lib/schema";

export const LANG_LABEL: Record<Lang, string> = { en: "영어", ko: "한국어", ja: "일본어" };
export const LANG_CODE: Record<Lang, string> = { en: "EN", ko: "KO", ja: "JA" };

export const STATS: { key: "structure" | "meaning" | "origin"; label: string; hint: string }[] = [
  {
    key: "structure",
    label: "구조력",
    hint: "독일어와 같은 방식으로 쪼개지는 정도예요. 요소의 개수와 순서가 같을수록, 접미사(-er ↔ 사)까지 짝이 맞을수록 높아요.",
  },
  {
    key: "meaning",
    label: "의미력",
    hint: "쪼갠 요소끼리 뜻이 얼마나 짝지어지는지예요. 뜻이 같으면 1점, 비슷하면 절반, 한쪽에만 있는 요소는 0점으로 평균을 내요.",
  },
  {
    key: "origin",
    label: "토박이력",
    hint: "외래어를 빌리지 않고 그 언어 자체의 재료로 만든 말인지예요. 고유어는 높고, 한자어는 조금 낮고, 외래어(볼펜)는 많이 낮아요.",
  },
];

export type Tone = "gold" | "pink" | "mint" | "sky" | "lilac" | "gray";

export interface Grade {
  title: string;
  mark: string; // 등급 기호(이모지 대신 단정한 도형)
  de: string; // 독일어 부제
  tone: Tone;
  line: string;
}

export function gradeOf(total: number): Grade {
  if (total >= 90) return { title: "쌍둥이 단어", mark: "★", de: "Zwillingswörter", tone: "gold", line: "거의 복사해서 붙인 수준이에요." };
  if (total >= 75) return { title: "찰떡궁합", mark: "◆", de: "Volltreffer", tone: "pink", line: "짜임이 놀랄 만큼 잘 맞아요." };
  if (total >= 60) return { title: "꽤 닮은 사이", mark: "●", de: "Nahe Verwandte", tone: "mint", line: "닮은 구석이 확실히 있어요." };
  if (total >= 45) return { title: "썸 타는 사이", mark: "▲", de: "Entfernt verwandt", tone: "sky", line: "비슷한 듯 아닌 듯 애매해요." };
  if (total >= 30) return { title: "먼 사촌", mark: "■", de: "Weitläufige Cousins", tone: "lilac", line: "뿌리는 달라도 한두 군데는 통해요." };
  return { title: "생판 남", mark: "○", de: "Völlig fremd", tone: "gray", line: "발상 자체가 달라요." };
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

/**
 * 가장 유사한 언어부터. 대응어를 못 찾은 언어는 맨 뒤. 동점이면 en·ko·ja 순서 유지.
 * place 는 공동 순위(같은 퍼센트면 같은 순위, 1·1·3), tied 는 공동 순위 여부. 못 찾은 언어는 place 가 null.
 */
export function rank<T extends { lang: Lang; found: boolean }>(
  items: T[],
  scores: ScoreBreakdown[],
): (T & { score: ScoreBreakdown; place: number | null; tied: boolean })[] {
  const sorted = items
    .flatMap((t) => {
      const score = scores.find((s) => s.lang === t.lang);
      return score ? [{ ...t, score }] : [];
    })
    .sort((a, b) => Number(b.found) - Number(a.found) || b.score.total - a.score.total);
  const totals = sorted.filter((r) => r.found).map((r) => r.score.total);
  const places = competitionRanks(totals);
  const tied = tiedFlags(totals);
  let k = 0;
  return sorted.map((r) => (r.found ? { ...r, place: places[k], tied: tied[k++] } : { ...r, place: null, tied: false }));
}
