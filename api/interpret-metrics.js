// api/interpret-metrics.js — 업종 평균 비교 진단 표의 "해석"을 GPT가 실시간으로 써 준다.
// 브라우저가 지표 숫자(우리 회사 / 업종 평균 / 차이)만 보내면 이 서버가 대신 OpenAI를 호출한다.
// 인증키는 서버 환경변수(OPENAI_API_KEY)에만 있고 응답·로그에 남기지 않는다. 회사명 등 식별정보는 받지 않는다.
const OPENAI_주소 = 'https://api.openai.com/v1/chat/completions';
const 기본모델 = 'gpt-4o-mini';
const 시간제한_ms = 20_000;
const 최대지표수 = 8;

// 낮을수록 좋은 지표는 GPT가 방향을 반대로 읽지 않도록 알려 준다
const 낮을수록좋음 = ['이자비용비율', '인건비비율', '감가상각비율'];

const 시스템프롬프트 = `당신은 한국 중소기업 대표에게 재무 지표를 설명하는 세무·재무 도우미입니다.
각 지표에 대해 "우리 회사 값"과 "업종 평균", 그 차이(%p)를 보고 한국어로 1~2문장 해석을 씁니다.
규칙:
- 주어진 숫자만 사용하고, 없는 숫자나 사실을 지어내지 마세요.
- 비전공자가 이해할 수 있는 쉬운 말로 쓰고, 가능하면 대표가 할 수 있는 다음 행동을 한 가지 덧붙이세요.
- 이자비용비율·인건비비율·감가상각비율은 값이 낮을수록 유리한 지표입니다. 방향을 반대로 해석하지 마세요.
- 단정적인 세무 판단("반드시 공제된다" 등)이나 투자 권유는 하지 마세요.
- 각 해석은 120자 이내로 간결하게.
반드시 지정된 JSON 형식으로만 답하세요.`;

const 응답스키마 = {
  type: 'object', additionalProperties: false,
  properties: {
    해석: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: { 지표: { type: 'string' }, 설명: { type: 'string' } },
        required: ['지표', '설명'],
      },
    },
  },
  required: ['해석'],
};

function 오류응답(res, 코드, 메시지, 상세) {
  res.statusCode = 코드;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(상세 ? { error: 메시지, detail: 상세 } : { error: 메시지 }));
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return 오류응답(res, 405, 'POST 요청만 지원합니다');

  const 키 = process.env.OPENAI_API_KEY;
  if (!키) return 오류응답(res, 400, 'GPT API 키(OPENAI_API_KEY)가 서버에 등록되지 않았습니다');

  let 본문;
  try { 본문 = JSON.parse(await 요청본문읽기(req)); }
  catch (e) { return 오류응답(res, 400, '요청 본문을 읽을 수 없습니다(JSON 형식이어야 함)'); }

  const 업종 = String((본문 && 본문.업종) || '').slice(0, 40);
  const 지표들 = Array.isArray(본문 && 본문.지표들) ? 본문.지표들.slice(0, 최대지표수) : [];
  if (!지표들.length) return 오류응답(res, 400, '지표 목록(지표들)이 비어 있습니다');

  const 숫자 = v => (v === null || v === undefined || Number.isNaN(Number(v))) ? null : Number(v);
  const 정리된 = 지표들.map(m => ({
    지표: String(m.지표 || '').slice(0, 30),
    우리: 숫자(m.우리), 평균: 숫자(m.평균), 차이: 숫자(m.차이),
    방향: 낮을수록좋음.includes(String(m.지표)) ? '낮을수록 좋음' : '높을수록 좋음',
  })).filter(m => m.지표);

  const 사용자프롬프트 = `업종: ${업종 || '(미상)'}\n단위: %, 차이는 %p (우리 회사 − 업종 평균)\n\n`
    + JSON.stringify(정리된, null, 1)
    + `\n\n각 지표마다 하나씩, 위 "지표" 이름을 그대로 써서 해석을 작성하세요.`;

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 시간제한_ms);
  try {
    const 응답 = await fetch(OPENAI_주소, {
      method: 'POST', signal: ctrl.signal,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${키}` },
      body: JSON.stringify({
        model: 본문.model || 기본모델,
        messages: [
          { role: 'system', content: 시스템프롬프트 },
          { role: 'user', content: 사용자프롬프트 },
        ],
        response_format: { type: 'json_schema', json_schema: { name: 'metric_interpretations', strict: true, schema: 응답스키마 } },
        temperature: 0.2,
      }),
    });
    const 결과 = await 응답.json();
    if (!응답.ok) {
      const 메시지 = (결과 && 결과.error && 결과.error.message) || `HTTP ${응답.status}`;
      return 오류응답(res, 502, 'GPT API 호출 실패', 메시지);
    }
    const 내용 = 결과.choices && 결과.choices[0] && 결과.choices[0].message && 결과.choices[0].message.content;
    if (!내용) return 오류응답(res, 502, 'GPT 응답에서 결과를 찾지 못했습니다');
    let 파싱;
    try { 파싱 = JSON.parse(내용); }
    catch (e) { return 오류응답(res, 502, 'GPT가 JSON이 아닌 형식으로 응답했습니다'); }
    res.statusCode = 200;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.end(JSON.stringify(파싱));
  } catch (e) {
    console.error('지표 해석 생성 실패:', e.name, e.message);
    오류응답(res, 502, 'GPT API 호출 실패', e.name === 'AbortError' ? `응답 시간 초과(${시간제한_ms / 1000}초)` : e.message);
  } finally { clearTimeout(timer); }
};

// Vercel Node 함수는 req가 스트림이라 body-parser 없이 직접 모아 읽는다
function 요청본문읽기(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', chunk => { data += chunk; if (data.length > 200_000) req.destroy(new Error('요청이 너무 큽니다')); });
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}
