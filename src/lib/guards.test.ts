import { describe, expect, it } from "vitest";
import { DEMO_ANALYSES } from "./demo";
import { isUnsplittable, unsplittableMessage } from "./guards";
import type { Analysis } from "./schema";

const withParts = (n: number, isGermanWord = true): Analysis => {
  const base = structuredClone(DEMO_ANALYSES[0]);
  base.isGermanWord = isGermanWord;
  base.de.morphemes = base.de.morphemes.slice(0, n);
  return base;
};

describe("쪼갤 수 없는 단일 단어 판정", () => {
  it("형태소가 1개면 진단하지 않는다", () => {
    expect(isUnsplittable(withParts(1))).toBe(true);
  });
  it("2개 이상이면 진단한다", () => {
    expect(isUnsplittable(withParts(2))).toBe(false);
    expect(isUnsplittable(withParts(3))).toBe(false);
  });
  it("독일어 단어가 아닌 입력은 따로 처리하므로 여기서는 걸리지 않는다", () => {
    expect(isUnsplittable(withParts(0, false))).toBe(false);
  });
  it("안내 문구에 입력한 단어가 들어간다", () => {
    expect(unsplittableMessage("Zeitung")).toContain("Zeitung");
  });
  it("준비된 예시 단어는 모두 진단 가능하다", () => {
    expect(DEMO_ANALYSES.some(isUnsplittable)).toBe(false);
  });
});
