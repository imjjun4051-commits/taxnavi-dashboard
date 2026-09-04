"""OpenDART API 호출 공통부.

인증키는 .env의 DART_API_KEY에서만 읽고, 로그·리포트에는 절대 출력하지 않는다.
모든 호출은 재시도(3회, 지수 백오프) + 호출 간 0.2초 대기 + 파일 캐시를 거친다.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

import requests
from dotenv import load_dotenv

BASE_URL = "https://opendart.fss.or.kr/api"
여기 = Path(__file__).resolve().parent
캐시폴더 = 여기 / "cache"
호출간격_초 = 0.2
일일한도 = 20_000

# 엔드포인트별 캐시 유효기간(초)
캐시수명 = {
    "corpCode.xml": 30 * 86400,
    "company.json": 30 * 86400,
    "fnlttMultiAcnt.json": 1 * 86400,
    "list.json": 3600,
}


class DartError(RuntimeError):
    """DART 호출 실패(키 없음·정상 응답 아님 등)."""


def 인증키_읽기() -> str:
    """.env에서 DART_API_KEY를 읽는다. 없으면 안내 메시지와 함께 예외를 낸다."""
    load_dotenv(여기 / ".env")
    load_dotenv(여기.parent.parent / ".env.local")
    키 = os.environ.get("DART_API_KEY", "").strip()
    if not 키:
        raise DartError(
            "DART_API_KEY가 없습니다. tools/peer-cluster/.env 파일에 "
            "DART_API_KEY=발급받은키 형식으로 넣어 주세요 (.env.example 참고). "
            "키 없이 실습하려면 --dry-run 옵션을 쓰세요."
        )
    return 키


def 금액숫자(값) -> int | None:
    """DART 금액 문자열('1,234', '-', '')을 정수로 바꾼다. 값이 없으면 None."""
    if 값 is None:
        return None
    s = str(값).strip().replace(",", "")
    if s in ("", "-", "N/A"):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


class 호출카운터:
    """하루 호출 수를 파일에 기록해 20,000건 한도에 가까워지면 경고한다."""

    def __init__(self, 폴더: Path):
        self.파일 = 폴더 / f"call_count_{date.today():%Y%m%d}.json"
        self.수 = json.loads(self.파일.read_text())["count"] if self.파일.exists() else 0

    def 더하기(self, n: int = 1) -> None:
        self.수 += n
        self.파일.parent.mkdir(parents=True, exist_ok=True)
        self.파일.write_text(json.dumps({"count": self.수}))
        if self.수 > 일일한도:
            print(f"  ⚠ 일일 호출 한도({일일한도:,}건)를 넘었습니다: 현재 {self.수:,}건")
        elif self.수 > 일일한도 * 0.9:
            print(f"  ⚠ 일일 호출 한도의 90%에 근접: {self.수:,}/{일일한도:,}건")


class DartClient:
    """DART 호출기. no_cache=True면 캐시를 무시하고 항상 새로 부른다."""

    def __init__(self, no_cache: bool = False, 인증키: str | None = None):
        self.키 = 인증키 if 인증키 is not None else 인증키_읽기()
        self.no_cache = no_cache
        캐시폴더.mkdir(parents=True, exist_ok=True)
        self.카운터 = 호출카운터(캐시폴더)
        self.세션 = requests.Session()

    # --- 캐시 --------------------------------------------------------
    def _캐시경로(self, 엔드포인트: str, 파라미터: dict) -> Path:
        """엔드포인트+파라미터+날짜로 캐시 파일 이름을 만든다(인증키는 이름에 넣지 않는다)."""
        키문자열 = json.dumps({k: v for k, v in 파라미터.items() if k != "crtfc_key"}, sort_keys=True)
        해시 = hashlib.sha1(키문자열.encode()).hexdigest()[:12]
        return 캐시폴더 / f"{엔드포인트.replace('.', '_')}_{해시}_{date.today():%Y%m%d}.json"

    def _캐시읽기(self, 경로: Path, 엔드포인트: str):
        if self.no_cache or not 경로.exists():
            return None
        if time.time() - 경로.stat().st_mtime > 캐시수명.get(엔드포인트, 86400):
            return None
        try:
            return json.loads(경로.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    # --- 호출 --------------------------------------------------------
    def 호출(self, 엔드포인트: str, **파라미터) -> dict:
        """DART JSON 엔드포인트를 부른다(캐시 → 재시도 3회 → 결과 저장)."""
        경로 = self._캐시경로(엔드포인트, 파라미터)
        캐시된 = self._캐시읽기(경로, 엔드포인트)
        if 캐시된 is not None:
            return 캐시된

        파라미터["crtfc_key"] = self.키
        마지막오류 = None
        for 시도 in range(3):
            try:
                time.sleep(호출간격_초)
                응답 = self.세션.get(f"{BASE_URL}/{엔드포인트}", params=파라미터, timeout=30)
                self.카운터.더하기()
                응답.raise_for_status()
                결과 = 응답.json()
                상태 = 결과.get("status")
                # 013 = 조회 결과 없음 → 오류가 아니라 "빈 결과"로 취급한다
                if 상태 not in (None, "000", "013"):
                    raise DartError(f"DART 응답 오류 status={상태} ({결과.get('message', '')})")
                경로.write_text(json.dumps(결과, ensure_ascii=False), encoding="utf-8")
                return 결과
            except (requests.RequestException, json.JSONDecodeError) as e:
                마지막오류 = e
                time.sleep(2 ** 시도)   # 지수 백오프: 1초 → 2초 → 4초
        raise DartError(f"{엔드포인트} 호출 실패(3회 재시도): {마지막오류}")

    def 고유번호목록(self) -> list[dict]:
        """corpCode.xml(ZIP)을 받아 전체 기업 목록을 만든다. 상장사는 stock_code가 채워져 있다."""
        경로 = self._캐시경로("corpCode.xml", {})
        캐시된 = self._캐시읽기(경로, "corpCode.xml")
        if 캐시된 is not None:
            return 캐시된

        time.sleep(호출간격_초)
        응답 = self.세션.get(f"{BASE_URL}/corpCode.xml", params={"crtfc_key": self.키}, timeout=120)
        self.카운터.더하기()
        응답.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(응답.content)) as z:
            xml = z.read(z.namelist()[0])
        목록 = []
        for 항목 in ElementTree.fromstring(xml).iter("list"):
            목록.append({
                "corp_code": (항목.findtext("corp_code") or "").strip(),
                "corp_name": (항목.findtext("corp_name") or "").strip(),
                "stock_code": (항목.findtext("stock_code") or "").strip(),
                "modify_date": (항목.findtext("modify_date") or "").strip(),
            })
        경로.write_text(json.dumps(목록, ensure_ascii=False), encoding="utf-8")
        return 목록

    def 기업개황(self, corp_code: str) -> dict:
        """company.json — corp_cls(Y 유가/K 코스닥/N 코넥스/E 기타), induty_code 등."""
        return self.호출("company.json", corp_code=corp_code)

    def 다중회사_주요계정(self, corp_codes: list[str], 사업연도: int) -> dict:
        """fnlttMultiAcnt.json — 최대 100개 회사의 사업보고서(11011) 주요 계정."""
        if len(corp_codes) > 100:
            raise ValueError("한 번에 최대 100개까지만 조회할 수 있습니다")
        return self.호출(
            "fnlttMultiAcnt.json",
            corp_code=",".join(corp_codes),
            bsns_year=str(사업연도),
            reprt_code="11011",
        )

    def 공시목록(self, corp_code: str, 시작일: str, 종료일: str) -> dict:
        """list.json — 기간(YYYYMMDD) 내 공시 목록, 최대 100건."""
        return self.호출(
            "list.json", corp_code=corp_code, bgn_de=시작일, end_de=종료일, page_count=100
        )


def 공시링크(rcept_no: str) -> str:
    """공시 접수번호 → DART 상세 페이지 주소."""
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
