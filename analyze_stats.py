# -*- coding: utf-8 -*-
"""
로또 6/45 과거 데이터 통계 분석기.

lotto_all.json (collect_lotto.py로 수집) 을 읽어
번호별 출현 빈도, 미출현(overdue) 기간, 홀짝·구간·합계 분포,
연속번호 출현 등을 계산하고 stats_report.txt 로 저장한다.

주의: 로또는 매 회차가 독립 시행이라 과거 빈도가 다음 회차 확률을
바꾸지 않는다. 아래 통계는 '지금까지 어땠는가'에 대한 기록일 뿐,
'앞으로 어떻게 될지'에 대한 예측이 아니다.
"""
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    with open(os.path.join(HERE, "lotto_all.json"), encoding="utf-8") as f:
        raw = json.load(f)
    rounds = []
    for r in raw:
        rounds.append({
            "round": r["ltEpsd"],
            "date": str(r["ltRflYmd"]),
            "nums": [r["tm%dWnNo" % i] for i in range(1, 7)],
            "bonus": r["bnsWnNo"],
        })
    rounds.sort(key=lambda x: x["round"])
    return rounds


def bar(n, maxn, width=40):
    return "#" * int(round(width * n / maxn)) if maxn else ""


def main():
    rounds = load()
    total = len(rounds)
    latest = rounds[-1]["round"]
    lines = []
    p = lines.append

    p("=" * 64)
    p(" 로또 6/45 통계 리포트  (1 ~ %d회, 총 %d회차)" % (latest, total))
    p("=" * 64)

    # 1) 번호별 출현 빈도 (본번호 기준)
    freq = Counter()
    for r in rounds:
        freq.update(r["nums"])
    expected = total * 6 / 45.0
    p("")
    p("[1] 번호별 출현 빈도  (기대 출현수 = %.1f회, 균등가정)" % expected)
    p("-" * 64)
    maxf = max(freq.values())
    for n in range(1, 46):
        c = freq[n]
        diff = c - expected
        p("%2d | %4d회  %-42s %+.0f" % (n, c, bar(c, maxf), diff))

    order = freq.most_common()
    hot = order[:10]
    cold = order[-10:][::-1]
    p("")
    p("  많이 나온 번호 TOP10 : " + ", ".join("%d(%d)" % (n, c) for n, c in hot))
    p("  적게 나온 번호 BOT10 : " + ", ".join("%d(%d)" % (n, c) for n, c in cold))

    # 2) 미출현 기간 (마지막 등장 이후 몇 회 지났나 = overdue)
    last_seen = {}
    for r in rounds:
        for n in r["nums"]:
            last_seen[n] = r["round"]
    p("")
    p("[2] 미출현 기간 (최근 미등장 회차 수)")
    p("-" * 64)
    overdue = sorted(((latest - last_seen.get(n, 0), n) for n in range(1, 46)),
                     reverse=True)
    for gap, n in overdue[:10]:
        p("  번호 %2d : 최근 %3d회 미출현 (마지막 %d회)" % (n, gap, last_seen.get(n, 0)))

    # 3) 홀짝 분포
    p("")
    p("[3] 홀수/짝수 개수 분포 (6개 중 홀수 개수)")
    p("-" * 64)
    oddc = Counter(sum(1 for x in r["nums"] if x % 2) for r in rounds)
    for k in range(7):
        c = oddc.get(k, 0)
        p("  홀%d 짝%d : %4d회 (%5.1f%%)  %s" %
          (k, 6 - k, c, 100 * c / total, bar(c, max(oddc.values()))))

    # 4) 당첨번호 합계 분포
    sums = [sum(r["nums"]) for r in rounds]
    p("")
    p("[4] 당첨번호 6개 합계")
    p("-" * 64)
    p("  최소 %d / 최대 %d / 평균 %.1f (이론평균 138)" %
      (min(sums), max(sums), sum(sums) / total))
    buckets = Counter((s // 20) * 20 for s in sums)
    for b in sorted(buckets):
        c = buckets[b]
        p("  %3d~%3d : %4d회  %s" % (b, b + 19, c, bar(c, max(buckets.values()))))

    # 5) 구간(10단위) 분포
    p("")
    p("[5] 번호대(10단위)별 총 출현수")
    p("-" * 64)
    band = Counter()
    for r in rounds:
        for n in r["nums"]:
            band[min(n // 10, 4)] += 1
    names = {0: "1-9", 1: "10-19", 2: "20-29", 3: "30-39", 4: "40-45"}
    for b in range(5):
        c = band[b]
        p("  %-6s : %5d회  %s" % (names[b], c, bar(c, max(band.values()))))

    # 6) 연속번호 포함 회차
    def has_consec(nums):
        s = sorted(nums)
        return any(s[i] + 1 == s[i + 1] for i in range(len(s) - 1))
    consec = sum(1 for r in rounds if has_consec(r["nums"]))
    p("")
    p("[6] 연속번호(예: 12,13) 포함 회차 : %d회 (%.1f%%)" %
      (consec, 100 * consec / total))

    report = "\n".join(lines)
    print(report)
    with open(os.path.join(HERE, "stats_report.txt"), "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print("\n[저장됨] stats_report.txt")


if __name__ == "__main__":
    main()
