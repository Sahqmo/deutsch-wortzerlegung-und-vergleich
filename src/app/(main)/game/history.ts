// 진단한 단어를 브라우저에 저장하는 "도감". 저장소를 못 쓰는 환경에서도 앱은 정상 동작해야 한다.

const KEY = "dkd-collection-v1";
const MAX = 40;

export interface Entry {
  word: string;
  lang: string; // 가장 닮은 언어 코드
  target: string; // 그 언어의 대응어
  total: number;
  at: number;
}

export function loadCollection(): Entry[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as Entry[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveEntry(entry: Entry): Entry[] {
  const list = loadCollection().filter((e) => e.word.toLowerCase() !== entry.word.toLowerCase());
  list.unshift(entry);
  const trimmed = list.slice(0, MAX);
  try {
    localStorage.setItem(KEY, JSON.stringify(trimmed));
  } catch {
    /* 저장 불가 환경은 무시 */
  }
  return trimmed;
}

export function clearCollection(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
