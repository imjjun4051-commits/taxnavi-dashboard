// tools/update-industry-avg.js — DART(전자공시시스템) 실제 재무제표로 docs/industry-avg.json을 갱신하는 보조 스크립트
// 사용법 (프로젝트 폴더에서):  node tools/update-industry-avg.js
// 하는 일: 업종별로 정해둔 대표 상장기업 목록(아래 업종별기업)의 최근 사업보고서를 DART Open API로 가져와
//          영업이익률·인건비비율·매출증가율을 계산하고 업종별 평균을 내어 docs/industry-avg.json에 저장한다.
//          그 다음 node tools/inline-data.js 를 함께 실행해야 index.html 인라인 데이터도 갱신된다.
// 주의:
//  - DART는 상장기업·외부감사 대상 대기업 위주로 공시하므로, 이 값은 "실제 중소기업 평균"이 아니라
//    "업종 내 대표 상장기업들의 평균"이다. 화면에도 이 사실을 표시한다.
//  - 감가상각비는 DART 표준 재무제표 API(fnlttSinglAcntAll)에 계정과목으로 나오지 않아(주석에만 있음)
//    이 스크립트로는 채울 수 없다 → 감가상각비율은 null로 두어 화면에 "데이터 없음"으로 표시된다.
//  - 인건비는 직원현황 API(empSttus)의 "연간급여총액"으로 근사한다. 이 항목을 공시하지 않는 회사(부문별로만
//    공시하는 대기업 등)는 그 회사만 인건비비율 계산에서 제외한다.
//  - 매 실행마다 회사당 API 호출 2번(재무제표 1 + 직원현황 1) × 30개 회사 = 약 60회. DART 일일 호출 한도(2만 회) 안에서 충분히 여유 있다.
//  - 실행 빈도: 자주 바꿀 필요 없는 값이므로 몇 달에 한 번, 또는 배포 전에 한 번씩 수동 실행하면 된다(주기적 캐싱).
'use strict';
const fs = require('fs');
const path = require('path');
const root = path.join(__dirname, '..');

