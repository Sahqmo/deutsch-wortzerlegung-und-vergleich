import type { Analysis, Decomposition, Morpheme, Origin, Role, TargetResult, AlignmentGroup, Lang } from "./schema";

// API 키가 없을 때 쓰는 미리 계산된 예시. (점수는 실제 경로와 똑같이 score.ts 가 계산한다.)

const m = (
  surface: string,
  lemma: string,
  gloss: string,
  role: Role,
  origin: Origin = "native",
): Morpheme => ({ surface, lemma, gloss, role, origin });

const dec = (
  word: string,
  kind: Decomposition["kind"],
  morphemes: Morpheme[],
  linking: string[] = [],
): Decomposition => ({ word, kind, morphemes, linking });

const g = (
  de: number[],
  target: number[],
  relation: AlignmentGroup["relation"],
  note: string,
): AlignmentGroup => ({ de, target, relation, note });

const t = (
  lang: Lang,
  decomposition: Decomposition,
  alignment: AlignmentGroup[],
  comment: string,
  confidence: TargetResult["confidence"] = "high",
): TargetResult => ({ lang, found: true, decomposition, alignment, confidence, comment });

const kugelschreiber: Analysis = {
  input: "Kugelschreiber",
  isGermanWord: true,
  de: dec("Kugelschreiber", "compound", [
    m("Kugel", "Kugel", "ball", "root"),
    m("schreib", "schreiben", "write", "root"),
    m("-er", "-er", "~하는 것(행위자·도구)", "suffix"),
  ]),
  targets: [
    t(
      "en",
      dec("ballpoint pen", "compound", [
        m("ball", "ball", "ball", "root"),
        m("point", "point", "tip", "root"),
        m("pen", "pen", "pen", "root"),
      ]),
      [
        g([0], [0], "same", "Kugel = ball"),
        g([1, 2], [2], "related", "schreiben(쓰다)과 pen은 어원이 무관하지만 '쓰는 도구'라는 뜻은 통함"),
        g([], [1], "added", "독일어에는 없는 point"),
      ],
      "공 + 끝이 들어간 3단 구조. 독일어보다 '펜촉' 설명이 하나 더 붙었어요.",
    ),
    t(
      "ko",
      dec("볼펜", "compound", [m("볼", "볼", "ball", "root", "loan"), m("펜", "펜", "pen", "root", "loan")]),
      [
        g([0], [0], "same", "Kugel = 볼(ball)"),
        g([1, 2], [1], "related", "schreiben과 펜은 어원이 무관하지만 '쓰는 도구'로 통함"),
      ],
      "조합 논리는 독일어와 똑같지만 둘 다 외래어라서 고유도는 낮아요.",
    ),
    t(
      "ja",
      dec("ボールペン", "compound", [m("ボール", "ボール", "ball", "root", "loan"), m("ペン", "ペン", "pen", "root", "loan")]),
      [
        g([0], [0], "same", "Kugel = ボール"),
        g([1, 2], [1], "related", "schreiben과 ペン은 어원이 무관하지만 '쓰는 도구'로 통함"),
      ],
      "한국어 볼펜과 같은 구조, 같은 외래어 사정이에요.",
    ),
  ],
};

const abfahrtszeit: Analysis = {
  input: "Abfahrtszeit",
  isGermanWord: true,
  de: dec(
    "Abfahrtszeit",
    "compound",
    [
      m("ab", "ab", "away / off", "prefix"),
      m("fahr", "fahren", "travel / ride", "root"),
      m("-t", "-t", "명사화 접미사", "suffix"),
      m("Zeit", "Zeit", "time", "root"),
    ],
    ["s"],
  ),
  targets: [
    t(
      "en",
      dec("departure time", "compound", [
        m("depart", "depart", "depart", "root"),
        m("-ure", "-ure", "명사화 접미사", "suffix"),
        m("time", "time", "time", "root"),
      ]),
      [g([0, 1, 2], [0, 1], "same", "Abfahrt = departure (둘 다 '출발'이라는 파생 명사)"), g([3], [2], "same", "Zeit = time")],
      "Abfahrt는 ab+fahren, departure는 depart+ure라 쪼개는 방식은 다르지만 뜻은 일대일이에요.",
    ),
    t(
      "ko",
      dec("출발 시간", "compound", [
        m("출", "出", "go out", "root", "sino"),
        m("발", "發", "leave", "root", "sino"),
        m("시", "時", "time", "root", "sino"),
        m("간", "間", "interval", "root", "sino"),
      ]),
      [g([0, 1, 2], [0, 1], "same", "Abfahrt = 출발(出發)"), g([3], [2, 3], "same", "Zeit = 시간(時間)")],
      "한자 단위로 보면 '나가-떠나' + '때-사이'. 독일어의 ab+fahr와도 닮았어요.",
    ),
    t(
      "ja",
      dec("出発時間", "compound", [
        m("出発", "出発", "departure", "root", "sino"),
        m("時間", "時間", "time", "root", "sino"),
      ]),
      [g([0, 1, 2], [0], "same", "Abfahrt = 出発"), g([3], [1], "same", "Zeit = 時間")],
      "한어(漢語) 단위로 보면 독일어와 2단 구조가 딱 맞아요.",
    ),
  ],
};

