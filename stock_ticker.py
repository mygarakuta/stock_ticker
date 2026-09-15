# -*- coding: utf-8 -*-
"""
stock_ticker (관심 종목 시세) - BookOasis 홈 대시보드 플러그인

환경설정 > 플러그인 설정에서 종목코드를 쉼표로 구분해 입력하면,
입력한 순서 그대로 홈 화면 위젯에 현재가/등락률을 보여줍니다.
(입력하지 않은 종목은 표시되지 않습니다)

시세 조회는 네이버 증권 모바일 API를 사용합니다(비공식, 사전 고지 없이
응답 형식이 바뀌거나 요청이 차단될 수 있습니다). 결과는 종목별로 캐싱되어
설정한 시간(기본 60초) 동안은 재조회하지 않습니다.
"""
import json

import requests

from plugins.metadata.base import BaseMetadataProvider


class StockTickerMetadataProvider(BaseMetadataProvider):
    id = "stock_ticker"
    name = "관심 종목 시세"
    is_searchable = False

    config_schema = [
        {
            "key": "STOCK_CODES",
            "label": "종목코드 목록 (쉼표로 구분, 입력한 순서대로 표시)",
            "type": "text",
            "required": False,
            "default": "",
            "placeholder": "예: 005930,000660,035420",
        },
        {
            "key": "CACHE_TTL_SEC",
            "label": "시세 캐시 유지 시간(초, 최소 10초)",
            "type": "number",
            "required": False,
            "default": 60,
        },
    ]

    # 사용자가 "홈 화면 플러그인 배치 모드"를 켜고 이 위젯을 직접 추가해야 노출됩니다.
    home_widget = {
        "title": "관심 종목 시세",
        "icon": "fa-solid fa-chart-line",
        "order": 60,
        "limit": 20,
        "sessions": "all",
        "layout": "grid",
        "size": 1,
    }

    NAVER_API_URL = "https://m.stock.naver.com/api/stock/{code}/basic"
    REQUEST_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://m.stock.naver.com/",
    }

    # ------------------------------------------------------------------
    # 필수 계약 (이 플러그인은 검색형 메타데이터 기능은 쓰지 않음)
    # ------------------------------------------------------------------
    def search(self, db_type, query):
        return {"success": True, "items": []}

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 도서 메타데이터에 적용할 수 없습니다."

    # ------------------------------------------------------------------
    # 홈 위젯 데이터 (home_widget이 재사용하는 공통 메서드)
    # ------------------------------------------------------------------
    def get_dashboard_data(self, db_type, limit=10):
        cfg = self.get_plugin_config(db_type, default={})
        raw_codes = str(cfg.get("STOCK_CODES") or "").strip()

        if not raw_codes:
            return {
                "success": True,
                "items": [
                    {
                        "item_type": "metric",
                        "metric": "설정 필요",
                        "value": "-",
                        "description": "환경설정 > 플러그인 설정에서 종목코드를 입력하세요.",
                    }
                ],
            }

        # 입력 순서를 그대로 유지하면서 중복/공백만 제거
        codes = []
        for part in raw_codes.split(","):
            code = part.strip()
            if code and code not in codes:
                codes.append(code)

        ttl = self._parse_ttl(cfg.get("CACHE_TTL_SEC"))

        target_codes = codes[:limit] if limit else codes
        items = [self._to_item(code, self._get_stock_info(code, ttl)) for code in target_codes]

        return {"success": True, "items": items}

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_ttl(value):
        try:
            ttl = int(value)
        except (TypeError, ValueError):
            ttl = 60
        return max(10, ttl)

    def _get_stock_info(self, code, ttl):
        cache_key = f"stock:{code}"
        cached = self.cache_get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except (TypeError, ValueError):
                pass  # 캐시가 손상된 경우 새로 조회

        info = self._fetch_from_naver(code)
        if info.get("success"):
            self.cache_set(cache_key, json.dumps(info), ttl=ttl)
        return info

    def _fetch_from_naver(self, code):
        try:
            res = requests.get(
                self.NAVER_API_URL.format(code=code),
                headers=self.REQUEST_HEADERS,
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
        except requests.RequestException as e:
            return {"success": False, "error": f"시세 조회 실패: {e}"}
        except ValueError as e:
            return {"success": False, "error": f"응답 파싱 실패: {e}"}

        name = data.get("stockName") or data.get("itemName") or code
        price = data.get("closePrice")
        change = data.get("compareToPreviousClosePrice")
        rate = data.get("fluctuationsRatio")
        # risingFalling: 네이버 내부 방향 코드(상승/보합/하락). 응답 필드명이 바뀌면
        # 이 값이 비어 있을 수 있으며, 이 경우 방향 화살표는 '-'로 표시됩니다.
        direction = str(data.get("risingFalling") or "")

        return {
            "success": True,
            "name": name,
            "price": price,
            "change": change,
            "rate": rate,
            "direction": direction,
        }

    @staticmethod
    def _to_item(code, info):
        # 위젯 카드 레이아웃상 metric 칸이 굵게, value/description 칸이 일반체로
        # 표시되는 것을 이용해: 이름(코드)은 metric에, 현재가/변동은 value에 담는다.
        if not info.get("success"):
            return {
                "item_type": "metric",
                "metric": code,
                "value": f"조회 실패 ({info.get('error', '')})",
                "description": "",
            }

        name = info.get("name") or code
        price = info.get("price")
        change = info.get("change")
        rate = info.get("rate")

        price_text = f"{price}원" if price is not None else "-"

        change_text = "-"
        if change is not None and rate is not None:
            try:
                change_num = float(str(change).replace(",", ""))
                rate_num = float(str(rate).replace(",", ""))
            except (TypeError, ValueError):
                change_num = None
                rate_num = None

            if change_num is not None:
                if change_num > 0:
                    arrow = "▲"
                elif change_num < 0:
                    arrow = "▼"
                else:
                    arrow = "－"
                change_text = f"{arrow}{abs(change_num):g}원 ({abs(rate_num):g}%)"
            else:
                # 숫자 변환에 실패하면 원본 값을 그대로 노출(부호 중복 방지를 위해 화살표는 생략)
                change_text = f"{change}원 ({rate}%)"

        return {
            "item_type": "metric",
            "metric": f"{name}({code})",
            "value": f"{price_text}  {change_text}",
            "description": "",
        }
