/**
 * 공동 순위(1, 1, 3 방식): 같은 점수는 같은 순위를 받고, 다음 순위는 그만큼 건너뛴다.
 * 점수는 화면에 보이는 퍼센트(정수)를 그대로 비교한다.
 */
export function competitionRanks(totals: number[]): number[] {
  return totals.map((t) => 1 + totals.filter((o) => o > t).length);
}

/** 같은 점수가 둘 이상인가 (공동 순위 표시용) */
export function tiedFlags(totals: number[]): boolean[] {
  return totals.map((t) => totals.filter((o) => o === t).length > 1);
}
