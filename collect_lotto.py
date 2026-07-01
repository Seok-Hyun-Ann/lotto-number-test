# -*- coding: utf-8 -*-
"""
동행복권 로또 6/45 전 회차 당첨결과 수집기.

개편된 동행복권 사이트(2026년)의 데이터 엔드포인트
  GET /lt645/selectPstLt645InfoNew.do
를 이용해 1회차부터 최신 회차까지 모두 수집한다.

요청에는 브라우저 XHR과 동일한 헤더(AJAX: true 등)가 필요하다.
결과는 lotto_all.csv (엑셀용, cp949) / lotto_all.json 으로 저장한다.
"""
import urllib.request
import http.cookiejar
import json
import time
import csv
import sys
import os

BASE = "https://www.dhlottery.co.kr"
API = BASE + "/lt645/selectPstLt645InfoNew.do"
HERE = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "AJAX": "true",
    "requestMenuUri": "/lt645/result",
    "Content-Type": "application/json;charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}


def make_opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [
        ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
        ("Accept-Language", "ko-KR,ko;q=0.9"),
        ("Referer", BASE + "/lt645/result"),
    ]
    # 세션 쿠키 확보
    op.open(BASE + "/", timeout=20).read()
    return op


def call(op, params, retries=4):
    qs = "&".join("%s=%s" % (k, v) for k, v in params.items())
    url = API + "?" + qs
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            raw = op.open(req, timeout=20).read().decode("utf-8", "ignore")
            data = json.loads(raw)
            return data.get("data", {}).get("list", []) or []
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    return []


def main():
    op = make_opener()

    collected = {}   # ltEpsd -> record
    # 1) 최신 회차 부근을 center로 확보
    seed = call(op, {"srchDir": "center", "srchLtEpsd": "9999"})
    if not seed:
        # 9999는 범위 밖 -> older로 최신부터 긁는다. 최대 회차를 이진탐색으로 탐색.
        lo, hi = 1000, 3000
        while lo < hi:
            mid = (lo + hi + 1) // 2
            e = [x["ltEpsd"] for x in call(op, {"srchDir": "center", "srchLtEpsd": str(mid)})]
            if mid in e:
                lo = mid
            else:
                hi = mid - 1
        maxround = lo
        seed = call(op, {"srchDir": "center", "srchLtEpsd": str(maxround)})

    for r in seed:
        collected[r["ltEpsd"]] = r
    print("seed rounds:", sorted(collected)[:3], "...", sorted(collected)[-3:], flush=True)

    # 2) older 방향으로 커서를 내리며 1회차까지 수집
    cursor = min(collected)
    while cursor > 1:
        lst = call(op, {"srchDir": "older", "srchCursorLtEpsd": str(cursor)})
        if not lst:
            break
        for r in lst:
            collected[r["ltEpsd"]] = r
        new_cursor = min(x["ltEpsd"] for x in lst)
        if new_cursor >= cursor:   # 더 내려가지 않으면 종료
            break
        cursor = new_cursor
        print("collected %d rounds, cursor=%d" % (len(collected), cursor), flush=True)
        time.sleep(0.3)   # 서버 배려

    rounds = sorted(collected.values(), key=lambda x: x["ltEpsd"])
    print("TOTAL collected:", len(rounds),
          "range", rounds[0]["ltEpsd"], "-", rounds[-1]["ltEpsd"], flush=True)

    # 누락 회차 점검
    have = set(collected)
    missing = [n for n in range(1, rounds[-1]["ltEpsd"] + 1) if n not in have]
    if missing:
        print("!! MISSING rounds:", missing, flush=True)
    else:
        print("no missing rounds (1 ~ %d 연속)" % rounds[-1]["ltEpsd"], flush=True)

    # 3) 원본 JSON 저장
    with open(os.path.join(HERE, "lotto_all.json"), "w", encoding="utf-8") as f:
        json.dump(rounds, f, ensure_ascii=False, indent=1)

    # 4) 정리된 CSV 저장 (엑셀 호환 cp949)
    def date_fmt(s):
        s = str(s)
        return "%s-%s-%s" % (s[0:4], s[4:6], s[6:8]) if len(s) == 8 else s

    cols = [
        ("round", "ltEpsd"),
        ("date", None),
        ("n1", "tm1WnNo"), ("n2", "tm2WnNo"), ("n3", "tm3WnNo"),
        ("n4", "tm4WnNo"), ("n5", "tm5WnNo"), ("n6", "tm6WnNo"),
        ("bonus", "bnsWnNo"),
        ("rank1_winners", "rnk1WnNope"), ("rank1_prize", "rnk1WnAmt"),
        ("rank2_winners", "rnk2WnNope"), ("rank2_prize", "rnk2WnAmt"),
        ("rank3_winners", "rnk3WnNope"), ("rank3_prize", "rnk3WnAmt"),
        ("rank4_winners", "rnk4WnNope"), ("rank4_prize", "rnk4WnAmt"),
        ("rank5_winners", "rnk5WnNope"), ("rank5_prize", "rnk5WnAmt"),
        ("total_sales", "rlvtEpsdSumNtslAmt"),
    ]
    path_csv = os.path.join(HERE, "lotto_all.csv")
    with open(path_csv, "w", newline="", encoding="cp949", errors="replace") as f:
        w = csv.writer(f)
        w.writerow([c[0] for c in cols])
        for r in rounds:
            row = []
            for name, key in cols:
                if name == "date":
                    row.append(date_fmt(r.get("ltRflYmd", "")))
                else:
                    row.append(r.get(key, ""))
            w.writerow(row)

    print("saved: lotto_all.json, lotto_all.csv", flush=True)


if __name__ == "__main__":
    main()
