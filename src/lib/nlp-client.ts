import { AnalysisSchema, type Analysis } from "./schema";

const NLP_URL = process.env.NLP_URL ?? "http://127.0.0.1:8000";

export class NlpUnavailableError extends Error {}
export class NlpFailedError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

/** Python 분석 서비스가 떠 있는지 */
export async function nlpAlive(): Promise<boolean> {
  try {
    const res = await fetch(`${NLP_URL}/health`, { signal: AbortSignal.timeout(1500), cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function analyzeWord(word: string): Promise<Analysis> {
  let res: Response;
  try {
    res = await fetch(`${NLP_URL}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ word }),
      signal: AbortSignal.timeout(90_000),
      cache: "no-store",
    });
  } catch {
    throw new NlpUnavailableError("분석 서비스에 연결하지 못했어요.");
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new NlpFailedError(body?.detail ?? "분석 중 오류가 났어요.", res.status);
  }
  const parsed = AnalysisSchema.safeParse(await res.json());
  if (!parsed.success) {
    console.error("NLP response failed validation", parsed.error.issues.slice(0, 3));
    throw new NlpFailedError("분석 결과 형식이 올바르지 않아요.", 502);
  }
  return parsed.data;
}
