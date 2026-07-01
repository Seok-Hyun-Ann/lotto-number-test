# -*- coding: utf-8 -*-
"""
로또 6/45 번호 추천 + 당첨 확률 + (전략별) 몬테카를로 시뮬레이션.

기능
  1) 등수별 이론 당첨 확률과 기대 구매횟수 출력
  2) 과거 통계 기반 번호 추천 (random / hot / cold / balanced)
  3) 전략별 몬테카를로 시뮬레이션
     - random/hot/cold/balanced 전략으로 각각 N게임을 사서
       등수별 당첨 횟수를 비교한다.
     - 추첨은 (공정한) 무작위이므로, 어떤 전략이든 결과가 사실상
       동일하게 나온다 = "통계 전략이 확률을 못 바꾼다"를 눈으로 확인.

정직한 전제: 로또는 매 회차 독립 시행이다.
'hot'/'cold' 추천은 재미를 위한 통계 반영일 뿐, 실제 당첨 확률은
어떤 조합을 골라도 1등 기준 1/8,145,060 으로 완전히 동일하다.
"""
import json
import os
import random
from collections import Counter
from math import comb
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOTAL_COMBOS = comb(45, 6)  # 8,145,060

RANK_WAYS = {
    1: comb(6, 6) * comb(39, 0),                 # 6개
    2: comb(6, 5) * 1,                           # 5개 + 보너스
    3: comb(6, 5) * (comb(39, 1) - 1),           # 5개, 보너스 아님
    4: comb(6, 4) * comb(39, 2),                 # 4개
    5: comb(6, 3) * comb(39, 3),                 # 3개
}
LABELS = {1: "1등(6개)", 2: "2등(5+보)", 3: "3등(5개)", 4: "4등(4개)", 5: "5등(3개)"}


def load_stats():
    with open(os.path.join(HERE, "lotto_all.json"), encoding="utf-8") as f:
        raw = json.load(f)
    freq = Counter()
    last_seen = {}
    latest = max(r["ltEpsd"] for r in raw)
    for r in raw:
        nums = [r["tm%dWnNo" % i] for i in range(1, 7)]
        freq.update(nums)
        for n in nums:
            last_seen[n] = r["ltEpsd"]
    freq_arr = np.array([freq[n] for n in range(1, 46)], dtype=float)
    gap_arr = np.array([latest - last_seen.get(n, 0) for n in range(1, 46)], dtype=float)
    return freq, last_seen, latest, freq_arr, gap_arr


# ---------- 전략별 가중치 (번호를 뽑을 확률의 상대적 크기) ----------
def strategy_logweights(strategy, freq_arr, gap_arr):
    if strategy == "random":
        w = np.ones(45)
    elif strategy == "hot":            # 많이 나온 번호일수록 가중 ↑
        w = freq_arr ** 2 + 1e-9
    elif strategy == "cold":           # 오래 안 나온 번호일수록 가중 ↑
        w = gap_arr + 1.0
    else:
        raise ValueError(strategy)
    return np.log(w)


# ---------- 1) 이론 확률 ----------
def print_theory(out):
    out("=" * 60)
    out(" 로또 6/45 등수별 이론 당첨 확률")
    out(" (전체 조합 수 = %s 가지)" % f"{TOTAL_COMBOS:,}")
    out("=" * 60)
    tot = 0.0
    for rk in range(1, 6):
        p = RANK_WAYS[rk] / TOTAL_COMBOS
        tot += p
        out("  %-12s 확률 1/%-12s  (%s게임에 1번꼴)" %
            (LABELS[rk], f"{round(1/p):,}", f"{round(1/p):,}"))
    out("-" * 60)
    out("  당첨(1~5등) 확률 : 1/%s  (%.4f%%)" % (f"{round(1/tot):,}", tot * 100))
    out("")


# ---------- 2) 번호 추천 ----------
def recommend(strategy, freq, last_seen, latest, n_sets=3):
    pool = list(range(1, 46))
    sets = []
    for _ in range(n_sets):
        if strategy == "balanced":
            pick = balanced_pick(pool)
        elif strategy == "random":
            pick = random.sample(pool, 6)
        else:
            if strategy == "hot":
                w = [freq[n] ** 2 for n in pool]
            else:  # cold
                w = [(latest - last_seen.get(n, 0)) + 1 for n in pool]
            pick = weighted_sample(pool, w, 6)
        sets.append(sorted(pick))
    return sets


def weighted_sample(pool, weights, k):
    pool, weights, out = pool[:], weights[:], []
    for _ in range(k):
        total = sum(weights)
        r = random.uniform(0, total)
        acc = 0
        for i, w in enumerate(weights):
            acc += w
            if r <= acc:
                out.append(pool.pop(i)); weights.pop(i); break
    return out


def balanced_pick(pool):
    for _ in range(2000):
        pick = random.sample(pool, 6)
        if sum(1 for x in pick if x % 2) in (2, 3, 4) and 100 <= sum(pick) <= 175:
            return pick
    return random.sample(pool, 6)


# ---------- 3) 벡터화 몬테카를로 시뮬레이션 (전략 적용) ----------
def _gumbel_topk_mask(rng, logw, k, n):
    """logw(45,) 가중치로 n게임 각각 k개를 비복원 가중추출 → 불리언 마스크(n,45).
    Gumbel-top-k: key = logw + Gumbel노이즈, 상위 k개 선택 (정확한 가중 비복원추출)."""
    keys = rng.gumbel(size=(n, 45)) + logw  # logw 브로드캐스트
    idx = np.argpartition(-keys, k - 1, axis=1)[:, :k]
    mask = np.zeros((n, 45), dtype=bool)
    mask[np.arange(n)[:, None], idx] = True
    return mask


