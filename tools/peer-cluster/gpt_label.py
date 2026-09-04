"""GPT에게 군 이름과 분류 기준을 쓰게 한다.

중요: 어느 회사가 어느 군에 속하는지는 **수학(K-means)이 정한다.**
GPT는 이미 나뉜 군에 A/B/C 라벨과 사람이 읽을 이름·기준 설명만 붙인다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

여기 = Path(__file__).resolve().parent
로그폴더 = 여기 / "cache" / "gpt_log"
기본모델 = "gpt-4o-mini"

시스템프롬프트 = (
    "당신은 한국 중소기업 재무 분석 보고서를 쓰는 도우미입니다. "
    "K-means로 이미 나뉜 3개 기업 군에 대해, 제공된 통계 수치만 근거로 "
    "라벨(A/B/C)·이름·핵심 기준·특징 요약을 한국어로 작성하세요. "
    "제공되지 않은 숫자를 지어내지 마세요. 라벨 A·B·C는 세 군에 서로 다르게 정확히 하나씩 배정하세요. "
    "반드시 지정된 JSON 형식으로만 답하세요."
)


def _요약통계(군요약: list[dict]) -> dict:
    """GPT에 보낼 최소 정보만 추린다(개별 회사 전체 목록은 보내지 않아 토큰을 아낀다)."""
    return {"군": 군요약}


def 군요약_만들기(군배정, 특성목록: list[str], 상위N: int = 5) -> list[dict]:
    """군별 기업 수·특성 중위값/평균·매출 상위 5개 회사명을 만든다."""
    요약 = []
    for 군, 그룹 in 군배정.groupby("군번호"):
        통계 = {}
        for 특성 in 특성목록:
            값 = 그룹[특성].dropna()
            if 값.empty:
                continue
            통계[특성] = {"중위값": round(float(값.median()), 4), "평균": round(float(값.mean()), 4)}
        상위 = (그룹.sort_values("매출액", ascending=False)["corp_name"].head(상위N).tolist()
               if "매출액" in 그룹 else [])
        요약.append({
            "군번호": int(군),
            "기업수": int(len(그룹)),
            "특성통계": 통계,
            "매출상위기업": 상위,
        })
    return 요약


def 대체라벨(군요약: list[dict], 사유: str) -> dict:
    """GPT를 못 쓰거나 응답이 깨졌을 때 군번호 순서대로 A/B/C만 붙인다."""
    라벨들 = ["A", "B", "C"]
    return {
        "군": [{
            "군번호": s["군번호"],
            "라벨": 라벨들[i] if i < len(라벨들) else f"G{s['군번호']}",
            "이름": f"{라벨들[i] if i < len(라벨들) else s['군번호']}군",
            "핵심기준": "자동 배정(GPT 라벨 없음)",
            "특징요약": f"기업 {s['기업수']}곳",
        } for i, s in enumerate(sorted(군요약, key=lambda x: x["군번호"]))],
        "분류기준_설명": f"GPT 라벨을 쓰지 못해 군 번호 순서대로 임시 배정했습니다. ({사유})",
        "실패": True,
        "실패사유": 사유,
    }


def 라벨_생성(군요약: list[dict], 특성목록: list[str], 모델: str = 기본모델,
              dry_run: bool = False) -> dict:
    """GPT에 군 요약을 보내 라벨·이름·기준을 받아온다. 실패하면 대체 라벨을 쓴다."""
    if dry_run:
        return 대체라벨(군요약, "--dry-run 모드(외부 호출 없음)")

    load_dotenv(여기 / ".env")
    load_dotenv(여기.parent.parent / ".env.local")   # dart_client와 같은 위치도 함께 본다
    키 = os.environ.get("OPENAI_API_KEY", "").strip()
    if not 키:
        return 대체라벨(군요약, "OPENAI_API_KEY 없음")

    사용자프롬프트 = (
        "다음은 K-means로 나눈 3개 기업 군의 통계입니다. 사용한 특성: "
        + ", ".join(특성목록) + "\n\n"
        + json.dumps(_요약통계(군요약), ensure_ascii=False, indent=2)
        + "\n\n아래 JSON 형식으로만 답하세요:\n"
        + '{"군": [{"군번호": 0, "라벨": "A", "이름": "...", "핵심기준": "...", "특징요약": "..."}], '
          '"분류기준_설명": "..."}'
    )

    try:
        from openai import OpenAI
        클라이언트 = OpenAI(api_key=키)
        원문 = None
        for 시도 in range(2):          # JSON 파싱 실패 시 1회만 다시 요청
            응답 = 클라이언트.chat.completions.create(
                model=모델, temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": 시스템프롬프트},
                          {"role": "user", "content": 사용자프롬프트}],
            )
            원문 = 응답.choices[0].message.content
            _로그저장(사용자프롬프트, 원문, 모델)
            try:
                파싱 = json.loads(원문)
            except json.JSONDecodeError:
                continue
            if _형식확인(파싱, 군요약):
                파싱["실패"] = False
                return 파싱
        return 대체라벨(군요약, "GPT 응답 JSON 형식 오류(2회 시도)")
    except Exception as e:
        return 대체라벨(군요약, f"GPT 호출 실패: {type(e).__name__}")


def _형식확인(파싱: dict, 군요약: list[dict]) -> bool:
    """군 3개·라벨 중복 없음·필수 키 존재를 확인한다."""
    군들 = 파싱.get("군")
    if not isinstance(군들, list) or len(군들) != len(군요약):
        return False
    라벨들 = []
    for g in 군들:
        if not all(k in g for k in ("군번호", "라벨", "이름", "핵심기준", "특징요약")):
            return False
        라벨들.append(g["라벨"])
    return len(set(라벨들)) == len(라벨들)


def _로그저장(프롬프트: str, 응답: str | None, 모델: str) -> None:
    """재현·검토를 위해 보낸 프롬프트와 원문 응답을 파일로 남긴다(API 키는 저장하지 않는다)."""
    로그폴더.mkdir(parents=True, exist_ok=True)
    파일 = 로그폴더 / f"{datetime.now():%Y%m%d_%H%M%S}.json"
    파일.write_text(json.dumps(
        {"모델": 모델, "프롬프트": 프롬프트, "응답": 응답}, ensure_ascii=False, indent=2
    ), encoding="utf-8")
