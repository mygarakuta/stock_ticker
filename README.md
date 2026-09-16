# stock_ticker (BookOasis 위젯)

관심 종목의 현재가와 등락률을 홈 대시보드 / 공통 데스크 위젯에 보여주는 플러그인입니다.

## 이번 변경 사항 (종목별 추이 그래프 추가)

BookOasis 코어 1.1.1+ 부터 `home_widget`을 쓰는 플러그인이 `dashboard.html` /
`dashboard.css` / `dashboard.js`를 함께 두면, 위젯마다 독립된 **Shadow DOM**에서
완전한 CSS/이미지를 자유롭게 쓸 수 있게 되었습니다(가이드 문서 §5-1). 이 계약을
활용해 아래처럼 구조를 바꿨습니다.

- `stock_ticker.py`
  - `get_dashboard_data()`가 현재가/등락률뿐 아니라 최근 종가 시계열(`series`, 최대
    60개 포인트)까지 함께 반환하도록 확장했습니다.
  - Yahoo Finance 비공식 chart API(`/v8/finance/chart/<symbol>`)를 사용해 API 키
    없이 시세 + 히스토리를 한 번에 가져옵니다.
  - `self.cache_get`/`self.cache_set`(Redis)로 결과를 캐싱해 홈 화면을 열 때마다
    외부 API를 다시 때리지 않도록 했습니다(기본 15분, `CACHE_TTL_SEC` 설정으로 조절).
  - `config_schema`에 `RANGE`(조회 기간), `INTERVAL`(일봉/주봉)을 추가해 그래프 구간을
    조절할 수 있게 했습니다.
- `dashboard.html` / `dashboard.css` / `dashboard.js` (신규)
  - `dashboard.js`가 `items`의 `series` 배열로 종목별 **SVG 스파크라인(추이 그래프)**을
    직접 그려 각 종목 카드에 삽입합니다. 외부 차트 라이브러리 없이 순수 SVG라
    번들 크기나 CSP 문제가 없습니다.
  - 상승/하락에 따라 선/영역 색상이 초록/빨강으로 자동 전환됩니다.
  - 그 외 색상(배경, 텍스트 등)은 `var(--app-bg-card)` 등 전역 CSS 변수를 사용해
    8종 대시보드 테마에 자동으로 맞춰집니다.
  - 이 파일들이 없던 구버전 코어(또는 파일 로드 실패 시)를 위해 `get_dashboard_data()`는
    여전히 `item_type: "metric"` 폴백 필드(`metric`/`value`/`description`)도 함께
    채워 보냅니다.
- `VERSION`
  - `plugin version`을 2로 올렸습니다. 저장소에 push 후, 환경설정 > 플러그인 설정에서
    "샘플 업데이트" 버튼으로 기존 설치본을 갱신할 수 있습니다.

## 설정

플러그인 설정 화면에서 아래 항목을 구성합니다.

| 키 | 설명 | 기본값 |
| :-- | :-- | :-- |
| `SYMBOLS` | 종목 코드, 쉼표로 구분 (예: `AAPL,MSFT,005930.KS`) | `AAPL,MSFT,NVDA` |
| `RANGE` | 추이 조회 기간 (`5d`/`1mo`/`3mo`/`6mo`/`1y`) | `1mo` |
| `INTERVAL` | 데이터 간격 (`1d`/`1wk`) | `1d` |
| `CACHE_TTL_SEC` | 캐시 유지 시간(초) | `900` |

## 참고

- 이 플러그인은 `home_widget`(실제 홈 화면)과 `dashboard_widget`(공통 데스크 탭)을
  동시에 선언하므로, 사용자가 "홈 화면 플러그인 배치 모드"를 켜지 않아도 기존처럼
  공통 데스크 탭에서는 계속 보입니다.
- Yahoo Finance 비공식 API는 별도 인증이 필요 없지만 SLA가 보장되지 않으므로,
  요청 실패 시 해당 종목만 조용히 목록에서 빠지도록 처리되어 있습니다(전체 위젯이
  깨지지 않음).
