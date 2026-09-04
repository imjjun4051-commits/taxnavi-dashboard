# 택스네비 대시보드 리디자인 + 기업마당 API 프록시 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (이 세션은 서브에이전트 사용 금지 → 인라인 실행). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 단일 `index.html`을 "다크 사이드바 + 라이트 본문" 전문가용 대시보드(화면 5개: 개요·입력·분석·절세·지원사업)로 갈아입히고, Vercel 서버리스 함수 `api/bizinfo.js`로 기업마당 API를 프록시해 로컬(`vercel dev`)·운영(`vercel --prod`)에서 실호출되게 한다.

**Architecture:** 계산·저장 로직([JS 1]~[JS 8], [JS 14] 계산 부분)은 그대로 두고, CSS([CSS 2]~[CSS 6])·HTML `<body>`·렌더/내비 JS([JS 10]~[JS 13], [JS 15])만 교체한다. 화면 이동은 `[data-nav]` 버튼(사이드바·하단 탭바 공용) → `탭이동(id)`; 액션(CSV·인쇄·초기화)은 `[data-action]` 공용 바인딩. 프록시는 `api/bizinfo.js` 1개(외부 패키지 0), 브라우저는 `http(s)`로 열렸을 때만 `/api/bizinfo`를 호출한다.

**Tech Stack:** HTML5 · CSS3 · Vanilla JS(단일 파일) · Node 18+ 내장 `fetch`(Vercel 함수) · Vercel CLI 54 · Playwright(Python, Chromium) 검증

## Global Constraints (설계서 §1·§5, STEERING.md)

- 외부 라이브러리 금지. 유일한 예외: Pretendard CDN `<link>` (이미 있음)
- 색상은 STEERING 4항 토큰만. **새 hex 추가 금지** — 사이드바 토큰은 기존 값 매핑(`--sidebar-bg: var(--gray-900)`, `--sidebar-fg: var(--gray-300)`, `--sidebar-active: var(--primary-500)`), 투명도 `rgba(255,96,0,.14)`·`rgba(255,255,255,.06)`만 허용
- 라운드: 입력 8px · 버튼 12px · 카드 16px · 칩 999px / 간격 4px 배수 / 서체 Pretendard
- 모든 문구·주석·오류 메시지 한국어. 함수 위 한국어 주석
- 금액: 입력 백만원, 표시 원(천단위 쉼표) + 억·만원 요약 (`요약금액`·`원표시`·`원단위표시` 재사용)
- 기존 기능 삭제 금지. 기존 id 유지: `f-*`, `data-fin`, `data-plan`, `fin-head/body/error`, `plan-year-chip`, `btn-load-sample/clear-form/analyze`, `chart-sales/profit/industry`, `quarter-table/note`, `industry-hint/comments`, `analysis-empty/content/title/desc`, `tax-empty/content/summary/disclaimer`, `strategy-cards`, `s-region/field/sort/hide-closed/api-key`, `btn-api-load/sample`, `api-status`, `support-source/count/list`, `save-status`, `footer-disclaimer`, `btn-export-csv/print/reset`, `dialog*`, `toast`, `chart-tooltip`
- 세무 수치는 `docs/tax-rules.json`에만(코드에 숫자 금지). JSON 수정 후 `node tools/inline-data.js`
- 기업마당 인증키는 어떤 파일·로그에도 기록하지 않음(서버 로그는 `crtfcKey=****` 마스킹)
- GitHub 커밋·푸시 금지(사용자 지시). 배포는 `vercel --prod`만
- 가로 스크롤 금지(표는 `.table-wrap` 안에서만). F12 JS 오류 0. 새로고침 후 입력 유지. 초기화 시 LocalStorage 키 3개 삭제
- 차트 색: 예측=`--primary-500`, 실적·평균 기준=`--gray-600` (dataviz 검증: CVD ΔE 14.7 PASS, 회색은 의도된 중립 기준색). 텍스트는 텍스트 토큰만(값에 시리즈 색 사용 금지)

## 파일 구조

| 파일 | 역할 | 작업 |
|---|---|---|
| `api/bizinfo.js` | 기업마당 API 프록시(Vercel Node 함수) | 신규 |
| `vercel.json` | 함수 `maxDuration: 10` | 신규 |
| `.vercelignore` | `tools/`, `docs/superpowers/`, `*.md` 배포 제외 | 신규 |
| `docs/tax-rules.json` | `법인세.신고일정` 2건 추가(개요 일정용) | 수정 → `node tools/inline-data.js` |
| `index.html` | [CSS 1] 토큰 5줄 추가, [CSS 2]~[CSS 6] 교체, `<body>`~데이터 블록 직전 HTML 교체, [JS 10]~[JS 13]·[JS 14]의 `바인딩_푸터`·`데이터초기화`·[JS 15] 교체, `기업마당_불러오기` 프록시 분기 | 수정 |
| `tools/test-e2e.py` | 선택자·흐름 갱신, `TEST_URL`, 개요·프록시·모바일 검사 추가 | 교체 |
| `STEERING.md` `SPECS.md` `README.md` `CLAUDE.md` `DEVELOPMENT_LOG.md` | 문서 갱신 | 수정 |

**작업 순서:** Task 1(프록시) → Task 2(테스트 갱신 → 화면 교체 → 통과) → Task 3(개요 화면) → Task 4(문서·배포·배포 검증)

---

### Task 1: 기업마당 API 프록시 `api/bizinfo.js` + Vercel 설정 + 브라우저 분기

**Files:**
- Create: `api/bizinfo.js`, `vercel.json`, `.vercelignore`
- Modify: `index.html` — 함수 `기업마당_불러오기`(현재 1873~1886행)와 `#btn-api-load` 실패 문구(1907행 부근)
- Test: `node -e`(모의 req/res) + `vercel dev` 수동 호출

**Interfaces:**
- Produces: `GET /api/bizinfo?crtfcKey=…&dataType=json&searchCnt=100[&hashtags=…]` → 기업마당 응답 본문 패스스루. 키 없음 `400 {"error":"인증키(crtfcKey)가 없습니다"}`, 상위 실패 `502 {"error":"기업마당 응답 실패","detail":"…"}`
- Consumes: 없음(독립)

- [x] **Step 1: 실패하는 자기검사 작성 — 핸들러 파일이 아직 없어 실패해야 함**

Run (프로젝트 폴더에서):
```bash
node -e '
const h = require("./api/bizinfo.js");
function res(){ const r={headers:{},statusCode:200,body:"",setHeader(k,v){this.headers[k]=v},end(b){this.body=b||""}}; return r; }
(async()=>{
  const r1=res(); await h({method:"GET",url:"/api/bizinfo"},r1);
  console.assert(r1.statusCode===400 && JSON.parse(r1.body).error.includes("인증키"), "키 없음 → 400");
  const r2=res(); await h({method:"POST",url:"/api/bizinfo?crtfcKey=x"},r2);
  console.assert(r2.statusCode===405, "POST → 405");
  console.log("자기검사 통과");
})();'
```
Expected: `Error: Cannot find module './api/bizinfo.js'`

- [x] **Step 2: `api/bizinfo.js` 작성**

```js
// api/bizinfo.js — 기업마당 "지원사업정보 Open API" 프록시 (Vercel Node 서버리스 함수, 외부 패키지 없음)
// 브라우저가 기업마당을 직접 부르면 보안정책(CORS)에 막히므로, 같은 주소(/api/bizinfo)로 받아 대신 호출해 돌려준다.
// 인증키(crtfcKey)는 브라우저가 쿼리에 실어 보내며, 이 서버는 저장하지 않고 로그에도 남기지 않는다.
const 대상주소 = 'https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do';
// 기업마당으로 넘길 수 있는 쿼리 키만 허용 (임의 주소 프록시가 되지 않도록 대상 호스트 고정)
const 허용키 = ['crtfcKey', 'dataType', 'searchCnt', 'searchLclasId', 'hashtags', 'pageUnit', 'pageIndex'];
const 시간제한_ms = 8000;   // Vercel 함수 제한(10초) 안에서 끝내기 위한 상위 호출 제한

// JSON 오류 응답 한 줄 도우미
function 오류응답(res, 코드, 메시지, 상세) {
  res.statusCode = 코드;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(상세 ? { error: 메시지, detail: 상세 } : { error: 메시지 }));
}

// 인증키를 가린 문자열 (로그용)
function 키가리기(s) { return String(s).replace(/crtfcKey=[^&\s]+/g, 'crtfcKey=****'); }

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'GET') return 오류응답(res, 405, 'GET 요청만 지원합니다');
  const 입력 = new URL(req.url, 'http://localhost').searchParams;
  const 쿼리 = new URLSearchParams();
  허용키.forEach(k => { const v = 입력.get(k); if (v) 쿼리.set(k, v); });
  if (!쿼리.get('crtfcKey')) return 오류응답(res, 400, '인증키(crtfcKey)가 없습니다');
  if (!쿼리.get('dataType')) 쿼리.set('dataType', 'json');

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 시간제한_ms);
  try {
    const 응답 = await fetch(`${대상주소}?${쿼리}`, { signal: ctrl.signal, headers: { Accept: 'application/json, */*' } });
    const 본문 = await 응답.text();
    res.statusCode = 응답.status;
    res.setHeader('Content-Type', 응답.headers.get('content-type') || 'application/json; charset=utf-8');
    res.end(본문);
  } catch (e) {
    console.error('기업마당 호출 실패:', e.name, 키가리기(e.message));
    오류응답(res, 502, '기업마당 응답 실패', e.name === 'AbortError' ? `응답 시간 초과(${시간제한_ms / 1000}초)` : e.message);
  } finally { clearTimeout(timer); }
};
```

- [x] **Step 3: 자기검사 재실행**

Run: Step 1의 `node -e …` 명령 그대로
Expected: `자기검사 통과` (assert 실패 메시지 없음)

- [x] **Step 4: `vercel.json` · `.vercelignore` 작성**

`vercel.json`:
```json
{
  "functions": { "api/bizinfo.js": { "maxDuration": 10 } }
}
```
`.vercelignore`:
```
tools/
docs/superpowers/
*.md
```

- [x] **Step 5: `index.html` `기업마당_불러오기` 프록시 분기**

기존 두 줄
```js
  const url = 'https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do?' + params.toString();
```
```js
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
```
을 각각 아래로 교체:
```js
  // http(s)로 열렸으면(vercel dev·배포 주소) 같은 서버의 프록시 /api/bizinfo 를, 더블클릭(file://)이면 기업마당을 직접 호출
  const 프록시사용 = location.protocol === 'http:' || location.protocol === 'https:';
  const url = (프록시사용 ? '/api/bizinfo?' : 'https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do?') + params.toString();
```
```js
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try { const j = await res.json(); if (j && j.error) msg = j.error + (j.detail ? ` (${j.detail})` : ''); } catch (_) { /* JSON 아님 → 상태코드만 표시 */ }
      throw new Error(msg);
    }
```
그리고 실패 안내 문구(`st.textContent = \`기업마당 API 호출에 실패해 …\``)의 뒷부분
`서버 없이 브라우저에서 직접 호출하면 보안정책(CORS)으로 막힐 수 있습니다 — 이 경우 2일차 서버(프록시) 구성에서 해결합니다.`
을
`더블클릭(file://)으로 열면 보안정책(CORS)에 막힐 수 있습니다 — \`vercel dev\` 또는 배포 주소에서 열면 서버 프록시(/api/bizinfo)로 호출됩니다.`
로 교체.

- [x] **Step 6: Vercel 프로젝트 연결 후 `vercel dev`로 프록시 확인** (⚠ 계정에 새 프로젝트 `taxnavi-dashboard`가 생성됨 — 사용자 승인된 배포 경로)

Run:
```bash
cd ~/Desktop/택스네비 && vercel link --yes --project taxnavi-dashboard 2>&1 | tail -3
vercel dev --listen 3000 > /tmp/vercel-dev.log 2>&1 &
sleep 8; curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/api/bizinfo
curl -s "http://localhost:3000/api/bizinfo?crtfcKey=TESTKEY&searchCnt=1" | head -c 300; echo
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
```
Expected: `400` / 기업마당의 오류 JSON 또는 HTML 일부(잘못된 키 — 200·4xx) 또는 `{"error":"기업마당 응답 실패",…}` / `200`
DEVELOPMENT_LOG.md에 "잘못된 키로 호출 시 기업마당이 돌려준 응답 형태"를 한 줄 기록(키 값은 기록 금지).

- [x] **Step 7: 기존 자동 검증이 그대로 통과하는지 확인 (아직 화면은 옛 것)**

Run: `cd ~/Desktop/택스네비 && python3 tools/test-e2e.py 2>&1 | tail -3`
Expected: `총 49개 검사, 실패 0개`

---

### Task 2: 대시보드 리디자인 — 검증 스크립트 갱신 → CSS·HTML·JS 교체 → 통과

**Files:**
- Modify(교체): `tools/test-e2e.py` 전체
- Modify: `index.html` — [CSS 1] 끝에 토큰 5줄 추가, [CSS 2]~[CSS 6] 교체(74~297행), `<body>`부터 `<!-- [DATA] 인라인 데이터` 주석 직전까지 교체(300~636행), [JS 10]~[JS 13] 교체(1688~1968행), [JS 14]의 `데이터초기화`·`바인딩_푸터`, [JS 15] `시작` 교체
- Test: `python3 tools/test-e2e.py`

**Interfaces:**
- Consumes: 기존 계산 함수 `계산_전체()`·`계산_법인세(과세표준)`·`상태`·`데이터`·포맷 함수(`요약금액`·`원표시`·`원단위표시`·`퍼센트`·`증감표시`·`쉼표`·`esc`)·`가로쌍막대차트`·`세로막대차트`·`툴팁연결`·`공고정규화`·`현재공고목록`·`디데이`·`날짜표시`·`확인다이얼로그`·`토스트`
- Produces (Task 3가 사용): `탭이동(id: 'overview'|'input'|'analysis'|'tax'|'support')`, `갱신_탭상태()`, `갱신_입력진행()`, `렌더_KPI()`, `렌더_시나리오표()`, `필터된공고목록() → 정규화 공고 배열`, `상태.선택시나리오` 변경 시 `렌더_시나리오의존()`, 개요용 자리표시자 함수 `렌더_개요()`(Task 2에서는 빈 상태만 처리, Task 3에서 완성)

- [x] **Step 1: 검증 스크립트를 새 화면 기준으로 교체 (실패해야 함)**

`tools/test-e2e.py` 전체를 아래로 교체:

