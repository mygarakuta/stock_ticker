# -*- coding: utf-8 -*-
"""
stock_ticker 플러그인 (BookOasis)

관심 종목의 현재가/등락률과 함께, 최근 구간의 종가 시계열(series)을 함께 반환하여
대시보드/홈 위젯에서 종목별 추이 그래프(스파크라인)를 그릴 수 있도록 합니다.

- 계약: dashboard_widget + home_widget (§5, §5-1 참고)
- 데이터 소스: Yahoo Finance 비공식 chart API (API 키 불필요)
- 캐싱: self.cache_get/self.cache_set (Redis, 코어 제공 헬퍼) 사용
- 커스텀 CSS/그래프: dashboard.html / dashboard.css / dashboard.js (Shadow DOM 격리 렌더링)
"""
import json

import requests

from plugins.metadata.base import BaseMetadataProvider


class StockTickerProvider(BaseMetadataProvider):
    id = "stock_ticker"
    name = "주식 시세 위젯 (Stock Ticker)"
    is_searchable = False

    config_schema = [
        {
            "key": "SYMBOLS",
            "label": "종목 코드 (쉼표로 구분, 예: AAPL,MSFT,005930.KS)",
            "type": "text",
            "default": "AAPL,MSFT,NVDA",
            "required": True,
        },
        {
            "key": "RANGE",
            "label": "추이 조회 기간",
            "type": "select",
            "default": "1mo",
            "options": [
                {"value": "5d", "label": "5일"},
                {"value": "1mo", "label": "1개월"},
                {"value": "3mo", "label": "3개월"},
                {"value": "6mo", "label": "6개월"},
                {"value": "1y", "label": "1년"},
            ],
        },
        {
            "key": "INTERVAL",
            "label": "데이터 간격",
            "type": "select",
            "default": "1d",
            "options": [
                {"value": "1d", "label": "일봉"},
                {"value": "1wk", "label": "주봉"},
            ],
        },
        {
            "key": "CACHE_TTL_SEC",
            "label": "캐시 유지 시간(초)",
            "type": "number",
            "default": 900,
        },
    ]

    update_manifest = {
        "enabled": True,
        "provider": "github-raw",
        "raw_base_url": "https://raw.githubusercontent.com/mygarakuta/stock_ticker/main",
        "files": [
            "stock_ticker.py",
            "__init__.py",
            "VERSION",
            "dashboard.html",
            "dashboard.css",
            "dashboard.js",
        ],
        "version_file": "VERSION",
        "version_key": "plugin version",
        "show_sample_update_button": True,
    }

    # [플러그인] 공통 데스크 탭 카드 (기존과 동일하게 유지)
    dashboard_widget = {
        "title": "주식 시세",
        "subtitle": "관심 종목 추이",
        "provider": "Yahoo Finance",
        "icon": "fa-solid fa-chart-line",
        "limit": 10,
    }

    # 실제 홈 대시보드 위젯 (플러그인 배치 모드를 켠 사용자만 노출, §5-1)
    home_widget = {
        "title": "주식 시세",
        "subtitle": "관심 종목 추이",
        "icon": "fa-solid fa-chart-line",
        "order": 60,
        "limit": 10,
        "sessions": "all",
        "layout": "grid",
        "size": 1,
    }

    # -----------------------------------------------------------------
    # 필수 계약 (대시보드 전용 플러그인이므로 실질 동작 없음)
    # -----------------------------------------------------------------
    def search(self, db_type, query):
        return {"success": True, "items": []}

    def apply(self, db_type, book_id, item_data):
        return False, "대시보드 전용 플러그인입니다."

    # -----------------------------------------------------------------
    # 내부 헬퍼
    # -----------------------------------------------------------------
    def _get_cfg(self, db_type):
        cfg = self.get_plugin_config(db_type, default={})
        symbols_raw = cfg.get("SYMBOLS") or "AAPL,MSFT,NVDA"
        symbols = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]
        rng = cfg.get("RANGE") or "1mo"
        interval = cfg.get("INTERVAL") or "1d"
        try:
            ttl = int(cfg.get("CACHE_TTL_SEC") or 900)
        except (TypeError, ValueError):
            ttl = 900
        return symbols, rng, interval, ttl

    def _fetch_symbol(self, symbol, rng, interval):
        """Yahoo Finance chart API에서 현재가 + 종가 시계열을 가져온다."""
        url = "https://query1.finance.yahoo.com/v8/finance/chart/{}".format(symbol)
        params = {"range": rng, "interval": interval}
        headers = {"User-Agent": "Mozilla/5.0 (BookOasis stock_ticker plugin)"}

        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            res.raise_for_status()
            data = res.json()

            result_list = (data.get("chart") or {}).get("result") or []
            if not result_list:
                return None

            node = result_list[0]
            meta = node.get("meta") or {}

            quote = ((node.get("indicators") or {}).get("quote") or [{}])[0]
            closes_raw = quote.get("close") or []
            # None(휴장/결측)을 건너뛰고 숫자만 남긴다
            closes = [float(c) for c in closes_raw if isinstance(c, (int, float))]
            if not closes:
                return None

            price = meta.get("regularMarketPrice", closes[-1])
            prev_close = meta.get("chartPreviousClose") or closes[0]
            change_pct = 0.0
            if prev_close:
                change_pct = round((price - prev_close) / prev_close * 100, 2)

            return {
                "symbol": symbol,
                "name": meta.get("shortName") or meta.get("longName") or symbol,
                "currency": meta.get("currency") or "",
                "price": round(float(price), 2),
                "change_pct": change_pct,
                # 위젯 그래프가 너무 촘촘해지지 않도록 최근 60개 포인트로 제한
                "series": [round(c, 4) for c in closes][-60:],
            }
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return None

    # -----------------------------------------------------------------
    # 대시보드 / 홈 위젯 공통 데이터 소스
    # -----------------------------------------------------------------
    def get_dashboard_data(self, db_type, limit=10):
        symbols, rng, interval, ttl = self._get_cfg(db_type)
        try:
            limit = int(limit or len(symbols)) or len(symbols)
        except (TypeError, ValueError):
            limit = len(symbols)
        symbols = symbols[:max(1, limit)]

        cache_key = "quotes:{}:{}:{}:{}".format(db_type, rng, interval, ",".join(symbols))
        cached = self.cache_get(cache_key)
        if cached:
            try:
                return {"success": True, "items": json.loads(cached)}
            except (ValueError, TypeError):
                pass  # 캐시가 손상된 경우 아래에서 다시 조회

        items = []
        for sym in symbols:
            info = self._fetch_symbol(sym, rng, interval)
            if not info:
                continue
            items.append(
                {
                    # dashboard.html/js가 없는 환경(구버전 코어)을 위한 최소 폴백 표시
                    "item_type": "metric",
                    "metric": info["symbol"],
                    "value": "{} {}".format(info["price"], info["currency"]).strip(),
                    "description": info["name"],
                    # dashboard.js가 그래프를 그릴 때 쓰는 실제 데이터
                    "symbol": info["symbol"],
                    "name": info["name"],
                    "price": info["price"],
                    "currency": info["currency"],
                    "change_pct": info["change_pct"],
                    "series": info["series"],
                }
            )

        if items:
            self.cache_set(cache_key, json.dumps(items), ttl=ttl)

        return {"success": True, "items": items}
