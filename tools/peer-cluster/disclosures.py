"""기준 기업이 속한 군의 회사들에 대해 최근 12개월 공시를 모은다."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from dart_client import DartClient, 공시링크

# 투자자가 주의 깊게 볼 만한 공시 키워드
주의키워드 = ["유상증자", "전환사채", "최대주주 변경", "최대주주변경", "영업정지",
             "감사의견", "상장폐지", "합병", "분할"]


def 주의여부(공시명: str) -> bool:
    """공시명에 주의 키워드가 들어 있는지 확인한다."""
    이름 = 공시명 or ""
    return any(k in 이름 for k in 주의키워드)


def 공시수집(client: DartClient, 회사들: pd.DataFrame, 오늘: date | None = None) -> pd.DataFrame:
    """소속 군 회사마다 최근 12개월 공시목록을 1회씩 호출해 모은다."""
    오늘 = 오늘 or date.today()
    시작 = (오늘 - timedelta(days=365)).strftime("%Y%m%d")
    끝 = 오늘.strftime("%Y%m%d")

    행들 = []
    for _, 회사 in 회사들.iterrows():
        try:
            결과 = client.공시목록(회사["corp_code"], 시작, 끝)
        except Exception as e:
            print(f"    · {회사.get('corp_name')} 공시 조회 실패: {e}")
            continue
        for 항목 in 결과.get("list", []) or []:
            이름 = 항목.get("report_nm", "")
            행들.append({
                "접수일": 항목.get("rcept_dt", ""),
                "corp_code": 회사["corp_code"],
                "회사명": 회사.get("corp_name", 항목.get("corp_name", "")),
                "공시명": 이름,
                "제출인": 항목.get("flr_nm", ""),
                "주의": "주의" if 주의여부(이름) else "",
                "링크": 공시링크(항목.get("rcept_no", "")),
            })
    if not 행들:
        return pd.DataFrame(columns=["접수일", "corp_code", "회사명", "공시명", "제출인", "주의", "링크"])
    return pd.DataFrame(행들).sort_values("접수일", ascending=False).reset_index(drop=True)


def 유형별_건수(공시: pd.DataFrame, 상위: int = 10) -> pd.DataFrame:
    """공시명 앞부분을 유형으로 보고 건수를 센다(대략적인 분류)."""
    if 공시.empty:
        return pd.DataFrame(columns=["공시유형", "건수"])
    유형 = 공시["공시명"].fillna("").str.replace(r"\[.*?\]", "", regex=True).str.strip().str.split().str[0]
    표 = 유형.value_counts().head(상위).reset_index()
    표.columns = ["공시유형", "건수"]
    return 표
