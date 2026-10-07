import { NextResponse } from "next/server";
import { DEMO_WORDS, findDemo } from "@/lib/demo";
import { isUnsplittable, unsplittableMessage } from "@/lib/guards";
import { analyzeWord, nlpAlive, NlpFailedError, NlpUnavailableError } from "@/lib/nlp-client";
import { scoreAnalysis } from "@/lib/score";
import { selectBestTargets } from "@/lib/select";
import type { Analysis, AnalyzeResponse } from "@/lib/schema";

export const runtime = "nodejs";
export const maxDuration = 120;

const WORD_RE = /^[A-Za-zÄÖÜäöüß-]{2,40}$/;

// 아주 단순한 IP별 호출 제한(메모리). 비공식 번역 엔드포인트가 막히지 않도록 보호한다.
// 개발 서버(npm run dev)에서는 꺼 둔다. 켜려면 RATE_LIMIT_PER_HOUR 를 지정하고, 배포(production)에서는 기본 60회.
const hits = new Map<string, number[]>();
function rateLimited(ip: string): boolean {
  const configured = process.env.RATE_LIMIT_PER_HOUR;
  if (configured === undefined && process.env.NODE_ENV !== "production") return false;
  const limit = Number(configured ?? 60);
  const now = Date.now();
  const recent = (hits.get(ip) ?? []).filter((t) => now - t < 3_600_000);
  const limited = recent.length >= limit;
  if (!limited) recent.push(now);
  hits.set(ip, recent);
  return limited;
}

const respond = (raw: Analysis, source: AnalyzeResponse["source"]) => {
  const analysis = selectBestTargets(raw); // 언어별 분석 후보 중 가장 잘 맞는 것을 고른다
  return NextResponse.json<AnalyzeResponse>({ analysis, scores: scoreAnalysis(analysis), source });
};

const fail = (message: string, status: number, extra: Record<string, unknown> = {}) =>
  NextResponse.json({ error: message, ...extra }, { status });

/** 화면이 분석 서비스 상태(데모 모드 여부)를 알 수 있게 한다. */
export async function GET() {
  return NextResponse.json({ demoMode: !(await nlpAlive()), demoWords: DEMO_WORDS });
}

export async function POST(req: Request) {
  let word = "";
  try {
    const body = (await req.json()) as { word?: unknown };
    word = typeof body.word === "string" ? body.word.trim().normalize("NFC") : "";
  } catch {
    return fail("요청 형식이 올바르지 않아요.", 400);
  }
  if (!WORD_RE.test(word)) {
    return fail("독일어 단어 하나만 입력해 주세요. (알파벳·ä ö ü ß, 2~40자)", 400);
  }

  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "local";
  if (rateLimited(ip)) return fail("잠시 후 다시 시도해 주세요. (시간당 호출 제한)", 429);

  try {
    const analysis = await analyzeWord(word);
    if (isUnsplittable(analysis)) return fail(unsplittableMessage(analysis.input), 422, { reason: "unsplittable" });
    return respond(analysis, "live");
  } catch (err) {
    if (err instanceof NlpUnavailableError) {
      // 분석 서비스가 꺼져 있으면 준비된 예시 단어만 보여 준다.
      const demo = findDemo(word);
      if (demo) return respond(demo, "demo");
      return fail(
        `분석 서비스(Python)가 꺼져 있어요. run.bat 으로 실행하면 아무 단어나 진단할 수 있어요. 지금은 예시 단어만 가능해요: ${DEMO_WORDS.join(", ")}`,
        503,
        { demoWords: DEMO_WORDS },
      );
    }
    if (err instanceof NlpFailedError) return fail(err.message, err.status === 502 ? 502 : 500);
    console.error(err);
    return fail("알 수 없는 오류가 났어요.", 500);
  }
}
