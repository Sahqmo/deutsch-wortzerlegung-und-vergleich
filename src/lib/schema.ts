import { z } from "zod";

export const ORIGINS = ["native", "sino", "loan", "calque", "unknown"] as const;
export const LANGS = ["en", "ko", "ja"] as const;

export const MorphemeSchema = z.object({
  surface: z.string().describe("표면형. 예: schreib, 볼, 出発"),
  lemma: z
    .string()
    .describe("기본형(사전형). 독일어 동사 어근은 부정형으로 복원. 예: schreib → schreiben. 한자어는 한자 표기. 접사는 -er 처럼 하이픈 표기"),
  gloss: z.string().describe("짧은 뜻풀이. 영어(ball, write). 문법 접미사 표지(명사화 등)는 한국어"),
  role: z.enum(["root", "prefix", "suffix"]),
  origin: z
    .enum(ORIGINS)
    .describe(
      "native=그 언어의 고유 어휘이거나 완전히 동화된 어휘(영어의 depart, pen 포함), sino=한국어·일본어 한자어, loan=지금도 외래어로 인식되는 차용어(한국어 외래어, 일본어 가타카나어), calque=번역 차용, unknown=불확실",
    ),
});

export const DecompositionSchema = z.object({
  word: z.string().describe("분해 대상 전체 단어 또는 구"),
  kind: z.enum(["compound", "derived", "simplex", "phrase"]),
  morphemes: z.array(MorphemeSchema),
  linking: z.array(z.string()).describe("독일어 연결요소(예: s, n, en, es). 없으면 빈 배열. 다른 언어는 항상 빈 배열"),
});

export const AlignmentGroupSchema = z.object({
  de: z.array(z.number().int()).describe("독일어 morphemes 인덱스. 대응어에만 있는 요소(added)면 빈 배열"),
  target: z.array(z.number().int()).describe("대응어 morphemes 인덱스. 독일어에만 있는 요소(missing)면 빈 배열"),
  relation: z.enum(["same", "related", "added", "missing"]),
  note: z.string().describe("한국어 한 줄 설명"),
});

const TargetBaseSchema = z.object({
  lang: z.enum(LANGS),
  found: z.boolean().describe("대응어가 하나라도 적절히 존재하는가"),
  label: z.string().optional().describe("이 분석의 경계 표기. 예: 냉 | 장고"),
  decomposition: DecompositionSchema,
  alignment: z.array(AlignmentGroupSchema),
  confidence: z.enum(["high", "medium", "low"]),
  comment: z.string().describe("재미 요소가 되는 한국어 한두 문장 코멘트"),
});

/** 여러 후보 분석 중 무엇이 선택됐는지 (선택은 점수 공식이 있는 select.ts 가 한다) */
export const SelectionSchema = z.object({
  label: z.string().describe("선택된 분석의 경계 표기"),
  isDefault: z.boolean().describe("기본 분석이 그대로 선택됐는가"),
  defaultLabel: z.string(),
  defaultTotal: z.number().describe("기본 분석의 총점"),
  options: z.array(
    z.object({
      label: z.string(),
      total: z.number(),
      chosen: z.boolean(),
      excluded: z.boolean().optional().describe("쪼개지 않은 한 덩어리라서 선택에서 제외된 후보"),
    }),
  ),
});

export const TargetResultSchema = TargetBaseSchema.extend({
  /** 분석 서비스가 만든 다른 분석 후보(한자어의 경계 조합 등). 선택 뒤에는 비워진다 */
  candidates: z.array(TargetBaseSchema).optional(),
  selection: SelectionSchema.optional(),
});

export const AnalysisSchema = z.object({
  input: z.string(),
  isGermanWord: z.boolean().describe("입력이 실제 독일어 단어(또는 그럴듯한 합성어)인가"),
  de: DecompositionSchema,
  targets: z.array(TargetResultSchema).describe("en, ko, ja 순서로 정확히 3개"),
});

export type Morpheme = z.infer<typeof MorphemeSchema>;
export type Decomposition = z.infer<typeof DecompositionSchema>;
export type AlignmentGroup = z.infer<typeof AlignmentGroupSchema>;
export type TargetResult = z.infer<typeof TargetResultSchema>;
export type TargetBase = z.infer<typeof TargetBaseSchema>;
export type Selection = z.infer<typeof SelectionSchema>;
export type Analysis = z.infer<typeof AnalysisSchema>;
export type Lang = (typeof LANGS)[number];
export type Origin = (typeof ORIGINS)[number];
export type Role = Morpheme["role"];

export interface ScoreBreakdown {
  lang: Lang;
  found: boolean;
  structure: number;
  meaning: number;
  origin: number;
  total: number;
  /** 누락된 요소를 added/missing 으로 채워 넣은, 실제 점수 계산에 쓰인 정렬 */
  groups: AlignmentGroup[];
  /** 구조 점수를 조정한 이유 (예: 파츠 수가 달라서 조금 깎음). 조정이 없으면 빈 배열 */
  structureNotes: string[];
}

export interface AnalyzeResponse {
  analysis: Analysis;
  scores: ScoreBreakdown[];
  source: "demo" | "live";
}