const krankenhaus: Analysis = {
  input: "Krankenhaus",
  isGermanWord: true,
  de: dec(
    "Krankenhaus",
    "compound",
    [m("Krank", "krank", "sick", "root"), m("Haus", "Haus", "house", "root")],
    ["en"],
  ),
  targets: [
    t(
      "en",
      dec("hospital", "simplex", [m("hospital", "hospital", "hospital", "root")]),
      [g([0, 1], [0], "related", "'아픈 + 집'이 한 단어 hospital로 합쳐짐")],
      "영어는 합성어가 아니라 라틴어에서 온 단일어예요. 뜻은 같지만 짜임은 전혀 달라요.",
    ),
    t(
      "ko",
      dec("병원", "compound", [m("병", "病", "illness", "root", "sino"), m("원", "院", "institution", "root", "sino")]),
      [g([0], [0], "same", "krank = 병(病)"), g([1], [1], "related", "Haus(집) ≈ 원(院, 건물·기관)")],
      "'병 + 원'으로 독일어와 같은 2단 구조예요. 한자어라 순우리말은 아니지만 짜임은 거의 판박이.",
    ),
    t(
      "ja",
      dec("病院", "compound", [m("病", "びょう", "illness", "root", "sino"), m("院", "いん", "institution", "root", "sino")]),
      [g([0], [0], "same", "krank = 病"), g([1], [1], "related", "Haus(집) ≈ 院(건물·기관)")],
      "한국어 병원과 완전히 같은 짜임이에요.",
    ),
  ],
};

const handschuh: Analysis = {
  input: "Handschuh",
  isGermanWord: true,
  de: dec("Handschuh", "compound", [m("Hand", "Hand", "hand", "root"), m("Schuh", "Schuh", "shoe", "root")]),
  targets: [
    t(
      "en",
      dec("glove", "simplex", [m("glove", "glove", "glove", "root")]),
      [g([0, 1], [0], "related", "'손 신발'이 한 단어 glove로 합쳐짐")],
      "영어는 합성어 감각이 없는 단일어예요.",
    ),
    t(
      "ko",
      dec("장갑", "simplex", [m("장갑", "장갑", "glove", "root", "unknown")]),
      [g([0, 1], [0], "related", "'손 신발'이 한 단어 장갑으로 합쳐짐")],
      "한자어 기원 설이 있지만 분해하지 않고 단일어로 봤어요.",
      "medium",
    ),
    t(
      "ja",
      dec("手袋", "compound", [m("手", "て", "hand", "root"), m("袋", "ふくろ", "bag", "root")]),
      [g([0], [0], "same", "Hand = 手"), g([1], [1], "related", "Schuh(신발) ≈ 袋(주머니): 손을 감싸는 물건이라는 발상은 같음")],
      "독일어는 '손 신발', 일본어는 '손 주머니'. 발상이 가장 비슷한 건 일본어예요.",
    ),
  ],
};

export const DEMO_ANALYSES: Analysis[] = [kugelschreiber, abfahrtszeit, krankenhaus, handschuh];

export const DEMO_WORDS = DEMO_ANALYSES.map((a) => a.input);

export function findDemo(word: string): Analysis | undefined {
  const key = word.trim().toLowerCase();
  return DEMO_ANALYSES.find((a) => a.input.toLowerCase() === key);
}
