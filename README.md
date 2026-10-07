# 독일어 합성어 상성 진단소

독일어 합성어를 분해하고 영어/한국어/일본어 대응어와 짜임 유사도를 퍼센트로 보여주는 웹앱. LLM·API 키 없이 동작한다. 설계 배경과 점수 공식은 `설계.md`.

## 실행

`run.bat` 더블클릭 (처음엔 npm/pip 설치로 몇 분). 웹(3000번)과 분석 서비스(8000번)가 같이 뜨고, 코드를 고치면 둘 다 자동으로 다시 불러온다. 둘 중 하나가 죽으면 3초 뒤 다시 시작한다.

```bash
npm test                                              # 점수 계산 테스트 (TS)
cd nlp && .venv\Scripts\python -m unittest test_nlp   # 분해·정렬 테스트 (Python)
```

- 분석 서비스가 꺼져 있으면 화면이 데모 모드(Kugelschreiber / Abfahrtszeit / Krankenhaus / Handschuh)로 동작한다.
- Python 테스트 중 일부는 번역기 결과(`nlp/translations.sqlite`)를 쓴다. 캐시가 있으면 오프라인으로도 통과한다.
- 환경변수는 선택 사항이다(`.env.example`): `NLP_URL`(분석 서비스 주소), `RATE_LIMIT_PER_HOUR`(호출 제한, 배포에서만 기본 적용).

## 파이프라인

```
독일어 단어 ─ HanTa / CharSplit / wordfreq ─▶ 독일어 요소 분해 (lemma, 연결요소, 접사)
     │
     └ 번역기 ─▶ 영어·한국어·일본어 대응어
                    ├ 영어: wordfreq 로 붙여 쓴 합성어·접미사·라틴계 접두사 분리
                    ├ 한국어: 번역 후보의 한자와 음이 맞으면 한자어(hanja 표), 가타카나와 발음 뼈대가 맞으면 외래어 (Kiwi)
                    └ 일본어: fugashi + UniDic 으로 분절, 어종(和/漢/外) → 고유도
          ─▶ 요소 정렬: 번역기의 직접 번역·역번역·영어 피벗 후보 비교 (+ 자리 기준 추정)
          ─▶ 점수 계산 (src/lib/score.ts): 구조 40 · 의미 40 · 고유도 20
```

| 위치 | 역할 |
|---|---|
| `nlp/translator.py` | 번역기 어댑터(`Translator` 프로토콜) + SQLite 캐시. 기본은 키 없는 비공식 Google 엔드포인트 |
| `nlp/german.py`, `nlp/targets.py` | 언어별 분해 |
| `nlp/align.py`, `nlp/pipeline.py` | 정렬, 뜻풀이 선택, 결과 JSON 조립 |
| `nlp/server.py` | FastAPI (`POST /analyze`) |
| `src/lib/nlp-client.ts`, `src/app/api/analyze/route.ts` | 웹 → 분석 서비스 연결, 입력 검증, 호출 제한 |
| `src/lib/score.ts`, `schema.ts` | 점수 공식, zod 스키마 |
| `src/app/(main)/` | 게임형 화면 (`page.tsx`, `game/`, `globals.css`, `layout.tsx`). 아래 참고 |
| `src/app/(legacy)/` | 이전 심플 카드형 디자인을 `/old` 주소로 되살린 것 (`layout.tsx`, `old.css`, `old/page.tsx`, `old/ResultCard.tsx`). 기능은 같고 외형만 다름 |
| `old/` | 이전 UI 백업 2종(심플 카드형, 게임형 팝 디자인) 원본 파일. 심플 카드형은 `/old` 로도 볼 수 있다. 복원 방법은 `old/README.md` |

