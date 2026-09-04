"""K-means에 넣을 특성(숫자 지표) 만들기.

기준 기업(비상장)과 비교군(상장사)을 **똑같은 방식**으로 계산해야 비교가 성립한다.
필수 4개는 항상 쓰고, 보조 3개는 기준 기업 입력이 모두 있을 때만 쓴다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

필수특성 = ["log매출액", "매출성장률", "영업이익률", "매출CAGR3"]
보조특성 = ["부채비율", "총자산회전율", "순이익률"]


def 안전나눗셈(분자, 분모):
    """0으로 나누기·결측을 None으로 처리하는 나눗셈."""
    if 분자 is None or 분모 is None:
        return None
    try:
        분자, 분모 = float(분자), float(분모)
    except (TypeError, ValueError):
        return None
    if 분모 == 0 or not np.isfinite(분자) or not np.isfinite(분모):
        return None
    값 = 분자 / 분모
    return 값 if np.isfinite(값) else None


def 성장률(최신, 이전):
    """최신/이전 - 1. 이전이 0 이하면 계산 불가(None)."""
    if 최신 is None or 이전 is None:
        return None
    try:
        최신, 이전 = float(최신), float(이전)
    except (TypeError, ValueError):
        return None
    if 이전 <= 0:
        return None
    return 최신 / 이전 - 1


def cagr(최신, 과거, 기간: int):
    """연평균 성장률 = (최신/과거)^(1/기간) - 1. 과거가 0 이하이거나 최신이 음수면 None."""
    if 최신 is None or 과거 is None or 기간 <= 0:
        return None
    try:
        최신, 과거 = float(최신), float(과거)
    except (TypeError, ValueError):
        return None
    if 과거 <= 0 or 최신 < 0:
        return None
    return (최신 / 과거) ** (1 / 기간) - 1


def 회사특성(매출: dict, 영업이익: dict, 당기순이익=None, 자산총계=None, 부채총계=None, 자본총계=None):
    """연도->값 딕셔너리들로 한 회사의 특성을 계산한다. 연도 키는 int/str 모두 허용."""
    연도 = sorted(int(y) for y, v in 매출.items() if v is not None)
    if not 연도:
        return {}
    가져오기 = lambda d, y: (d or {}).get(y, (d or {}).get(str(y)))
    최신 = 연도[-1]
    S = 가져오기(매출, 최신)
    S전 = 가져오기(매출, 최신 - 1)
    S3 = 가져오기(매출, 최신 - 2)          # 3개년 = 2번 성장 -> 지수 1/2
    OP = 가져오기(영업이익, 최신)

    특성 = {
        "최신연도": 최신,
        "매출액": S,
        "영업이익": OP,
        "log매출액": float(np.log10(S)) if S and S > 0 else None,
        "매출성장률": 성장률(S, S전),
        "영업이익률": 안전나눗셈(OP, S),
        "매출CAGR3": cagr(S, S3, 2),
    }
    NI, A, L, E = (가져오기(d, 최신) for d in (당기순이익, 자산총계, 부채총계, 자본총계))
    특성["부채비율"] = 안전나눗셈(L, E)
    특성["총자산회전율"] = 안전나눗셈(S, A)
    특성["순이익률"] = 안전나눗셈(NI, S)
    return 특성


def 비교군특성(재무: pd.DataFrame) -> pd.DataFrame:
    """revenue_history 형태의 표에서 회사별 특성을 만든다."""
    행들 = []
    for corp_code, 그룹 in 재무.groupby("corp_code"):
        만들기 = lambda 열: {int(r["연도"]): (None if pd.isna(r[열]) else r[열])
                            for _, r in 그룹.iterrows()} if 열 in 그룹 else {}
        특성 = 회사특성(만들기("매출액"), 만들기("영업이익"), 만들기("당기순이익"),
                       만들기("자산총계"), 만들기("부채총계"), 만들기("자본총계"))
        if not 특성:
            continue
        특성["corp_code"] = corp_code
        행들.append(특성)
    return pd.DataFrame(행들)


# 기준 기업 입력은 백만원 단위인데 DART 비교군 금액은 원 단위라, 같은 축에서 비교하려면 환산이 필요하다
백만원_to_원 = 1_000_000


def 기준기업특성(target: dict, 단위배수: int = 백만원_to_원) -> dict:
    """sample_target.json 내용을 비교군과 같은 방식(원 단위)으로 계산한다."""
    숫자화 = lambda d: {int(k): (v * 단위배수) for k, v in (d or {}).items() if v is not None}
    return 회사특성(
        숫자화(target.get("매출액")), 숫자화(target.get("영업이익")),
        숫자화(target.get("당기순이익")), 숫자화(target.get("자산총계")),
        숫자화(target.get("부채총계")), 숫자화(target.get("자본총계")),
    )


def 사용할특성(기준특성: dict) -> tuple[list[str], str]:
    """기준 기업이 보조 특성을 모두 갖췄으면 7개, 하나라도 없으면 필수 4개만 쓴다."""
    if all(기준특성.get(k) is not None for k in 보조특성):
        return 필수특성 + 보조특성, "필수 4개 + 보조 3개 특성 사용"
    return list(필수특성), "필수 4개 특성만 사용 (기준 기업의 당기순이익·자산·부채·자본 입력이 없음)"


def 윈저라이즈(표: pd.DataFrame, 열들: list[str]) -> pd.DataFrame:
    """1~99 백분위 밖의 극단값을 그 경계값으로 눌러 준다(이상치가 군집을 흔들지 않게)."""
    잘린 = 표.copy()
    for 열 in 열들:
        값 = pd.to_numeric(잘린[열], errors="coerce")
        하, 상 = 값.quantile(0.01), 값.quantile(0.99)
        잘린[열] = 값.clip(하, 상)
    return 잘린


def 전처리(비교군: pd.DataFrame, 특성목록: list[str]):
    """결측·무한대 제거 -> 윈저라이징 -> 표준화. (쓸 수 있는 표, 스케일된 배열, 스케일러, 제외 표)"""
    작업 = 비교군.copy()
    for 열 in 특성목록:
        작업[열] = pd.to_numeric(작업.get(열), errors="coerce")
    작업 = 작업.replace([np.inf, -np.inf], np.nan)

    쓸수있음 = 작업.dropna(subset=특성목록)
    제외 = 작업[~작업.index.isin(쓸수있음.index)][["corp_code"] + 특성목록].copy()
    if not 제외.empty:
        제외["사유"] = "특성 결측(재무 항목 누락 또는 계산 불가)"

    잘린 = 윈저라이즈(쓸수있음, 특성목록)
    스케일러 = StandardScaler().fit(잘린[특성목록].to_numpy(dtype=float))
    X = 스케일러.transform(잘린[특성목록].to_numpy(dtype=float))
    return 잘린.reset_index(drop=True), X, 스케일러, 제외.reset_index(drop=True)
