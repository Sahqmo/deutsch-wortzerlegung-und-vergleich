import type { Analysis } from "./schema";

/** 독일어 단어가 이 이상의 형태소로 쪼개져야 짜임을 비교할 수 있다. */
export const MIN_PARTS = 2;

/** 독일어 단어이지만 더 쪼갤 수 없어서 진단할 거리가 없는 경우 */
export function isUnsplittable(a: Analysis): boolean {
  return a.isGermanWord && a.de.morphemes.length < MIN_PARTS;
}

export const unsplittableMessage = (word: string) =>
  `‘${word}’은(는) 더 쪼갤 수 없는 단일 단어로 보여서 진단하지 않아요. 합성어나 파생어를 넣어 주세요. (분해기가 쪼개지 못한 합성어일 수도 있어요.)`;