```python
# tools/test-e2e.py — 자동 검증 스크립트. Playwright(Chromium)로 index.html을 열어
# 콘솔 오류, 계산 결과, 화면 이동(사이드바·하단 탭바), LocalStorage 유지, 초기화, 반응형·인쇄 스크린샷, 프록시를 확인한다.
# 준비: python3 -m pip install --user playwright && python3 -m playwright install chromium
# 실행: python3 tools/test-e2e.py                                   (file:// — 더블클릭과 동일, 프록시 검사 생략)
#       TEST_URL=http://localhost:3000 python3 tools/test-e2e.py    (vercel dev 또는 배포 주소 — /api/bizinfo 검사 포함)
import asyncio, os, sys
from playwright.async_api import async_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('TEST_URL') or 'file://' + os.path.join(BASE, 'index.html')
SERVER = URL.startswith('http')
SHOTS = os.path.join(BASE, 'tools', 'screenshots'); os.makedirs(SHOTS, exist_ok=True)
NAVS = ['overview', 'input', 'analysis', 'tax', 'support']

results = []
def check(name, ok, detail=''):
    results.append((name, ok, detail)); print(('PASS' if ok else 'FAIL'), name, detail)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={'width': 1440, 'height': 900}, locale='ko-KR', accept_downloads=True)
        page = await ctx.new_page()
        errors = []; network = []
        # 네트워크 자원 실패(폰트 CDN·API 호출 차단 등)는 JS 오류가 아니므로 따로 모아 참고용으로 출력
        page.on('console', lambda m: (network if m.text.startswith('Failed to load resource') else errors).append(f'console.{m.type}: {m.text}') if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
        page.on('requestfailed', lambda r: network.append(f'requestfailed: {r.url} ({r.failure})'))
        await page.goto(URL); await page.wait_for_load_state('load')

        # 초기 화면: 개요(빈 상태) → "입력 시작" → 입력
        check('초기 화면: 개요 표시 + 빈 상태', await page.is_visible('#panel-overview') and await page.is_visible('#overview-empty'))
        check('초기 화면: 사이드바 메뉴 5개', await page.locator('.sidebar [data-nav]').count() == 5)
        await page.click('#overview-empty [data-nav="input"]'); await page.wait_for_timeout(150)
        check('초기 화면: 입력 시작 → 입력 화면', await page.is_visible('#panel-input'))
        check('초기 화면: 재무 표 입력칸 18개', await page.locator('[data-fin]').count() == 18, str(await page.locator('[data-fin]').count()))
        check('초기 화면: 업종 6개', await page.locator('#f-industry option').count() == 6)
        check('입력: 진행률 표시(필수 18개 중)', '/ 18' in await page.inner_text('#input-progress'))

        # 샘플 불러오기
        await page.click('#btn-load-sample'); await page.wait_for_timeout(200)
        v = await page.input_value('[data-fin="매출액"][data-idx="2"]')
        check('샘플: 2025 매출액 5,100', v == '5,100', v)
        check('샘플: 회사명', await page.input_value('#f-company') == '샘플정밀(주)')
        check('샘플: 임금인상률 8', await page.input_value('#f-wage') == '8')
        check('입력: 진행률 18 / 18', '18 / 18' in await page.inner_text('#input-progress'))

        # 분석 시작
        await page.click('#btn-analyze'); await page.wait_for_timeout(400)
        check('분석: 분석 화면 표시', await page.is_visible('#panel-analysis') and await page.is_visible('#analysis-content'))
        check('분석: KPI 4개', await page.locator('#analysis-kpis .kpi').count() == 4)
        tbl = await page.inner_text('#scenario-table')
        check('분석: 시나리오 표 열 3개(+실적)', await page.locator('#scenario-table thead th.scenario').count() == 3)
        check('분석: 기본 매출 51억원', '51억원' in tbl, tbl[:80].replace('\n', ' '))
        check('분석: 기본 세부담 6,160만원(법인세 56,000,000 + 지방 5,600,000)', '6,160만원' in tbl and '56,000,000원' in tbl and '5,600,000원' in tbl)
        check('분석: 기본 부가세 (5100-3150)*10% = 195 → 1.95억원', '1.95억원' in tbl)
        # 낙관: 매출 5610, 변동비 = (5100-380-1330-220)=3170*1.1=3487, 영업이익 = 5610-1330-220-3487 = 573
        check('분석: 낙관 영업이익 5.73억원', '5.73억원' in tbl)
        check('분석: 차트 SVG 3개', await page.locator('#panel-analysis svg').count() == 3, str(await page.locator('#panel-analysis svg').count()))
        check('분석: 분기표 5행', await page.locator('#quarter-table tbody tr').count() == 5)
        check('분석: 툴바 시나리오 세그먼트 표시', await page.is_visible('#scenario-switch'))
        await page.click('#scenario-switch button[data-scn="2"]'); await page.wait_for_timeout(100)
        check('분석: 시나리오 전환 → 분기표·KPI 낙관', '낙관' in await page.inner_text('#quarter-note') and '5.73억원' in await page.inner_text('#analysis-kpis'))
        await page.click('#scenario-switch button[data-scn="1"]'); await page.wait_for_timeout(100)
        check('분석: 업종 비교 표 4행', await page.locator('#industry-comments tbody tr').count() == 4)

        # 개요 (Task 3에서 완성 — Task 2 시점에는 이 5건이 FAIL이어도 정상)
        await page.click('#nav-overview'); await page.wait_for_timeout(200)
        check('개요: KPI 4개', await page.locator('#overview-kpis .kpi').count() == 4)
        ov = await page.inner_text('#overview-kpis')
        check('개요: 매출 51억·세부담 6,160만원·절세 3/3', '51억원' in ov and '6,160만원' in ov and '3 / 3' in ov, ov[:160].replace('\n', ' '))
        check('개요: 세금 일정 3건', await page.locator('#overview-schedule li').count() == 3)
        check('개요: 시나리오 비교 3행', await page.locator('#overview-scn-table tbody tr').count() == 3)
        check('개요: 임박 공고 표시', await page.locator('#overview-support .support').count() >= 1)
        check('개요: 업종 대비 문장', '업종 평균' in await page.inner_text('#overview-industry'))

        # 절세
        await page.click('#nav-tax'); await page.wait_for_timeout(200)
        rows = page.locator('#strategy-cards .strategy')
        check('절세: 전략 3개', await rows.count() == 3)
        emp = await rows.nth(0).inner_text(); inv = await rows.nth(1).inner_text(); wage = await rows.nth(2).inner_text()
        check('절세: 통합고용 1년차 17,000,000원 / 3년 81,000,000원', '17,000,000원' in emp and '81,000,000원' in emp, emp[:160].replace('\n', ' '))
        check('절세: 통합투자 41,250,000원', '41,250,000원' in inv, inv[:160].replace('\n', ' '))
        check('절세: 근로소득증대 적용 가능', '적용 가능' in wage, wage[:200].replace('\n', ' '))
        summary = await page.inner_text('#tax-summary')
        check('절세: 요약 적용 3/3', '3' in summary and '/ 3' in summary, summary[:100].replace('\n', ' '))
        await rows.nth(0).locator('.collapse__btn').click(); await page.wait_for_timeout(100)
        check('절세: 자세히 펼침', await page.locator('#detail-employment').evaluate('el => el.classList.contains("is-open")'))

        # 지원사업
        await page.click('#nav-support'); await page.wait_for_timeout(200)
        check('지원사업: 지역 필터 기본 광주', await page.input_value('#s-region') == '광주')
        n_open = await page.locator('#support-list .support').count()
        check('지원사업: 광주+전국 미마감 공고 표시', n_open > 0, str(n_open))
        check('지원사업: 마감 공고 숨김(SAMPLE-0010 없음)', '도약기업' not in await page.inner_text('#support-list'))
        await page.uncheck('#s-hide-closed'); await page.wait_for_timeout(100)
        check('지원사업: 마감 숨김 해제 시 표시', '도약기업' in await page.inner_text('#support-list'))
        await page.select_option('#s-region', 'all'); await page.wait_for_timeout(100)
        check('지원사업: 전체 12건', await page.locator('#support-list .support').count() == 12, str(await page.locator('#support-list .support').count()))
        # 기업마당 연동 패널 열기 → 키 없이 불러오기 → 안내
        if not await page.evaluate('document.getElementById("api-panel").open'):
            await page.click('#api-panel summary'); await page.wait_for_timeout(100)
        await page.click('#btn-api-load'); await page.wait_for_timeout(100)
        check('지원사업: 인증키 없음 안내', '인증키를 먼저' in await page.inner_text('#api-status'))
        await page.fill('#s-api-key', 'TESTKEY'); await page.click('#btn-api-load'); await page.wait_for_timeout(9000 if SERVER else 3000)
        st = await page.inner_text('#api-status')
        check('지원사업: 잘못된 키 → 실패 안내 + 샘플 유지', ('실패' in st or '불러왔습니다' in st) and await page.locator('#support-list .support').count() > 0, st[:120])
        if SERVER:
            code = await page.evaluate("fetch('/api/bizinfo').then(r => r.status)")
            check('프록시: 키 없음 → 400', code == 400, str(code))
            body = await page.evaluate("fetch('/api/bizinfo?crtfcKey=TESTKEY&searchCnt=1').then(r => r.text())")
            check('프록시: 잘못된 키 → 기업마당/프록시 응답 수신', len(body) > 0, body[:100].replace('\n', ' '))

        # 새로고침 후 유지 (분석결과 있음 → 개요로 진입)
        await page.reload(); await page.wait_for_load_state('load'); await page.wait_for_timeout(300)
        check('새로고침: 개요로 진입', await page.is_visible('#panel-overview'))
        check('새로고침: 매출액 유지', await page.input_value('[data-fin="매출액"][data-idx="2"]') == '5,100')
        check('새로고침: 회사명 유지', await page.input_value('#f-company') == '샘플정밀(주)')
        check('새로고침: 완료 점(입력·분석·절세)', await page.locator('.sidebar [data-nav].is-done').count() == 3, str(await page.locator('.sidebar [data-nav].is-done').count()))
        check('새로고침: 저장 상태 칩', '자동 저장됨' in await page.inner_text('#save-status'))
        keys = await page.evaluate('Object.keys(localStorage)')
        check('저장 키 3개', set(keys) >= {'재무제표', '절세전략', '지원사업_검색'}, str(keys))
        check('새로고침: 지원사업 필터 유지(전체)', await page.evaluate('JSON.parse(localStorage.getItem("지원사업_검색")).지역') == 'all')

        # 입력 검증: 매출액 비우고 분석 → 오류
        await page.click('#nav-input'); await page.wait_for_timeout(150)
        await page.fill('[data-fin="매출액"][data-idx="2"]', ''); await page.click('#btn-analyze'); await page.wait_for_timeout(200)
        check('검증: 빈 값 오류 표시', await page.is_visible('#fin-error') and '매출액' in await page.inner_text('#fin-error'))
        check('검증: 분석 화면으로 이동 안 함', await page.is_visible('#panel-input'))
        await page.fill('[data-fin="매출액"][data-idx="2"]', '5100'); await page.locator('[data-fin="매출액"][data-idx="2"]').blur(); await page.wait_for_timeout(100)
        check('검증: blur 시 쉼표 포맷', await page.input_value('[data-fin="매출액"][data-idx="2"]') == '5,100')
        # 영업이익 음수 허용 → 결손 시 법인세 0
        await page.fill('[data-fin="영업이익"][data-idx="2"]', '-120'); await page.click('#btn-analyze'); await page.wait_for_timeout(300)
        check('검증: 영업이익 음수 허용 → 분석 진행', await page.is_visible('#panel-analysis'))
        check('결손: 법인세 0(과세표준 없음)', '과세표준 없음' in await page.inner_text('#scenario-table'))
        await page.click('#nav-input'); await page.fill('[data-fin="영업이익"][data-idx="2"]', '380'); await page.click('#btn-analyze'); await page.wait_for_timeout(300)

        # CSV 내보내기 (사이드바 버튼)
        async with page.expect_download() as dl:
            await page.click('#btn-export-csv')
        d = await dl.value
        path = await d.path(); content = open(path, 'rb').read()
        check('CSV: BOM + 한글 내용', content.startswith(b'\xef\xbb\xbf') and '택스네비'.encode() in content and '통합고용'.encode() in content, d.suggested_filename)

        # 반응형 스크린샷 — 모바일(<768)은 하단 탭바 #mnav-*, 그 외 사이드바 #nav-*
        for w, name in [(320, 'mobile-320'), (768, 'tablet-768'), (1024, 'tablet-1024'), (1920, 'desktop-1920')]:
            await page.set_viewport_size({'width': w, 'height': 900 if w > 400 else 740})
            prefix = '#mnav-' if w < 768 else '#nav-'
            for nav in NAVS:
                await page.click(f'{prefix}{nav}'); await page.wait_for_timeout(250)
                await page.screenshot(path=os.path.join(SHOTS, f'{name}-{nav}.png'), full_page=True)
            overflow = await page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 1')
            check(f'반응형 {w}px: 가로 스크롤 없음', not overflow)
            if w < 768:
                check(f'반응형 {w}px: 사이드바 숨김·하단 탭바·본문 액션 표시', (not await page.is_visible('#nav-input')) and await page.is_visible('#mnav-input') and await page.is_visible('.mobile-actions'))

        # 인쇄: 사이드바·탭바 숨김, 5개 화면 모두 출력
        await page.set_viewport_size({'width': 1440, 'height': 900})
        await page.emulate_media(media='print'); await page.wait_for_timeout(100)
        await page.screenshot(path=os.path.join(SHOTS, 'print.png'), full_page=True)
        check('인쇄: 사이드바 숨김 + 패널 5개 표시', (not await page.is_visible('.sidebar')) and await page.locator('.panel:visible').count() == 5, str(await page.locator('.panel:visible').count()))
        await page.emulate_media(media='screen'); await page.wait_for_timeout(100)

        # 데이터 초기화 (사이드바 버튼 → 자체 다이얼로그)
        await page.click('#nav-input'); await page.click('#btn-reset'); await page.wait_for_timeout(100)
        check('초기화: 다이얼로그 표시', await page.is_visible('#dialog'))
        await page.click('#dialog-ok'); await page.wait_for_timeout(300)
        check('초기화: 입력 화면 + 입력값 비움', await page.is_visible('#panel-input') and await page.input_value('[data-fin="매출액"][data-idx="2"]') == '' and await page.input_value('#f-company') == '')
        keys = await page.evaluate('Object.keys(localStorage)')
        check('초기화: localStorage 비움', len(keys) == 0, str(keys))
        check('초기화: 저장 상태 칩', '저장된 데이터 없음' in await page.inner_text('#save-status'))
        check('초기화: 완료 점 없음', await page.locator('.sidebar [data-nav].is-done').count() == 0)

        check('콘솔/페이지 JS 오류 0개', len(errors) == 0, '\n'.join(errors)[:800])
        print('참고) 네트워크 자원 실패:', '\n  '.join(network) or '없음')
        await browser.close()

    fails = [r for r in results if not r[1]]
    print(f'\n총 {len(results)}개 검사, 실패 {len(fails)}개')
    sys.exit(1 if fails else 0)

asyncio.run(main())
```

- [x] **Step 2: 옛 화면에서 실행해 실패 확인**

Run: `cd ~/Desktop/택스네비 && python3 tools/test-e2e.py 2>&1 | tail -3`
Expected: 첫 검사 `FAIL 초기 화면: 개요 표시 + 빈 상태` 후 `#overview-empty [data-nav="input"]` 클릭에서 타임아웃 예외(옛 화면에 요소 없음) — 스크립트가 예외로 종료되어도 "실패 확인"으로 간주

- [x] **Step 3: [CSS 1] 토큰 5줄 추가 + [CSS 2]~[CSS 6] 교체**

3-a. `index.html` [CSS 1]의 `--shadow-card: …;` 줄 바로 아래(닫는 `}` 앞)에 추가:
```css
  /* 앱 셸 — 사이드바 토큰은 기존 색에 매핑 (새 hex 없음) */
  --sidebar-bg: var(--gray-900);
  --sidebar-fg: var(--gray-300);
  --sidebar-active: var(--primary-500);
  --sidebar-w: 240px;
  --toolbar-h: 56px;
```

3-b. `/* ===…\n   [CSS 2] 기본 리셋` 주석 시작부터 `</style>` 직전까지를 아래 CSS로 교체 (스플라이스: 아래 내용을 `/tmp/…/new.css`에 저장 후 Python으로 `[CSS 2]` 마커 위치~`</style>` 사이를 치환):

