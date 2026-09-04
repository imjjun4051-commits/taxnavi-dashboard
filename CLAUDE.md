# 텍스내비 — Claude Code 작업 규칙 (자동 로드 파일)

Claude Code는 프로젝트 폴더를 열면 이 `CLAUDE.md`를 **자동으로** 읽습니다.
(STEERING.md·SPECS.md는 자동으로 읽히지 않으므로, 이 파일이 그 둘을 가리키는 역할을 합니다.)

## 작업 전 반드시 읽을 파일
1. `STEERING.md` — 프로젝트 규칙 (기술 스택, 디자인 토큰, 데이터·세무 규칙, 검증 기준)
2. `SPECS.md` — 요구사항 · 화면 설계 · 작업 목록(Task) · 테스트 체크리스트
3. `DEVELOPMENT_LOG.md` — 지금까지의 진행 기록과 결정 사항

## 항상 지킬 것
- **기존 기능 삭제 금지.** 새 기능은 기존 코드 옆에 추가하고, 완료 후 기존 기능이 모두 동작하는지 확인한다.
- **전체 파일을 출력하지 않는다.** 파일은 디스크에 직접 쓰고, 답변에는 "어떤 부분이 바뀌었는지" 요약 + 주요 함수 설명만 쓴다.
- 모든 문구·주석·에러 메시지는 **한국어**. 함수 위에는 비전공자가 이해할 수 있는 한국어 주석.
- 금액 단위: 입력은 **백만원**, 화면 표시는 **원(천단위 쉼표)** + 억/만원 요약.
- 디자인: `STEERING.md` 4항의 토큰(오렌지 #FF6000 / 진한 오렌지 #CC4D00 / 쿨그레이)만 사용. 새 색상·외부 라이브러리 추가 금지.

## 데이터를 고칠 때
- 원본은 `sample-data.json`, `docs/tax-rules.json`, `docs/industry-avg.json`, `docs/government-support.json`.
- 고친 뒤 **`node tools/inline-data.js`** 를 실행해 `index.html` 안의 인라인 데이터 블록(`<script type="application/json" id="data-...">`)을 갱신한다. (더블클릭으로 열어도 동작하도록 데이터를 인라인하기 때문)
- 세무 수치를 바꿀 때는 `docs/tax-rules.json`의 `기준연도`·`확인일`·`출처`를 함께 갱신하고 `DEVELOPMENT_LOG.md`에 근거를 적는다.

## 작업 후
- 검증: 브라우저에서 `index.html`을 열어 F12 콘솔 JavaScript 오류 0개, 새로고침 후 입력값 유지, 320px~1920px 레이아웃, "데이터 초기화" 동작 확인. (자동 검증: `python3 tools/test-e2e.py`, Playwright 필요. 서버 포함 검증: `vercel dev` 실행 후 `TEST_URL=http://localhost:3000 python3 tools/test-e2e.py` — `/api/bizinfo` 프록시까지 확인)
- `DEVELOPMENT_LOG.md`에 날짜·변경 내용·검증 결과를 추가한다.
- `SPECS.md`의 Task 체크박스를 갱신한다.
