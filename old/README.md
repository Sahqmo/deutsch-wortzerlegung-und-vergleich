# old — 이전 UI 백업 (심플한 카드형 디자인)

`src/app/` 에 있던 화면 파일을 그대로 복사해 둔 백업입니다. 이 폴더는 빌드/타입검사 대상이 아니에요.

| 파일 | 원래 위치 |
|---|---|
| `layout.tsx` | `src/app/layout.tsx` |
| `page.tsx` | `src/app/page.tsx` |
| `ResultCard.tsx` | `src/app/ResultCard.tsx` |
| `globals.css` | `src/app/globals.css` |

## 되돌리는 법
이 폴더의 네 파일을 `src/app/` 에 덮어쓰고, 새 디자인이 추가한 `src/app/game/` 폴더와 `src/app/page.tsx` 가 가져오는 파일들은 지우거나 그냥 두세요(안 쓰이면 무시됩니다).

---

# old/v2-pop-ui — 게임형 팝 디자인 백업 (굵은 외곽선·원색 팝 스타일)

두 번째 UI(게임형 단독 페이지, 네오브루탈 팝 스타일)를 그대로 복사해 둔 백업입니다. 구조는 지금 UI와 같고 외형(CSS)과 일부 문구·기호가 다릅니다.

| 파일 | 원래 위치 |
|---|---|
| `old/v2-pop-ui/page.tsx`, `layout.tsx`, `globals.css` | `src/app/` |
| `old/v2-pop-ui/game/*` | `src/app/game/` |

되돌리려면 이 폴더의 파일을 위 위치에 덮어쓰면 됩니다.