def _balanced_mask(rng, n):
    """홀짝 2~4 + 합계 100~175 조건을 만족하는 픽 n개 (벡터 rejection)."""
    masks = np.zeros((n, 45), dtype=bool)
    filled = 0
    nums = np.arange(1, 46)
    while filled < n:
        batch = max(n - filled, 10000)
        keys = rng.gumbel(size=(batch, 45))
        idx = np.argpartition(-keys, 5, axis=1)[:, :6]      # 균등 6개
        picks = np.sort(idx + 1, axis=1)                    # 실제 번호
        odd = (picks % 2).sum(axis=1)
        s = picks.sum(axis=1)
        ok = (odd >= 2) & (odd <= 4) & (s >= 100) & (s <= 175)
        good = idx[ok]
        take = min(len(good), n - filled)
        rows = np.arange(filled, filled + take)
        masks[rows[:, None], good[:take]] = True
        filled += take
    return masks


def simulate_strategy(strategy, n_games, freq_arr, gap_arr, seed=0, chunk=200_000):
    rng = np.random.default_rng(seed)
    logw = None if strategy == "balanced" else strategy_logweights(strategy, freq_arr, gap_arr)
    hits = Counter()
    done = 0
    while done < n_games:
        n = min(chunk, n_games - done)
        # 추첨: 균등하게 7개 (앞 6개=당첨, 7번째=보너스)
        dkeys = rng.gumbel(size=(n, 45))
        draw = np.argpartition(-dkeys, 6, axis=1)[:, :7]
        # 상위 7개를 key 기준 정렬해 보너스(7번째) 구분
        order = np.argsort(-dkeys[np.arange(n)[:, None], draw], axis=1)
        draw = np.take_along_axis(draw, order, axis=1)
        win_idx, bonus_idx = draw[:, :6], draw[:, 6]
        win_mask = np.zeros((n, 45), dtype=bool)
        win_mask[np.arange(n)[:, None], win_idx] = True
        # 내 픽
        if strategy == "balanced":
            pick_mask = _balanced_mask(rng, n)
        else:
            pick_mask = _gumbel_topk_mask(rng, logw, 6, n)
        # 채점
        m = (pick_mask & win_mask).sum(axis=1)
        bonus_hit = pick_mask[np.arange(n), bonus_idx]
        rank = np.zeros(n, dtype=int)
        rank[m == 3] = 5
        rank[m == 4] = 4
        rank[m == 5] = 3
        rank[(m == 5) & bonus_hit] = 2
        rank[m == 6] = 1
        for rk in range(1, 6):
            hits[rk] += int((rank == rk).sum())
        done += n
    return hits


def main():
    freq, last_seen, latest, freq_arr, gap_arr = load_stats()
    lines = []
    out = lines.append

    print_theory(out)

    out("=" * 60)
    out(" 번호 추천 (참고용 — 실제 확률은 전략과 무관하게 동일)")
    out("=" * 60)
    for strat, desc in [("random", "완전 무작위"), ("hot", "자주 나온 번호 가중"),
                        ("cold", "오래 안 나온 번호 가중"), ("balanced", "홀짝·구간·합계 균형")]:
        out("[%s] %s" % (strat, desc))
        for s in recommend(strat, freq, last_seen, latest):
            out("   " + "  ".join("%2d" % x for x in s))
    out("")

    # ---- 전략별 시뮬레이션 비교 ----
    N = 2_000_000
    out("=" * 60)
    out(" 전략별 몬테카를로 시뮬레이션  (각 전략 %s게임)" % f"{N:,}")
    out("=" * 60)
    out(" 같은 조건에서 4개 전략으로 각각 %s게임씩 실제로 사본다." % f"{N:,}")
    out("")
    header = " %-10s" % "전략" + "".join("%9s" % LABELS[rk] for rk in range(1, 6)) + "   당첨률(1~5등)"
    out(header)
    out(" " + "-" * (len(header) - 1))
    for strat in ["random", "hot", "cold", "balanced"]:
        hits = simulate_strategy(strat, N, freq_arr, gap_arr, seed=100 + hash(strat) % 999)
        won = sum(hits.values())
        row = " %-10s" % strat + "".join("%9d" % hits.get(rk, 0) for rk in range(1, 6))
        row += "   1/%s" % f"{round(N/won):,}" if won else "   -"
        out(row)
    # 이론 기대 (참고행)
    exp = " %-10s" % "이론기대" + "".join("%9.1f" % (N * RANK_WAYS[rk] / TOTAL_COMBOS)
                                           for rk in range(1, 6))
    out(exp)
    out("")
    out(" ※ 추첨이 공정(무작위)하므로 네 전략의 결과는 통계적으로 동일하다.")
    out("   즉 hot/cold로 골라도 당첨 기대는 무작위와 같다 — 확률은 안 바뀐다.")

    report = "\n".join(lines)
    print(report)
    with open(os.path.join(HERE, "simulation_report.txt"), "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print("\n[저장됨] simulation_report.txt")


if __name__ == "__main__":
    main()