```css
/* =====================================================================
   [CSS 2] 기본 리셋 · 타이포그래피
   ===================================================================== */
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; font-family: var(--font); font-size: var(--fs-p2); line-height: 1.5; color: var(--fg-normal); background: var(--bg-normal); }
h1, h2, h3, h4, p { margin: 0; }
a { color: var(--fg-primary); text-decoration: none; }
a:hover { text-decoration: underline; }
button { font-family: inherit; }
input, select { font-family: inherit; font-size: var(--fs-p2); color: var(--fg-normal); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
.muted { color: var(--fg-muted); }
.small { font-size: var(--fs-p3); }
.num { font-variant-numeric: tabular-nums; }
.link { background: none; border: 0; padding: 0; color: var(--fg-primary); font-weight: 600; font-size: var(--fs-p3); cursor: pointer; }
.link:hover { text-decoration: underline; }
:focus-visible { outline: 2px solid var(--border-primary); outline-offset: 2px; border-radius: var(--radius-1); }

/* =====================================================================
   [CSS 3] 앱 셸 — 다크 사이드바 · 툴바 · 본문 · 모바일 하단 탭바
   ===================================================================== */
.app { display: flex; min-height: 100vh; }
.sidebar { position: fixed; top: 0; bottom: 0; left: 0; width: var(--sidebar-w); background: var(--sidebar-bg); color: var(--sidebar-fg); display: flex; flex-direction: column; gap: var(--space-2); padding: var(--space-5) var(--space-3); z-index: 30; overflow-y: auto; }
.sidebar__brand { display: flex; align-items: center; gap: var(--space-3); padding: 0 var(--space-2) var(--space-4); }
.brand__mark { flex: none; width: 40px; height: 40px; border-radius: var(--radius-3); background: var(--bg-primary); display: grid; place-items: center; }
.brand__name { font-size: var(--fs-h5); font-weight: 800; letter-spacing: -0.3px; line-height: 1.2; color: var(--white); }
.brand__tagline { font-size: var(--fs-p5); color: var(--gray-500); margin-top: 2px; line-height: 1.35; }
.sidebar__nav, .sidebar__actions { display: flex; flex-direction: column; gap: 2px; }
.nav { position: relative; display: flex; align-items: center; gap: var(--space-3); width: 100%; min-height: 44px; padding: 0 var(--space-3); border: 0; border-radius: var(--radius-3); background: transparent; color: var(--sidebar-fg); font-size: var(--fs-p2); font-weight: 600; text-align: left; cursor: pointer; }
.nav:hover { background: rgba(255,255,255,.06); color: var(--white); }
.nav[aria-current="page"] { background: rgba(255,96,0,.14); color: var(--white); }
.nav[aria-current="page"] .nav__icon { color: var(--sidebar-active); }
.nav__icon { flex: none; width: 20px; height: 20px; color: var(--gray-500); }
.nav__icon svg { width: 20px; height: 20px; display: block; }
.nav__label { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nav__dot { flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--sidebar-active); opacity: 0; transition: opacity .15s; }
.nav.is-done .nav__dot { opacity: 1; }
.nav--action { min-height: 40px; font-size: var(--fs-p3); font-weight: 500; color: var(--gray-400); }
.nav--action:hover { color: var(--white); }
.sidebar__divider { height: 1px; background: rgba(255,255,255,.08); margin: var(--space-2); }
.sidebar__foot { margin-top: auto; padding: var(--space-3) var(--space-2) 0; }
.sidebar__caption { font-size: var(--fs-p5); color: var(--gray-500); line-height: 1.45; }

.main { flex: 1; min-width: 0; margin-left: var(--sidebar-w); display: flex; flex-direction: column; min-height: 100vh; }
.toolbar { position: sticky; top: 0; z-index: 20; min-height: var(--toolbar-h); background: var(--bg-white); border-bottom: 1px solid var(--border-weak); display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); padding: var(--space-2) var(--space-6); }
.toolbar__title { min-width: 0; }
.toolbar__title h1 { font-size: var(--fs-p1); font-weight: 700; letter-spacing: -0.2px; color: var(--gray-900); white-space: nowrap; }
.toolbar__desc { font-size: var(--fs-p4); color: var(--fg-muted); margin-top: 1px; }
.toolbar__right { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; justify-content: flex-end; }
.content { flex: 1; width: 100%; max-width: 1400px; margin: 0 auto; padding: var(--space-5) var(--space-6) var(--space-10); }
.content__foot { border-top: 1px solid var(--border-weak); margin-top: var(--space-8); padding-top: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); }
.footer__note { font-size: var(--fs-p3); color: var(--fg-muted); }
.mobile-actions { display: none; }
.bottombar { display: none; }

/* 태블릿(768~1023px): 아이콘 사이드바 */
@media (max-width: 1023px) {
  :root { --sidebar-w: 72px; }
  .sidebar { padding: var(--space-4) var(--space-2); }
  .sidebar__brand { justify-content: center; padding: 0 0 var(--space-3); }
  .sidebar__brand > div, .nav__label, .nav__dot, .sidebar__caption { display: none; }
  .nav { justify-content: center; padding: 0; }
  .nav.is-done::after { content: ""; position: absolute; top: 8px; right: 10px; width: 6px; height: 6px; border-radius: 50%; background: var(--sidebar-active); }
  .sidebar__foot { padding: 0; }
  .toolbar { padding: var(--space-2) var(--space-4); }
  .content { padding: var(--space-4) var(--space-4) var(--space-10); }
}
/* 모바일(<768px): 사이드바 숨김 → 하단 탭바 + 본문 하단 액션 */
@media (max-width: 767px) {
  .sidebar { display: none; }
  .main { margin-left: 0; }
  .content { padding-bottom: 96px; }
  .mobile-actions { display: flex; }
  .bottombar { display: grid; grid-template-columns: repeat(5, 1fr); position: fixed; left: 0; right: 0; bottom: 0; z-index: 30; background: var(--bg-white); border-top: 1px solid var(--border-weak); padding-bottom: env(safe-area-inset-bottom); }
  .bottombar__item { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; min-height: 56px; border: 0; background: transparent; color: var(--fg-muted); font-size: var(--fs-p5); font-weight: 600; cursor: pointer; }
  .bottombar__item svg { width: 22px; height: 22px; }
  .bottombar__item[aria-current="page"] { color: var(--fg-primary); }
  .bottombar__item.is-done::after { content: ""; position: absolute; top: 6px; right: calc(50% - 18px); width: 6px; height: 6px; border-radius: 50%; background: var(--primary-500); }
  .toolbar { flex-wrap: wrap; gap: var(--space-2); }
  .toolbar__desc, #company-chip { display: none; }
}
@media (max-width: 480px) { #year-chip { display: none; } .toolbar__title h1 { font-size: var(--fs-p2); } }

/* =====================================================================
   [CSS 4] 카드 · 칩 · 버튼 · 폼 · 표
   ===================================================================== */
.panel[hidden] { display: none; }
.card { background: var(--bg-white); border: 1px solid var(--border-weak); border-radius: var(--radius-4); padding: var(--space-4); box-shadow: var(--shadow-card); margin-bottom: var(--space-4); }
.card--weak { background: var(--bg-primary-weak); border-color: var(--primary-100); box-shadow: none; }
.card--table { padding: 0; overflow: hidden; }
.card--table .table-wrap { border: 0; border-radius: 0; }
.card__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.card--table .card__head { padding: var(--space-3) var(--space-4) 0; }
.card__title { font-size: var(--fs-p2); font-weight: 700; display: flex; align-items: center; gap: var(--space-2); color: var(--gray-900); }
.card__hint { color: var(--fg-muted); font-size: var(--fs-p4); }
.grid { display: grid; gap: var(--space-4); }
.grid--2, .grid--3 { grid-template-columns: 1fr; }
.grid--4 { grid-template-columns: 1fr 1fr; }
@media (min-width: 768px) { .grid--2 { grid-template-columns: repeat(2, minmax(0,1fr)); } .grid--3 { grid-template-columns: repeat(3, minmax(0,1fr)); } .grid--4 { grid-template-columns: repeat(4, minmax(0,1fr)); } }
.layout { display: grid; gap: var(--space-4); grid-template-columns: 1fr; align-items: start; }
@media (min-width: 1024px) { .layout { grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); } .layout__side { position: sticky; top: calc(var(--toolbar-h) + var(--space-4)); } }

.chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: var(--radius-full); font-size: var(--fs-p3); font-weight: 500; background: var(--gray-100); color: var(--gray-700); white-space: nowrap; }
.chip--primary { background: var(--bg-primary-weak); color: var(--fg-primary); }
.chip--strong { background: var(--bg-primary); color: var(--fg-white); }
.chip--muted { background: var(--gray-100); color: var(--gray-500); }
.chip__dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }

.btn { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2); min-height: 40px; padding: 0 var(--space-4); border-radius: var(--radius-3); border: 1px solid transparent; font-size: var(--fs-p2); font-weight: 600; cursor: pointer; transition: background .15s, color .15s, border-color .15s; white-space: nowrap; }
.btn--primary { background: var(--bg-primary); color: var(--fg-white); }
.btn--primary:hover { background: var(--primary-600); }
.btn--secondary { background: var(--bg-white); color: var(--fg-primary); border-color: var(--border-primary); }
.btn--secondary:hover { background: var(--bg-primary-weak); }
.btn--ghost { background: var(--bg-white); color: var(--gray-700); border-color: var(--border-normal); }
.btn--ghost:hover { background: var(--gray-50); }
.btn--danger { background: var(--bg-white); color: var(--gray-700); border-color: var(--border-normal); }
.btn--danger:hover { background: var(--gray-100); color: var(--gray-900); }
.btn--sm { min-height: 34px; padding: 0 var(--space-3); font-size: var(--fs-p3); border-radius: var(--radius-2); }
.btn--block { width: 100%; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.actions { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; }
.actions--end { justify-content: flex-end; }

.field { display: flex; flex-direction: column; gap: 6px; }
.field__label { font-size: var(--fs-p3); font-weight: 600; color: var(--gray-700); }
.field__help { font-size: var(--fs-p4); color: var(--fg-muted); }
.field__error { font-size: var(--fs-p4); color: var(--primary-700); display: none; }
.field.is-invalid .field__error { display: block; }
.input, .select { width: 100%; min-height: 40px; padding: 0 var(--space-3); border: 1px solid var(--border-normal); border-radius: var(--radius-2); background: var(--bg-white); outline: none; transition: border-color .15s, box-shadow .15s; }
.input:focus, .select:focus { border-color: var(--border-primary); box-shadow: 0 0 0 3px var(--primary-50); }
.input[aria-invalid="true"] { border-color: var(--primary-600); background: var(--primary-50); }
.input::placeholder { color: var(--fg-disabled); }
.input--num { text-align: right; font-variant-numeric: tabular-nums; }
.input-suffix { display: flex; align-items: center; gap: var(--space-2); }
.input-suffix .input { flex: 1; }
.input-suffix__unit { color: var(--fg-muted); font-size: var(--fs-p3); white-space: nowrap; }
.select { appearance: none; background-image: linear-gradient(45deg, transparent 50%, var(--gray-600) 50%), linear-gradient(135deg, var(--gray-600) 50%, transparent 50%); background-position: calc(100% - 18px) 50%, calc(100% - 13px) 50%; background-size: 5px 5px, 5px 5px; background-repeat: no-repeat; padding-right: 34px; }
.check { display: flex; align-items: center; gap: var(--space-2); font-size: var(--fs-p3); color: var(--gray-700); min-height: 40px; }
.check input { width: 18px; height: 18px; accent-color: var(--primary-500); }
.filters { display: grid; gap: var(--space-3); grid-template-columns: 1fr 1fr; align-items: end; }
@media (min-width: 768px) { .filters { grid-template-columns: repeat(4, minmax(0,1fr)) auto; } }

/* 표 (재무 입력표 + 데이터 표 공용) */
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; border: 1px solid var(--border-weak); border-radius: var(--radius-3); }
.table-wrap__hint { display: none; font-size: var(--fs-p4); color: var(--fg-muted); margin: 6px 0 0; }
table.data, table.fin-table { width: 100%; border-collapse: collapse; font-size: var(--fs-p3); }
.data th, .data td, .fin-table th, .fin-table td { padding: var(--space-2) var(--space-3); text-align: right; border-bottom: 1px solid var(--border-weak); white-space: nowrap; vertical-align: middle; }
.data th, .fin-table th { font-size: var(--fs-p4); font-weight: 600; color: var(--gray-600); background: var(--gray-50); }
.data th:first-child, .data td:first-child, .fin-table th:first-child, .fin-table td:first-child { text-align: left; position: sticky; left: 0; background: var(--bg-white); z-index: 1; }
.data th:first-child, .fin-table th:first-child { background: var(--gray-50); }
.data tr:last-child td { border-bottom: 0; }
.data th.is-base, .data td.is-base { background: var(--bg-primary-weak); }
.data th.is-base { color: var(--fg-primary); }
.data td.is-base { color: var(--gray-900); font-weight: 600; }
.data tr.is-total td { font-weight: 700; background: var(--gray-50); }
.data td b { font-weight: 700; color: var(--gray-900); }
.data td small, .data th small { display: block; font-weight: 400; color: var(--fg-muted); font-size: var(--fs-p5); white-space: normal; }
.data td.wrap { white-space: normal; min-width: 220px; }
.data th.left, .data td.left { text-align: left; }
.fin-table td .input { min-height: 36px; min-width: 110px; padding: 0 var(--space-2); }
.fin-table .row-label { font-weight: 600; color: var(--gray-800); }
.fin-table .row-help { display: block; font-size: var(--fs-p5); color: var(--fg-muted); font-weight: 400; }
.fin-table th.is-base { color: var(--fg-primary); }

/* =====================================================================
   [CSS 5] KPI 타일 · 배지 · 세그먼트 · 차트 · 일정 · 진행률 · 빈 상태 · 절세/지원 표
   ===================================================================== */
.kpis { display: grid; gap: var(--space-3); grid-template-columns: repeat(2, minmax(0,1fr)); margin-bottom: var(--space-4); }
@media (min-width: 1024px) { .kpis { grid-template-columns: repeat(4, minmax(0,1fr)); } }
.kpis--3 { grid-template-columns: 1fr; }
@media (min-width: 768px) { .kpis--3 { grid-template-columns: repeat(3, minmax(0,1fr)); } }
.kpi { background: var(--bg-white); border: 1px solid var(--border-weak); border-radius: var(--radius-4); padding: var(--space-4); box-shadow: var(--shadow-card); display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.kpi--accent { border-color: var(--primary-200); background: var(--bg-primary-weak); }
.kpi__label { font-size: var(--fs-p4); color: var(--fg-muted); font-weight: 600; }
.kpi__value { font-size: var(--fs-h3); font-weight: 800; letter-spacing: -0.5px; color: var(--gray-900); font-variant-numeric: tabular-nums; line-height: 1.15; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kpi__value.is-negative { color: var(--primary-700); }
.kpi__value--sm { font-size: var(--fs-h5); }
.kpi__sub { font-size: var(--fs-p4); color: var(--fg-muted); font-variant-numeric: tabular-nums; }
.delta { font-weight: 600; }
.delta.up { color: var(--primary-600); }
.delta.down { color: var(--gray-600); }
.is-negative { color: var(--primary-700); }

.badge { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; flex: none; padding: 2px 8px; border-radius: var(--radius-1); font-size: var(--fs-p4); font-weight: 600; }
.badge--ok { background: var(--bg-primary-weak); color: var(--fg-primary); }
.badge--no { background: var(--gray-100); color: var(--gray-600); }
.badge--urgent { background: var(--primary-500); color: var(--fg-white); }
.badge--soon { background: var(--bg-primary-weak); color: var(--primary-700); }
.badge--open { background: var(--gray-100); color: var(--gray-700); }
.badge--closed { background: var(--gray-100); color: var(--gray-400); text-decoration: line-through; }
.segmented { display: inline-flex; border: 1px solid var(--border-normal); border-radius: var(--radius-2); overflow: hidden; }
.segmented[hidden] { display: none; }
.segmented button { min-height: 32px; padding: 0 var(--space-3); border: 0; background: var(--bg-white); color: var(--gray-700); font-size: var(--fs-p3); font-weight: 600; cursor: pointer; }
.segmented button + button { border-left: 1px solid var(--border-normal); }
.segmented button[aria-pressed="true"] { background: var(--bg-primary-weak); color: var(--fg-primary); }
.note { font-size: var(--fs-p3); color: var(--fg-muted); padding: var(--space-3) var(--space-4); background: var(--gray-50); border-radius: var(--radius-2); border: 1px solid var(--border-weak); }
.note--warn { background: var(--bg-primary-weak); border-color: var(--primary-100); color: var(--primary-800); }
.chart { width: 100%; }
.chart svg { width: 100%; height: auto; display: block; }
.chart--wide svg { max-width: 720px; }
.chart__legend { display: flex; flex-wrap: wrap; gap: var(--space-3); font-size: var(--fs-p3); color: var(--fg-muted); margin-top: var(--space-2); }
.chart__legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
.chart-tooltip { position: fixed; z-index: 50; pointer-events: none; background: var(--gray-900); color: var(--fg-white); font-size: var(--fs-p3); padding: 6px 10px; border-radius: var(--radius-2); box-shadow: var(--shadow-card); max-width: 260px; }
.chart-tooltip[hidden] { display: none; }
/* 개요: 시나리오 가로 막대(HTML) — 예측 시리즈 1개이므로 색 1개, 선택 행은 글자 굵게 */
.bars { display: grid; gap: var(--space-2); margin-top: var(--space-3); }
.bars__row { display: grid; grid-template-columns: 40px 1fr 80px; gap: var(--space-2); align-items: center; font-size: var(--fs-p3); color: var(--gray-700); }
.bars__row.is-selected { font-weight: 700; color: var(--gray-900); }
.bars__track { height: 10px; border-radius: 999px; background: var(--gray-100); overflow: hidden; }
.bars__fill { height: 100%; border-radius: 999px; background: var(--chart-forecast); }
.bars__val { text-align: right; font-variant-numeric: tabular-nums; }
/* 개요: 세금 일정 */
.timeline { list-style: none; margin: 0; padding: 0; }
.timeline li { display: grid; grid-template-columns: 72px 1fr auto; gap: var(--space-3); align-items: center; padding: var(--space-3) 0; border-bottom: 1px dashed var(--border-weak); font-size: var(--fs-p3); }
.timeline li:last-child { border-bottom: 0; }
.timeline__date { font-weight: 700; color: var(--gray-900); font-variant-numeric: tabular-nums; }
.timeline__date small { display: block; font-weight: 500; color: var(--fg-muted); font-size: var(--fs-p5); }
.timeline__name { font-weight: 600; color: var(--gray-800); }
.timeline__name small { display: block; font-weight: 400; color: var(--fg-muted); font-size: var(--fs-p5); }
.timeline__amt { font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; color: var(--gray-900); }
/* 입력 진행률 */
.progress { height: 6px; border-radius: 999px; background: var(--gray-200); overflow: hidden; margin: var(--space-2) 0 var(--space-3); }
.progress i { display: block; height: 100%; background: var(--primary-500); border-radius: 999px; transition: width .2s; }
.side-list { display: grid; gap: var(--space-2); font-size: var(--fs-p3); color: var(--gray-700); margin: 0 0 var(--space-4); padding: 0; list-style: none; }
.side-list li { display: flex; justify-content: space-between; gap: var(--space-2); }
.empty { text-align: center; padding: var(--space-10) var(--space-4); color: var(--fg-muted); }
.empty__title { font-size: var(--fs-p1); font-weight: 600; color: var(--gray-700); margin-bottom: var(--space-2); }
.empty .btn { margin-top: var(--space-4); }

/* 절세 전략 표 + 확장 행 */
.collapse__btn { background: none; border: 0; padding: 0; color: var(--fg-primary); font-weight: 600; font-size: var(--fs-p3); cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
.collapse__btn::after { content: "▾"; transition: transform .15s; }
.collapse__btn[aria-expanded="true"]::after { transform: rotate(180deg); }
.collapse__body { display: none; font-size: var(--fs-p3); color: var(--gray-700); padding: var(--space-3) var(--space-4); background: var(--gray-50); }
.collapse__body.is-open { display: block; }
.collapse__body dl { display: grid; grid-template-columns: auto 1fr; gap: 6px var(--space-3); margin: 0; }
.collapse__body dt { color: var(--fg-muted); }
.collapse__body dd { margin: 0; white-space: normal; }
.collapse__body ol, .collapse__body ul { margin: var(--space-1) 0 0; padding-left: 18px; }
.strategies td.wrap { min-width: 260px; }
.strategy__detail td { padding: 0; white-space: normal; }
.strategy__detail:not(.is-open) { display: none; }
/* 지원사업 표 */
.supports td.wrap { min-width: 280px; }
.support__title { font-weight: 700; color: var(--gray-900); }
.support__title:hover { color: var(--fg-primary); }
.api-panel summary { cursor: pointer; font-weight: 700; font-size: var(--fs-p2); color: var(--gray-900); display: flex; align-items: center; gap: var(--space-2); list-style: none; }
.api-panel summary::-webkit-details-marker { display: none; }
.api-panel summary::before { content: "▸"; color: var(--fg-muted); transition: transform .15s; }
.api-panel[open] summary::before { transform: rotate(90deg); }
.api-panel[open] summary { margin-bottom: var(--space-3); }
.api-row { display: grid; gap: var(--space-3); grid-template-columns: 1fr; align-items: end; }
@media (min-width: 768px) { .api-row { grid-template-columns: 1fr auto; } }
/* 모바일: 절세·지원 표를 카드처럼 쌓기 */
@media (max-width: 767px) {
  .strategies thead, .supports thead { display: none; }
  .strategies tr.strategy, .supports tr.support { display: grid; grid-template-columns: 1fr auto; gap: 4px var(--space-3); padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-weak); }
  .strategies tr.strategy td, .supports tr.support td { display: block; border: 0; padding: 0; white-space: normal; text-align: left; position: static; background: transparent; min-width: 0; }
  .strategies tr.strategy td:nth-child(1), .supports tr.support td:nth-child(2) { grid-column: 1; }
  .strategies tr.strategy td:nth-child(2), .supports tr.support td:nth-child(1) { grid-column: 2; justify-self: end; }
  .strategies tr.strategy td:nth-child(n+3), .supports tr.support td:nth-child(n+3) { grid-column: 1 / -1; }
  .supports tr.support td:nth-child(1) { grid-row: 1; }
  .strategies td[data-label]::before, .supports td[data-label]::before { content: attr(data-label) " "; color: var(--fg-muted); font-weight: 500; }
  .strategy__detail td { display: block; }
  .table-wrap__hint { display: block; }
  .brand__tagline { display: none; }
}

/* =====================================================================
   [CSS 6] 다이얼로그 · 토스트 · 인쇄
   ===================================================================== */
.dialog { position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; background: rgba(25, 31, 40, .45); padding: var(--space-4); }
.dialog[hidden] { display: none; }
.dialog__box { width: 100%; max-width: 420px; background: var(--bg-white); border-radius: var(--radius-4); padding: var(--space-6); box-shadow: 0 20px 60px rgba(25,31,40,.25); }
.dialog__title { font-size: var(--fs-p1); font-weight: 700; margin-bottom: var(--space-2); }
.dialog__desc { color: var(--fg-muted); font-size: var(--fs-p2); margin-bottom: var(--space-5); }
.toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); z-index: 110; background: var(--gray-900); color: var(--fg-white); padding: var(--space-3) var(--space-5); border-radius: var(--radius-3); font-size: var(--fs-p2); box-shadow: 0 8px 30px rgba(25,31,40,.3); max-width: calc(100% - 32px); }
.toast[hidden] { display: none; }
@media (max-width: 767px) { .toast { bottom: 76px; } }
@media print {
  .sidebar, .bottombar, .toolbar__right, .mobile-actions, .actions, .filters, .api-panel, .collapse__btn, .chart-tooltip, .toast, .dialog, .layout__side, #overview-empty, #analysis-empty, #tax-empty { display: none !important; }
  .main { margin-left: 0; }
  .toolbar { position: static; border: 0; }
  .panel[hidden] { display: block !important; }
  .collapse__body { display: block !important; }
  .strategy__detail { display: table-row !important; }
  body { background: #fff; }
  .card, .kpi { box-shadow: none; break-inside: avoid; }
  .content { padding: 0; max-width: none; }
  .panel + .panel { page-break-before: always; }
}
```