// .env.local 에서 DART_API_KEY 를 읽는다 (Vercel 배포 환경에서는 이미 process.env 에 있으므로 건너뜀).
// 외부 라이브러리(dotenv) 없이 직접 파싱한다. 값 자체는 절대 콘솔에 출력하지 않는다.
function 환경변수_불러오기() {
  if (process.env.DART_API_KEY) return;
  const envPath = path.join(root, '.env.local');
  if (!fs.existsSync(envPath)) return;
  for (const line of fs.readFileSync(envPath, 'utf8').split('\n')) {
    const m = line.match(/^([A-Z_][A-Z0-9_]*)="?(.*?)"?\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
  }
}
환경변수_불러오기();
const 인증키 = process.env.DART_API_KEY;
if (!인증키) { console.error('DART_API_KEY 환경변수가 없습니다. .env.local 또는 Vercel 환경변수에 등록하세요.'); process.exit(1); }

// 업종(6종)별 대표 코스닥·코넥스 기업 — 이름·시장구분은 DART company.json(corp_cls: K=코스닥, N=코넥스)으로
// 실제 확인한 값이다(추측 아님, 2026-09-03 확인). 코스피 대기업은 제외했다.
// 음식·숙박업은 코스닥·코넥스 상장사를 찾지 못해 비워 두었다 — main()에서 기존 샘플값을 그대로 유지한다.
const 업종별기업 = {
  manufacturing: [['에코프로비엠', '01160363'], ['파크시스템스', '00244747'], ['리노공업', '00369657'], ['HPSP', '01288827'], ['동진쎄미켐', '00118804'], ['서울반도체', '00130763'], ['원익IPS', '01135941'], ['코미코', '00997812']],
  wholesale:     [['실리콘투', '00982023'], ['대산F&B', '00390860'], ['푸드나무', '01259311']],
  service:       [['메가스터디교육', '01074862'], ['씨엔알리서치', '01487446']],
  construction:  [['특수건설', '00186939'], ['서한', '00131504'], ['이화공영', '00145668'], ['KCC건설', '00105466']],
  ict:           [['안랩', '00298270'], ['웹케시', '00323868'], ['이스트소프트', '00273420'], ['비트컴퓨터', '00231707'], ['케이엘넷', '00246620'], ['인성정보', '00229021'], ['컴투스홀딩스', '00535746'], ['골프존', '01067516']],
  'food-lodging': []
};
const 업종이름 = { manufacturing: '제조업', wholesale: '도소매업', service: '서비스업', construction: '건설업', ict: '정보통신업', 'food-lodging': '음식·숙박업' };
// 매출액 계정과목 이름 후보 (회사마다 "매출액" 대신 "영업수익"·"수익(매출액)"으로 공시하기도 함 — 실측 확인)
const 매출액_계정후보 = ['매출액', '영업수익', '수익(매출액)'];
const 시도할연도 = [2024, 2023, 2022];   // 최근 사업보고서부터 시도, 없으면 이전 연도로

function 지연(ms) { return new Promise(r => setTimeout(r, ms)); }

async function dart호출(엔드포인트, 쿼리) {
  const params = new URLSearchParams({ crtfc_key: 인증키, ...쿼리 });
  const res = await fetch(`https://opendart.fss.or.kr/api/${엔드포인트}?${params}`);
  if (!res.ok) throw new Error(`DART HTTP ${res.status}`);
  return res.json();
}

// 한 회사의 재무제표에서 매출액(당기·전기)·영업이익(당기)·금융비용(당기, 이자비용 근사)을 뽑는다. CFS(연결) 우선, 없으면 OFS(개별).
async function 재무제표_읽기(corp_code, 연도) {
  for (const fs_div of ['CFS', 'OFS']) {
    const d = await dart호출('fnlttSinglAcntAll.json', { corp_code, bsns_year: String(연도), reprt_code: '11011', fs_div });
    if (d.status !== '000' || !Array.isArray(d.list)) continue;
    // 손익계산서는 회사마다 sj_div가 'IS'(손익계산서) 또는 'CIS'(포괄손익계산서)로 다르게 옴 — 둘 다 허용
    const 손익 = it => it.sj_div === 'IS' || it.sj_div === 'CIS';
    const 매출행 = d.list.find(it => 손익(it) && 매출액_계정후보.includes(it.account_nm));
    const 영업이익행 = d.list.find(it => 손익(it) && /^영업이익/.test(it.account_nm));
    if (!매출행 || !영업이익행) continue;
    const 당기매출 = Number(매출행.thstrm_amount), 전기매출 = Number(매출행.frmtrm_amount);
    const 영업이익 = Number(영업이익행.thstrm_amount);
    if (!Number.isFinite(당기매출) || 당기매출 <= 0) continue;
    // 순수 "이자비용"만 분리 공시하는 회사가 드물어 "금융비용"(외환손실 등 포함된 상위 계정)으로 근사한다
    const 금융비용행 = d.list.find(it => 손익(it) && it.account_nm === '금융비용');
    const 금융비용 = 금융비용행 ? Number(금융비용행.thstrm_amount) : null;
    return { 당기매출, 전기매출: Number.isFinite(전기매출) ? 전기매출 : null, 영업이익, 금융비용: Number.isFinite(금융비용) ? 금융비용 : null };
  }
  return null;
}

// 직원현황에서 급여총액(성별 합산)을 읽는다. 공시하지 않는 회사는 null.
async function 인건비_읽기(corp_code, 연도) {
  const d = await dart호출('empSttus.json', { corp_code, bsns_year: String(연도), reprt_code: '11011' });
  if (d.status !== '000' || !Array.isArray(d.list)) return null;
  let 합계 = 0, 확인됨 = false;
  for (const row of d.list) {
    const v = Number(String(row.fyer_salary_totamt || '').replace(/,/g, ''));
    if (Number.isFinite(v) && v > 0) { 합계 += v; 확인됨 = true; }
  }
  return 확인됨 ? 합계 : null;
}

async function 회사데이터_가져오기(이름, corp_code) {
  for (const 연도 of 시도할연도) {
    const 재무 = await 재무제표_읽기(corp_code, 연도);
    if (!재무) continue;
    await 지연(120);   // DART API 과도한 연속 호출 방지용 짧은 간격
    const 급여총액 = await 인건비_읽기(corp_code, 연도).catch(() => null);
    await 지연(120);
    return { 이름, corp_code, 연도, ...재무, 급여총액 };
  }
  return null;
}

// 숫자 배열 평균 (null/NaN 제외). 유효한 값이 하나도 없으면 null.
function 평균(값들) {
  const 유효 = 값들.filter(v => Number.isFinite(v));
  if (!유효.length) return null;
  return Math.round((유효.reduce((a, b) => a + b, 0) / 유효.length) * 10) / 10;
}

async function main() {
  // 음식·숙박업처럼 코스닥·코넥스 기업을 찾지 못한 업종은 기존 파일의 샘플값을 그대로 유지한다.
  const 기존경로 = path.join(root, 'docs/industry-avg.json');
  const 기존 = fs.existsSync(기존경로) ? JSON.parse(fs.readFileSync(기존경로, 'utf8')) : { 업종: [] };
  const 기존업종 = Object.fromEntries((기존.업종 || []).map(u => [u.코드, u]));

  const 업종결과 = [];
  for (const [코드, 기업목록] of Object.entries(업종별기업)) {
    if (!기업목록.length) {
      const 옛값 = 기존업종[코드] || {};
      console.log(`--- ${업종이름[코드]}: 코스닥·코넥스 상장기업 없음 → 기존 샘플값 유지 ---`);
      업종결과.push({
        코드, 이름: 업종이름[코드],
        영업이익률: 옛값.영업이익률 ?? null, 인건비비율: 옛값.인건비비율 ?? null,
        매출증가율: 옛값.매출증가율 ?? null, 감가상각비율: 옛값.감가상각비율 ?? null,
        이자비용비율: 옛값.이자비용비율 ?? null,
        표본기업: [], 샘플값임: true
      });
      continue;
    }
    console.log(`--- ${업종이름[코드]} (${기업목록.length}개 기업) ---`);
    const 회사들 = [];
    for (const [이름, corp_code] of 기업목록) {
      try {
        const d = await 회사데이터_가져오기(이름, corp_code);
        if (d) { 회사들.push(d); console.log(`  ${이름}: 매출 ${(d.당기매출 / 1e8).toFixed(0)}억원 (${d.연도}년)`); }
        else console.log(`  ${이름}: 데이터 없음(건너뜀)`);
      } catch (e) { console.log(`  ${이름}: 오류(${e.message}) — 건너뜀`); }
    }
    const 영업이익률 = 평균(회사들.map(c => c.당기매출 ? c.영업이익 / c.당기매출 * 100 : NaN));
    const 매출증가율 = 평균(회사들.filter(c => c.전기매출).map(c => (c.당기매출 - c.전기매출) / c.전기매출 * 100));
    const 인건비비율 = 평균(회사들.filter(c => c.급여총액).map(c => c.급여총액 / c.당기매출 * 100));
    const 이자비용비율 = 평균(회사들.filter(c => c.금융비용 != null).map(c => c.금융비용 / c.당기매출 * 100));
    업종결과.push({
      코드, 이름: 업종이름[코드], 영업이익률, 인건비비율, 매출증가율, 감가상각비율: null, 이자비용비율,
      표본기업: 회사들.map(c => `${c.이름}(${c.연도})`)
    });
  }

  const 산출물 = {
    _설명: '업종별 평균 재무 비율. DART(전자공시시스템)의 업종별 대표 코스닥·코넥스 상장기업 실제 재무제표로 계산했습니다. ' +
      '코스피 대기업은 제외하고 코스닥·코넥스 중소·중견기업 위주로 선정했지만, 그래도 상장·공시 의무가 있는 기업이라 ' +
      '실제 비상장 중소기업 평균과는 차이가 있을 수 있습니다 — 참고용으로만 활용하세요. ' +
      '업종별 표본 수가 적을 수 있고(도소매업 3곳·서비스업 2곳), 음식·숙박업은 코스닥·코넥스 상장사를 찾지 못해 샘플값을 유지합니다. ' +
      '감가상각비는 DART 표준 API에 계정과목으로 없어 "데이터 없음"으로 남겨둡니다. ' +
      '갱신: node tools/update-industry-avg.js 실행 후 node tools/inline-data.js 로 index.html에 동기화.',
    출처: 'DART 전자공시시스템 실제 사업보고서 (업종별 대표 코스닥·코넥스 상장기업 평균 — 표본기업 항목 참고. 음식·숙박업은 상장사 없어 샘플값)',
    기준연도: new Date().getFullYear(),
    확인일: new Date().toISOString().slice(0, 10),
    단위: '%',
    지표설명: {
      영업이익률: '영업이익 ÷ 매출액 × 100',
      인건비비율: '연간급여총액(DART 직원현황 공시분) ÷ 매출액 × 100 — 급여총액 미기재 회사는 그 회사만 제외',
      매출증가율: '(당해 매출액 − 전년 매출액) ÷ 전년 매출액 × 100',
      감가상각비율: 'DART 표준 재무제표 API에 계정과목으로 제공되지 않아 데이터 없음',
      이자비용비율: '금융비용(이자비용 근사, 외환손익 등 포함될 수 있음) ÷ 매출액 × 100'
    },
    업종: 업종결과
  };
  fs.writeFileSync(기존경로, JSON.stringify(산출물, null, 2) + '\n', 'utf8');
  console.log('\ndocs/industry-avg.json 갱신 완료 →', 업종결과.map(u => `${u.이름}(${u.표본기업.length}곳${u.샘플값임 ? ',샘플' : ''})`).join(', '));
  console.log('다음: node tools/inline-data.js 실행해 index.html에 동기화하세요.');
}
main().catch(e => { console.error('실패:', e.message); process.exit(1); });
