"""비교군의 최근 5개 사업연도 재무제표 수집.

fnlttMultiAcnt(다중회사 주요계정)를 100개씩 묶어 연도별로 부른다.
연결(CFS)을 우선 쓰고 없으면 개별(OFS)을 쓰며, 어느 쪽을 썼는지 열로 남긴다.
"""
from __future__ import annotations

import pandas as pd

from dart_client import DartClient, 금액숫자

# DART 계정과목명 -> 우리가 쓰는 이름
계정매핑 = {
    "매출액": "매출액",
    "수익(매출액)": "매출액",
    "영업수익": "매출액",
    "영업이익": "영업이익",
    "영업이익(손실)": "영업이익",
    "당기순이익": "당기순이익",
    "당기순이익(손실)": "당기순이익",
    "자산총계": "자산총계",
    "부채총계": "부채총계",
    "자본총계": "자본총계",
}


def 재무수집(client: DartClient, corp_codes: list[str], 기준연도: int, 연수: int = 5) -> pd.DataFrame:
    """corp_code 100개씩 묶어 (기준연도-연수+1 … 기준연도) 사업보고서를 모은다."""
    연도들 = list(range(기준연도 - 연수 + 1, 기준연도 + 1))
    묶음들 = [corp_codes[i:i + 100] for i in range(0, len(corp_codes), 100)]
    행들 = []
    for 연도 in 연도들:
        for 묶음 in 묶음들:
            try:
                결과 = client.다중회사_주요계정(묶음, 연도)
            except Exception as e:
                print(f"    · {연도}년 재무 조회 실패({len(묶음)}곳): {e}")
                continue
            for 항목 in 결과.get("list", []) or []:
                이름 = 계정매핑.get((항목.get("account_nm") or "").strip())
                if not 이름:
                    continue
                행들.append({
                    "corp_code": 항목.get("corp_code"),
                    "연도": 연도,
                    "계정": 이름,
                    "fs_div": 항목.get("fs_div"),
                    "금액": 금액숫자(항목.get("thstrm_amount")),
                })
    if not 행들:
        return pd.DataFrame(columns=["corp_code", "연도", "매출액", "영업이익", "당기순이익",
                                     "자산총계", "부채총계", "자본총계", "fs_div"])
    return _연결우선_피벗(pd.DataFrame(행들))


def _연결우선_피벗(긴표: pd.DataFrame) -> pd.DataFrame:
    """(회사, 연도)별로 연결(CFS)을 우선 고르고, 계정을 열로 펼친다."""
    긴표 = 긴표.dropna(subset=["corp_code", "금액"]).copy()
    긴표["우선순위"] = (긴표["fs_div"] == "CFS").map({True: 0, False: 1})
    긴표 = 긴표.sort_values("우선순위").drop_duplicates(["corp_code", "연도", "계정"], keep="first")

    넓은표 = 긴표.pivot_table(index=["corp_code", "연도"], columns="계정",
                             values="금액", aggfunc="first").reset_index()
    쓴구분 = (긴표.sort_values("우선순위")
                .drop_duplicates(["corp_code", "연도"], keep="first")[["corp_code", "연도", "fs_div"]])
    넓은표 = 넓은표.merge(쓴구분, on=["corp_code", "연도"], how="left")
    for 열 in ["매출액", "영업이익", "당기순이익", "자산총계", "부채총계", "자본총계"]:
        if 열 not in 넓은표.columns:
            넓은표[열] = pd.NA
    넓은표.columns.name = None
    열순서 = ["corp_code", "연도", "매출액", "영업이익", "당기순이익",
              "자산총계", "부채총계", "자본총계", "fs_div"]
    return 넓은표[열순서].sort_values(["corp_code", "연도"]).reset_index(drop=True)


def 최신연도_정리(재무: pd.DataFrame, 기준연도: int):
    """회사별 최신 사업연도를 찾고, 매출액이 없는 회사는 제외 사유를 남긴다.

    반환: (쓸 수 있는 회사 목록 DataFrame, 제외 사유 DataFrame)
    """
    if 재무.empty:
        return pd.DataFrame(columns=["corp_code", "최신연도", "결산지연"]), pd.DataFrame(columns=["corp_code", "사유"])

    매출있음 = 재무[재무["매출액"].notna()]
    최신 = (매출있음.groupby("corp_code")["연도"].max().reset_index()
            .rename(columns={"연도": "최신연도"}))
    최신["결산지연"] = 최신["최신연도"] < 기준연도       # 기준연도 사업보고서가 아직 없는 회사

    제외 = 재무.loc[~재무["corp_code"].isin(최신["corp_code"]), ["corp_code"]].drop_duplicates()
    제외["사유"] = "최신 연도 매출액 없음(코넥스 등 공시 누락)"
    return 최신, 제외.reset_index(drop=True)