- [x] **Step 4: `<body>` HTML 교체 — `<body>`부터 `<!-- ===…\n     [DATA] 인라인 데이터` 주석 직전까지를 아래로 교체**

```html
<body>
<!-- 아이콘 스프라이트 (자체 제작, 사이드바·하단 탭바 공용) -->
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <symbol id="i-overview" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="8" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/><rect x="13" y="13" width="8" height="8" rx="2"/></symbol>
  <symbol id="i-input" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h5"/></symbol>
  <symbol id="i-analysis" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16"/><rect x="6" y="11" width="3" height="6" rx="1"/><rect x="11" y="6" width="3" height="11" rx="1"/><rect x="16" y="9" width="3" height="8" rx="1"/></symbol>
  <symbol id="i-tax" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8.5 15.5l7-7"/><circle cx="9" cy="9" r="1"/><circle cx="15" cy="15" r="1"/></symbol>
  <symbol id="i-support" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21V4"/><path d="M5 4h11l-1.5 3.5L16 11H5"/></symbol>
  <symbol id="i-csv" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M4 21h16"/></symbol>
  <symbol id="i-print" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="3" width="12" height="6" rx="1"/><rect x="3" y="9" width="18" height="8" rx="2"/><rect x="7" y="14" width="10" height="7" rx="1"/></symbol>
  <symbol id="i-reset" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/></symbol>
</svg>

<div class="app">
<!-- =====================================================================
     [HTML 1] 사이드바 — 브랜드 · 메뉴 5개(완료 점) · 액션 3개 · 캡션
     ===================================================================== -->
<aside class="sidebar" aria-label="주 메뉴">
  <div class="sidebar__brand">
    <span class="brand__mark" aria-hidden="true">
      <!-- 자체 제작 심볼: 나침반 바늘 (내비게이터 의미) -->
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="9.5" stroke="#FFFFFF" stroke-width="1.6" opacity=".85"/>
        <path d="M12 5.5 L14.6 11.2 L12 18.5 L9.4 11.2 Z" fill="#FFFFFF"/>
        <path d="M12 5.5 L14.6 11.2 L12 12.4 L9.4 11.2 Z" fill="#FFDFCC"/>
      </svg>
    </span>
    <div>
      <p class="brand__name">택스네비</p>
      <p class="brand__tagline">내년 실적을 미리 보고, 세금은 미리 설계하세요</p>
    </div>
  </div>
  <nav class="sidebar__nav" aria-label="화면 이동">
    <button type="button" class="nav" id="nav-overview" data-nav="overview" aria-current="page"><span class="nav__icon"><svg><use href="#i-overview"/></svg></span><span class="nav__label">개요</span><span class="nav__dot" aria-hidden="true"></span></button>
    <button type="button" class="nav" id="nav-input" data-nav="input"><span class="nav__icon"><svg><use href="#i-input"/></svg></span><span class="nav__label">입력</span><span class="nav__dot" aria-hidden="true"></span></button>
    <button type="button" class="nav" id="nav-analysis" data-nav="analysis"><span class="nav__icon"><svg><use href="#i-analysis"/></svg></span><span class="nav__label">분석결과</span><span class="nav__dot" aria-hidden="true"></span></button>
    <button type="button" class="nav" id="nav-tax" data-nav="tax"><span class="nav__icon"><svg><use href="#i-tax"/></svg></span><span class="nav__label">절세전략</span><span class="nav__dot" aria-hidden="true"></span></button>
    <button type="button" class="nav" id="nav-support" data-nav="support"><span class="nav__icon"><svg><use href="#i-support"/></svg></span><span class="nav__label">지원사업</span><span class="nav__dot" aria-hidden="true"></span></button>
  </nav>
  <div class="sidebar__divider"></div>
  <div class="sidebar__actions">
    <button type="button" class="nav nav--action" id="btn-export-csv" data-action="csv" title="CSV 내보내기"><span class="nav__icon"><svg><use href="#i-csv"/></svg></span><span class="nav__label">CSV 내보내기</span></button>
    <button type="button" class="nav nav--action" id="btn-print" data-action="print" title="인쇄 / PDF 저장"><span class="nav__icon"><svg><use href="#i-print"/></svg></span><span class="nav__label">인쇄 / PDF 저장</span></button>
    <button type="button" class="nav nav--action" id="btn-reset" data-action="reset" title="데이터 초기화"><span class="nav__icon"><svg><use href="#i-reset"/></svg></span><span class="nav__label">데이터 초기화</span></button>
  </div>
  <div class="sidebar__foot">
    <p class="sidebar__caption" id="sidebar-caption">광주·전남 중소기업 재무 내비게이터</p>
  </div>
</aside>

<div class="main">
<!-- =====================================================================
     [HTML 2] 툴바 — 화면 제목 · 회사/예측연도 칩 · 자동 저장 상태 · 시나리오 세그먼트
     ===================================================================== -->
<header class="toolbar">
  <div class="toolbar__title">
    <h1 id="page-title">개요</h1>
    <p class="toolbar__desc" id="page-desc">내년 예측 · 세금 · 절세 · 지원사업을 한눈에</p>
  </div>
  <div class="toolbar__right">
    <span class="chip" id="company-chip" hidden></span>
    <span class="chip chip--primary" id="year-chip">예측 2026년</span>
    <span id="save-status" class="chip chip--muted" role="status" aria-live="polite"><span class="chip__dot"></span>저장된 데이터 없음</span>
    <div class="segmented" id="scenario-switch" role="group" aria-label="시나리오 선택" hidden>
      <button type="button" data-scn="0" aria-pressed="false">보수</button>
      <button type="button" data-scn="1" aria-pressed="true">기본</button>
      <button type="button" data-scn="2" aria-pressed="false">낙관</button>
    </div>
  </div>
</header>

<main class="content">
  <!-- ===================================================================
       [HTML 3] 화면 1 — 개요 (KPI 4 · 시나리오 비교 · 세금 일정 · 임박 공고 · 업종 대비)
       =================================================================== -->
  <section class="panel" id="panel-overview" aria-label="개요">
    <div id="overview-empty" class="card empty">
      <p class="empty__title">재무데이터를 입력하면 여기에 요약이 표시됩니다</p>
      <p>최근 3개년 재무데이터와 내년 계획을 입력하면 예측 실적·세금·절세전략·지원사업을 한 화면에서 볼 수 있습니다.</p>
      <button type="button" class="btn btn--primary" data-nav="input">입력 시작 →</button>
    </div>
    <div id="overview-content" hidden>
      <div class="kpis" id="overview-kpis"></div>
      <div class="grid grid--2">
        <div class="card">
          <div class="card__head"><h2 class="card__title">시나리오 비교</h2><span class="card__hint" id="overview-scn-hint"></span></div>
          <div class="table-wrap"><table class="data" id="overview-scn-table"><thead></thead><tbody></tbody></table></div>
          <div class="bars" id="overview-bars"></div>
        </div>
        <div class="card">
          <div class="card__head"><h2 class="card__title">다가오는 세금 일정</h2><span class="card__hint">오늘 기준 · 선택 시나리오 추정액</span></div>
          <ol class="timeline" id="overview-schedule"></ol>
        </div>
      </div>
      <div class="grid grid--2">
        <div class="card card--table">
          <div class="card__head"><h2 class="card__title">임박한 지원사업</h2><button type="button" class="link" data-nav="support">전체 보기 →</button></div>
          <div id="overview-support"></div>
        </div>
        <div class="card">
          <div class="card__head"><h2 class="card__title">업종 평균 대비</h2><button type="button" class="link" data-nav="analysis">분석 보기 →</button></div>
          <p id="overview-industry"></p>
        </div>
      </div>
    </div>
  </section>

  <!-- ===================================================================
       [HTML 4] 화면 2 — 입력 (좌: 기업정보 · 재무데이터 · 내년 계획 / 우: 진행 요약 · 버튼)
       =================================================================== -->
  <section class="panel" id="panel-input" aria-label="입력" hidden>
    <div class="layout">
      <div>
        <div class="card">
          <div class="card__head">
            <h2 class="card__title">기업정보</h2>
            <span class="card__hint">소재지는 세액공제(수도권 외 우대)와 지원사업 지역 필터에 사용됩니다</span>
          </div>
          <div class="grid grid--3" id="company-fields">
            <div class="field">
              <label class="field__label" for="f-company">회사명 <span class="muted">(선택)</span></label>
              <input class="input" id="f-company" data-field="회사명" type="text" placeholder="예: 샘플정밀(주)" autocomplete="organization">
            </div>
            <div class="field">
              <label class="field__label" for="f-industry">업종</label>
              <select class="select" id="f-industry" data-field="업종"></select>
            </div>
            <div class="field">
              <label class="field__label" for="f-region">소재지</label>
              <select class="select" id="f-region" data-field="소재지">
                <option value="gwangju">광주광역시</option>
                <option value="jeonnam">전라남도</option>
                <option value="other">기타 (수도권 외)</option>
                <option value="capital">수도권 (서울·인천·경기)</option>
              </select>
            </div>
            <div class="field">
              <label class="field__label" for="f-employees">상시근로자 수</label>
              <div class="input-suffix">
                <input class="input input--num" id="f-employees" data-field="상시근로자수" type="text" inputmode="numeric" placeholder="0">
                <span class="input-suffix__unit">명</span>
              </div>
              <span class="field__help">기준연도 말 기준 (대표·임원 제외)</span>
              <span class="field__error">0 이상의 정수를 입력하세요</span>
            </div>
            <div class="field">
              <label class="field__label" for="f-base-year">기준연도 (가장 최근 결산연도)</label>
              <select class="select" id="f-base-year" data-field="기준연도">
                <option value="2024">2024년</option>
                <option value="2025" selected>2025년</option>
                <option value="2026">2026년</option>
              </select>
              <span class="field__help">예측은 기준연도 다음 해를 기준으로 합니다</span>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card__head">
            <h2 class="card__title">재무데이터 <span class="chip chip--primary">단위: 백만원</span></h2>
            <span class="card__hint">최근 3개년 손익계산서·재무상태표 기준. 영업이익이 적자면 음수(-)로 입력</span>
          </div>
          <div class="table-wrap">
            <table class="fin-table" id="fin-table">
              <thead><tr id="fin-head"></tr></thead>
              <tbody id="fin-body"></tbody>
            </table>
          </div>
          <p class="table-wrap__hint">← 표를 좌우로 밀어 연도별 칸을 입력하세요 →</p>
          <p class="field__error" id="fin-error" style="margin-top:8px"></p>
        </div>

        <div class="card">
          <div class="card__head">
            <h2 class="card__title">내년 계획 <span class="chip" id="plan-year-chip">예측연도</span></h2>
            <span class="card__hint">세액공제는 '계획'이 있을 때 미리 설계할 수 있습니다. 없으면 0으로 두세요</span>
          </div>
          <div class="grid grid--4" id="plan-fields">
            <div class="field">
              <label class="field__label" for="f-emp-delta">상시근로자 증감</label>
              <div class="input-suffix">
                <input class="input input--num" id="f-emp-delta" data-plan="상시근로자증감" type="text" inputmode="numeric" placeholder="0">
                <span class="input-suffix__unit">명</span>
              </div>
              <span class="field__help">채용 +, 감원 −</span>
              <span class="field__error">정수를 입력하세요</span>
            </div>
            <div class="field">
              <label class="field__label" for="f-youth">그중 청년등 채용</label>
              <div class="input-suffix">
                <input class="input input--num" id="f-youth" data-plan="청년등증가" type="text" inputmode="numeric" placeholder="0">
                <span class="input-suffix__unit">명</span>
              </div>
              <span class="field__help">15~34세·장애인·60세 이상·경력단절여성</span>
              <span class="field__error">0 이상, 증감 인원 이하로 입력하세요</span>
            </div>
            <div class="field">
              <label class="field__label" for="f-capex">설비투자 계획액</label>
              <div class="input-suffix">
                <input class="input input--num" id="f-capex" data-plan="설비투자계획액" type="text" inputmode="numeric" placeholder="0">
                <span class="input-suffix__unit">백만원</span>
              </div>
              <span class="field__help">기계장치·비품 등 (토지·건물 제외)</span>
              <span class="field__error">0 이상의 숫자를 입력하세요</span>
            </div>
            <div class="field">
              <label class="field__label" for="f-wage">임금 인상률 계획</label>
              <div class="input-suffix">
                <input class="input input--num" id="f-wage" data-plan="임금인상률" type="text" inputmode="decimal" placeholder="0">
                <span class="input-suffix__unit">%</span>
              </div>
              <span class="field__help">평균임금 기준 (예: 4 → 4%)</span>
              <span class="field__error">-50 ~ 100 사이 숫자를 입력하세요</span>
            </div>
          </div>
        </div>
      </div>

      <aside class="layout__side">
        <div class="card">
          <div class="card__head"><h2 class="card__title">입력 진행</h2><span class="card__hint num" id="input-progress">0 / 18</span></div>
          <div class="progress"><i id="input-progress-bar" style="width:0%"></i></div>
          <ul class="side-list" id="input-summary"></ul>
          <div style="display:grid;gap:8px">
            <button type="button" class="btn btn--primary btn--block" id="btn-analyze">분석 시작 →</button>
            <button type="button" class="btn btn--ghost btn--block" id="btn-load-sample">샘플 데이터 불러오기</button>
            <button type="button" class="btn btn--ghost btn--sm btn--block" id="btn-clear-form">입력값 지우기</button>
          </div>
          <p class="field__help" style="margin-top:12px">금액은 <strong>백만원</strong> 단위입니다 (예: 30억원 → 3,000). 입력하는 즉시 이 브라우저에 자동 저장됩니다.</p>
        </div>
      </aside>
    </div>
  </section>

  <!-- ===================================================================
       [HTML 5] 화면 3 — 분석결과 (KPI · 차트 · 시나리오 비교표 · 분기표 · 업종 비교)
       =================================================================== -->
  <section class="panel" id="panel-analysis" aria-label="분석결과" hidden>
    <div id="analysis-empty" class="card empty">
      <p class="empty__title">아직 분석 결과가 없습니다</p>
      <p>입력 화면에서 재무데이터를 채우고 <strong>분석 시작</strong>을 눌러 주세요.</p>
      <button type="button" class="btn btn--primary" data-nav="input">입력으로 이동 →</button>
    </div>
    <div id="analysis-content" hidden>
      <p class="note" id="analysis-desc" style="margin-bottom:16px"></p>
      <div class="kpis" id="analysis-kpis"></div>
      <div class="grid grid--2">
        <div class="card">
          <div class="card__head"><h2 class="card__title">매출액 비교</h2><span class="card__hint">실적 vs 내년 시나리오</span></div>
          <div class="chart" id="chart-sales"></div>
        </div>
        <div class="card">
          <div class="card__head"><h2 class="card__title">영업이익 비교</h2><span class="card__hint">실적 vs 내년 시나리오</span></div>
          <div class="chart" id="chart-profit"></div>
        </div>
      </div>
      <div class="card card--table">
        <div class="card__head"><h2 class="card__title" id="analysis-title">시나리오 비교</h2><span class="card__hint">억·만원 요약 + 원 단위 · 기본 시나리오 강조</span></div>
        <div class="table-wrap"><table class="data" id="scenario-table"><thead></thead><tbody></tbody></table></div>
      </div>
      <div class="card card--table">
        <div class="card__head"><h2 class="card__title">분기별 예상 실적과 세금 일정</h2><span class="card__hint" id="quarter-scn"></span></div>
        <div class="table-wrap"><table class="data" id="quarter-table"><thead></thead><tbody></tbody></table></div>
        <p class="note" id="quarter-note" style="margin:12px 16px 16px"></p>
      </div>
      <div class="card">
        <div class="card__head"><h2 class="card__title">업종 평균과 비교</h2><span class="card__hint" id="industry-hint"></span></div>
        <div class="grid grid--2">
          <div class="chart chart--wide" id="chart-industry"></div>
          <div class="table-wrap"><table class="data" id="industry-comments"><thead><tr><th>지표</th><th>우리 회사</th><th>업종 평균</th><th>차이</th><th class="left">해석</th></tr></thead><tbody></tbody></table></div>
        </div>
      </div>
      <div class="actions actions--end"><button type="button" class="btn btn--primary" data-nav="tax">절세전략 보기 →</button></div>
    </div>
  </section>

  <!-- ===================================================================
       [HTML 6] 화면 4 — 절세전략 (요약 KPI 3 · 전략 표 + 확장 행 · 면책)
       =================================================================== -->
  <section class="panel" id="panel-tax" aria-label="절세전략" hidden>
    <div id="tax-empty" class="card empty">
      <p class="empty__title">먼저 분석을 실행해 주세요</p>
      <p>입력 화면에서 <strong>분석 시작</strong>을 누르면 절세전략이 함께 계산됩니다.</p>
      <button type="button" class="btn btn--primary" data-nav="input">입력으로 이동 →</button>
    </div>
    <div id="tax-content" hidden>
      <p class="note" id="tax-desc" style="margin-bottom:16px"></p>
      <div class="kpis kpis--3" id="tax-summary"></div>
      <div class="card card--table">
        <div class="card__head"><h2 class="card__title">전략별 적용 여부와 절감 예상액</h2><span class="card__hint">규칙: docs/tax-rules.json · 원 단위</span></div>
        <div class="table-wrap">
          <table class="data strategies" id="strategy-cards">
            <thead><tr><th>전략</th><th>적용</th><th>절감 예상액 (1년차)</th><th>3년 누계</th><th class="left">요약 · 행동 힌트</th><th></th></tr></thead>
            <tbody id="strategy-body"></tbody>
          </table>
        </div>
      </div>
      <p class="note note--warn" id="tax-disclaimer"></p>
      <div class="actions actions--end" style="margin-top:16px"><button type="button" class="btn btn--primary" data-nav="support">지원사업 보기 →</button></div>
    </div>
  </section>

  <!-- ===================================================================
       [HTML 7] 화면 5 — 지원사업 (필터 · 기업마당 연동 패널 · 공고 표)
       =================================================================== -->
  <section class="panel" id="panel-support" aria-label="지원사업" hidden>
    <div class="card">
      <div class="filters">
        <div class="field">
          <label class="field__label" for="s-region">지역</label>
          <select class="select" id="s-region">
            <option value="all">전체</option>
            <option value="광주">광주 + 전국</option>
            <option value="전남">전남 + 전국</option>
            <option value="전국">전국 공통만</option>
          </select>
        </div>
        <div class="field">
          <label class="field__label" for="s-field">분야</label>
          <select class="select" id="s-field">
            <option value="all">전체</option>
            <option value="금융">금융</option><option value="기술">기술</option><option value="인력">인력</option><option value="수출">수출</option>
            <option value="내수">내수</option><option value="창업">창업</option><option value="경영">경영</option><option value="기타">기타</option>
          </select>
        </div>
        <div class="field">
          <label class="field__label" for="s-sort">정렬</label>
          <select class="select" id="s-sort">
            <option value="deadline">마감 임박순</option>
            <option value="latest">신청 시작 최신순</option>
          </select>
        </div>
        <label class="check"><input type="checkbox" id="s-hide-closed" checked> 마감된 공고 숨기기</label>
        <span class="chip chip--muted" id="support-source"><span class="chip__dot"></span>샘플 데이터</span>
      </div>
    </div>
    <details class="card api-panel" id="api-panel">
      <summary>기업마당 실시간 공고 연동 <span class="chip">선택</span></summary>
      <div class="api-row">
        <div class="field">
          <label class="field__label" for="s-api-key">기업마당 Open API 인증키</label>
          <input class="input" id="s-api-key" type="password" placeholder="발급받은 인증키를 붙여 넣으세요" autocomplete="off">
          <span class="field__help">인증키는 이 브라우저에만 저장됩니다. 발급: 기업마당 로그인 → 활용정보 → 정책정보 개방 → 지원사업정보 API → 인증키 신청 · <a href="https://www.bizinfo.go.kr/web/lay1/program/S1T175C174/apiDetail.do?id=bizinfoApi" target="_blank" rel="noopener">API·인증키 안내 ↗</a></span>
        </div>
        <div class="actions">
          <button type="button" class="btn btn--secondary" id="btn-api-load">기업마당에서 불러오기</button>
          <button type="button" class="btn btn--ghost" id="btn-api-sample">샘플로 되돌리기</button>
        </div>
      </div>
      <p class="note" id="api-status" hidden style="margin-top:12px"></p>
    </details>
    <p class="small muted" id="support-count" style="margin:0 0 12px"></p>
    <div id="support-list"></div>
  </section>

  <!-- =====================================================================
       [HTML 8] 본문 하단 — 면책 · (모바일) 액션
       ===================================================================== -->
  <footer class="content__foot">
    <p class="footer__note" id="footer-disclaimer">※ 세금·공제 금액은 단순 추정치입니다. 실제 신고 전 세무사 등 전문가의 확인을 받으세요.</p>
    <div class="actions mobile-actions">
      <button type="button" class="btn btn--ghost btn--sm" data-action="csv">CSV 내보내기</button>
      <button type="button" class="btn btn--ghost btn--sm" data-action="print">인쇄 / PDF</button>
      <button type="button" class="btn btn--danger btn--sm" data-action="reset">데이터 초기화</button>
    </div>
  </footer>
</main>
</div><!-- /.main -->
</div><!-- /.app -->

<!-- 모바일 하단 탭바 (768px 미만에서만 표시) -->
<nav class="bottombar" aria-label="화면 이동 (모바일)">
  <button type="button" class="bottombar__item" id="mnav-overview" data-nav="overview" aria-current="page"><svg><use href="#i-overview"/></svg>개요</button>
  <button type="button" class="bottombar__item" id="mnav-input" data-nav="input"><svg><use href="#i-input"/></svg>입력</button>
  <button type="button" class="bottombar__item" id="mnav-analysis" data-nav="analysis"><svg><use href="#i-analysis"/></svg>분석</button>
  <button type="button" class="bottombar__item" id="mnav-tax" data-nav="tax"><svg><use href="#i-tax"/></svg>절세</button>
  <button type="button" class="bottombar__item" id="mnav-support" data-nav="support"><svg><use href="#i-support"/></svg>지원</button>
</nav>

<!-- 확인 다이얼로그 (브라우저 confirm 대신 자체 구현) -->
<div class="dialog" id="dialog" hidden role="dialog" aria-modal="true" aria-labelledby="dialog-title">
  <div class="dialog__box">
    <p class="dialog__title" id="dialog-title"></p>
    <p class="dialog__desc" id="dialog-desc"></p>
    <div class="actions actions--end">
      <button type="button" class="btn btn--ghost" id="dialog-cancel">취소</button>
      <button type="button" class="btn btn--primary" id="dialog-ok">확인</button>
    </div>
  </div>
</div>
<div class="toast" id="toast" hidden role="status" aria-live="polite"></div>
<div class="chart-tooltip" id="chart-tooltip" hidden></div>

```

