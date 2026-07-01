# 로또 6/45 당첨 데이터 분석

동행복권 로또 6/45의 1회차부터 최신 회차까지의 당첨 결과를 수집하고,
통계 분석과 확률 시뮬레이션을 수행하는 파이썬 프로젝트입니다.

## 실행 환경

- Windows / macOS / Linux
- Python 3.8 이상
- 패키지: `numpy`, `scipy` (통계 검정 스크립트에서 사용)
  ```
  pip install numpy scipy
  ```
- `collect_lotto.py` 실행 시 인터넷 연결 필요 (동행복권 데이터 조회)

## 구성

| 파일 | 설명 |
|------|------|
| `collect_lotto.py` | 1회차~최신 회차 당첨 결과 수집 → `lotto_all.json`, `lotto_all.csv` 생성 |
| `analyze_stats.py` | 번호 빈도·미출현 기간·홀짝·합계·구간·연속번호 등 기술 통계 |
| `enhanced_stats.py` | 카이제곱 적합도 검정, 번호별 z-score, 전략 백테스트 |
| `recommend_simulate.py` | 등수별 이론 확률, 번호 추천, 전략별 몬테카를로 시뮬레이션 |
| `lotto_all.json` / `lotto_all.csv` | 수집된 전체 회차 데이터 |

## 사용법

```bash
python collect_lotto.py        # 데이터 수집 / 갱신
python analyze_stats.py        # 기술 통계 리포트
python enhanced_stats.py       # 통계 검정 + 백테스트
python recommend_simulate.py   # 확률 계산 + 시뮬레이션
```

각 스크립트는 결과를 화면에 출력하고 `*_report.txt` 파일로도 저장합니다.

## 데이터 출처

동행복권(dhlottery.co.kr) 공개 회차별 결과. 새 회차가 추첨되면
`collect_lotto.py`를 다시 실행해 최신 데이터로 갱신할 수 있습니다.

## 참고

로또는 매 회차가 독립 시행이므로 과거 데이터로 다음 당첨 번호를 예측할 수
없습니다. 이 프로젝트의 통계 검정은 추첨의 공정성(균등성)을 확인하기 위한
것이며, 번호 추천 기능은 참고용입니다.
