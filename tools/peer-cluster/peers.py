"""비교군(코스닥·코넥스 상장기업) 만들기.

전체 상장사의 표준산업분류(induty_code)를 모아 두고, 기준 기업의 업종코드와
앞자리(prefix)가 같은 회사를 고른다. 15개가 안 되면 비교 자릿수를 줄여 넓힌다.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from dart_client import DartClient

여기 = Path(__file__).resolve().parent
업종캐시 = 여기 / "cache" / "listed_industry.csv"
시장이름 = {"K": "코스닥", "N": "코넥스", "Y": "유가증권", "E": "기타"}


def 상장사_업종표(client: DartClient, 진행표시: bool = True) -> pd.DataFrame:
    """코스닥·코넥스 상장사의 업종코드 표를 만든다(최초 1회만 대량 호출, 이후 캐시)."""
    if 업종캐시.exists() and not client.no_cache:
        return pd.read_csv(업종캐시, dtype=str)

    전체 = client.고유번호목록()
    상장 = [c for c in 전체 if c["stock_code"]]
    if 진행표시:
        print(f"  상장사 {len(상장):,}곳의 기업개황을 조회합니다(최초 1회, 이후 캐시 사용)")

    행들 = []
    for i, 회사 in enumerate(상장, 1):
        try:
            개황 = client.기업개황(회사["corp_code"])
        except Exception as e:                      # 한 회사 실패가 전체를 막지 않게 한다
            print(f"    · {회사['corp_name']} 개황 조회 실패: {e}")
            continue
        if 개황.get("corp_cls") not in ("K", "N"):  # 코스닥·코넥스만 남긴다
            continue
        행들.append({
            "corp_code": 개황.get("corp_code") or 회사["corp_code"],
            "corp_name": 개황.get("corp_name") or 회사["corp_name"],
            "stock_code": (개황.get("stock_code") or "").strip(),
            "corp_cls": 개황.get("corp_cls"),
            "induty_code": (개황.get("induty_code") or "").strip(),
        })
        if 진행표시 and i % 200 == 0:
            print(f"    {i:,}/{len(상장):,} 조회 중… (코스닥·코넥스 {len(행들):,}곳 수집)")

    표 = pd.DataFrame(행들)
    업종캐시.parent.mkdir(parents=True, exist_ok=True)
    표.to_csv(업종캐시, index=False)
    return 표


def 업종코드_자릿수분포(표: pd.DataFrame) -> dict:
    """induty_code가 몇 자리인지 세어 본다(리포트 '방법론'에 기록용)."""
    길이 = 표["induty_code"].fillna("").astype(str).str.len()
    return {int(k): int(v) for k, v in 길이.value_counts().sort_index().items()}


def 비교군_후보들(표: pd.DataFrame, 기준업종코드: str):
    """비교 자릿수 L을 좁은 것부터 넓은 것 순(4 -> 3 -> 2)으로 후보 비교군을 만들어 준다.

    매칭된 회사 수가 아니라 '실제 분석에 쓸 수 있는 회사 수'로 최소 인원을 판단하려면
    호출하는 쪽에서 후보를 하나씩 받아 재무·특성까지 확인해야 하므로 목록으로 돌려준다.
    """
    기준 = str(기준업종코드).strip()
    유효 = 표[표["induty_code"].fillna("").astype(str).str.len() > 0].copy()
    시작L = min(4, len(기준))
    후보들 = []
    for L in range(시작L, 1, -1):
        골라진 = 유효[유효["induty_code"].astype(str).str[:L] == 기준[:L]].copy()
        골라진["매칭단계"] = L
        후보들.append({"L": L, "시작L": 시작L, "비교군": _정리(골라진)})
    return 후보들


def 비교군_찾기(표: pd.DataFrame, 기준업종코드: str, 최소개수: int = 15):
    """기준 업종코드와 앞자리가 같은 회사를 고른다.

    L(비교 자릿수) = min(4, 기준코드 길이)에서 시작해, 비교군이 최소개수보다
    적으면 L을 1씩 줄여(3 -> 2) 범위를 넓힌다. 2자리에서도 부족하면 경고를 남긴다.
    """
    기준 = str(기준업종코드).strip()
    유효 = 표[표["induty_code"].fillna("").astype(str).str.len() > 0].copy()
    시작L = min(4, len(기준))
    확장기록 = []

    for L in range(시작L, 1, -1):
        골라진 = 유효[유효["induty_code"].astype(str).str[:L] == 기준[:L]].copy()
        확장기록.append({"L": L, "개수": len(골라진)})
        if len(골라진) >= 최소개수:
            골라진["매칭단계"] = L
            return _정리(골라진), {
                "최종L": L, "확장여부": L < 시작L, "시작L": 시작L,
                "단계별개수": 확장기록, "최소개수": 최소개수, "경고": None,
            }

    L = 2
    골라진 = 유효[유효["induty_code"].astype(str).str[:L] == 기준[:L]].copy()
    골라진["매칭단계"] = L
    if not 확장기록 or 확장기록[-1]["L"] != L:
        확장기록.append({"L": L, "개수": len(골라진)})
    return _정리(골라진), {
        "최종L": L, "확장여부": True, "시작L": 시작L,
        "단계별개수": 확장기록, "최소개수": 최소개수,
        "경고": f"중분류(2자리)까지 넓혔지만 비교군이 {len(골라진)}곳으로 최소 {최소개수}곳에 못 미칩니다. "
                f"통계적 대표성이 약하니 결과를 참고용으로만 보세요.",
    }


def _정리(표: pd.DataFrame) -> pd.DataFrame:
    """비교군 표에 시장 이름을 붙이고 열 순서를 맞춘다."""
    표 = 표.copy()
    표["시장"] = 표["corp_cls"].map(시장이름).fillna("기타")
    열 = ["corp_code", "corp_name", "stock_code", "시장", "induty_code", "매칭단계"]
    return 표[열].sort_values("corp_name").reset_index(drop=True)

# 텍스내비 화면의 6개 업종 ↔ 한국표준산업분류(KSIC 10차) 2자리 대분류 범위
# 앞자리 prefix 하나로는 "제조업 10~34"처럼 넓은 대분류를 표현할 수 없어 범위 목록으로 둔다.
업종_KSIC범위 = {
    "manufacturing": [(10, 34)],                    # C 제조업
    "construction": [(41, 42)],                     # F 건설업
    "wholesale": [(45, 47)],                        # G 도매 및 소매업
    "food-lodging": [(55, 56)],                     # I 숙박 및 음식점업
    "ict": [(58, 63)],                              # J 정보통신업
    "service": [(70, 76), (94, 96)],                # M·N·S 서비스업
}
업종이름 = {
    "manufacturing": "제조업", "construction": "건설업", "wholesale": "도소매업",
    "food-lodging": "음식·숙박업", "ict": "정보통신업", "service": "서비스업",
}


def 업종별_비교군(표: pd.DataFrame, 업종코드: str) -> pd.DataFrame:
    """텍스내비 6개 업종 중 하나에 해당하는 코스닥·코넥스 상장사를 KSIC 2자리 범위로 고른다."""
    범위 = 업종_KSIC범위.get(업종코드)
    if not 범위:
        return _정리(표.iloc[0:0].assign(매칭단계=2))
    유효 = 표[표["induty_code"].fillna("").astype(str).str.len() >= 2].copy()
    두자리 = pd.to_numeric(유효["induty_code"].astype(str).str[:2], errors="coerce")
    조건 = False
    for 시작, 끝 in 범위:
        조건 = (두자리 >= 시작) & (두자리 <= 끝) if 조건 is False else 조건 | ((두자리 >= 시작) & (두자리 <= 끝))
    골라진 = 유효[조건.fillna(False)].copy()
    골라진["매칭단계"] = 2
    return _정리(골라진)
