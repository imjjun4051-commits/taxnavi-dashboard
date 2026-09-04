"""동종 상장기업 비교군 분석 CLI.

실행 예:
  python tools/peer-cluster/run.py --target tools/peer-cluster/sample_target.json
  python tools/peer-cluster/run.py --target ... --dry-run     # API 키 없이 가짜 데이터로 전체 실행
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

여기 = Path(__file__).resolve().parent
sys.path.insert(0, str(여기))          # 모듈을 이름 그대로 import 하기 위해

import cluster, disclosures, features, financials, gpt_label, growth, peers, report
from dart_client import DartClient


def 인자읽기():
    """CLI 옵션을 정의한다."""
    p = argparse.ArgumentParser(description="동종 상장기업(코스닥·코넥스) 비교군 분석")
    p.add_argument("--target", required=True, help="기준 기업 JSON 경로")
    p.add_argument("--year", type=int, default=None, help="기준연도(기본: target의 기준연도)")
    p.add_argument("--min-peers", type=int, default=15, help="최소 비교군 수(기본 15)")
    p.add_argument("--model", default=gpt_label.기본모델, help="GPT 모델(기본 gpt-4o-mini)")
    p.add_argument("--no-cache", action="store_true", help="캐시 무시하고 새로 호출")
    p.add_argument("--dry-run", action="store_true", help="API 호출 없이 tests/fixtures 가짜 데이터로 실행")
    return p.parse_args()


class 가짜클라이언트:
    """--dry-run용. tests/fixtures의 가짜 응답만 돌려주고 외부 호출을 하지 않는다."""

    def __init__(self):
        self.no_cache = False
        self.카운터 = type("C", (), {"수": 0})()
        폴더 = 여기 / "tests" / "fixtures"
        self.업종표 = pd.read_csv(폴더 / "listed_industry.csv", dtype=str)
        self.재무 = pd.read_csv(폴더 / "financials.csv", dtype={"corp_code": str})
        self.공시 = json.loads((폴더 / "disclosures.json").read_text(encoding="utf-8"))

    def 공시목록(self, corp_code, 시작일, 종료일):
        return {"status": "000", "list": self.공시.get(corp_code, [])}


def 실행(args) -> int:
    """전체 파이프라인을 순서대로 돌린다."""
    target = json.loads(Path(args.target).read_text(encoding="utf-8"))
    기준연도 = args.year or int(target.get("기준연도"))
    회사명 = target.get("회사명", "기준기업")
    print(f"▶ 기준 기업: {회사명} (업종 {target.get('업종코드')}, 기준연도 {기준연도})")

    # 1) 비교군 만들기
    if args.dry_run:
        print("  [--dry-run] tests/fixtures의 가짜 데이터로 실행합니다(외부 호출 없음)")
        client = 가짜클라이언트()
        업종표 = client.업종표
    else:
        client = DartClient(no_cache=args.no_cache)
        업종표 = peers.상장사_업종표(client)
    자릿수분포 = peers.업종코드_자릿수분포(업종표)
    기준특성 = features.기준기업특성(target)
    특성목록, 특성설명 = features.사용할특성(기준특성)
    print(f"  {특성설명}")

    # 2~3) 업종 범위를 좁은 것부터 넓혀 가며, **분석에 실제로 쓸 수 있는 회사 수**가 최소 인원을 넘을 때까지 반복한다.
    #      (매칭만 되고 재무가 비어 있는 회사가 많아, 매칭 수로만 판단하면 정작 군집에 쓸 표본이 모자란다)
    후보들 = peers.비교군_후보들(업종표, target["업종코드"])
    선택 = None
    단계기록 = []
    for 후보 in 후보들:
        비교군 = 후보["비교군"]
        if 비교군.empty:
            단계기록.append({"L": 후보["L"], "매칭": 0, "사용가능": 0})
            continue
        if args.dry_run:
            재무 = client.재무[client.재무["corp_code"].isin(비교군["corp_code"])].copy()
        else:
            재무 = financials.재무수집(client, 비교군["corp_code"].tolist(), 기준연도)
        최신정보, 재무제외 = financials.최신연도_정리(재무, 기준연도)
        비교군특성 = features.비교군특성(재무).merge(비교군, on="corp_code", how="inner")
        잘린표, X, 스케일러, 특성제외 = features.전처리(비교군특성, 특성목록)
        단계기록.append({"L": 후보["L"], "매칭": len(비교군), "사용가능": len(잘린표)})
        print(f"  업종 {후보['L']}자리 매칭: {len(비교군)}곳 중 분석 가능 {len(잘린표)}곳")
        선택 = dict(L=후보["L"], 시작L=후보["시작L"], 비교군=비교군, 재무=재무, 최신정보=최신정보,
                    재무제외=재무제외, 잘린표=잘린표, X=X, 스케일러=스케일러, 특성제외=특성제외)
        if len(잘린표) >= args.min_peers:
            break

    if 선택 is None:
        print("  ✖ 비교군이 하나도 없습니다. 업종코드를 확인해 주세요.")
        return 1
    비교군, 재무 = 선택["비교군"], 선택["재무"]
    최신정보, 재무제외 = 선택["최신정보"], 선택["재무제외"]
    잘린표, X, 스케일러, 특성제외 = 선택["잘린표"], 선택["X"], 선택["스케일러"], 선택["특성제외"]
    경고 = None
    if len(잘린표) < args.min_peers:
        경고 = (f"업종 중분류(2자리)까지 넓혔지만 분석 가능한 비교군이 {len(잘린표)}곳으로 "
               f"최소 {args.min_peers}곳에 못 미칩니다. 군 크기가 치우칠 수 있으니 참고용으로만 보세요.")
        print(f"  ⚠ {경고}")
    매칭정보 = {"최종L": 선택["L"], "시작L": 선택["시작L"], "확장여부": 선택["L"] < 선택["시작L"],
              "단계별개수": 단계기록, "최소개수": args.min_peers, "경고": 경고}
    print(f"  비교군 확정: {len(비교군)}곳 매칭 · 분석 {len(잘린표)}곳 (L={선택['L']}"
          + (", 확장됨" if 매칭정보["확장여부"] else "") + ")")
    if len(잘린표) < 3:
        print(f"  ✖ 특성을 계산할 수 있는 회사가 {len(잘린표)}곳뿐이라 3개 군으로 나눌 수 없습니다.")
        return 1

    # 4) K-means + 기준 기업 배정
    군배정, 모델, 군집메타 = cluster.군집화(잘린표, X, 특성목록)
    배정 = cluster.기준기업_배정(기준특성, 특성목록, 스케일러, 모델)
    실루엣표시 = f"{군집메타['실루엣']:.3f}" if 군집메타["실루엣"] is not None else "계산 불가"
    print(f"  군집화 완료 (실루엣 {실루엣표시}) → 기준 기업은 {배정['소속군']}번 군")

    # 5) GPT 라벨
    군요약 = gpt_label.군요약_만들기(군배정, 특성목록)
    라벨 = gpt_label.라벨_생성(군요약, 특성목록, 모델=args.model, dry_run=args.dry_run)
    if 라벨.get("실패"):
        print(f"  ⚠ GPT 라벨 실패({라벨.get('실패사유')}) → A/B/C 임시 배정")

    # 6) 성장 분석
    성장요약, 성장지표 = growth.군별_성장분석(재무, 군배정)
    백분위 = growth.기준기업_백분위(기준특성, 성장지표, 배정["소속군"])
    연도별합계 = growth.연도별_매출합계(재무, 군배정)

    # 7) 소속 군 공시
    소속회사 = 군배정[군배정["군번호"] == 배정["소속군"]][["corp_code", "corp_name"]]
    공시 = disclosures.공시수집(client, 소속회사)
    공시유형 = disclosures.유형별_건수(공시)
    print(f"  소속 군 {len(소속회사)}곳의 공시 {len(공시)}건 수집")

    # 8) CSV 4개 저장
    라벨맵 = {g["군번호"]: g["라벨"] for g in 라벨["군"]}
    출력 = 군배정.copy()
    출력["라벨"] = 출력["군번호"].map(라벨맵)
    저장 = {
        "peers.csv": 비교군,
        "revenue_history.csv": 재무,
        "clusters.csv": 출력,
        "growth_by_cluster.csv": 성장요약.assign(라벨=lambda d: d["군번호"].map(라벨맵)),
        "disclosures.csv": 공시,
    }
    for 이름, 표 in 저장.items():
        표.to_csv(여기 / 이름, index=False, encoding="utf-8-sig")
    print(f"  CSV 저장: {', '.join(저장)}")

    # 9) index.html이 읽을 요약 JSON (docs/peer-cluster.json → tools/inline-data.js가 인라인)
    라벨정보 = {g["군번호"]: g for g in 라벨["군"]}
    산점도 = [{
        "회사명": r["corp_name"], "군번호": int(r["군번호"]),
        "log매출액": round(float(r["log매출액"]), 3),
        "매출성장률": round(float(r["매출성장률"]) * 100, 2),
        "영업이익률": round(float(r["영업이익률"]) * 100, 2),
        "매출CAGR3": round(float(r["매출CAGR3"]) * 100, 2),
        "시장": r.get("시장", ""),
    } for _, r in 출력.iterrows()]
    군요약JSON = []
    for _, r in 성장요약.iterrows():
        g = 라벨정보.get(int(r["군번호"]), {})
        같은군 = 출력[출력["군번호"] == int(r["군번호"])]
        군요약JSON.append({
            "군번호": int(r["군번호"]), "라벨": g.get("라벨", ""), "이름": g.get("이름", ""),
            "핵심기준": g.get("핵심기준", ""), "특징요약": g.get("특징요약", ""),
            "기업수": int(r["기업수"]), "판정": r["판정"],
            "CAGR3중위": None if pd.isna(r["CAGR3중위"]) else round(float(r["CAGR3중위"]) * 100, 2),
            "증가비율_3년": None if pd.isna(r["증가비율_3년"]) else round(float(r["증가비율_3년"]) * 100, 1),
            "중위값": {k: (None if 같은군[k].dropna().empty else round(float(같은군[k].dropna().median()) * (1 if k == "log매출액" else 100), 2))
                     for k in 특성목록},
        })
    peer_json = {
        "_설명": "tools/peer-cluster/run.py가 만든 동종 상장기업 비교군 분석 요약. 화면 표시용이며 투자 권유가 아닙니다.",
        "생성시각": pd.Timestamp.now().isoformat(timespec="seconds"),
        "기준기업": {"회사명": 회사명, "업종코드": target.get("업종코드"),
                  "특성": {k: (None if 기준특성.get(k) is None else round(float(기준특성[k]) * (1 if k == "log매출액" else 100), 2))
                          for k in 특성목록}},
        "메타": {"매칭자릿수": 매칭정보["최종L"], "확장여부": 매칭정보["확장여부"],
               "매칭수": int(len(비교군)), "분석수": int(len(출력)),
               "코스닥": int((비교군["시장"] == "코스닥").sum()), "코넥스": int((비교군["시장"] == "코넥스").sum()),
               "실루엣": None if 군집메타["실루엣"] is None else round(군집메타["실루엣"], 3),
               "약한군집": bool(군집메타.get("약한군집")), "특성목록": 특성목록, "특성설명": 특성설명,
               "최신사업연도": int(최신정보["최신연도"].max()) if not 최신정보.empty else 기준연도,
               "경고": 매칭정보.get("경고"), "GPT라벨실패": bool(라벨.get("실패"))},
        "군": 군요약JSON,
        "배정": {"소속군": 배정["소속군"], "차순위군": 배정["차순위군"],
               "거리": {str(k): round(v, 3) for k, v in 배정["거리"].items()}},
        "순위": {"CAGR3": 백분위.get("CAGR3순위"), "최근1년": 백분위.get("최근1년순위")},
        "회사들": 산점도,
        "분류기준_설명": 라벨.get("분류기준_설명", ""),
    }
    # --dry-run은 가짜 데이터라 화면에 노출되면 안 되므로 docs/를 덮어쓰지 않는다
    if args.dry_run:
        docs = 여기 / "peer-cluster.dryrun.json"
        docs.write_text(json.dumps(peer_json, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  (dry-run) 화면용 JSON 예시만 저장: {docs.name} — docs/peer-cluster.json은 건드리지 않음")
    else:
        docs = 여기.parent.parent / "docs" / "peer-cluster.json"
        docs.write_text(json.dumps(peer_json, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  화면용 JSON 저장: {docs.relative_to(여기.parent.parent)} (node tools/inline-data.js 로 index.html에 반영)")

    # 10) 리포트
    그림경로 = None
    상자파일 = report.리포트폴더 / f"peer-cluster_{회사명}_{pd.Timestamp.now():%Y%m%d}_cagr.png"
    if report.상자그림(성장지표, {g["군번호"]: g for g in 라벨["군"]}, 상자파일):
        그림경로 = 상자파일.name
    최신사업연도 = int(최신정보["최신연도"].max()) if not 최신정보.empty else 기준연도
    파일 = report.리포트작성({
        "target": target, "기준연도": 기준연도, "최신사업연도": 최신사업연도,
        "peers": 비교군, "매칭정보": 매칭정보, "자릿수분포": 자릿수분포,
        "군배정": 출력, "특성제외": 특성제외, "특성목록": 특성목록, "특성설명": 특성설명,
        "기준특성": 기준특성, "배정": 배정, "군집메타": 군집메타, "라벨": 라벨,
        "성장요약": 성장요약, "성장지표": 성장지표, "연도별합계": 연도별합계, "백분위": 백분위,
        "공시": 공시, "공시유형": 공시유형, "그림경로": 그림경로,
        "호출수": client.카운터.수,
    })
    print(f"✔ 리포트: {파일}")
    return 0


def main() -> int:
    args = 인자읽기()
    try:
        return 실행(args)
    except Exception as e:
        print(f"✖ 실행 실패: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