- [x] **Step 5: JS 교체 — [JS 10]~[JS 13] 전체, [JS 14]의 `바인딩_푸터`, [JS 15] `시작`**

5-a. `/* ---…\n   [JS 10] 렌더 — 분석결과 패널` 주석 시작부터 `/* ---…\n   [JS 14]` 주석 직전까지를 아래로 교체 (Python으로 두 마커 사이 치환):

```js
/* ---------------------------------------------------------------------
   [JS 10] 렌더 — 분석결과 화면 (KPI 스트립 · 차트 · 시나리오 비교표 · 분기표 · 업종 비교)
   --------------------------------------------------------------------- */
// 툴바 세그먼트로 고른 시나리오 객체 (없으면 '기본')
function 선택시나리오() {
  const 분 = 상태.분석결과; if (!분) return null;
  return 분.시나리오[상태.선택시나리오] || 분.시나리오[1];
}
// KPI 타일 1개 HTML. 값 글자는 텍스트 색만 사용(시리즈 색 금지), 음수는 진한 오렌지
function KPI타일(라벨, 값, 보조, 옵션 = {}) {
  return `<div class="kpi ${옵션.강조 ? 'kpi--accent' : ''}"><span class="kpi__label">${esc(라벨)}</span><span class="kpi__value ${옵션.음수 ? 'is-negative' : ''} ${옵션.작게 ? 'kpi__value--sm' : ''}">${값}</span>${보조 ? `<span class="kpi__sub">${보조}</span>` : ''}</div>`;
}
// 분석 화면 KPI 4개 (선택 시나리오 기준)
function 렌더_KPI() {
  const 분 = 상태.분석결과, s = 선택시나리오(); if (!s) return;
  const 실 = 분.실적;
  $('#analysis-kpis').innerHTML = [
    KPI타일(`${s.이름} 시나리오 예상 매출`, 요약금액(s.매출), `${원표시(s.매출)} <span class="delta ${s.매출 >= 실.매출 ? 'up' : 'down'}">${증감표시(s.매출, 실.매출)}</span>`),
    KPI타일('예상 영업이익', 요약금액(s.영업이익), `영업이익률 ${퍼센트(s.영업이익률)} · 실적 ${요약금액(실.영업이익)}`, { 음수: s.영업이익 < 0 }),
    KPI타일('예상 법인세 + 지방소득세', 요약금액(s.세부담합계), esc(s.구간설명)),
    KPI타일('예상 부가세 납부', 요약금액(s.부가세), esc(s.부가세방식))
  ].join('');
}
// 시나리오 비교표: 행 = 지표, 열 = 기준연도 실적 · 보수 · 기본(강조) · 낙관
function 렌더_시나리오표() {
  const 분 = 상태.분석결과; if (!분) return;
  const 실 = 분.실적, y = 연도목록()[2], 예 = 분.예측연도;
  const 실세금 = 계산_법인세(실.영업이익);
  const 부가세율 = (데이터.세무규칙.부가가치세 && 데이터.세무규칙.부가가치세.세율) || 0.10;
  const 실부가세 = 실.매입 == null ? 실.매출 * 부가세율 : (실.매출 - 실.매입) * 부가세율;
  const 열 = [
    { 이름: `${y}년 실적`, 실적: true, v: { 매출: 실.매출, 영업이익: 실.영업이익, 영업이익률: 실.영업이익률, 법인세: 실세금.법인세, 지방소득세: 실세금.지방소득세, 세부담합계: 실세금.합계, 부가세: 실부가세, 세후영업이익: 실.영업이익 - 실세금.합계, 구간설명: 실세금.구간설명 } },
    ...분.시나리오.map(s => ({ 이름: s.이름, 부제: s.설명, id: s.id, 기본: s.id === 1, v: s }))
  ];
  const 돈 = v => `<b>${요약금액(v)}</b><small>${원표시(v)}</small>`;
  const 행 = [
    ['매출액', c => 돈(c.v.매출)],
    ['영업이익', c => `<span class="${c.v.영업이익 < 0 ? 'is-negative' : ''}">${돈(c.v.영업이익)}</span><small>영업이익률 ${퍼센트(c.v.영업이익률)}</small>`],
    ['법인세', c => 돈(c.v.법인세)],
    ['지방소득세', c => 돈(c.v.지방소득세)],
    ['세부담 합계', c => 돈(c.v.세부담합계)],
    ['부가세 예상 납부', c => 돈(c.v.부가세)],
    ['세후 영업이익', c => 돈(c.v.세후영업이익)],
    ['세율 구간', c => `<small>${esc(c.v.구간설명)}</small>`]
  ];
  $('#scenario-table thead').innerHTML = '<tr><th>항목</th>' + 열.map(c =>
    `<th class="${c.실적 ? '' : 'scenario'} ${c.기본 ? 'is-base' : ''}"${c.id != null ? ` data-scn="${c.id}"` : ''}>${esc(c.이름)}<small>${c.실적 ? '기준연도' : esc(c.부제) + ' · ' + 예 + '년'}</small></th>`).join('') + '</tr>';
  $('#scenario-table tbody').innerHTML = 행.map(([라벨, f]) =>
    `<tr><td>${라벨}</td>${열.map(c => `<td class="${c.기본 ? 'is-base' : ''}">${f(c)}</td>`).join('')}</tr>`).join('');
  $('#analysis-title').textContent = `${예}년 시나리오 비교 — 보수 · 기본 · 낙관`;
}
function 렌더_분석() {
  const 분 = 상태.분석결과;
  $('#analysis-empty').hidden = !!분;
  $('#analysis-content').hidden = !분;
  if (!분) return;
  const 예 = 분.예측연도, 실 = 분.실적, y = 연도목록()[2];
  $('#analysis-desc').textContent = `${상태.기업정보.회사명 ? 상태.기업정보.회사명 + ' · ' : ''}기준연도 ${y}년 실적을 바탕으로 ${예}년을 예측했습니다. 인건비·감가상각비는 고정, 나머지 비용은 매출과 같은 비율로 움직인다고 가정합니다.`
    + (분.비용구조경고 ? ' ⚠ 영업이익+인건비+감가상각비가 매출보다 커서 비용 구조를 확인해 주세요.' : '');
  렌더_KPI();
  세로막대차트($('#chart-sales'), [{ label: `${y}년 실적`, value: 실.매출, kind: 'ref' }, ...분.시나리오.map(s => ({ label: s.이름, sub: `${예}년`, value: s.매출, kind: 'fc' }))]);
  세로막대차트($('#chart-profit'), [{ label: `${y}년 실적`, value: 실.영업이익, kind: 'ref' }, ...분.시나리오.map(s => ({ label: s.이름, sub: `${예}년`, value: s.영업이익, kind: 'fc' }))]);
  렌더_시나리오표();
  렌더_분기표();
  렌더_업종비교();
}
// 분기별 표 (연간 ÷ 4 균등) + 부가세 신고 일정. 시나리오는 툴바 세그먼트(#scenario-switch)로 선택
function 렌더_분기표() {
  const 분 = 상태.분석결과; if (!분) return;
  const s = 선택시나리오();
  $$('#scenario-switch button').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.scn) === s.id)));
  $('#quarter-scn').textContent = `${s.이름} 시나리오 · ${분.예측연도}년`;
  const 일정 = (데이터.세무규칙.부가가치세 && 데이터.세무규칙.부가가치세.법인_신고일정) || [];
  const 분기명 = ['1분기 (1~3월)', '2분기 (4~6월)', '3분기 (7~9월)', '4분기 (10~12월)'];
  $('#quarter-table thead').innerHTML = `<tr><th>분기</th><th>예상 매출</th><th>예상 영업이익</th><th>부가세 예상 납부</th><th class="left">신고·납부 시기</th></tr>`;
  $('#quarter-table tbody').innerHTML = 분기명.map((q, i) => `
    <tr><td>${q}</td><td class="num">${요약금액(s.분기.매출)}</td><td class="num">${요약금액(s.분기.영업이익)}</td><td class="num">${요약금액(s.분기.부가세)}</td><td class="left small muted">${esc(일정[i] ? `${일정[i].구분} · ${일정[i].신고납부}` : '-')}</td></tr>`).join('')
    + `<tr class="is-total"><td>연간 합계</td><td class="num">${요약금액(s.매출)}</td><td class="num">${요약금액(s.영업이익)}</td><td class="num">${요약금액(s.부가세)}</td><td class="left small muted">법인세 ${요약금액(s.세부담합계)}: 다음 해 3월 신고 (8월 중간예납)</td></tr>`;
  $('#quarter-note').textContent = `${s.이름} 시나리오 · 연간 예측치를 4로 나눈 균등 배분입니다 (계절성 미반영). ${(데이터.세무규칙.부가가치세 || {}).참고 || ''}`;
}
// 지표별 한 줄 해석 (분석·개요 공용)
function 업종해석(지표, d) {
  const 해석 = {
    영업이익률: d > 0 ? '업종 평균보다 수익성이 높습니다.' : '업종 평균보다 수익성이 낮습니다. 원가·판관비 점검이 필요할 수 있습니다.',
    인건비비율: d > 0 ? '매출 대비 인건비 비중이 업종 평균보다 높습니다. 고용 관련 세액공제 활용 여지가 큽니다.' : '인건비 비중이 업종 평균 이하입니다.',
    매출증가율: d > 0 ? '업종 평균보다 빠르게 성장하고 있습니다.' : '성장률이 업종 평균에 못 미칩니다.',
    감가상각비율: d > 0 ? '설비 비중이 높은 편입니다. 투자세액공제·사후관리를 함께 챙기세요.' : '설비 비중이 업종 평균보다 낮습니다.'
  };
  return 해석[지표] || '';
}
// 업종 평균 비교: 가로 쌍 막대 + 해석 표
function 렌더_업종비교() {
  const 비 = 상태.분석결과 && 상태.분석결과.업종비교; if (!비) return;
  $('#industry-hint').textContent = 비.업종 ? `${비.업종.이름} 평균 (${데이터.업종평균.출처 || '샘플값'})` : '업종 평균 데이터 없음';
  가로쌍막대차트($('#chart-industry'), 비.행, 비.업종 && 비.업종.이름);
  $('#industry-comments tbody').innerHTML = 비.행.map(r => {
    if (!Number.isFinite(r.평균)) return `<tr><td>${esc(r.지표)}</td><td class="num">${퍼센트(r.우리)}</td><td colspan="3" class="left muted">데이터 없음</td></tr>`;
    const d = r.우리 - r.평균;
    return `<tr><td>${esc(r.지표)}</td><td class="num"><b>${퍼센트(r.우리)}</b></td><td class="num">${퍼센트(r.평균)}</td><td class="num delta ${d >= 0 ? 'up' : 'down'}">${d >= 0 ? '+' : ''}${쉼표(d, 1)}p</td><td class="left wrap small">${업종해석(r.지표, d)}</td></tr>`;
  }).join('');
}

/* ---------------------------------------------------------------------
   [JS 11] 렌더 — 절세전략 화면 (요약 KPI 3 · 전략 표 + 확장 행)
   --------------------------------------------------------------------- */
function 렌더_절세() {
  const 절 = 상태.절세결과;
  $('#tax-empty').hidden = !!절;
  $('#tax-content').hidden = !절;
  if (!절) return;
  const 예 = 예측연도();
  $('#tax-desc').textContent = `${예}년 계획(채용 ${상태.내년계획.상시근로자증감 || 0}명 · 설비투자 ${요약금액(상태.내년계획.설비투자계획액 || 0)} · 임금 인상 ${퍼센트(상태.내년계획.임금인상률 || 0)})을 기준으로 계산했습니다. 계획을 바꾸면 절감액이 달라집니다.`;
  $('#tax-summary').innerHTML = [
    KPI타일('적용 가능한 전략', `${절.적용수} <span class="muted" style="font-size:var(--fs-p1)">/ ${절.전략.length}개</span>`, '내년 계획 기준'),
    KPI타일(`${예}년 절감 예상액 (1년차)`, 원단위표시(절.총절감), 요약금액_원(절.총절감), { 강조: true }),
    KPI타일('기본 시나리오 세부담 → 공제 후', `${요약금액_원(절.기본시나리오_세부담)} → ${요약금액_원(절.반영후_세부담)}`, 절.공제한도초과 ? '공제액이 법인세를 넘어 일부는 이월(10년) 대상입니다' : '세액공제는 법인세에서 차감, 지방소득세는 그대로', { 작게: true })
  ].join('');
  $('#strategy-body').innerHTML = 절.전략.map(s => `
    <tr class="strategy" data-strategy="${s.id}">
      <td class="left wrap"><b>${esc(s.이름)}</b><small>${esc(s.근거)}</small></td>
      <td><span class="badge ${s.적용가능 ? 'badge--ok' : 'badge--no'}">${s.적용가능 ? '✓ 적용 가능' : '적용 불가'}</span></td>
      <td class="num" data-label="절감 예상액">${s.적용가능 ? `<b>${원단위표시(s.절감액)}</b>` : '<span class="muted">0원</span>'}</td>
      <td class="num" data-label="3년 누계">${s.누계3년 ? 원단위표시(s.누계3년) : '<span class="muted">-</span>'}</td>
      <td class="left wrap">${esc(s.요약)}</td>
      <td><button type="button" class="collapse__btn" aria-expanded="false" aria-controls="detail-${s.id}">자세히</button></td>
    </tr>
    <tr class="strategy__detail">
      <td colspan="6"><div class="collapse__body" id="detail-${s.id}">
        <dl>
          <dt>적용 조건</dt><dd><ul>${s.조건.map(c => `<li>${esc(c)}</li>`).join('')}</ul></dd>
          <dt>계산 근거</dt><dd><ol>${s.계산근거.map(c => `<li>${esc(c)}</li>`).join('')}</ol></dd>
          <dt>주의</dt><dd>${esc(s.주의)}</dd>
        </dl>
      </div></td>
    </tr>`).join('');
  $('#tax-disclaimer').textContent = (데이터.세무규칙.면책문구 || '') + ` (세제 기준연도 ${데이터.세무규칙.기준연도 || ''}, 확인일 ${데이터.세무규칙.확인일 || ''})`;
  $$('#strategy-body .collapse__btn').forEach(btn => btn.addEventListener('click', () => {
    const open = btn.getAttribute('aria-expanded') !== 'true';
    btn.setAttribute('aria-expanded', String(open)); btn.textContent = open ? '접기' : '자세히';
    const body = $('#' + btn.getAttribute('aria-controls'));
    body.classList.toggle('is-open', open); body.closest('tr').classList.toggle('is-open', open);
  }));
}

/* ---------------------------------------------------------------------
   [JS 12] 지원사업 — 정규화 · 필터 · 표 렌더 · 기업마당 Open API(프록시)
   --------------------------------------------------------------------- */
// 공고 1건을 화면용으로 정규화 (샘플 JSON과 기업마당 API 응답 모두 처리)
function 공고정규화(raw) {
  const 기간 = String(raw.reqstBeginEndDe || '');
  const [시작s, 끝s] = 기간.split('~').map(s => s && s.trim());
  const 텍스트 = `${raw.pblancNm || ''} ${raw.hashtags || ''} ${raw.jrsdInsttNm || ''} ${raw.excInsttNm || ''}`;
  let region = raw.region;
  if (!region) region = /광주/.test(텍스트) ? '광주' : /전남|전라남도/.test(텍스트) ? '전남' : '전국';
  let url = raw.pblancUrl || '';
  if (url && url.startsWith('/')) url = 'https://www.bizinfo.go.kr' + url;
  return {
    id: raw.pblancId || raw.pblancNm, 제목: raw.pblancNm || '(제목 없음)', 소관: raw.jrsdInsttNm || '', 수행: raw.excInsttNm || '',
    분야: raw.pldirSportRealmLclasCodeNm || '기타', 대상: raw.trgetNm || '', 요약: raw.bsnsSumryCn || '', 태그: raw.hashtags || '',
    시작: 날짜파싱(시작s), 끝: 날짜파싱(끝s), 기간원문: 기간, url, region
  };
}
function 현재공고목록() {
  const 설 = 상태.지원사업설정;
  if (설.소스 === 'api' && Array.isArray(설.캐시) && 설.캐시.length) return 설.캐시.map(공고정규화);
  return (데이터.지원사업.공고 || []).map(공고정규화);
}
// D-day 계산: 양수 = 남은 일수, 0 = 오늘 마감, 음수 = 마감됨, null = 기간 없음(상시)
function 디데이(끝) {
  if (!끝) return null;
  const 오늘 = new Date(); 오늘.setHours(0, 0, 0, 0);
  return Math.round((끝 - 오늘) / 86_400_000);
}
// 필터·정렬을 적용한 공고 목록 (지원사업 화면 · 개요 화면 공용)
function 필터된공고목록() {
  const 설 = 상태.지원사업설정;
  let 목록 = 현재공고목록();
  if (설.지역 && 설.지역 !== 'all') 목록 = 목록.filter(g => 설.지역 === '전국' ? g.region === '전국' : (g.region === 설.지역 || g.region === '전국'));
  if (설.분야 && 설.분야 !== 'all') 목록 = 목록.filter(g => g.분야 === 설.분야);
  if (설.마감숨김 !== false) 목록 = 목록.filter(g => { const d = 디데이(g.끝); return d === null || d >= 0; });
  if (설.정렬 === 'latest') 목록.sort((a, b) => (b.시작 ? b.시작.getTime() : 0) - (a.시작 ? a.시작.getTime() : 0));
  else 목록.sort((a, b) => { const da = 디데이(a.끝), db = 디데이(b.끝); const ka = da === null ? 9e9 : (da < 0 ? 8e9 - da : da), kb = db === null ? 9e9 : (db < 0 ? 8e9 - db : db); return ka - kb; });
  return 목록;
}
// D-day 배지 HTML
function 디데이배지(끝) {
  const d = 디데이(끝);
  if (d === null) return '<span class="badge badge--open">상시</span>';
  if (d < 0) return '<span class="badge badge--closed">마감</span>';
  if (d === 0) return '<span class="badge badge--urgent">오늘 마감</span>';
  return `<span class="badge ${d <= 7 ? 'badge--urgent' : d <= 30 ? 'badge--soon' : 'badge--open'}">D-${d}</span>`;
}
// 공고 표 HTML (지원사업 화면 전체 목록 / 개요 임박 3건 — 간단 모드는 소관·요약 생략)
function 공고표(목록, { 간단 = false } = {}) {
  const 행 = 목록.map(g => `<tr class="support">
      <td>${디데이배지(g.끝)}</td>
      <td class="left wrap">${g.url ? `<a class="support__title" href="${esc(g.url)}" target="_blank" rel="noopener">${esc(g.제목)}</a>` : `<span class="support__title">${esc(g.제목)}</span>`}${!간단 && g.요약 ? `<small>${esc(g.요약)}</small>` : ''}${!간단 && g.대상 ? `<small>대상: ${esc(g.대상)}</small>` : ''}</td>
      <td class="left"><span class="chip">${esc(g.분야)}</span></td>
      <td class="left" data-label="지역">${esc(g.region)}</td>
      ${간단 ? '' : `<td class="left" data-label="소관">${esc(g.소관 || '-')}${g.수행 ? `<small>수행: ${esc(g.수행)}</small>` : ''}</td>`}
      <td class="left small muted" data-label="신청">${g.시작 || g.끝 ? `${날짜표시(g.시작)} ~ ${날짜표시(g.끝)}` : esc(g.기간원문 || '상시')}</td>
    </tr>`).join('');
  return `<div class="table-wrap"><table class="data supports"><thead><tr><th>마감</th><th class="left">공고</th><th class="left">분야</th><th class="left">지역</th>${간단 ? '' : '<th class="left">소관</th>'}<th class="left">신청기간</th></tr></thead><tbody>${행}</tbody></table></div>`;
}
function 렌더_지원사업() {
  const 설 = 상태.지원사업설정;
  $('#s-region').value = 설.지역 || 'all'; $('#s-field').value = 설.분야 || 'all'; $('#s-sort').value = 설.정렬 || 'deadline';
  $('#s-hide-closed').checked = 설.마감숨김 !== false; $('#s-api-key').value = 설.인증키 || '';
  const src = $('#support-source');
  src.className = 'chip ' + (설.소스 === 'api' ? 'chip--primary' : 'chip--muted');
  src.innerHTML = `<span class="chip__dot"></span>${설.소스 === 'api' ? `기업마당 실시간 (${설.캐시시각 ? 날짜표시(new Date(설.캐시시각)) : ''})` : '샘플 데이터 (가상 공고)'}`;
  const 목록 = 필터된공고목록();
  $('#support-count').textContent = `${목록.length}건 표시 중` + (설.지역 && 설.지역 !== 'all' ? ` · 지역: ${설.지역}` : '') + (설.분야 !== 'all' ? ` · 분야: ${설.분야}` : '');
  if (!목록.length) { $('#support-list').innerHTML = `<div class="card empty"><p class="empty__title">조건에 맞는 공고가 없습니다</p><p>지역·분야 필터를 바꾸거나 '마감된 공고 숨기기'를 해제해 보세요.</p></div>`; return; }
  $('#support-list').innerHTML = `<div class="card card--table">${공고표(목록)}</div>`;
}
// 기업마당 지원사업정보 Open API 호출 (인증키 필요). 실패하면 예외 → 호출한 곳에서 샘플로 대체
async function 기업마당_불러오기(인증키) {
  const params = new URLSearchParams({ crtfcKey: 인증키, dataType: 'json', searchCnt: '100' });
  const 지역 = 소재지_지역필터[상태.기업정보.소재지];
  if (지역 && 지역 !== '전국') params.set('hashtags', 지역);
  // http(s)로 열렸으면(vercel dev·배포 주소) 같은 서버의 프록시 /api/bizinfo 를, 더블클릭(file://)이면 기업마당을 직접 호출
  const 프록시사용 = location.protocol === 'http:' || location.protocol === 'https:';
  const url = (프록시사용 ? '/api/bizinfo?' : 'https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do?') + params.toString();
  const ctrl = new AbortController(); const timer = setTimeout(() => ctrl.abort(), 10_000);
  try {
    const res = await fetch(url, { signal: ctrl.signal });
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try { const j = await res.json(); if (j && j.error) msg = j.error + (j.detail ? ` (${j.detail})` : ''); } catch (_) { /* JSON 아님 → 상태코드만 표시 */ }
      throw new Error(msg);
    }
    const json = await res.json();
    if (json && json.reqErr) throw new Error('기업마당: ' + json.reqErr);   // 예: "존재하지 않는 인증키 입니다." (HTTP 200으로 옴)
    const list = json.jsonArray || json.items || json.item || (Array.isArray(json) ? json : null);
    if (!Array.isArray(list)) throw new Error('응답 형식을 해석할 수 없습니다 (jsonArray 없음)');
    return list;
  } finally { clearTimeout(timer); }
}
function 바인딩_지원사업() {
  const 설 = 상태.지원사업설정;
  const 저장후렌더 = () => { 저장_지원사업설정(); 렌더_지원사업(); };
  $('#s-region').addEventListener('change', e => { 설.지역 = e.target.value; 저장후렌더(); });
  $('#s-field').addEventListener('change', e => { 설.분야 = e.target.value; 저장후렌더(); });
  $('#s-sort').addEventListener('change', e => { 설.정렬 = e.target.value; 저장후렌더(); });
  $('#s-hide-closed').addEventListener('change', e => { 설.마감숨김 = e.target.checked; 저장후렌더(); });
  $('#s-api-key').addEventListener('input', e => { 설.인증키 = e.target.value.trim(); 저장_지원사업설정(); });
  $('#btn-api-sample').addEventListener('click', () => { 설.소스 = 'sample'; 설.캐시 = null; $('#api-status').hidden = true; 저장후렌더(); });
  $('#btn-api-load').addEventListener('click', async () => {
    $('#api-panel').open = true;
    const st = $('#api-status'); st.hidden = false; st.className = 'note';
    if (!설.인증키) { st.textContent = '인증키를 먼저 입력하세요. 기업마당 로그인 → 활용정보 → 정책정보 개방 → 지원사업정보 API → 인증키 신청.'; return; }
    st.textContent = '기업마당에서 공고를 불러오는 중…';
    const btn = $('#btn-api-load'); btn.disabled = true;
    try {
      const list = await 기업마당_불러오기(설.인증키);
      설.소스 = 'api'; 설.캐시 = list; 설.캐시시각 = new Date().toISOString();
      st.textContent = `기업마당 공고 ${list.length}건을 불러왔습니다.`;
      저장후렌더(); 토스트(`기업마당 공고 ${list.length}건 불러오기 완료`);
    } catch (e) {
      설.소스 = 'sample'; 설.캐시 = null;
      st.className = 'note note--warn';
      st.textContent = `기업마당 API 호출에 실패해 샘플 데이터를 표시합니다. 원인: ${e.name === 'AbortError' ? '응답 시간 초과' : e.message}. 더블클릭(file://)으로 열면 보안정책(CORS)에 막힐 수 있습니다 — vercel dev 또는 배포 주소에서 열면 서버 프록시(/api/bizinfo)로 호출됩니다.`;
      저장후렌더();
    } finally { btn.disabled = false; }
  });
}

