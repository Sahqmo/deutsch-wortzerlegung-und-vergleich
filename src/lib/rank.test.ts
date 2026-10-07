import { describe, expect, it } from "vitest";
import { competitionRanks, tiedFlags } from "./rank";

describe("competitionRanks", () => {
  it("같은 점수는 같은 순위, 다음 순위는 건너뛴다", () => {
    expect(competitionRanks([88, 88, 54])).toEqual([1, 1, 3]);
    expect(competitionRanks([90, 70, 70])).toEqual([1, 2, 2]);
    expect(competitionRanks([60, 60, 60])).toEqual([1, 1, 1]);
    expect(competitionRanks([90, 70, 50])).toEqual([1, 2, 3]);
  });
  it("입력 순서와 상관없이 점수로만 정한다", () => {
    expect(competitionRanks([54, 88, 88])).toEqual([3, 1, 1]);
    expect(competitionRanks([])).toEqual([]);
  });
  it("tiedFlags", () => {
    expect(tiedFlags([88, 88, 54])).toEqual([true, true, false]);
  });
});