## 분해 깊이 정책 (언어끼리 같은 깊이로 비교)
- **여러 단어가 이어진 한자어는 글자가 아니라 '단어' 단위가 형태소다.** 한국어 `진공청소기` → 진공 | 청소 | 기, 일본어 `真空清掃機` → 真空 | 清掃 | 機. 한자 한 글자씩 쪼개면 `세탁`(洗濯)이 독일어 `wasch` 하나와 짝지어질 때 2:1로 어긋나 유사도가 낮아진다. **단, 번역 결과 전체가 띄어쓰기 없는 한 단어이고 2~3글자면 한자 한 글자씩 나눈다**(한국어 `병원` → 병 | 원, 띄어 쓴 `출발 시간`은 출발 | 시간). 일본어도 같은 규칙이다(`病院` → 病 | 院, 和語 `今日`는 그대로). 용언화·형용사화 어미(`-한`, `-な`)가 붙어도 어근이 2~3글자 한자어면 같다(`불쾌한` → 불 | 쾌+한, `不快な` → 不 | 快+な). 한자 접미사(`-적`·`的`, `庫`)가 붙으면 단어 단위 그대로다. 단 한국어 한자어의 단어 경계를 얻을 때(`_sino_units`)는 이 분리를 끈다.
- 단어 경계는 번역으로 얻은 한자 표기(真空清掃機)를 일본어 분석기(UniDic)로 끊어서 얻고, 한자 한 글자 = 한글 한 음절로 한국어에 옮긴다. 그래서 같은 단어를 한국어·일본어가 같은 구조로 본다. 번역기 조회도 한자(真空) 표기로 해서 신호가 더 정확하다.
- 띄어쓰기 덩어리 통째로 한자어 매칭을 먼저 시도해서 Kiwi 가 끊어 버리는 말(`대학교`의 `대`)을 살린다. 일본 신자체가 다른 옛 글자와 겹치는 경우(証=정 ≠ 證=증)는 옛 글자의 음도 확인한다.
- 한자 접미사(庫·館·機)는 UniDic 접미사로 분류되면 앞 단어에 붙은 접미사 형태소로 두고, 구조 점수의 개수 비교에서는 뺀다.
- 和語 합성어(手袋)는 읽기가 부분 읽기의 이어 붙임(연탁 허용)과 같을 때만 쪼갠다(今日=きょう 는 今+日 이 아님).
- **독일어 접사 표(`nlp/german.py`):** 분리할 수 있다고 여기는 접사를 데이터로 두고(`STRONG_PREFIXES` be·ge·er·ver·zer·ent·un·miss·ur …, `WEAK_PREFIXES` 전치사·분리 접두사, `SUFFIX_DATA` -ung·-heit·-keit·-schaft·-lich·-bar·-los·-sam·-haft·-ig·-isch·-ler·-in·-er … 와 어간 종류 v/n/vn), 접사를 뗀 나머지가 실제 단어(동사 부정형이나 명사·형용사)일 때만 쪼갠다. 접미사를 안쪽으로 벗기고(`Lehrerin` = Lehr + -er + -in) 남은 어간에서 접두사를 겹쳐 벗긴다(`unverbindlich` = un + ver + bind + -lich). 합성어 분해가 따로 떼어낸 접두사(`Ver|Gleich`)는 뒤 요소에 접두사로 붙인다. 강한 접두사는 합성어보다 빈도가 높은 말도 쪼개고(verbinden = ver + binden), 약한 접두사는 전체가 훨씬 흔하면 쪼개지 않는다. 우연한 일치는 `LEXICALIZED` 목록으로 막는다(`Nachbar`, `Verein`, `Mutter` …).
- **독일어 파생(접두사·접미사):** 접미사를 떼고 어간을 복원할 때 그대로 · +e(`Gesell` → Geselle) · 움라우트 풀기(`gefähr` → Gefahr)를 시도한다. `-schaft`·`-heit`·`-keit`·`-lich`·`-nis`는 구별력이 높아서 어간 빈도 문턱을 낮췄다(`Gesellschaft` = Geselle + -schaft). `-lich`·`-schaft` 같은 접미사는 합성어의 뒷 요소로 떼지 않는다(`ungefährlich` = un + gefähr + -lich).
- **형용사 어미를 접미사 형태소로:** 영어 `-less/-ful/-able/-ous/-ish/-ive/-ic/-ize`(`harm+less`), 한국어 용언화·형용사화 어미(`무해+한`, `부정+적`), 일본어 `な`·`に`(`無害+な`)를 접미사로 둔다. 독일어 `-lich` 와 짝지어져 파생 접미사 평행성 가산점을 받는다.
- **영어 접미사 어간 복원:** 접미사를 떼고 원래 단어를 되살린다(`import+ance`, `clos(e)+ure`, `entr+ance` → enter, `centr+al` → center). 모음 뒤의 r 은 건드리지 않는다(`general`).
- **영어 라틴계 접두사:** `de-part-ure` 처럼 접두사+어근+접미사로 쪼개 독일어 ab-fahr-t 와 깊이를 맞춘다. 남는 부분이 흔한 영단어이고 전체는 굳어진 흔한 단어(report, detail…)가 아닐 때만 쪼갠다.
- **영어 라틴·그리스계 어근 표:** `nlp/targets.py` 의 `LATIN_PREFIXES`(접두사, 자음 앞에서 바뀐 모양 ac-/ap-/col-/im- … 포함), `BOUND_ROOTS`(자유 단어가 아닌 결합형 어근: pare, scribe, ceive, dict …), `EN_STEM_ALT`(어간 변형 script→scribe)에 모아 둔다. `comparison` → com + par + -ison, `description` → de + script + -ion. `-ion`·`-ison`·`-ent`·`-ant` 는 뗀 어간이 접두사+어근 구조일 때만 접미사로 인정해서 `million`·`student` 같은 말은 그대로 둔다. 짧거나 모양이 바뀐 접두사(in-, im-, ap- …)는 어근이 결합형일 때만 써서 `import` 같은 말을 쪼개지 않는다.

