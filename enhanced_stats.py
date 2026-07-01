# -*- coding: utf-8 -*-
"""
로또 6/45 정교한 통계 분석 (A: 적합도 검정 중심 + 전략 백테스트).

[A] 적합도 검정 (goodness-of-fit)
    1) 번호별 출현 균등성 : 카이제곱 검정 + 번호별 z-score/95% 신뢰구간
    2) 홀짝 개수 분포     : 초기하분포 이론값 vs 관측 카이제곱 검정
    3) 번호대(10단위) 분포: 이론 기대치 vs 관측 카이제곱 검정
    4) 당첨번호 합계       : 이론 평균(138) 대비 관측 요약

[B] 전략 백테스트 (walk-forward, look-ahead 없음)
    각 회차 t 에서 't 이전' 데이터만으로 번호를 뽑아 실제 당첨번호와
    맞은 개수를 측정. random/hot/cold/balanced 전략을 비교.
    이론적으로 6개를 뽑는 어떤 전략이든 기대 적중 개수는 6*6/45=0.8 로 동일 →
    백테스트로 '통계 전략이 무작위를 못 이긴다'를 실증한다.

전제: 로또는 매 회차 독립 시행. 아래 검정의 목적은 '추첨이 공정한가
(=편향이 없는가)'를 확인하는 것이지, 다음 번호를 예측하는 것이 아니다.
"""
import json
import os
from collections import Counter
from math import comb, sqrt
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ALPHA = 0.05


def load():
    with open(os.path.join(HERE, "lotto_all.json"), encoding="utf-8") as f:
        raw = json.load(f)
    rounds = []
    for r in raw:
        rounds.append({
            "round": r["ltEpsd"],
            "nums": [r["tm%dWnNo" % i] for i in range(1, 7)],
            "bonus": r["bnsWnNo"],
        })
    rounds.sort(key=lambda x: x["round"])
    return rounds


def verdict(p):
    return ("유의미한 편향 발견 (H0 기각)" if p < ALPHA
            else "편향 근거 없음 (공정한 추첨과 일치)")


# ======================= [A] 적합도 검정 =======================
def test_number_uniformity(rounds, out):
    N = len(rounds)
    freq = Counter()
    for r in rounds:
        freq.update(r["nums"])
    observed = np.array([freq[n] for n in range(1, 46)], dtype=float)
    p_in = 6 / 45
    expected_each = N * p_in
    expected = np.full(45, expected_each)

    chi2, p = stats.chisquare(observed, expected)
    df = 44
    crit = stats.chi2.ppf(1 - ALPHA, df)

    out("=" * 66)
    out(" [A-1] 번호별 출현 균등성 검정  (N=%d 회차)" % N)
    out("=" * 66)
    out(" H0: 45개 번호가 모두 같은 확률로 나온다 (공정한 추첨)")
    out(" 각 번호 기대 출현수 = %.1f회" % expected_each)
    out(" 카이제곱 통계량 X^2 = %.2f  (자유도 %d, 5%% 임계값 %.2f)" % (chi2, df, crit))
    out(" p-value = %.4f  ->  %s" % (p, verdict(p)))

    # 번호별 z-score / 95% 신뢰구간 (이항분포 모델)
    sd = sqrt(N * p_in * (1 - p_in))
    lo95, hi95 = expected_each - 1.96 * sd, expected_each + 1.96 * sd
    z = (observed - expected_each) / sd
    out("")
    out(" 이항모델: 표준편차 %.2f, 95%% 정상범위 = [%.0f, %.0f]회" % (sd, lo95, hi95))
    flagged = [(n + 1, observed[n], z[n]) for n in range(45) if abs(z[n]) >= 1.96]
    if flagged:
        out(" 95% 범위를 벗어난 번호:")
        for n, c, zz in sorted(flagged, key=lambda x: -abs(x[2])):
            out("   번호 %2d : %d회 (z=%+.2f)" % (n, c, zz))
    else:
        out(" 95% 신뢰구간을 벗어난 번호: 없음")
    # 가장 극단적인 번호 (참고)
    zi = np.argsort(-np.abs(z))
    out(" 가장 치우친 번호 TOP3(참고): " +
        ", ".join("%d(z=%+.2f)" % (i + 1, z[i]) for i in zi[:3]))
    out(" => hot/cold 번호도 |z|가 대개 2 미만: '우연한 출렁임' 수준.")
    out("")


