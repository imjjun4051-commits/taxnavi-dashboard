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
        check('초기 화면: 재무 표 입력칸 42개(14항목×3개년, 매출원가·판관비·당기순이익 등 추가)', await page.locator('[data-fin]').count() == 42, str(await page.locator('[data-fin]').count()))
        check('초기 화면: 업종 6개', await page.locator('#f-industry option').count() == 6)
        check('입력: 진행률 표시(필수 18개 중)', '/ 18' in await page.inner_text('#input-progress'))

        # 샘플(데모) 데이터 불러오기 — 재무데이터 표 위 "자동 입력(샘플)" 세그먼트 사용
        # ("샘플 데이터 불러오기" 사이드바 버튼은 이제 ERP CSV 파일 선택창을 여는 용도로 바뀌었음)
        # "자동 입력(샘플)" 버튼은 화면에서 삭제됐고, 함수는 데모·검증용으로 남아 있어 직접 호출한다
        await page.evaluate('샘플불러오기()'); await page.wait_for_timeout(200)
        v = await page.input_value('[data-fin="매출액"][data-idx="2"]')
        check('샘플: 2025 매출액 5,100', v == '5,100', v)
        check('샘플: 회사명', await page.input_value('#f-company') == '샘플정밀(주)')
        check('샘플: 임금인상률 8', await page.input_value('#f-wage') == '8')
        check('입력: 진행률 18 / 18', '18 / 18' in await page.inner_text('#input-progress'))
        check('입력: 기준연도 직접 입력칸(2025)', await page.input_value('#f-base-year') == '2025')
        check('입력: 자동 입력(샘플) 세그먼트 삭제됨', await page.locator('#fin-mode-switch').count() == 0)
        await page.fill('#f-base-year', '2024'); await page.locator('#f-base-year').blur(); await page.wait_for_timeout(100)
        check('입력: 기준연도 변경 시 연도 헤더 갱신(2024년 기준)', '2024년 (기준)' in await page.inner_text('#fin-head'))
        await page.fill('#f-base-year', '2025'); await page.locator('#f-base-year').blur(); await page.wait_for_timeout(100)

        # 분석 시작
        await page.click('#btn-analyze'); await page.wait_for_timeout(400)
        check('분석: 분석 화면 표시', await page.is_visible('#panel-analysis') and await page.is_visible('#analysis-content'))
        check('분석: 정적 KPI 스트립 삭제됨(시뮬레이션으로 통합)', await page.locator('#analysis-kpis').count() == 0)
        tbl = await page.inner_text('#scenario-table')
        check('분석: 예측 표 열 1개(+실적, 보수·낙관 없음)', await page.locator('#scenario-table thead th.scenario').count() == 1)
        check('분석: 기본 매출 51억원', '51억원' in tbl, tbl[:80].replace('\n', ' '))
        check('분석: 기본 세부담 5,720만원(과세표준 380−이자 20=360 → 법인세 52,000,000 + 지방 5,200,000)', '5,720만원' in tbl and '52,000,000원' in tbl and '5,200,000원' in tbl, tbl[:200].replace('\n', ' '))
        check('분석: 기본 부가세 (5100-3150)*10% = 195 → 1.95억원', '1.95억원' in tbl)
        check('분석: 과세표준을 세전이익(당기순이익+법인세비용=360)으로 계산', '법인세차감전순이익' in tbl and '3.6억원' in tbl, tbl[:400].replace('\n', ' '))
        # 새 항목(매출원가·판관비·당기순이익·법인세비용·무형자산·이연법인세·법인세납부액)이 표에 채워졌는지
        입력값 = {k: await page.input_value(f'[data-fin="{k}"][data-idx="2"]') for k in ['매출원가', '판관비', '당기순이익', '법인세비용', '무형자산', '이연법인세', '법인세납부액']}
        check('입력: 신규 재무항목 7개 모두 채워짐', all(v.strip() for v in 입력값.values()), str(입력값))
        check('분석: 차트 SVG 4개(진단 막대 + K-means 산점도 + 시뮬 매출·영업이익)', await page.locator('#panel-analysis svg').count() == 4, str(await page.locator('#panel-analysis svg').count()))
        diag = await page.inner_text('#chart-diag-bars')
        check('분석: 업종 평균 비교 진단(지표 막대) 지표 4개', all(k in diag for k in ['매출증가율', '영업이익률', '이자비용비율', '인건비비율']), diag[:200].replace('\n', ' '))
        check('분석: 툴바 시나리오 세그먼트 삭제됨', await page.locator('#scenario-switch').count() == 0)
        check('분석: 업종 비교 표 4행', await page.locator('#industry-comments tbody tr').count() == 4)
        check('분석: 해석 칸에 지표별 문장 표시', await page.locator('#industry-comments .해석칸').count() == 4)
        if SERVER:
            # 서버 모드에서는 GPT가 해석을 다시 써 준다(실패해도 기본 해석이 남아야 한다)
            await page.wait_for_timeout(9000)
            해석들 = await page.locator('#industry-comments .해석칸').all_inner_texts()
            check('분석: GPT 해석 반영(또는 기본 해석 유지)', all(len(t.strip()) > 5 for t in 해석들), ' / '.join(t[:40] for t in 해석들))
            ai표시 = await page.is_visible('#diag-ai-note')
            check('분석: GPT 해석 시 AI 안내 문구 표시', ai표시 or all('업종 평균보다' in t or '이자비용 부담' in t or '매출 대비' in t for t in 해석들), str(ai표시))
        else:
            check('분석: file://에서는 기본 해석 유지', '업종 평균보다' in await page.inner_text('#industry-comments'))

        # 동종 상장기업 비교군(K-means) — docs/peer-cluster.json이 있으면 산점도·해설이 나온다
        if await page.locator('#chart-peer-scatter svg').count():
            점 = await page.locator('#chart-peer-scatter circle').count()
            check('비교군: K-means 산점도에 회사 점 표시', 점 >= 15, str(점))
            check('비교군: 작동 프로세스 4단계 표시', await page.locator('#peer-steps li').count() == 4)
            축 = await page.eval_on_selector_all('#chart-peer-scatter text', 'els => els.map(e => e.textContent)')
            check('비교군: 가로·세로 축 제목 표시', any('매출 규모' in t for t in 축) and any('3년 매출 성장률' in t for t in 축), ' / '.join(t for t in 축 if '매출' in t))
            겹침 = await page.evaluate('''() => {
              const svg = document.querySelector('#chart-peer-scatter svg');
              const t = [...svg.querySelectorAll('text')].find(x => x.textContent.includes('우리 회사'));
              const lb = t.getBBox();
              return [...svg.querySelectorAll('circle')].filter(c => {
                const cx = +c.getAttribute('cx'), cy = +c.getAttribute('cy'), r = +c.getAttribute('r');
                return cx + r > lb.x && cx - r < lb.x + lb.width && cy + r > lb.y && cy - r < lb.y + lb.height;
              }).length;
            }''')
            check('비교군: "우리 회사" 라벨이 다른 회사 점과 겹치지 않음', 겹침 == 0, f'겹친 점 {겹침}개')
            색 = await page.evaluate('''() => {
              const svg = document.querySelector('#chart-peer-scatter svg');
              const m = new Map();
              svg.querySelectorAll('circle').forEach(c => {
                const t = c.getAttribute('data-tip') || '';
                const g = t.match(/([ABC])군/);
                if (g) m.set(g[1], getComputedStyle(c).fill);
              });
              return Object.fromEntries([...m.entries()].sort());
            }''')
            check('비교군: A=연두 · B=하늘 · C=회색 고정', 색.get('A') == 'rgb(139, 195, 74)' and 색.get('B') == 'rgb(79, 179, 232)' and 색.get('C') == 'rgb(107, 117, 131)', str(색))
            해설 = await page.inner_text('#peer-cluster-summary')
            check('비교군: 군 3개 + 소속 군 해설', ('A' in 해설 and 'B' in 해설 and 'C' in 해설) and '배정됐습니다' in 해설, 해설[:150].replace('\n', ' '))
            check('비교군: 우리 회사 소속 표시', '우리 회사' in 해설 and '판정됩니다' in 해설)

            # 업종을 바꾸면 비교군도 실시간으로 바뀌어야 한다(업종별 사전 계산 + 브라우저 실시간 배정)
            제조업요약 = await page.inner_text('#peer-cluster-summary')
            await page.click('#nav-input'); await page.wait_for_timeout(150)
            await page.select_option('#f-industry', 'ict'); await page.wait_for_timeout(100)
            await page.click('#btn-analyze'); await page.wait_for_timeout(350)
            await page.click('#nav-analysis'); await page.wait_for_timeout(300)
            ict요약 = await page.inner_text('#peer-cluster-summary')
            check('비교군: 업종 변경 시 비교군도 바뀜(제조업 → 정보통신업)', 제조업요약 != ict요약, ict요약[:110].replace('\n', ' '))
            # 코스닥·코넥스 상장사가 거의 없는 업종은 이유를 안내한다
            await page.click('#nav-input'); await page.wait_for_timeout(150)
            await page.select_option('#f-industry', 'food-lodging'); await page.wait_for_timeout(100)
            await page.click('#btn-analyze'); await page.wait_for_timeout(350)
            await page.click('#nav-analysis'); await page.wait_for_timeout(300)
            check('비교군: 데이터 없는 업종은 사유 안내', await page.is_visible('#peer-none') and '상장사가 거의 없어' in await page.inner_text('#peer-none'))
            # 재무데이터를 바꾸면 소속 군·순위도 다시 계산된다
            await page.click('#nav-input'); await page.wait_for_timeout(150)
            await page.select_option('#f-industry', 'manufacturing'); await page.wait_for_timeout(100)
            await page.fill('[data-fin="매출액"][data-idx="2"]', '51000'); await page.wait_for_timeout(100)
            await page.click('#btn-analyze'); await page.wait_for_timeout(350)
            await page.click('#nav-analysis'); await page.wait_for_timeout(300)
            큰회사요약 = await page.inner_text('#peer-cluster-summary')
            check('비교군: 재무데이터 변경 시 소속 군·순위 재계산', 큰회사요약 != 제조업요약, 큰회사요약[:110].replace('\n', ' '))
            # 원상 복구
            await page.click('#nav-input'); await page.wait_for_timeout(150)
            await page.fill('[data-fin="매출액"][data-idx="2"]', '5100'); await page.wait_for_timeout(100)
            await page.click('#btn-analyze'); await page.wait_for_timeout(350)

        # 사업자 유형별 세금 계산 분기: 간이과세자(업종 부가가치율 방식) / 개인 일반과세자(매출-매입) / 법인(법인세+부가세)
        await page.click('#nav-input'); await page.wait_for_timeout(150)
        await page.select_option('#f-biztype', 'simplified'); await page.wait_for_timeout(100)
        await page.click('#btn-analyze'); await page.wait_for_timeout(300)
        await page.click('#nav-analysis'); await page.wait_for_timeout(200)
        simp = await page.inner_text('#scenario-table')
        check('사업자유형(간이과세자): 법인세 행 없음', '법인세' not in simp, simp[:120].replace('\n', ' '))
        check('사업자유형(간이과세자): 부가세 8,625만원(5100×20%×10% − 3150×0.5%)', '8,625만원' in simp, simp[:200].replace('\n', ' '))
        await page.click('#nav-input'); await page.wait_for_timeout(150)
        await page.select_option('#f-biztype', 'individual'); await page.wait_for_timeout(100)
        await page.click('#btn-analyze'); await page.wait_for_timeout(300)
        await page.click('#nav-analysis'); await page.wait_for_timeout(200)
        indiv = await page.inner_text('#scenario-table')
        check('사업자유형(개인 일반과세자): 법인세 행 없음, 부가세는 일반 방식 1.95억원', '법인세' not in indiv and '1.95억원' in indiv, indiv[:200].replace('\n', ' '))
        # 원상 복구 (이후 검사는 법인사업자 기준)
        await page.click('#nav-input'); await page.wait_for_timeout(150)
        await page.select_option('#f-biztype', 'corporate'); await page.wait_for_timeout(100)
        await page.click('#btn-analyze'); await page.wait_for_timeout(300)
        await page.click('#nav-analysis'); await page.wait_for_timeout(200)
        corp = await page.inner_text('#scenario-table')
        check('사업자유형(법인사업자) 복구: 법인세 행 다시 표시', '법인세' in corp, corp[:120].replace('\n', ' '))

        # 실시간 시뮬레이션: 슬라이더를 움직이면 즉시 KPI·차트가 바뀌는지 확인
        before = await page.inner_text('#sim-kpis')
        await page.fill('#sim-growth-num', '10'); await page.wait_for_timeout(100)
        after = await page.inner_text('#sim-kpis')
        check('시뮬레이션: 매출성장률 조정 시 조정 매출 변경', before != after, f'{before[:40]} → {after[:40]}'.replace('\n', ' '))
        check('시뮬레이션: 슬라이더·숫자칸 동기화', await page.input_value('#sim-growth') == '10')
        sim_sales = await page.inner_text('#sim-chart-sales')
        check('시뮬레이션: 매출 차트에 "조정 예측" 라벨', '조정 예측' in sim_sales)
        tbl_before = await page.inner_text('#scenario-table')
        check('시뮬레이션: "실적 대비 예측" 표도 슬라이더 값에 맞춰 함께 갱신(매출 56.1억원)', '56.1억원' in tbl_before, tbl_before[:120].replace('\n', ' '))
        await page.fill('#sim-growth-num', '0'); await page.wait_for_timeout(100)   # 원상 복구
        tbl_after = await page.inner_text('#scenario-table')
        check('시뮬레이션: 원상 복구 시 표도 51억원으로 복귀', '51억원' in tbl_after and '56.1억원' not in tbl_after, tbl_after[:120].replace('\n', ' '))
        await page.fill('#sim-growth-num', '0'); await page.wait_for_timeout(100)
        위치 = await page.evaluate('''() => ['sim-growth','sim-opm','sim-interest'].map(id => {
          const e = document.getElementById(id);
          return Math.round((e.valueAsNumber - e.min) / (e.max - e.min) * 100);
        })''')
        check('시뮬레이션: 세 슬라이더 모두 같은 지점(정중앙)에서 시작', 위치 == [50, 50, 50], str(위치))
        라벨 = (await page.inner_text('#sim-opm-base')) + ' / ' + (await page.inner_text('#sim-interest-base'))
        check('시뮬레이션: 증감 슬라이더 옆에 적용 비율 표시', '기준' in 라벨 and '적용' in 라벨, 라벨)

        # 개요 (Task 3에서 완성 — Task 2 시점에는 이 5건이 FAIL이어도 정상)
        await page.click('#nav-overview'); await page.wait_for_timeout(200)
        check('개요: KPI 4개', await page.locator('#overview-kpis .kpi').count() == 4)
        ov = await page.inner_text('#overview-kpis')
        check('개요: 매출 51억·세부담 5,720만원·절세 4/6', '51억원' in ov and '5,720만원' in ov and '4 / 6' in ov, ov[:160].replace('\n', ' '))
        check('개요: 세금 일정 5건(화면을 채우도록 확대)', await page.locator('#overview-schedule li').count() == 5, str(await page.locator('#overview-schedule li').count()))
        check('개요: 임박 공고 표시', await page.locator('#overview-support .support').count() >= 1)
        check('개요: 업종 대비 문장', '업종 평균' in await page.inner_text('#overview-industry'))
        # 개요는 데스크톱에서 스크롤 없이 한 화면에 들어와야 한다(면책 문구까지)
        await page.set_viewport_size({'width': 1600, 'height': 900}); await page.wait_for_timeout(300)
        꽉참 = await page.evaluate('''() => ({
          세로: document.documentElement.scrollHeight > innerHeight + 2,
          가로: document.documentElement.scrollWidth > innerWidth + 2,
          면책: (() => { const f = document.querySelector('.content__foot'); const r = f.getBoundingClientRect(); return r.bottom <= innerHeight + 2 && r.top >= 0; })(),
          폭: Math.round(document.querySelector('.content').getBoundingClientRect().width),
          본문영역폭: Math.round(document.querySelector('.main').getBoundingClientRect().width)
        })''')
        check('개요: 1600px에서 스크롤 없이 한 화면', not 꽉참['세로'] and not 꽉참['가로'], str(꽉참))
        check('개요: 면책 문구까지 화면 안에 표시', 꽉참['면책'])
        check('개요: 본문이 사이드바를 뺀 화면 폭을 꽉 채움(1400px 제한 해제)', 꽉참['폭'] == 꽉참['본문영역폭'], f"content {꽉참['폭']} vs main {꽉참['본문영역폭']}")
        await page.set_viewport_size({'width': 1440, 'height': 900}); await page.wait_for_timeout(200)

        # 절세
        await page.click('#nav-tax'); await page.wait_for_timeout(200)
        rows = page.locator('#strategy-cards .strategy')
        check('절세: 전략 6개(법인사업자 대상)', await rows.count() == 6, str(await rows.count()))
        emp = await rows.nth(0).inner_text(); inv = await rows.nth(1).inner_text(); wage = await rows.nth(2).inner_text()
        durunuri = await rows.nth(3).inner_text(); youth = await rows.nth(4).inner_text()
        check('절세: 통합고용 1년차 17,000,000원 / 3년 81,000,000원', '17,000,000원' in emp and '81,000,000원' in emp, emp[:160].replace('\n', ' '))
        check('절세: 통합투자 40,000,000원(과거 투자액에 무형자산 증가분 반영 → 추가공제 0)', '40,000,000원' in inv, inv[:160].replace('\n', ' '))
        check('절세: 근로소득증대 적용 가능', '적용 가능' in wage, wage[:200].replace('\n', ' '))
        check('절세: 두루누리 적용 불가(상시근로자 10명 이상)', '적용 불가' in durunuri and '10명' in durunuri, durunuri[:200].replace('\n', ' '))
        check('절세: 청년일자리도약장려금 적용 가능', '적용 가능' in youth, youth[:200].replace('\n', ' '))
        summary = await page.inner_text('#tax-summary')
        check('절세: 요약 적용 4/6', '4' in summary and '/ 6' in summary, summary[:100].replace('\n', ' '))
        await rows.nth(0).locator('.collapse__btn').click(); await page.wait_for_timeout(100)
        check('절세: 자세히 펼침', await page.locator('#detail-employment').evaluate('el => el.classList.contains("is-open")'))
        check('절세: 법령 근거(조세특례제한법) 표에 안 보임', '조세특례제한법' not in await page.inner_text('#strategy-body'))

        # 세무 정합성: 최저한세(조특법 §132)와 혜택 성격 분리
        절 = await page.evaluate('''() => {
          const z = 상태.절세결과;
          return {최저한세: z.최저한세, 법인세공제액: z.법인세공제액, 실제법인세공제: z.실제법인세공제,
                  배제된공제: z.배제된공제, 현금: z.현금지원액, 반영후: z.반영후_세부담};
        }''')
        # 과세표준 360백만 × 7% = 25,200,000원
        check('세무: 최저한세 = 과세표준 × 7%(중소기업)', round(절['최저한세']) == 25_200_000, str(round(절['최저한세'])))
        check('세무: 공제 후 법인세가 최저한세 아래로 안 내려감', 절['반영후'] >= 절['최저한세'], f"반영후 {절['반영후']:,} vs 최저한세 {절['최저한세']:,}")
        check('세무: 최저한세로 배제된 공제는 이월로 분리', abs(절['배제된공제'] - (절['법인세공제액'] - 절['실제법인세공제'])) < 1, str(round(절['배제된공제'])))
        check('세무: 현금 지원금은 법인세 공제액에 섞이지 않음', round(절['현금']) == 7_200_000 and round(절['법인세공제액']) == 58_218_079, f"현금 {round(절['현금']):,} / 법인세공제 {round(절['법인세공제액']):,}")
        종류 = await page.inner_text('#tax-kinds')
        check('세무: 혜택 성격 분리 안내 표시', '법인세 세액공제' in 종류 and '현금 지원금' in 종류, 종류[:110].replace('\n', ' '))
        check('세무: 고용 세액공제 + 고용지원금 중복지원 경고', await page.is_visible('#tax-overlap') and '중복지원' in await page.inner_text('#tax-overlap'))

        # 적용 불가 상태에서 "부족합니다" 식 설명이 뜨는지 확인 (내년 계획을 모두 0으로)
        await page.click('#nav-input'); await page.wait_for_timeout(150)
        await page.fill('#f-emp-delta', '0'); await page.fill('#f-youth', '0')
        await page.fill('#f-capex', '0'); await page.fill('#f-wage', '0')
        await page.locator('#f-wage').blur(); await page.click('#btn-analyze'); await page.wait_for_timeout(300)
        await page.click('#nav-tax'); await page.wait_for_timeout(200)
        unavail = await page.inner_text('#strategy-body')
        check('절세: 적용 불가 시 부족분 설명(통합고용)', '부족합니다' in unavail, unavail[:300].replace('\n', ' '))
        check('절세: 적용 불가 시 설명(통합투자)', '0원' in unavail and '투자 계획을 입력' in unavail)

        # 사업자 유형별 절세전략·세금 일정 구분
        await page.click('#nav-input'); await page.wait_for_timeout(150)
        await page.fill('#f-emp-delta', '2'); await page.fill('#f-youth', '1')
        await page.fill('#f-capex', '400'); await page.fill('#f-wage', '8')
        await page.select_option('#f-biztype', 'individual'); await page.wait_for_timeout(100)
        await page.click('#btn-analyze'); await page.wait_for_timeout(300)
        await page.click('#nav-tax'); await page.wait_for_timeout(200)
        개인전략 = await page.inner_text('#strategy-body')
        check('사업자유형(개인): 신용카드 매출세액공제 추가(전략 7개)', await page.locator('#strategy-cards .strategy').count() == 7 and '신용카드 등 매출세액공제' in 개인전략, str(await page.locator('#strategy-cards .strategy').count()))
        check('사업자유형(개인): 간이 전용 제도는 안 보임', '간이과세자 부가세 납부의무 면제' not in 개인전략)
        check('사업자유형(개인): 노란우산공제 적용 가능', '노란우산공제' in 개인전략)
        await page.click('#nav-overview'); await page.wait_for_timeout(200)
        개인일정 = await page.inner_text('#overview-schedule')
        check('사업자유형(개인): 세금 일정에 법인세 없음', '법인세' not in 개인일정 and '부가세' in 개인일정, 개인일정[:120].replace('\n', ' '))

        await page.click('#nav-input'); await page.wait_for_timeout(150)
        await page.select_option('#f-biztype', 'simplified'); await page.wait_for_timeout(100)
        await page.click('#btn-analyze'); await page.wait_for_timeout(300)
        await page.click('#nav-tax'); await page.wait_for_timeout(200)
        간이전략 = await page.inner_text('#strategy-body')
        check('사업자유형(간이): 간이 전용 제도 포함(전략 8개)', await page.locator('#strategy-cards .strategy').count() == 8 and '간이과세자 부가세 납부의무 면제' in 간이전략, str(await page.locator('#strategy-cards .strategy').count()))
        await page.click('#nav-overview'); await page.wait_for_timeout(200)
        간이일정 = await page.inner_text('#overview-schedule')
        check('사업자유형(간이): 부가세 확정신고 1회만', '확정신고' in 간이일정 and '예정' not in 간이일정, 간이일정[:120].replace('\n', ' '))

        # 원상 복구 (이후 검사는 법인사업자 기준)
        await page.click('#nav-input'); await page.wait_for_timeout(150)
        await page.select_option('#f-biztype', 'corporate'); await page.wait_for_timeout(100)
        await page.click('#btn-analyze'); await page.wait_for_timeout(300)
        # 원상 복구 (이후 검사는 샘플 값 기준)
        await page.click('#nav-input'); await page.wait_for_timeout(150)
        await page.fill('#f-emp-delta', '2'); await page.fill('#f-youth', '1')
        await page.fill('#f-capex', '400'); await page.fill('#f-wage', '8')
        await page.locator('#f-wage').blur(); await page.click('#btn-analyze'); await page.wait_for_timeout(300)
        await page.click('#nav-tax'); await page.wait_for_timeout(200)

        # ERP CSV 업로드 — 사이드바 "ERP CSV 불러오기" 버튼은 숨겨진 파일 선택창을 열 뿐이라(OS 네이티브
        # 다이얼로그는 자동화 불가) 여기서는 set_input_files로 파일을 바로 지정해 change 이벤트를 확인한다.
        await page.click('#nav-input'); await page.wait_for_timeout(150)
        check('입력: 사이드바 버튼 라벨이 "ERP CSV 불러오기"로 변경됨', 'ERP CSV 불러오기' in await page.inner_text('#btn-load-sample'))
        csv_path = os.path.join(SHOTS, '_erp_sample.csv')
        with open(csv_path, 'w', encoding='utf-8') as f:
            # 회사명도 함께 인식하는지 보려고 제목 줄을 넣는다
            f.write('대한정밀공업(주) 손익계산서\n(단위: 원)\n계정과목,금액\n매출액,5100000000\n영업이익,380000000\n')
        await page.fill('#f-company', '')   # 비어 있을 때만 CSV의 회사명으로 채워야 한다
        await page.set_input_files('#erp-csv-file', csv_path)
        await page.wait_for_timeout(6000 if SERVER else 200)
        erp_status = await page.inner_text('#erp-csv-status')
        if SERVER:
            check('입력: ERP CSV 서버 모드 응답(성공 또는 키 미등록 안내)', ('채웠습니다' in erp_status or '실패' in erp_status or 'CSV 처리' in erp_status), erp_status[:200])
            if '채웠습니다' in erp_status:
                회사명 = await page.input_value('#f-company')
                check('입력: ERP CSV에서 회사명도 인식해 채움', '대한정밀공업' in 회사명, 회사명)
        else:
            check('입력: ERP CSV file:// 안내(서버 필요)', '서버가 없어' in erp_status, erp_status[:200])
        # 이후 검사는 샘플 회사명 기준이라 되돌려 놓는다
        await page.fill('#f-company', '샘플정밀(주)'); await page.locator('#f-company').blur(); await page.wait_for_timeout(150)
        os.remove(csv_path)

        # 지원사업 — 인증키 입력란·버튼은 삭제됨. 서버 모드는 화면 진입 전 앱 시작 시 자동으로 기업마당 공고를 불러온다.
        await page.click('#nav-support'); await page.wait_for_timeout(200)
        check('지원사업: 지역 필터 기본값 = 입력 소재지(광산구)', await page.input_value('#s-region') == 'gwangsan', await page.input_value('#s-region'))
        if not SERVER:
            # file://는 서버가 없어 지원사업_자동조회()가 시도하지 않고 항상 샘플 데이터를 쓴다 — 필터·정렬 로직을 알려진 샘플로 검증한다.
            n_open = await page.locator('#support-list .support').count()
            check('지원사업: 광주+전국 공고 표시', n_open > 0, str(n_open))
            check('지원사업: 마감 숨기기 체크박스 삭제됨', await page.locator('#s-hide-closed').count() == 0)
            await page.select_option('#s-region', 'all'); await page.wait_for_timeout(100)
            n_all = await page.locator('#support-list .support').count()
            check('지원사업: 전체 12건(마감 공고도 함께 표시)', n_all == 12, str(n_all))
            # 사업자 유형 필터: 법인사업자 기준으로 개인·소상공인 전용 공고가 걸러지는지
            await page.check('#s-mytype'); await page.wait_for_timeout(150)
            n_mine = await page.locator('#support-list .support').count()
            check('지원사업: 내 사업자 유형 필터 적용 시 건수 감소 또는 유지', 0 < n_mine <= n_all, f'{n_all} → {n_mine}')
            check('지원사업: 필터 표시에 사업자 유형 노출', '법인사업자 대상만' in await page.inner_text('#support-count'), await page.inner_text('#support-count'))
            await page.uncheck('#s-mytype'); await page.wait_for_timeout(150)
            check('지원사업: 소스 표시(샘플 데이터, file://)', '샘플 데이터' in await page.inner_text('#support-source'))
        else:
            # 등록된 인증키가 유효하면 자동으로 실시간 공고로, 실패하면 자동으로 샘플로 바뀐다 — 소스 칩으로 확인한다.
            src_text = await page.inner_text('#support-source')
            check('지원사업: 자동 조회로 채워짐(실시간 또는 샘플)', ('기업마당 실시간' in src_text or '샘플 데이터' in src_text) and await page.locator('#support-list .support').count() > 0, src_text)
            await page.select_option('#s-region', 'all'); await page.wait_for_timeout(100)
            check('지원사업: 필터 조작 후에도 목록 표시', await page.locator('#support-list .support').count() > 0, str(await page.locator('#support-list .support').count()))
            # searchCnt 없이 부르면 기업마당이 전체 목록을 내려주다 8초 타임아웃(502)이 날 수 있어 searchCnt=1로 고정해서 확인한다.
            # 서버에 BIZINFO_API_KEY가 등록돼 있으면 200(성공), 등록돼 있지 않으면 400(우리 프록시가 즉시 거절)이 정상이다.
            code = await page.evaluate("fetch('/api/bizinfo?searchCnt=1').then(r => r.status)")
            check('프록시: 최소 요청 응답(등록 시 200 / 미등록 시 400)', code in (200, 400), str(code))
            body = await page.evaluate("fetch('/api/bizinfo?crtfcKey=TESTKEY&searchCnt=1').then(r => r.text())")
            check('프록시: 잘못된 키 → 기업마당/프록시 응답 수신', len(body) > 0, body[:100].replace('\n', ' '))

        # 새로고침 후 유지 (분석결과 있음 → 개요로 진입)
        await page.reload(); await page.wait_for_load_state('load'); await page.wait_for_timeout(300)
        check('새로고침: 개요로 진입', await page.is_visible('#panel-overview'))
        check('새로고침: 매출액 유지', await page.input_value('[data-fin="매출액"][data-idx="2"]') == '5,100')
        check('새로고침: 회사명 유지', await page.input_value('#f-company') == '샘플정밀(주)')
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

        # 인쇄: 분석결과의 3개 카드(업종 평균 비교 진단·실시간 시뮬레이션·실적 대비 예측)만 출력
        await page.set_viewport_size({'width': 1440, 'height': 900})
        await page.click('#nav-analysis'); await page.wait_for_timeout(150)
        await page.emulate_media(media='print'); await page.wait_for_timeout(100)
        await page.screenshot(path=os.path.join(SHOTS, 'print.png'), full_page=True)
        보이는패널 = await page.locator('.panel:visible').count()
        check('인쇄: 사이드바·툴바 숨김 + 분석결과 패널만 출력', (not await page.is_visible('.sidebar')) and (not await page.is_visible('.toolbar')) and 보이는패널 == 1, str(보이는패널))
        보이는카드 = await page.locator('#analysis-content > .card:visible').count()
        check('인쇄: 분석결과 카드 3개만 출력(진단·시뮬레이션·실적 대비 예측)', 보이는카드 == 3, str(보이는카드))
        인쇄본문 = await page.inner_text('#panel-analysis')
        check('인쇄: 3개 카드 제목 포함', all(k in 인쇄본문 for k in ['업종 평균 비교 진단', '실시간 시뮬레이션', '실적 대비 예측']), 인쇄본문[:120].replace('\n', ' '))
        check('인쇄: 머리글에 회사명·출력 시각', '샘플정밀(주)' in 인쇄본문 and '출력' in 인쇄본문)
        check('인쇄: 슬라이더 컨트롤은 숨김', not await page.is_visible('#sim-controls'))
        await page.emulate_media(media='screen'); await page.wait_for_timeout(100)

        # 데이터 초기화 (사이드바 버튼 → 자체 다이얼로그)
        await page.click('#nav-input'); await page.click('#btn-reset'); await page.wait_for_timeout(100)
        check('초기화: 다이얼로그 표시', await page.is_visible('#dialog'))
        await page.click('#dialog-ok'); await page.wait_for_timeout(300)
        check('초기화: 입력 화면 + 입력값 비움', await page.is_visible('#panel-input') and await page.input_value('[data-fin="매출액"][data-idx="2"]') == '' and await page.input_value('#f-company') == '')
        keys = await page.evaluate('Object.keys(localStorage)')
        check('초기화: localStorage 비움', len(keys) == 0, str(keys))
        check('초기화: 저장 상태 칩', '저장된 데이터 없음' in await page.inner_text('#save-status'))

        check('콘솔/페이지 JS 오류 0개', len(errors) == 0, '\n'.join(errors)[:800])
        print('참고) 네트워크 자원 실패:', '\n  '.join(network) or '없음')
        await browser.close()

    fails = [r for r in results if not r[1]]
    print(f'\n총 {len(results)}개 검사, 실패 {len(fails)}개')
    sys.exit(1 if fails else 0)

asyncio.run(main())