## 독일어 분해 사전 (선택)
합성어 경계는 규칙(CharSplit·빈도)만으로는 드문 말에서 자주 놓친다(정답 표의 어려운 집합에서 약 28%만 맞고 70%는 통째로 남았다). 그래서 **독일어 Wiktionary 어원**에서 만든 사전을 규칙보다 먼저 조회한다. 사전에 없는 말(신조어 등)과 사전 파일이 없는 환경은 지금까지의 규칙으로 처리한다.

```bash
cd nlp
.venv\Scripts\pip install -r requirements-lexicon.txt    # 사전을 만들 때만 필요 (pyarrow)
.venv\Scripts\python build_lexicon.py                     # 원본(약 88MB)을 nlp/data/ 에 받고 nlp/lexicon.sqlite 를 만든다
```

- 원본은 Hugging Face `yuanxin112/wiktionary-morph`(de, kaikki.org/wiktextract 기반)의 `etymology_text`다. "Determinativkompositum aus den Substantiven Bund und Anwaltschaft sowie dem Fugenelement -es" 같은 문장을 파싱해 구성요소·연결요소를 뽑고(`parse_etymology`), 입력 단어의 표면 조각에 맞춘다(`align`: Grenzkosten → Grenz|Kosten, Gänsefeder → Gäns|Feder). 합성어 4.1만 개 중 약 3.8만 개(91%)가 사전에 들어간다.
- 사전의 분해는 한 단계라서, 조각을 다시 조회해 더 쪼갠다(`german._split_by_lexicon`). 접두사·접미사는 `SUFFIX_DATA` 접사 표가 계속 맡는다.
- **라이선스:** 원본이 CC-BY-SA-4.0 이라 `lexicon.sqlite` 도 같은 조건(출처 표기 + 동일 조건 공유)을 이어받는다. 저장소에는 넣지 않는다(`.gitignore`). **공개 배포 전에 라이선스를 다시 확인할 것.**
- 한계: Wiktionary 에 실린 말만 풀린다. 정답 표 단어 중 사전에 있는 비율은 쉬운 집합 41%, 어려운 집합 23% 였다(사전에 있으면 99% 일치하지만, 정답 표가 같은 출처라 정확도의 증거는 아니다).

## 쪼갤 수 없는 단어는 진단하지 않는다
독일어 단어가 형태소 1개(`Zeitung`, `Bibliothek`, `Finger` …)로 판정되면 비교할 짜임이 없어서 어느 언어든 100% 근처가 나온다. 그래서 `nlp/pipeline.py`가 번역기를 부르기 전에 멈추고, `/api/analyze`가 422와 안내 문구(`src/lib/guards.ts`)를 돌려주고, 화면은 로딩 연출을 기다리지 않고 바로 메인으로 돌아와 문구를 보여준다(이전 디자인 `/old`에서는 같은 문구가 그 페이지에 뜬다). 파생어라도 어간+접미사로 쪼개지면(`Gesundheit`) 진단한다. 어휘화된 말(`Zeitung`, `Verein`)과 분해기가 놓친 합성어는 단일 단어로 판정되니, 문구에도 그 가능성을 적어 두었다.

## 정렬 보정과 뜻풀이 선택
- **위치 기반 추정은 자리가 같을 때만.** 번역기 신호로 짝이 안 지어진 요소는, 핵심어(마지막 요소)는 핵심어끼리, 수식어는 수식어끼리만 묶는다. 수식어 `Staub`가 핵심어 자리의 `기`(機)와 짝지어지는 엉뚱한 대응을 막고, 짝이 없으면 '없음/추가'로 남긴다.
- 독일어가 한 단어인데 대응어가 여러 요소면 뜻은 같음으로 본다(짜임 차이는 구조 점수가 반영).
- **뜻풀이는 영어로 둔다.** 번역기를 한 번 더 거쳐 한국어로 옮기면 `Ein → 'A' → 라`, `Gang → 'course' → 강의` 같은 엉뚱한 뜻이 나온다. 영어 뜻을 그대로 보여주고, 문법 기능을 나타내는 접미사 표지(명사화·축소 등)만 한국어로 둔다. 영어 대응어의 형태소는 그 자체가 영어라 뜻풀이를 비운다.
- **독일어 요소의 영어 뜻은 증거로 고른다.** 번역기에 단어 하나만 물으면 `Kugel → bullet`처럼 드문 뜻부터 나온다. ① 전치사·불변화사(`ein`, `aus`, `um`, `vor` …)는 `nlp/pipeline.py`의 `PARTICLE_GLOSS` 표에서 가져오고, ② 세 언어 정렬에서 대응어와 영어 번역 후보가 겹친 뜻(ball)을 우선하고, ③ 증거가 없으면 영어에서 더 흔한 뜻을 고른다. 후보는 **그 요소의 품사와 같은 번역기 사전 항목**만 쓴다(HanTa 로 독일어 품사를 판정, 번역기 응답의 품사별 묶음 사용). 문장 번역 결과가 섞여 드는 `Ein → A` 같은 잡음이 빠지고, 사전이 앞에 둔 후보에도 점수를 준다. 대응어(한국어·일본어) 형태소도 명사 항목이 있으면 그것을 우선한다.
- 접두사를 뗀 명사는 명사로 취급한다(`Abfahrt` → ab + Fahrt).

