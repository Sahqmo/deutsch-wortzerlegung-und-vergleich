import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { AnalysisSchema, type Analysis } from "./schema";
import { selectBestTargets } from "./select";
import { scoreAnalysis } from "./score";

const load = (name: string): Analysis =>
  AnalysisSchema.parse(JSON.parse(readFileSync(`src/lib/__fixtures__/${name}.json`, "utf-8")));
const target = (a: Analysis, lang: string) => a.targets.find((t) => t.lang === lang)!;

describe("selectBestTargets", () => {
  it("Kühlschrank: 냉장 | 고 가 아니라 냉 | 장고 (Kühl = 냉, Schrank = 장고)를 고른다", () => {
    const a = selectBestTargets(load("kuhlschrank"));
    for (const lang of ["ko", "ja"]) {
      const t = target(a, lang);
      expect(t.selection?.isDefault).toBe(false);
      expect(t.selection?.label).toMatch(/^(냉 \| 장고|冷 \| 蔵庫)$/);
      expect(t.candidates).toBeUndefined(); // 선택 뒤에는 후보를 비운다
      expect(t.decomposition.morphemes.map((m) => m.surface)).toHaveLength(2);
    }
    // 선택된 분석의 점수가 기본 분석보다 크게 높다
    const scores = scoreAnalysis(a);
    const ko = scores.find((s) => s.lang === "ko")!;
    expect(ko.total).toBeGreaterThan(target(a, "ko").selection!.defaultTotal + 20);
  });

  it("기본 분석이 이미 잘 맞으면 그대로 둔다 (기본 우대)", () => {
    for (const name of ["krankenhaus", "waschmaschine", "abfahrtszeit"]) {
      const a = selectBestTargets(load(name));
      for (const t of a.targets) {
        if (t.selection) expect(t.selection.isDefault, `${name} ${t.lang}`).toBe(true);
      }
    }
  });

  it("Mehrheit: 쪼개지 않은 한 덩어리(다수·過半数)가 점수가 가장 높아도 고르지 않는다", () => {
    const raw = load("mehrheit");
    // 한 덩어리 후보가 기본 분석보다 점수가 높은 상황이 실제로 있었다 (이 테스트의 전제)
    const a = selectBestTargets(raw);
    for (const lang of ["ko", "ja"]) {
      const t = target(a, lang);
      const whole = t.selection!.options.find((o) => o.excluded);
      expect(whole, lang).toBeDefined();
      expect(whole!.total).toBeGreaterThan(t.selection!.defaultTotal);
      expect(t.selection!.isDefault, lang).toBe(true);
      expect(t.decomposition.morphemes.length, lang).toBeGreaterThan(1);
    }
  });

  it("후보가 없으면 selection 없이 그대로", () => {
    const a = selectBestTargets(load("kuhlschrank"));
    expect(target(a, "en").selection).toBeUndefined();
  });

  it("margin 이 크면 기본 분석을 유지한다", () => {
    const a = selectBestTargets(load("kuhlschrank"), 100);
    expect(target(a, "ko").selection?.isDefault).toBe(true);
  });
});
