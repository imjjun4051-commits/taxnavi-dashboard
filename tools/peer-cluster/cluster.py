"""K-means로 비교군을 3개 군으로 나누고, 기준 기업이 어느 군에 속하는지 정한다.

기준 기업은 학습에 넣지 않는다(비상장이라 성격이 다를 수 있어 군의 모양을 흔들지 않게).
학습이 끝난 뒤 같은 스케일러로 변환해 가장 가까운 중심에 배정한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

군수 = 3
실루엣_약함기준 = 0.25


def 군집화(잘린표: pd.DataFrame, X: np.ndarray, 특성목록: list[str]):
    """KMeans(k=3) 학습 -> 군 번호와 실루엣 점수를 돌려준다."""
    모델 = KMeans(n_clusters=군수, n_init=10, random_state=42).fit(X)
    결과 = 잘린표.copy()
    결과["군번호"] = 모델.labels_

    점수 = None
    if len(set(모델.labels_)) > 1 and len(X) > 군수:
        점수 = float(silhouette_score(X, 모델.labels_))

    중심거리 = np.linalg.norm(X - 모델.cluster_centers_[모델.labels_], axis=1)
    결과["중심까지거리"] = 중심거리
    메타 = {
        "실루엣": 점수,
        "약한군집": (점수 is not None and 점수 < 실루엣_약함기준),
        "특성목록": 특성목록,
    }
    return 결과, 모델, 메타


def 기준기업_배정(기준특성: dict, 특성목록: list[str], 스케일러, 모델):
    """기준 기업을 같은 스케일로 변환해 가장 가까운 군에 배정한다(1·2순위와 거리 포함)."""
    값 = np.array([[float(기준특성[k]) for k in 특성목록]])
    변환 = 스케일러.transform(값)
    거리 = np.linalg.norm(모델.cluster_centers_ - 변환[0], axis=1)
    순서 = np.argsort(거리)
    return {
        "소속군": int(순서[0]),
        "차순위군": int(순서[1]),
        "거리": {int(i): float(거리[i]) for i in range(len(거리))},
        "1순위거리": float(거리[순서[0]]),
        "2순위거리": float(거리[순서[1]]),
    }