## 화면 (게임형 UI, 차분한 독일풍 모던 스타일)
메인 화면 맨 아래의 "이전 디자인으로 보기" 링크(또는 `/old`)로 이전 심플 카드형 디자인을 볼 수 있다. 두 디자인은 루트 레이아웃(라우트 그룹 `(main)`, `(legacy)`)과 CSS 가 완전히 분리되어 있고, 같은 `/api/analyze` 를 써서 기능은 같다(이전 디자인에는 도감·결과 공유 링크가 없다). 서로 오갈 때는 전체 페이지가 새로 로드된다.

외형은 흑·적·금(독일 국기 색을 한 톤 눌러서)을 포인트로 쓴 차분한 모던 스타일이다. DIN 계열 활자(Barlow Condensed), 방안지 배경, 바우하우스 도형, 상단 흑·적·금 띠, 점수 인장(`GEPRÜFT`), 독일어 캡션(`Eingabe`, `Ergebnis`, `Bausteine`, 등급별 독일어 부제)이 독일스러움을 살짝 더한다. 이모지 대신 도형 기호를 쓴다.

인트로(단어 투입구·스테이지 선택·도감) → 로딩(검체 검사 연출: 절단선·눈금자·4단계 체크리스트) → 결과(분해 블록·시상대·언어별 카드·블록 맞추기) 한 페이지 흐름. 결과는 `/?w=단어` 링크로 공유할 수 있고, 진단한 단어는 브라우저 도감(localStorage)에 쌓인다. 언어 카드는 유사도 순으로 정렬된다.

| 위치 | 역할 |
|---|---|
| `src/app/(main)/page.tsx` | 화면 단계(인트로/로딩/결과) 상태 관리, 호출, 도감 저장 |
| `src/app/(main)/game/` | `Intro`, `Loading`, `Result`, `LangCard`, `BlockLanes`, 등급 문구(`grades.ts`), 도감(`history.ts`) |
| `src/app/(main)/globals.css` | 디자인 토큰과 스타일 (라이트/다크 자동) |

## 호출 제한
`POST /api/analyze` 는 배포(production)에서만 IP별 시간당 60회로 제한한다(`RATE_LIMIT_PER_HOUR`로 조절). 개발 서버(`run.bat`, `npm run dev`)에서는 꺼져 있다. 개발 중에 켜 보려면 `RATE_LIMIT_PER_HOUR`를 지정하면 된다. 서버 메모리에 세는 방식이라 서버를 다시 시작하면 초기화되고, 형식이 맞는 요청은 성공·실패·캐시 여부와 상관없이 한 번씩 센다.

## 알아둘 점 / 한계
- 비공식 번역 엔드포인트는 약관상 개인 프로토타입용이다. 공개 배포 시 `Translator` 를 공식 Cloud Translation 구현이나 로컬 번역 모델로 교체할 것.
- 번역기는 단어 하나를 맥락 없이 번역하므로 대응어가 가장 일반적인 뜻으로 고정된다(예: Handschuh → 일본어 グローブ).
- 정렬은 휴리스틱이다. `confidence` 가 낮은 항목은 화면에 경고가 뜬다. 점수는 `score.ts` 의 고정 공식이 계산한다.
- 영어 hospital은 한 덩어리라 독일어 `Krankenhaus`(krank+Haus)와 한 그룹으로 묶이고, 한국어 `병원`·일본어 `病院`은 한 글자씩 나뉘어 krank = 병/病, Haus = 원/院으로 짝지어진다.
- 라틴계 어근이 자유 단어가 아닌 경우(`prefer`)는 쪼개지 않는다. `우체국`(郵便局) 같은 일본식 한자어는 한자어로 인식하지 못하고, `전자레인지`처럼 한자어와 외래어가 섞인 말은 한 덩어리로 남는다.
- 독일어 뜻풀이는 정렬 증거가 약하면 영어 빈도로 고르기 때문에 틀릴 수 있다(`Führerschein`의 `Schein` → 특허).
