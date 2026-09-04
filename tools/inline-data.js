// tools/inline-data.js — 데이터 JSON 파일을 index.html 안의 인라인 블록에 다시 채워 넣는 보조 스크립트
// 사용법 (프로젝트 폴더에서):  node tools/inline-data.js
// 하는 일: sample-data.json, docs/tax-rules.json, docs/industry-avg.json, docs/government-support.json, docs/peer-cluster.json 의 내용을
//          index.html 의 <script type="application/json" id="data-..."> 블록에 그대로 복사한다.
//          (index.html 을 더블클릭으로 열어도 동작하도록 데이터를 인라인하기 때문에, JSON 파일을 고치면 이 스크립트를 한 번 실행한다)
const fs = require('fs');
const path = require('path');
const root = path.join(__dirname, '..');
const 대응 = {
  'data-sample': 'sample-data.json',
  'data-tax-rules': 'docs/tax-rules.json',
  'data-industry-avg': 'docs/industry-avg.json',
  'data-support': 'docs/government-support.json',
  'data-peer-cluster': 'docs/peer-cluster.json'
};
const htmlPath = path.join(root, 'index.html');
let html = fs.readFileSync(htmlPath, 'utf8');
let 변경 = 0;
for (const [id, file] of Object.entries(대응)) {
  const raw = fs.readFileSync(path.join(root, file), 'utf8');
  const json = JSON.stringify(JSON.parse(raw), null, 1).replace(/<\/script/gi, '<\\/script'); // 문법 검사 + 안전 처리
  const re = new RegExp(`(<script type="application/json" id="${id}">)[\\s\\S]*?(</script>)`);
  if (!re.test(html)) { console.error(`index.html 에 #${id} 블록이 없습니다`); process.exit(1); }
  html = html.replace(re, (_, a, b) => { 변경++; return a + json + b; });
  console.log(`✓ ${file} → #${id}`);
}
fs.writeFileSync(htmlPath, html);
console.log(`index.html 갱신 완료 (${변경}개 블록, ${(html.length / 1024).toFixed(1)} KB)`);
