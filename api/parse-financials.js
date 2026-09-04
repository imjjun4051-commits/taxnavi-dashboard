// api/parse-financials.js — ERP CSV → 재무데이터 자동 인식 (Vercel Node 서버리스 함수, 외부 패키지 없음)
// 브라우저가 CSV 원문을 이 주소로 보내면, OpenAI GPT API에 "계정과목 순서·명칭이 회사마다 달라도
// 매출액·영업이익·인건비·유형자산·감가상각비·이자비용을 찾아 JSON으로 돌려달라"고 요청해 대신 호출해 준다.
// CSV 내용(회사 재무 정보)과 인증키 모두 이 서버에 저장하지 않고 로그에도 남기지 않는다.
const OPENAI_주소 = 'https://api.openai.com/v1/chat/completions';
const 모델 = 'gpt-4o-mini';
const 시간제한_ms = 25_000;          // GPT 응답은 기업마당 API보다 느릴 수 있어 여유를 더 둔다 (Vercel Hobby 함수 한도 내)
const CSV_최대글자수 = 40_000;       // 과도하게 큰 파일이 그대로 GPT로 넘어가지 않도록 자른다 (약 1만 토큰 안팎)
const 항목목록 = ['매출액', '영업이익', '인건비', '유형자산', '감가상각비', '이자비용'];

function 오류응답(res, 코드, 메시지, 상세) {
  res.statusCode = 코드;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(상세 ? { error: 메시지, detail: 상세 } : { error: 메시지 }));
}

// GPT에게 정확히 이 모양의 JSON만 돌려달라고 강제하는 스키마(OpenAI Structured Outputs)
const 항목스키마 = {
  type: 'object', additionalProperties: false,
  properties: { 값들: { type: 'array', items: { type: 'number' } }, 단위: { type: 'string', enum: ['원', '천원', '백만원', '억원', '알수없음'] } },
  required: ['값들', '단위']
};
const 응답스키마 = {
  type: 'object', additionalProperties: false,
  properties: Object.assign(
    { 회사명: { type: ['string', 'null'] } },        // CSV 머리말·제목행에 회사명이 있으면 함께 뽑는다
    Object.fromEntries(항목목록.map(k => [k, 항목스키마]))
  ),
  required: ['회사명'].concat(항목목록)
};

const 시스템프롬프트 = `당신은 한국 중소기업 ERP 프로그램에서 내보낸 CSV 재무 데이터를 읽는 도우미입니다.
계정과목의 순서·표현은 회사마다 다릅니다(예: "매출액"/"매출"/"수익(매출액)"/"영업수익", "영업이익"/"영업이익(손실)", "인건비"/"급여"/"급여와임금", "유형자산"/"유형자산(순액)", "감가상각비"/"감가상각누계액 변동", "이자비용"/"금융비용"/"이자비용(금융비용)" 등).
아래 6개 항목 각각에 대해 CSV에서 해당하는 값을 찾아 반환하세요: 매출액, 영업이익, 인건비, 유형자산, 감가상각비, 이자비용.
CSV 위쪽 제목·머리말에 회사 이름(예: "샘플정밀(주) 손익계산서", "회사명: OO산업")이 있으면 "회사명"에 그 상호만 담으세요. 파일명·보고서 종류·기간은 회사명이 아닙니다. 회사 이름을 찾지 못하면 회사명은 null로 두세요.
CSV에 여러 회계연도(열)가 있으면 오래된 연도부터 최신 연도 순서로 최대 3개까지 배열에 담으세요(예: [2023년값, 2024년값, 2025년값]). 한 연도만 있으면 배열에 숫자 1개만 담으세요.
금액에 쉼표·원·괄호(음수)가 섞여 있어도 순수 숫자로 변환하세요. 괄호로 표시된 음수는 음수로 변환하세요.
찾지 못한 항목은 값들을 빈 배열 []로 반환하세요. 각 항목의 "단위"는 그 항목이 표시된 원래 금액 단위를 그대로 적으세요(원/천원/백만원/억원 중 확실치 않으면 "알수없음").
반드시 정해진 JSON 스키마에 맞춰서만 답하고, 다른 설명은 절대 덧붙이지 마세요.`;

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return 오류응답(res, 405, 'POST 요청만 지원합니다');

  const 키 = process.env.OPENAI_API_KEY;
  if (!키) return 오류응답(res, 400, 'GPT API 키(OPENAI_API_KEY)가 서버에 등록되지 않았습니다');

  let 본문;
  try { 본문 = JSON.parse(await 요청본문읽기(req)); } catch (e) { return 오류응답(res, 400, '요청 본문을 읽을 수 없습니다(JSON 형식이어야 함)'); }
  const csv = String(본문 && 본문.csv || '').trim();
  if (!csv) return 오류응답(res, 400, 'CSV 내용(csv)이 비어 있습니다');
  const 잘린CSV = csv.length > CSV_최대글자수 ? csv.slice(0, CSV_최대글자수) : csv;

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 시간제한_ms);
  try {
    const 응답 = await fetch(OPENAI_주소, {
      method: 'POST', signal: ctrl.signal,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${키}` },
      body: JSON.stringify({
        model: 모델,
        messages: [
          { role: 'system', content: 시스템프롬프트 },
          { role: 'user', content: `다음은 ERP에서 내보낸 CSV 재무 데이터입니다. 각 계정과목의 값을 찾아 주세요:\n\n${잘린CSV}` }
        ],
        response_format: { type: 'json_schema', json_schema: { name: 'financial_items', strict: true, schema: 응답스키마 } },
        temperature: 0
      })
    });
    const 결과 = await 응답.json();
    if (!응답.ok) {
      const 메시지 = (결과 && 결과.error && 결과.error.message) || `HTTP ${응답.status}`;
      return 오류응답(res, 502, 'GPT API 호출 실패', 메시지);
    }
    const 내용 = 결과.choices && 결과.choices[0] && 결과.choices[0].message && 결과.choices[0].message.content;
    if (!내용) return 오류응답(res, 502, 'GPT 응답에서 결과를 찾지 못했습니다');
    let 파싱;
    try { 파싱 = JSON.parse(내용); } catch (e) { return 오류응답(res, 502, 'GPT가 JSON이 아닌 형식으로 응답했습니다'); }
    res.statusCode = 200;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.end(JSON.stringify(파싱));
  } catch (e) {
    console.error('GPT 재무데이터 추출 실패:', e.name, e.message);
    오류응답(res, 502, 'GPT API 호출 실패', e.name === 'AbortError' ? `응답 시간 초과(${시간제한_ms / 1000}초)` : e.message);
  } finally { clearTimeout(timer); }
};

// Vercel Node 함수는 req가 스트림이라 body-parser 없이 직접 모아 읽는다
function 요청본문읽기(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', chunk => { data += chunk; if (data.length > 2_000_000) req.destroy(new Error('요청이 너무 큽니다')); });
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}
