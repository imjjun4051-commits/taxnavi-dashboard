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
  // 서버에 인증키가 미리 등록되어 있으면(Vercel 환경변수 BIZINFO_API_KEY) 그 값을 우선 사용 — 화면에서 입력하지 않아도 동작
  // 등록되어 있지 않으면 예전처럼 요청에 실려 온 인증키(crtfcKey)를 그대로 사용 (등록 전 임시 동작)
  const 등록된키 = process.env.BIZINFO_API_KEY;
  if (등록된키) 쿼리.set('crtfcKey', 등록된키);
  if (!쿼리.get('crtfcKey')) return 오류응답(res, 400, '인증키(crtfcKey)가 없습니다 — 서버에 등록되지 않았고, 요청에도 포함되지 않았습니다');
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