/* ---------------------------------------------------------------------
   [JS 12.5] 렌더 — 개요 화면 (Task 3에서 완성. 여기서는 빈 상태/내용 전환만)
   --------------------------------------------------------------------- */
function 렌더_개요() {
  const 분 = 상태.분석결과;
  $('#overview-empty').hidden = !!분;
  $('#overview-content').hidden = !분;
}

/* ---------------------------------------------------------------------
   [JS 13] 화면 이동(사이드바·하단 탭바) · 툴바 · 완료 점 · 입력 진행률 · 다이얼로그 · 토스트
   --------------------------------------------------------------------- */
const 화면순서 = ['overview', 'input', 'analysis', 'tax', 'support'];
const 화면정보 = {
  overview: { 제목: '개요', 설명: '내년 예측 · 세금 · 절세 · 지원사업을 한눈에', 시나리오: true },
  input:    { 제목: '입력', 설명: '기업정보 · 최근 3개년 재무데이터 · 내년 계획 (금액 백만원)' },
  analysis: { 제목: '분석결과', 설명: '3개 시나리오 예측 · 세금 · 분기 · 업종 비교', 시나리오: true },
  tax:      { 제목: '절세전략', 설명: '내년 계획 기준 적용 가능 여부와 절감 예상액' },
  support:  { 제목: '지원사업', 설명: '소재지 기준 필터 · 마감 임박순 · 기업마당 연동' }
};
// 현재 보고 있는 화면 id (사이드바 aria-current 기준)
function 현재화면() { const b = $('.nav[aria-current="page"]'); return b ? b.dataset.nav : 'overview'; }
// 화면 이동: 패널 표시, 사이드바·하단 탭바 aria-current, 툴바 제목·세그먼트, 해당 화면 렌더. (이름은 예전 탭 시절 그대로 유지)
function 탭이동(id) {
  if (!화면정보[id]) id = 'overview';
  화면순서.forEach(t => { $(`#panel-${t}`).hidden = t !== id; });
  $$('.nav[data-nav], .bottombar__item[data-nav]').forEach(b => { if (b.dataset.nav === id) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current'); });
  $('#page-title').textContent = 화면정보[id].제목; $('#page-desc').textContent = 화면정보[id].설명;
  $('#scenario-switch').hidden = !(화면정보[id].시나리오 && 상태.분석결과);
  if (id === 'overview') 렌더_개요();
  if (id === 'analysis') 렌더_분석();
  if (id === 'tax') 렌더_절세();
  if (id === 'support') 렌더_지원사업();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
// 완료 점(입력·분석·절세) + 툴바 칩 + 시나리오 세그먼트 표시 여부 + 입력 진행률
function 갱신_탭상태() {
  const 완료 = { input: 입력완료여부(), analysis: !!상태.분석결과, tax: !!상태.절세결과 };
  $$('.nav[data-nav], .bottombar__item[data-nav]').forEach(b => b.classList.toggle('is-done', !!완료[b.dataset.nav]));
  const 회사 = $('#company-chip'); 회사.hidden = !상태.기업정보.회사명; 회사.textContent = 상태.기업정보.회사명 || '';
  $('#year-chip').textContent = `예측 ${예측연도()}년`;
  const 정보 = 화면정보[현재화면()];
  $('#scenario-switch').hidden = !(상태.분석결과 && 정보 && 정보.시나리오);
  갱신_입력진행();
}
// 입력 진행률: 필수 재무 5항목 × 3개년(15) + 상시근로자 + 업종 + 소재지 = 18
function 갱신_입력진행() {
  const 필수 = 재무항목.filter(a => a.required);
  const 총 = 필수.length * 3 + 3;
  let 채움 = 0;
  필수.forEach(a => (상태.재무데이터[a.key] || []).forEach(v => { if (typeof v === 'number' && Number.isFinite(v)) 채움++; }));
  if (Number.isInteger(상태.기업정보.상시근로자수)) 채움++;
  if (상태.기업정보.업종) 채움++;
  if (상태.기업정보.소재지) 채움++;
  $('#input-progress').textContent = `${채움} / ${총}`;
  $('#input-progress-bar').style.width = `${Math.round(채움 / 총 * 100)}%`;
  const 업 = (데이터.업종평균.업종 || []).find(u => u.코드 === 상태.기업정보.업종);
  $('#input-summary').innerHTML = [
    ['회사명', 상태.기업정보.회사명 || '-'], ['업종', 업 ? 업.이름 : '-'], ['소재지', 소재지이름[상태.기업정보.소재지] || '-'],
    ['기준연도 → 예측', `${연도목록()[2]}년 → ${예측연도()}년`], ['상태', 상태.분석결과 ? '분석 완료' : (입력완료여부() ? '분석 준비됨' : '입력 중')]
  ].map(([k, v]) => `<li><span class="muted">${k}</span><b>${esc(v)}</b></li>`).join('');
}
// 시나리오 세그먼트가 바뀌면 다시 그릴 것들
function 렌더_시나리오의존() { if (!상태.분석결과) return; 렌더_KPI(); 렌더_분기표(); 렌더_개요(); }
function 바인딩_탭() {
  $$('[data-nav]').forEach(b => b.addEventListener('click', () => 탭이동(b.dataset.nav)));
  // 사이드바 메뉴: 위/아래 화살표·Home·End 로 이동
  $('.sidebar__nav').addEventListener('keydown', e => {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return;
    const cur = 화면순서.indexOf(현재화면()); let next = cur;
    if (e.key === 'ArrowDown') next = (cur + 1) % 화면순서.length;
    if (e.key === 'ArrowUp') next = (cur - 1 + 화면순서.length) % 화면순서.length;
    if (e.key === 'Home') next = 0; if (e.key === 'End') next = 화면순서.length - 1;
    탭이동(화면순서[next]); $(`#nav-${화면순서[next]}`).focus(); e.preventDefault();
  });
  $$('[data-goto]').forEach(b => b.addEventListener('click', () => 탭이동(b.dataset.goto)));
  $$('#scenario-switch button').forEach(b => b.addEventListener('click', () => { 상태.선택시나리오 = Number(b.dataset.scn); 렌더_시나리오의존(); }));
}
// 자체 확인 다이얼로그 (window.confirm 대체)
let 다이얼로그콜백 = null;
function 확인다이얼로그(제목, 설명, onOk) {
  $('#dialog-title').textContent = 제목; $('#dialog-desc').textContent = 설명; 다이얼로그콜백 = onOk;
  $('#dialog').hidden = false; $('#dialog-ok').focus();
}
function 다이얼로그닫기() { $('#dialog').hidden = true; 다이얼로그콜백 = null; }
function 바인딩_다이얼로그() {
  $('#dialog-cancel').addEventListener('click', 다이얼로그닫기);
  $('#dialog-ok').addEventListener('click', () => { const cb = 다이얼로그콜백; 다이얼로그닫기(); if (cb) cb(); });
  $('#dialog').addEventListener('click', e => { if (e.target === e.currentTarget) 다이얼로그닫기(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('#dialog').hidden) 다이얼로그닫기(); });
}
let 토스트타이머;
function 토스트(msg) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(토스트타이머); 토스트타이머 = setTimeout(() => { t.hidden = true; }, 3200);
}

```

5-b. [JS 14]의 `function 바인딩_푸터() { … }` 전체를 아래로 교체:
```js
// 액션 버튼 (사이드바 + 모바일 하단 공용): data-action = csv | print | reset
function 바인딩_액션() {
  $$('[data-action]').forEach(b => b.addEventListener('click', () => {
    if (b.dataset.action === 'csv') CSV내보내기();
    if (b.dataset.action === 'print') window.print();
    if (b.dataset.action === 'reset') 확인다이얼로그('저장된 데이터를 모두 지울까요?', '이 브라우저에 저장된 재무제표·절세전략·지원사업 검색 설정이 모두 삭제됩니다. 되돌릴 수 없습니다.', 데이터초기화);
  }));
}
```

5-c. [JS 15] `function 시작() { … }` 전체를 아래로 교체:
```js
function 시작() {
  렌더_업종선택();
  const 저장됨 = 불러오기_재무제표();
  불러오기_지원사업설정();
  폼채우기();
  폼읽기();
  if (저장됨) { 저장상태표시(저장됨.저장시각); if (입력완료여부()) { 계산_전체(); } }
  $('#footer-disclaimer').textContent = '※ ' + (데이터.세무규칙.면책문구 || '세금·공제 금액은 단순 추정치입니다.');
  $('#sidebar-caption').textContent = `세제 기준연도 ${데이터.세무규칙.기준연도 || '-'} · 확인일 ${데이터.세무규칙.확인일 || '-'} · 광주·전남 중소기업 재무 내비게이터`;
  바인딩_입력폼(); 바인딩_탭(); 바인딩_다이얼로그(); 바인딩_액션(); 바인딩_지원사업();
  갱신_탭상태(); 렌더_분석(); 렌더_절세(); 렌더_지원사업();
  탭이동('overview');   // 기본 진입 화면 = 개요 (데이터 없으면 빈 상태 + '입력 시작' 버튼)
}
```
5-d. [JS 0] 앱 개요 주석의 `- 화면 순서: 입력 → 분석 → 절세 → 지원사업 (탭)` 을 `- 화면 5개: 개요 · 입력 · 분석 · 절세 · 지원사업 (좌측 사이드바 / 모바일 하단 탭바)` 로 수정.

- [x] **Step 6: 검증 실행 — 개요 5건(Task 3)만 FAIL, 나머지 전부 PASS**

Run: `cd ~/Desktop/택스네비 && python3 tools/test-e2e.py 2>&1 | grep -E "^FAIL|총 "`
Expected: `FAIL 개요: …` 5줄만 출력되고 `총 N개 검사, 실패 5개`. 다른 FAIL이 있으면 해당 렌더/CSS를 고친 뒤 재실행.

---

### Task 3: 개요 화면 — 세금 일정 데이터 + `렌더_개요` 완성

**Files:**
- Modify: `docs/tax-rules.json` — `법인세.신고일정` 추가 → `node tools/inline-data.js`
- Modify: `index.html` — [JS 12.5] `렌더_개요` 자리표시자를 아래 코드로 교체
- Test: `python3 tools/test-e2e.py` (Task 2 Step 1의 "개요" 5건이 통과해야 함)

**Interfaces:**
- Consumes: `선택시나리오()`, `KPI타일()`, `필터된공고목록()`, `공고표(목록, {간단:true})`, `업종해석()`, `디데이()`, `날짜표시()`, `데이터.세무규칙.부가가치세.법인_신고일정[{구분, 대상기간, 신고납부}]`, `데이터.세무규칙.법인세.신고일정[{구분, 신고납부, 참고}]`
- Produces: `일정날짜(문자열, 오늘) → Date|null`, `다가오는일정(시나리오, 개수) → [{날짜, 이름, 대상, 금액(백만원)}]`, `렌더_개요()`

- [x] **Step 1: 검증 실행해 개요 5건 FAIL 확인**

Run: `cd ~/Desktop/택스네비 && python3 tools/test-e2e.py 2>&1 | grep -E "^FAIL 개요"`
Expected: `FAIL 개요: KPI 4개` 등 5줄

- [x] **Step 2: `docs/tax-rules.json` 법인세에 신고일정 추가 (숫자는 JSON에만)**

Run:
```bash
cd ~/Desktop/택스네비 && python3 - <<'PY'
import json, io
p = 'docs/tax-rules.json'
j = json.load(open(p, encoding='utf-8'))
j['법인세']['신고일정'] = [
  {"구분": "확정 신고·납부", "신고납부": "3월 31일", "참고": "12월 결산법인 기준 — 사업연도 종료 후 3개월 이내 (법인세법 제60조)"},
  {"구분": "중간예납", "신고납부": "8월 31일", "참고": "직전 사업연도 산출세액의 1/2 기준 추정 (법인세법 제63조)"}
]
json.dump(j, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
PY
node tools/inline-data.js && grep -c '"신고일정"' index.html
```
Expected: inline-data.js 성공 메시지, `1`

- [x] **Step 3: `렌더_개요` 교체 — [JS 12.5] 블록 전체를 아래로**

```js
/* ---------------------------------------------------------------------
   [JS 12.5] 렌더 — 개요 화면 (KPI 4 · 시나리오 비교 · 세금 일정 · 임박 공고 · 업종 대비)
   --------------------------------------------------------------------- */
// 세무규칙의 일정 문자열("4월 25일", "다음 해 1월 25일") → 오늘 이후 가장 가까운 해당 날짜
function 일정날짜(문자열, 오늘) {
  const m = String(문자열).match(/(\d{1,2})월\s*(\d{1,2})일/); if (!m) return null;
  for (const y of [오늘.getFullYear(), 오늘.getFullYear() + 1]) {
    const d = new Date(y, Number(m[1]) - 1, Number(m[2]));
    if (d >= 오늘) return d;
  }
  return null;
}
// 다가오는 세금 일정 N건: 부가세 신고 4회 + 법인세 확정·중간예납. 금액은 선택 시나리오 추정치(백만원)
function 다가오는일정(s, 개수 = 3) {
  const 오늘 = new Date(); 오늘.setHours(0, 0, 0, 0);
  const 부 = 데이터.세무규칙.부가가치세 || {}, 법 = 데이터.세무규칙.법인세 || {};
  const 후보 = [];
  (부.법인_신고일정 || []).forEach(j => { const d = 일정날짜(j.신고납부, 오늘); if (d) 후보.push({ 날짜: d, 이름: `부가세 ${j.구분} 신고·납부`, 대상: `${j.대상기간} 실적분 · 분기 추정`, 금액: s.분기.부가세 }); });
  (법.신고일정 || []).forEach(j => { const d = 일정날짜(j.신고납부, 오늘); if (!d) return; const 중간 = /중간/.test(j.구분); 후보.push({ 날짜: d, 이름: `법인세 ${j.구분}`, 대상: 중간 ? '전년 법인세의 약 1/2 추정' : '법인세 + 지방소득세 추정', 금액: 중간 ? s.법인세 / 2 : s.세부담합계 }); });
  return 후보.sort((a, b) => a.날짜 - b.날짜).slice(0, 개수);
}
function 렌더_개요() {
  const 분 = 상태.분석결과, 절 = 상태.절세결과;
  $('#overview-empty').hidden = !!분;
  $('#overview-content').hidden = !분;
  if (!분) return;
  const s = 선택시나리오(), 실 = 분.실적, 예 = 분.예측연도;
  // KPI 4개 (선택 시나리오 기준). 절세 반영 후 세부담은 기본 시나리오에서만 계산되어 있음
  $('#overview-kpis').innerHTML = [
    KPI타일(`${예}년 예상 매출 (${s.이름})`, 요약금액(s.매출), `<span class="delta ${s.매출 >= 실.매출 ? 'up' : 'down'}">${증감표시(s.매출, 실.매출)}</span> vs ${연도목록()[2]}년 실적 ${요약금액(실.매출)}`),
    KPI타일('예상 영업이익', 요약금액(s.영업이익), `영업이익률 ${퍼센트(s.영업이익률)}`, { 음수: s.영업이익 < 0 }),
    KPI타일('예상 세부담 (법인세+지방소득세)', 요약금액(s.세부담합계), 절 && s.id === 1 ? `절세 반영 후 ${요약금액_원(절.반영후_세부담)}` : `부가세 별도 ${요약금액(s.부가세)}`),
    KPI타일('절세 예상액 (1년차)', 절 ? 요약금액_원(절.총절감) : '-', 절 ? `${절.적용수} / ${절.전략.length}개 전략 적용 가능` : '', { 강조: true })
  ].join('');
  // 시나리오 비교 미니표 + 매출 가로 막대 (시리즈 1개 → 색 1개, 선택 행은 굵게)
  $('#overview-scn-hint').textContent = `${예}년 · 선택: ${s.이름}`;
  $('#overview-scn-table thead').innerHTML = '<tr><th>시나리오</th><th>매출</th><th>영업이익</th><th>세부담</th><th>부가세</th></tr>';
  $('#overview-scn-table tbody').innerHTML = 분.시나리오.map(x => `<tr class="${x.id === s.id ? 'is-total' : ''}"><td>${esc(x.이름)}<small>${esc(x.설명)}</small></td><td class="num">${요약금액(x.매출)}</td><td class="num ${x.영업이익 < 0 ? 'is-negative' : ''}">${요약금액(x.영업이익)}</td><td class="num">${요약금액(x.세부담합계)}</td><td class="num">${요약금액(x.부가세)}</td></tr>`).join('');
  const 최대 = Math.max(1, ...분.시나리오.map(x => x.매출));
  $('#overview-bars').innerHTML = 분.시나리오.map(x => `<div class="bars__row ${x.id === s.id ? 'is-selected' : ''}"><span>${esc(x.이름)}</span><div class="bars__track"><div class="bars__fill" style="width:${Math.max(2, x.매출 / 최대 * 100)}%"></div></div><span class="bars__val">${요약금액(x.매출)}</span></div>`).join('');
  // 다가오는 세금 일정 3건
  $('#overview-schedule').innerHTML = 다가오는일정(s, 3).map(j => `<li><span class="timeline__date">${날짜표시(j.날짜)}<small>D-${디데이(j.날짜)}</small></span><span class="timeline__name">${esc(j.이름)}<small>${esc(j.대상)}</small></span><span class="timeline__amt">${요약금액(j.금액)}</span></li>`).join('') || '<li class="muted">표시할 일정이 없습니다</li>';
  // 임박 공고 3건 (지원사업 화면의 현재 필터 그대로)
  const 공고 = 필터된공고목록().slice(0, 3);
  $('#overview-support').innerHTML = 공고.length ? 공고표(공고, { 간단: true }) : '<p class="muted small" style="padding:0 16px 16px">조건에 맞는 공고가 없습니다</p>';
  // 업종 대비 한 줄 (영업이익률)
  const 비 = 분.업종비교, r = 비 && 비.행.find(x => x.지표 === '영업이익률');
  if (r && Number.isFinite(r.평균)) {
    const d = r.우리 - r.평균;
    $('#overview-industry').innerHTML = `영업이익률 <b>${퍼센트(r.우리)}</b> — 업종 평균(${esc(비.업종.이름)}, ${esc(데이터.업종평균.출처 || '샘플값')}) ${퍼센트(r.평균)} 대비 <b class="delta ${d >= 0 ? 'up' : 'down'}">${d >= 0 ? '+' : ''}${쉼표(d, 1)}p</b>. ${업종해석('영업이익률', d)}`;
  } else $('#overview-industry').textContent = '업종 평균 데이터가 없습니다.';
}
```

- [x] **Step 4: 전체 검증 통과**

Run: `cd ~/Desktop/택스네비 && python3 tools/test-e2e.py 2>&1 | tail -3`
Expected: `총 N개 검사, 실패 0개` (N ≈ 70). 스크린샷 `tools/screenshots/desktop-1920-overview.png` 등을 열어 라벨 겹침·넘침을 눈으로 확인.

---

### Task 4: 문서 갱신 · Vercel 배포 · 배포 주소 검증 · 인증키 안내

**Files:**
- Modify: `STEERING.md`(2·4·8항), `SPECS.md`(2항 다이어그램, Task 13·14·19), `README.md`(실행·화면), `CLAUDE.md`(검증 한 줄), `DEVELOPMENT_LOG.md`(새 항목)
- Test: `vercel --prod` 후 `TEST_URL=<배포주소> python3 tools/test-e2e.py`

- [x] **Step 1: STEERING.md**
  - 2항 "외부 API" 항목: `서버 없이 브라우저에서 직접 호출하므로 …` 줄을 `→ **서버 프록시 `api/bizinfo.js`(Vercel 함수)** 로 호출. 로컬은 `vercel dev`, 배포는 `vercel --prod`. 더블클릭(file://)은 직접 호출 → CORS 실패 시 샘플 대체` 로, `2일차(EC2 서버) 이후…` 줄을 `EC2 대신 Vercel 함수로 CORS 해결 완료(2026-09-03)` 로 교체
  - 4항 "화면 구성": `상단 탭 4개…` → `좌측 다크 사이드바(≥1024px 240px / 768~1023px 아이콘 72px) + 라이트 본문 + 모바일(<768px) 하단 탭바. 화면 5개: 개요 · 입력 · 분석결과 · 절세전략 · 지원사업. 툴바(제목·회사/예측연도 칩·자동 저장·시나리오 세그먼트)`. 토큰 표에 `사이드바 배경/글자/활성 | --sidebar-bg/--sidebar-fg/--sidebar-active | gray-900 / gray-300 / primary-500 (기존 값 매핑)` 행 추가
  - 8항: 6번 항목을 `python3 tools/test-e2e.py` (file://) / `TEST_URL=http://localhost:3000 python3 tools/test-e2e.py` (vercel dev, 프록시 포함) 두 줄로
- [x] **Step 2: SPECS.md**
  - 2항 화면 설계 코드블록을 사이드바 5개 화면 다이어그램으로 교체(설계서 §3·§4 요약)
  - Task 13: `- [ ] Task 13: … (인증키 미발급 — 발급 절차 안내 완료, 사용자 발급 후 실호출 테스트 예정)`
  - Task 14: `- [x] Task 14: ~~EC2~~ Vercel 서버리스 함수 `api/bizinfo.js` 프록시로 CORS 해결 (2026-09-03)`
  - 추가: `- [x] Task 19: 대시보드 리디자인 — 사이드바 5화면·개요 화면·표 밀도형 UI, 검증 스크립트 갱신 (2026-09-03)`
- [x] **Step 3: README.md** "바로 실행" 을 3가지로: ① 더블클릭(샘플 데이터) ② `vercel dev` → http://localhost:3000 (기업마당 실호출) ③ `vercel --prod` 배포. "화면 구성" 표를 5개 화면으로.
- [x] **Step 4: CLAUDE.md** "작업 후" 검증 줄에 `(서버 포함 검증: vercel dev 실행 후 TEST_URL=http://localhost:3000 python3 tools/test-e2e.py)` 추가
- [x] **Step 5: 배포 → 배포 주소 검증**

Run:
```bash
cd ~/Desktop/택스네비 && vercel --prod --yes 2>&1 | tail -3
# 출력의 https://…vercel.app 주소로
TEST_URL=https://<배포주소> python3 tools/test-e2e.py 2>&1 | tail -3
```
Expected: `총 N개 검사, 실패 0개` (프록시 2건 포함)
- [x] **Step 6: DEVELOPMENT_LOG.md** 에 항목 추가: 날짜, 결정 사항(설계서 §2 표), 변경 요약(파일별), 검증 결과(file:// · localhost · 배포 주소 3회 실행 결과 수치), 배포 URL, 남은 과제(인증키 발급 후 실호출, Task 15~18). **인증키 값 기록 금지.**
- [x] **Step 7: 사용자에게 인증키 발급 절차 안내** (설계서 §6.4) — 발급 후 지원사업 화면 "기업마당 실시간 공고 연동" 패널에 입력 → "기업마당에서 불러오기" → 결과를 LOG에 기록

---

## 계획 자체 점검 (2026-09-03)

- **설계서 커버리지:** §3 앱 셸 → Task 2 Step 3·4 / §4.1 개요 → Task 3 / §4.2~4.5 → Task 2 Step 4·5 / §5 토큰 → Task 2 Step 3-a(새 hex 없음) / §6 프록시·배포 → Task 1·Task 4 Step 5 / §6.4 인증키 → Task 4 Step 7 / §7 검증 → Task 2 Step 1 / §8 문서 → Task 4
- **자리표시자 점검:** 코드 단계마다 전체 코드 수록. "TBD/TODO" 없음. Task 4 문서 단계는 교체 문구를 직접 명시
- **이름 일관성:** `탭이동`·`갱신_탭상태`(이름 유지) / `선택시나리오`·`KPI타일`·`렌더_KPI`·`렌더_시나리오표`·`업종해석`·`필터된공고목록`·`디데이배지`·`공고표`·`렌더_개요`·`일정날짜`·`다가오는일정`·`바인딩_액션`·`렌더_시나리오의존`·`현재화면`·`갱신_입력진행` — Task 2 정의, Task 3 사용 이름 동일. HTML id: `nav-*`·`mnav-*`·`scenario-switch`·`scenario-table`·`analysis-kpis`·`overview-*`·`strategy-body`·`api-panel`·`input-progress(-bar)`·`input-summary`·`company-chip`·`year-chip`·`page-title/desc`·`sidebar-caption`·`quarter-scn` — CSS·JS·테스트에서 같은 이름 사용
- **의도적 단순화:** 시나리오 선택은 저장하지 않음(새로고침 시 '기본') / 별도 server.js 없음 / 개요 막대는 HTML(시리즈 1개, dataviz 단일 색) / 법인세 중간예납 금액은 법인세의 1/2 단순 추정(화면에 '추정' 표기)
