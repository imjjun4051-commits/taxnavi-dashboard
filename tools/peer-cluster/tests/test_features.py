"""특성 계산(성장률·CAGR·영업이익률) 검증."""
import pytest

from features import cagr, 성장률, 안전나눗셈, 회사특성, 사용할특성, 필수특성, 보조특성


def test_성장률_기본():
    assert 성장률(110, 100) == pytest.approx(0.10)
    assert 성장률(90, 100) == pytest.approx(-0.10)


def test_성장률_계산불가():
    assert 성장률(100, 0) is None      # 0으로 나눌 수 없음
    assert 성장률(100, -50) is None    # 음수 매출 기준은 의미 없음
    assert 성장률(None, 100) is None


def test_cagr_3개년은_지수_2분의1():
    # 100 -> 121, 2번 성장 -> 연평균 10%
    assert cagr(121, 100, 2) == pytest.approx(0.10)
    # 100 -> 100, 성장 없음
    assert cagr(100, 100, 4) == pytest.approx(0.0)


def test_cagr_계산불가():
    assert cagr(100, 0, 2) is None
    assert cagr(-10, 100, 2) is None
    assert cagr(100, 100, 0) is None


def test_안전나눗셈():
    assert 안전나눗셈(10, 4) == pytest.approx(2.5)
    assert 안전나눗셈(10, 0) is None
    assert 안전나눗셈(None, 5) is None


def test_회사특성_샘플정밀_숫자():
    특성 = 회사특성({2023: 4200, 2024: 4650, 2025: 5100},
                   {2023: 260, 2024: 310, 2025: 380})
    assert 특성["최신연도"] == 2025
    assert 특성["매출성장률"] == pytest.approx(5100 / 4650 - 1)
    assert 특성["영업이익률"] == pytest.approx(380 / 5100)
    assert 특성["매출CAGR3"] == pytest.approx((5100 / 4200) ** 0.5 - 1)


def test_사용할특성_보조없으면_필수4개만():
    특성목록, 설명 = 사용할특성({"부채비율": None, "총자산회전율": 1.0, "순이익률": 0.05})
    assert 특성목록 == 필수특성
    assert "필수 4개" in 설명


def test_사용할특성_보조있으면_7개():
    특성목록, _ = 사용할특성({"부채비율": 1.2, "총자산회전율": 1.0, "순이익률": 0.05})
    assert 특성목록 == 필수특성 + 보조특성