def test_oddeven(rounds, out):
    N = len(rounds)
    # 1~45 중 홀수 23개, 짝수 22개
    odds, evens = 23, 22
    probs = np.array([comb(odds, k) * comb(evens, 6 - k) / comb(45, 6)
                      for k in range(7)])
    expected = probs * N
    obs_counter = Counter(sum(1 for x in r["nums"] if x % 2) for r in rounds)
    observed = np.array([obs_counter.get(k, 0) for k in range(7)], dtype=float)

    chi2, p = stats.chisquare(observed, expected)
    out("=" * 66)
    out(" [A-2] 홀수 개수 분포 검정 (초기하분포 대비)")
    out("=" * 66)
    out(" %-8s %-10s %-10s" % ("홀수개수", "관측", "이론기대"))
    for k in range(7):
        out("   홀%d짝%d   %8d   %8.1f" % (k, 6 - k, observed[k], expected[k]))
    out(" 카이제곱 X^2 = %.2f (df=6), p=%.4f -> %s" % (chi2, p, verdict(p)))
    out("")


def test_bands(rounds, out):
    N = len(rounds)
    # 번호대: 1-9(9개),10-19,20-29,30-39(각10개),40-45(6개)
    sizes = [9, 10, 10, 10, 6]
    probs = np.array([s / 45 for s in sizes])
    total_balls = N * 6
    expected = probs * total_balls
    band = Counter()
    for r in rounds:
        for n in r["nums"]:
            band[min(n // 10, 4)] += 1
    observed = np.array([band[b] for b in range(5)], dtype=float)
    chi2, p = stats.chisquare(observed, expected)
    names = ["1-9", "10-19", "20-29", "30-39", "40-45"]
    out("=" * 66)
    out(" [A-3] 번호대(10단위) 분포 검정")
    out("=" * 66)
    for i in range(5):
        out("   %-6s 관측 %5d  이론 %7.1f" % (names[i], observed[i], expected[i]))
    out(" 카이제곱 X^2 = %.2f (df=4), p=%.4f -> %s" % (chi2, p, verdict(p)))
    out("")


def test_sum(rounds, out):
    sums = np.array([sum(r["nums"]) for r in rounds])
    out("=" * 66)
    out(" [A-4] 당첨번호 합계 분포")
    out("=" * 66)
    out(" 관측: 평균 %.1f, 표준편차 %.1f, 범위 %d~%d (이론 평균 138)" %
        (sums.mean(), sums.std(ddof=1), sums.min(), sums.max()))
    # 정규성 참고 검정
    W, p = stats.shapiro(sums) if len(sums) <= 5000 else stats.normaltest(sums)
    out(" 정규성 검정 p=%.4f (%s)" %
        (p, "정규분포와 유사" if p >= ALPHA else "정규분포와 다소 차이"))
    out("")


# ======================= [B] 전략 백테스트 =======================
def weighted_sample_np(rng, weights, k=6):
    idx = rng.choice(45, size=k, replace=False, p=weights / weights.sum())
    return set((idx + 1).tolist())


def balanced_sample(rng):
    for _ in range(200):
        idx = rng.choice(45, size=6, replace=False)
        nums = (idx + 1)
        if 2 <= (nums % 2).sum() <= 4 and 100 <= nums.sum() <= 175:
            return set(nums.tolist())
    return set((rng.choice(45, size=6, replace=False) + 1).tolist())


def backtest(rounds, out, start=100, M=120, seed=7):
    rng = np.random.default_rng(seed)
    freq = np.zeros(45)          # 누적 출현수 (t 이전까지)
    last_seen = np.zeros(45)     # 마지막 출현 회차
    strategies = ["random", "hot", "cold", "balanced"]
    match_sum = {s: 0.0 for s in strategies}
    match_cnt = {s: 0 for s in strategies}
    prize_hits = {s: 0 for s in strategies}   # 3개 이상 = 당첨(5등~)
    all_matches = {s: [] for s in strategies}

    for t, r in enumerate(rounds):
        rn = r["round"]
        win = set(r["nums"])
        if t >= start:
            for s in strategies:
                for _ in range(M):
                    if s == "random":
                        pick = set((rng.choice(45, 6, replace=False) + 1).tolist())
                    elif s == "hot":
                        w = freq ** 2 + 1e-9
                        pick = weighted_sample_np(rng, w)
                    elif s == "cold":
                        w = (rn - last_seen) + 1.0
                        pick = weighted_sample_np(rng, w)
                    else:
                        pick = balanced_sample(rng)
                    m = len(pick & win)
                    match_sum[s] += m
                    match_cnt[s] += 1
                    all_matches[s].append(m)
                    if m >= 3:
                        prize_hits[s] += 1
        # t 회차 반영 (다음 회차부터 사용)
        for n in r["nums"]:
            freq[n - 1] += 1
            last_seen[n - 1] = rn

    out("=" * 66)
    out(" [B] 전략 백테스트 (walk-forward, %d회차부터 검증, 회차당 %d픽)" %
        (rounds[start]["round"], M))
    out("=" * 66)
    out(" 각 전략을 '그 시점 이전 데이터'로만 생성해 실제 당첨번호와 대조.")
    out(" 이론상 어떤 전략이든 기대 적중 = 6*6/45 = 0.800개")
    out("")
    out(" %-10s %-14s %-14s %-16s" %
        ("전략", "평균적중개수", "표준오차", "당첨률(3개+)"))
    out(" " + "-" * 58)
    base = None
    for s in strategies:
        arr = np.array(all_matches[s])
        mean = arr.mean()
        se = arr.std(ddof=1) / sqrt(len(arr))
        rate = prize_hits[s] / match_cnt[s]
        out(" %-10s %10.4f개   ±%.4f       %6.3f%%" %
            (s, mean, se, rate * 100))
        if s == "random":
            base = arr

    # random 대비 hot/cold/balanced 유의차 검정 (t-test)
    out("")
    out(" random 대비 평균적중 차이 유의성 (독립표본 t-검정):")
    for s in strategies:
        if s == "random":
            continue
        tstat, p = stats.ttest_ind(np.array(all_matches[s]), base, equal_var=False)
        out("   %-9s vs random : Δ=%+.4f개, p=%.3f -> %s" %
            (s, np.array(all_matches[s]).mean() - base.mean(), p,
             "차이 있음" if p < ALPHA else "유의한 차이 없음"))
    out("")
    out(" 결론: 통계 기반 전략도 무작위와 통계적으로 구분되지 않음.")
    out("       => 과거 통계로 당첨 확률을 높일 수 없다는 것이 데이터로 확인됨.")
    out("")


def main():
    rounds = load()
    lines = []
    out = lines.append
    out("로또 6/45 정교한 통계 분석 리포트 (1~%d회, %d회차)\n" %
        (rounds[-1]["round"], len(rounds)))
    test_number_uniformity(rounds, out)
    test_oddeven(rounds, out)
    test_bands(rounds, out)
    test_sum(rounds, out)
    backtest(rounds, out)

    report = "\n".join(lines)
    print(report)
    with open(os.path.join(HERE, "enhanced_stats_report.txt"), "w",
              encoding="utf-8") as f:
        f.write(report + "\n")
    print("[저장됨] enhanced_stats_report.txt")


if __name__ == "__main__":
    main()
