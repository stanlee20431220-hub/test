import base64
import json
import time
from datetime import datetime, timedelta

import bcrypt
import requests

from .base import OrderCollector

BASE_URL = "https://api.commerce.naver.com/external"
TOKEN_URL = f"{BASE_URL}/v1/oauth2/token"
CHANGED_STATUS_URL = f"{BASE_URL}/v1/pay-order/seller/product-orders/last-changed-statuses"
ORDER_QUERY_URL = f"{BASE_URL}/v1/pay-order/seller/product-orders/query"


class NaverApiError(Exception):
    pass


class NaverCollector(OrderCollector):
    """네이버 커머스API센터(apicenter.commerce.naver.com)에서 발급받은
    Client ID / Client Secret 으로 최근 변경된 주문을 가져오는 수집기.

    주의: 네이버 오픈API는 정책/필드명이 바뀔 수 있으므로, 실제 연동 전에
    최신 공식 문서를 꼭 확인하세요. https://apicenter.commerce.naver.com
    """

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

    def _get_access_token(self):
        timestamp = str(int(time.time() * 1000))
        password = f"{self.client_id}_{timestamp}"
        hashed = bcrypt.hashpw(password.encode("utf-8"), self.client_secret.encode("utf-8"))
        client_secret_sign = base64.b64encode(hashed).decode("utf-8")

        resp = requests.post(
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "timestamp": timestamp,
                "client_secret_sign": client_secret_sign,
                "grant_type": "client_credentials",
                "type": "SELF",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            raise NaverApiError(f"토큰 발급 실패 ({resp.status_code}): {resp.text}")
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise NaverApiError(f"토큰 응답에 access_token이 없습니다: {data}")
        return token

    def fetch_new_orders(self, minutes=60 * 24):
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        now = datetime.utcnow()
        since = now - timedelta(minutes=minutes)
        params = {
            "lastChangedFrom": since.strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
            "lastChangedTo": now.strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
        }

        resp = requests.get(CHANGED_STATUS_URL, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            raise NaverApiError(f"변경 주문 조회 실패 ({resp.status_code}): {resp.text}")

        changed = resp.json().get("data", {}).get("lastChangeStatuses", [])
        product_order_ids = list({item.get("productOrderId") for item in changed if item.get("productOrderId")})
        if not product_order_ids:
            return []

        detail_resp = requests.post(
            ORDER_QUERY_URL,
            headers=headers,
            json={"productOrderIds": product_order_ids},
            timeout=15,
        )
        if detail_resp.status_code != 200:
            raise NaverApiError(f"주문 상세 조회 실패 ({detail_resp.status_code}): {detail_resp.text}")

        raw_orders = detail_resp.json().get("data", [])
        return [self._normalize(raw) for raw in raw_orders]

    def _normalize(self, raw):
        order = raw.get("productOrder", raw)
        delivery = raw.get("delivery", {}) or {}

        quantity = int(order.get("quantity", 1) or 1)
        unit_price = int(order.get("unitPrice", 0) or 0)

        ordered_at = None
        ordered_at_raw = order.get("orderDate") or order.get("paymentDate")
        if ordered_at_raw:
            try:
                ordered_at = datetime.fromisoformat(ordered_at_raw.replace("Z", "+00:00"))
            except ValueError:
                ordered_at = None

        return {
            "external_order_id": str(order.get("productOrderId")),
            "product_name": order.get("productName", ""),
            "option_name": order.get("productOption", ""),
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": order.get("totalPaymentAmount", unit_price * quantity),
            "buyer_name": raw.get("ordererName", ""),
            "buyer_tel": raw.get("ordererTel", ""),
            "receiver_name": delivery.get("receiverName", ""),
            "receiver_tel": delivery.get("receiverTel1", ""),
            "address": delivery.get("baseAddress", ""),
            "order_status": order.get("productOrderStatus", ""),
            "ordered_at": ordered_at,
            "raw_json": json.dumps(raw, ensure_ascii=False),
        }
