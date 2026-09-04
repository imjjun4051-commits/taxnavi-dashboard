"""군별로 과거 매출이 실제로 늘었는지 따져 본다(성장 / 정체 / 감소 판정).

판정 규칙(리포트에도 그대로 적는다):
  - 3년 CAGR 중위값 >= +5% 이고 3년 증가 기업 비율 >= 60%  -> 성장
  - 3년 CAGR 중위값 <= -5% 또는 3년 증가 기업 비율 <= 40%  -> 감소
  - 그 밖   -> 정체
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from features import cagr, 성장률

성장_CAGR기준 = 0.05
성장_비율기준 = 0.60
감소_CAGR기준 = -0.05
감소_비율기준 = 0.40


def 판정(cagr3중위: float | None, 증가비율3: float | None) -> str:
    """3년 CAGR 중위값과 증가 기업 비율로 군의 성장 상태를 한 단어로 판정한다."""
    if cagr3중위 is None or 증가비율3 is None:
        return "판정 불가"
    if cagr3중위 >= 성장_CAGR기준 and 증가비율3 >= 성장_비율기준:
        return "성장"
    if cagr3중위 <= 감소_CAGR기준 or 증가비율3 <= 감소_비율기준:
        return "감소"
    return "정체"


def _회사별_성장지표(재무: pd.DataFrame) -> pd.DataFrame:
    """회사마다 5년 CAGR·3년 CAGR·최근 1년 성장률을 계산한다."""
    행들 = []
    for corp_code, 그룹 in 재무.groupby("corp_code"):
        연도별 = {int(r["연도"]): (None if pd.isna(r["매출액"]) else float(r["매출액"]))
                 for _, r in 그룹.iterrows()}
        있는연도 = sorted(y for y, v in 연도별.items() if v is not None)
        if not 있는연도:
            continue
        최신 = 있는연도[-1]
        행들.append({
            "corp_code": corp_code,
            "최신연도": 최신,
            "CAGR5": cagr(연도별.get(최신), 연도별.get(최신 - 4), 4),
            "CAGR3": cagr(연도별.get(최신), 연도별.get(최신 - 2), 2),
            "최근1년": 성장률(연도별.get(최신), 연도별.get(최신 - 1)),
            "매출액": 연도별.get(최신),
        })
    return pd.DataFrame(행들)


def 군별_성장분석(재무: pd.DataFrame, 군배정: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """군별 성장 지표 요약표와, 회사별 원자료 표를 함께 돌려준다."""
    지표 = _회사별_성장지표(재무).merge(군배정[["corp_code", "군번호"]], on="corp_code", how="inner")
    행들 = []
    for 군, 그룹 in 지표.groupby("군번호"):
        중위 = lambda 열: (None if 그룹[열].dropna().empty else float(그룹[열].dropna().median()))
        비율 = lambda 열: (None if 그룹[열].dropna().empty
                          else float((그룹[열].dropna() > 0).mean()))
        c3, r3 = 중위("CAGR3"), 비율("CAGR3")
        행들.append({
            "군번호": int(군), "기업수": int(len(그룹)),
            "CAGR5중위": 중위("CAGR5"), "CAGR3중위": c3, "최근1년중위": 중위("최근1년"),
            "증가비율_최근1년": 비율("최근1년"), "증가비율_3년": r3,
            "판정": 판정(c3, r3),
        })
    return pd.DataFrame(행들).sort_values("군번호").reset_index(drop=True), 지표


def 연도별_매출합계(재무: pd.DataFrame, 군배정: pd.DataFrame) -> pd.DataFrame:
    """군별·연도별 매출 합계 추이(리포트 표시용)."""
    합친표 = 재무.merge(군배정[["corp_code", "군번호"]], on="corp_code", how="inner")
    return (합친표.dropna(subset=["매출액"])
            .groupby(["군번호", "연도"])["매출액"].sum().reset_index()
            .sort_values(["군번호", "연도"]))


def 기준기업_백분위(기준특성: dict, 지표: pd.DataFrame, 소속군: int) -> dict:
    """기준 기업의 3년 CAGR·최근 성장률이 소속 군 안에서 상위 몇 %인지 계산한다."""
    같은군 = 지표[지표["군번호"] == 소속군]

    def 순위(값, 열):
        """군 안에서 몇 위인지(1위 = 가장 높음)와 상위 몇 %인지 함께 돌려준다."""
        후보 = 같은군[열].dropna()
        if 값 is None or 후보.empty:
            return None
        위 = int((후보 > 값).sum()) + 1              # 나보다 높은 회사 수 + 1 = 내 순위
        전체 = int(len(후보)) + 1                    # 기준 기업까지 포함한 모수
        return {"순위": 위, "모수": 전체, "상위퍼센트": 위 / 전체 * 100}

    return {
        "CAGR3순위": 순위(기준특성.get("매출CAGR3"), "CAGR3"),
        "최근1년순위": 순위(기준특성.get("매출성장률"), "최근1년"),
        "군기업수": int(len(같은군)),
    }
