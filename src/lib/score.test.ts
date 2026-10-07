import { describe, expect, it } from "vitest";
import { DEMO_ANALYSES, findDemo } from "./demo";
import { normalizeAlignment, scoreAnalysis, scoreTarget } from "./score";
import { AnalysisSchema } from "./schema";

const kugel = findDemo("Kugelschreiber")!;
const byLang = (a = kugel) => Object.fromEntries(scoreAnalysis(a).map((s) => [s.lang, s]));

describe("scoring (설계.md 검산 예시)", () => {
  it("Kugelschreiber ↔ 볼펜 = 76% (구조는 같지만 외래어)", () => {
    const ko = byLang().ko;
    expect(ko.structure).toBe(100);
    expect(ko.meaning).toBe(75);
    expect(ko.origin).toBe(30);
    expect(ko.total).toBe(76);
  });

  it("Kugelschreiber ↔ ballpoint pen = 71% (point 가 추가됨)", () => {
    const en = byLang().en;
    expect(en.structure).toBeCloseTo(76.7, 1);
    expect(en.meaning).toBe(50);
    expect(en.origin).toBe(100);
    expect(en.total).toBe(71);
  });

  it("볼펜이 ballpoint pen 보다 높다", () => {
    const s = byLang();
    expect(s.ko.total).toBeGreaterThan(s.en.total);
  });
});

describe("robustness", () => {
  it("모든 데모 데이터가 스키마를 통과하고 점수가 0~100 범위", () => {
    for (const a of DEMO_ANALYSES) {
      expect(AnalysisSchema.safeParse(a).success).toBe(true);
      for (const s of scoreAnalysis(a)) {
        expect(s.total).toBeGreaterThanOrEqual(0);
        expect(s.total).toBeLessThanOrEqual(100);
      }
    }
  });

  it("정렬에서 빠진 요소는 missing/added 로 채워진다", () => {
    const ko = structuredClone(kugel.targets[1]);
    ko.alignment = [{ de: [0], target: [0], relation: "same", note: "" }];
    const groups = normalizeAlignment(kugel.de, ko);
    expect(groups.filter((g) => g.relation === "missing")).toHaveLength(2);
    expect(groups.filter((g) => g.relation === "added")).toHaveLength(1);
  });

  it("범위를 벗어난 인덱스와 중복 배정은 무시된다", () => {
    const ko = structuredClone(kugel.targets[1]);
    ko.alignment = [
      { de: [0, 99], target: [0], relation: "same", note: "" },
      { de: [0], target: [1], relation: "same", note: "중복" },
      { de: [1, 2], target: [1], relation: "related", note: "" },
    ];
    const groups = normalizeAlignment(kugel.de, ko);
    expect(groups[0].de).toEqual([0]);
    // 두 번째 그룹은 de 가 이미 쓰였으므로 target 만 남아 added 로 바뀌었다가, target 1 은 세 번째 그룹과 충돌
    expect(groups.every((g) => g.de.every((i) => i < 3))).toBe(true);
  });

  it("대응어가 없으면 0점", () => {
    const ko = structuredClone(kugel.targets[1]);
    ko.found = false;
    expect(scoreTarget(kugel.de, ko).total).toBe(0);
  });

  it("순서가 뒤집히면 구조 점수가 깎인다", () => {
    const ko = structuredClone(kugel.targets[1]);
    ko.alignment = [
      { de: [0], target: [1], relation: "same", note: "" },
      { de: [1, 2], target: [0], relation: "related", note: "" },
    ];
    expect(scoreTarget(kugel.de, ko).structure).toBeLessThan(100);
  });
});

describe("파생 접미사 평행성 · 한자어 토박이력", () => {
  // Krankenpfleger ↔ 간호사 / nurse (krank 는 대응 없음, Pfleg+er 는 대응어 전체와 짝)
  const de = {
    word: "Krankenpfleger",
    kind: "compound" as const,
    morphemes: [
      { surface: "krank", lemma: "krank", gloss: "아픈", role: "root" as const, origin: "native" as const },
      { surface: "Pfleg", lemma: "pflegen", gloss: "돌보다", role: "root" as const, origin: "native" as const },
      { surface: "-er", lemma: "-er", gloss: "~하는 사람", role: "suffix" as const, origin: "native" as const },
    ],
    linking: ["en"],
  };
  const mk = (lang: "en" | "ko", morphemes: { surface: string; role: "root" | "suffix"; origin: "native" | "sino" }[]) => ({
    lang,
    found: true,
    confidence: "high" as const,
    comment: "",
    decomposition: {
      word: morphemes.map((m) => m.surface).join(""),
      kind: "derived" as const,
      linking: [],
      morphemes: morphemes.map((m) => ({ ...m, lemma: m.surface, gloss: "" })),
    },
    alignment: [
      { de: [0], target: [], relation: "missing" as const, note: "" },
      { de: [1, 2], target: morphemes.map((_, i) => i), relation: "same" as const, note: "" },
    ],
  });
  const en = mk("en", [{ surface: "nurse", role: "root", origin: "native" }]);
  const ko = mk("ko", [
    { surface: "간호", role: "root", origin: "sino" },
    { surface: "사", role: "suffix", origin: "sino" },
  ]);

  it("-er 에 대응어도 접미사(사)가 짝지어지면 구조 점수가 더 높다", () => {
    const sEn = scoreTarget(de, en);
    const sKo = scoreTarget(de, ko);
    expect(sKo.structure).toBeGreaterThan(sEn.structure);
    expect(sKo.structure - sEn.structure).toBeCloseTo(10, 1);
  });

  it("대응어에 접미사가 없다고 감점하지는 않는다", () => {
    const noSuffixDe = { ...de, morphemes: de.morphemes.slice(0, 2) };
    const a = scoreTarget(noSuffixDe, { ...en, alignment: [{ de: [0], target: [], relation: "missing" as const, note: "" }, { de: [1], target: [0], relation: "same" as const, note: "" }] });
    expect(a.structure).toBeCloseTo(65, 0);
  });

  it("가산 후에도 구조 점수는 100을 넘지 않는다", () => {
    const perfect = scoreTarget(
      { ...de, morphemes: de.morphemes.slice(1) },
      { ...ko, alignment: [{ de: [0, 1], target: [0, 1], relation: "same" as const, note: "" }] },
    );
    expect(perfect.structure).toBe(100);
  });

  it("한자어(sino)는 토박이력 0.9, 외래어는 0.3", () => {
    expect(scoreTarget(de, ko).origin).toBe(90);
  });

  it("한국어 간호사가 영어 nurse 보다 높게 나온다", () => {
    expect(scoreTarget(de, ko).total).toBeGreaterThan(scoreTarget(de, en).total);
  });
});
