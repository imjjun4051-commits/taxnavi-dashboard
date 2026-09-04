"""6개 업종 전부에 대해 비교군·K-means 결과를 만들어 docs/peer-cluster.json 하나로 합친다.

화면(index.html)은 사용자가 고른 업종의 묶음을 꺼내 쓰고, **우리 회사가 어느 군에 속하는지는
브라우저가 그 자리에서 계산**한다. 그래서 표준화 정보(평균·표준편차)와 군 중심 좌표를 함께 내보낸다.

실행: python3 tools/peer-cluster/build_all_industries.py [--year 2025] [--model gpt-4o-mini]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

여기 = Path(__file__).resolve().parent
sys.path.insert(0, str(여기))

import cluster, features, financials, gpt_label, growth, peers
from dart_client import DartClient

프로젝트루트 = 여기.parent.parent


def 업종하나(client, 업종표, 업종코드: str, 기준연도: int, 모델: str) -> dict | None:
    """업종 하나에 대해 비교군 수집 → 특성 → K-means → GPT 라벨 → 화면용 묶음을 만든다."""
    이름 = peers.업종이름.get(업종코드, 업종코드)
    비교군 = peers.업종별_비교군(업종표, 업종코드)
    print(f"\n▶ {이름}({업종코드}): 코스닥·코넥스 {len(비교군)}곳 매칭")
    if len(비교군) < 3:
        print("  건너뜀 — 상장사가 너무 적어 군집을 만들 수 없습니다")
        return None

    재무 = financials.재무수집(client, 비교군["corp_code"].tolist(), 기준연도)
    if 재무.empty:
        print("  건너뜀 — 재무 데이터를 받지 못했습니다")
        return None
    최신정보, _ = financials.최신연도_정리(재무, 기준연도)
    특성표 = features.비교군특성(재무).merge(비교군, on="corp_code", how="inner")
    특성목록 = list(features.필수특성)          # 기준 기업 입력이 제각각이라 필수 4개로 통일
    잘린표, X, 스케일러, 제외 = features.전처리(특성표, 특성목록)
    print(f"  분석 가능 {len(잘린표)}곳 (특성 결측 {len(제외)}곳 제외)")
    if len(잘린표) < 3:
        print("  건너뜀 — 분석 가능한 회사가 3곳 미만")
        return None

    군배정, 모델객체, 메타 = cluster.군집화(잘린표, X, 특성목록)
    성장요약, 성장지표 = growth.군별_성장분석(재무, 군배정)
    군요약 = gpt_label.군요약_만들기(군배정, 특성목록)
    라벨 = gpt_label.라벨_생성(군요약, 특성목록, 모델=모델)
    if 라벨.get("실패"):
        print(f"  ⚠ GPT 라벨 실패({라벨.get('실패사유')}) → A/B/C 임시 배정")
    라벨정보 = {g["군번호"]: g for g in 라벨["군"]}

    # 산점도에 찍을 점은 군별 비율을 유지한 표본으로 줄인다(통계는 전체 기준, 파일 크기 절약)
    표시상한 = 300
    표시대상 = 군배정
    if len(군배정) > 표시상한:
        비율 = 표시상한 / len(군배정)
        표시대상 = (군배정.groupby("군번호", group_keys=False)
                    .apply(lambda g: g.sample(max(3, int(round(len(g) * 비율))), random_state=42)))
    회사들 = [{
        "회사명": r["corp_name"], "군번호": int(r["군번호"]), "시장": r.get("시장", ""),
        "log매출액": round(float(r["log매출액"]), 2),
        "매출성장률": round(float(r["매출성장률"]) * 100, 1),
        "영업이익률": round(float(r["영업이익률"]) * 100, 1),
        "매출CAGR3": round(float(r["매출CAGR3"]) * 100, 1),
    } for _, r in 표시대상.iterrows()]

    군목록 = []
    for _, r in 성장요약.iterrows():
        번호 = int(r["군번호"]); g = 라벨정보.get(번호, {})
        같은군 = 군배정[군배정["군번호"] == 번호]
        군목록.append({
            "군번호": 번호, "라벨": g.get("라벨", ""), "이름": g.get("이름", ""),
            "핵심기준": g.get("핵심기준", ""), "특징요약": g.get("특징요약", ""),
            "기업수": int(r["기업수"]), "판정": r["판정"],
            "CAGR3중위": None if pd.isna(r["CAGR3중위"]) else round(float(r["CAGR3중위"]) * 100, 2),
            "증가비율_3년": None if pd.isna(r["증가비율_3년"]) else round(float(r["증가비율_3년"]) * 100, 1),
            "중위값": {k: (None if 같은군[k].dropna().empty
                        else round(float(같은군[k].dropna().median()) * (1 if k == "log매출액" else 100), 2))
                     for k in 특성목록},
        })

    return {
        "업종코드": 업종코드, "업종이름": 이름,
        "특성목록": 특성목록,
        # 브라우저가 우리 회사를 같은 자로 재려면 표준화 기준과 군 중심이 필요하다
        "표준화": {"평균": [round(float(v), 6) for v in 스케일러.mean_],
                 "표준편차": [round(float(v), 6) for v in 스케일러.scale_]},
        "군중심": [[round(float(v), 6) for v in c] for c in 모델객체.cluster_centers_],
        "메타": {"매칭수": int(len(비교군)), "분석수": int(len(잘린표)),
               "코스닥": int((비교군["시장"] == "코스닥").sum()),
               "코넥스": int((비교군["시장"] == "코넥스").sum()),
               "실루엣": None if 메타["실루엣"] is None else round(메타["실루엣"], 3),
               "약한군집": bool(메타.get("약한군집")),
               "최신사업연도": int(최신정보["최신연도"].max()) if not 최신정보.empty else 기준연도,
               "GPT라벨실패": bool(라벨.get("실패")), "표시수": int(len(표시대상))},
        "군": 군목록, "회사들": 회사들,
        "분류기준_설명": 라벨.get("분류기준_설명", ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="6개 업종 비교군 데이터 일괄 생성")
    ap.add_argument("--year", type=int, default=2025, help="기준연도(기본 2025)")
    ap.add_argument("--model", default=gpt_label.기본모델)
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    client = DartClient(no_cache=args.no_cache)
    업종표 = peers.상장사_업종표(client)
    print(f"코스닥·코넥스 상장사 {len(업종표):,}곳 확보")

    묶음 = {}
    for 코드 in peers.업종_KSIC범위:
        결과 = 업종하나(client, 업종표, 코드, args.year, args.model)
        if 결과:
            묶음[코드] = 결과

    출력 = {
        "_설명": "업종별 동종 상장기업 비교군·K-means 결과. 우리 회사의 군 배정은 브라우저가 실시간 계산합니다.",
        "생성시각": pd.Timestamp.now().isoformat(timespec="seconds"),
        "기준연도": args.year,
        "업종별": 묶음,
    }
    경로 = 프로젝트루트 / "docs" / "peer-cluster.json"
    경로.write_text(json.dumps(출력, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"\n✔ 저장: docs/peer-cluster.json ({len(묶음)}개 업종) — node tools/inline-data.js 로 index.html에 반영")
    print(f"  총 API 호출: {client.카운터.수:,}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
