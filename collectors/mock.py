import json
import random
import uuid
from datetime import datetime, timedelta

from .base import OrderCollector

PRODUCT_SAMPLES = [
    ("무선 이어폰 프로", "블랙"),
    ("스테인리스 텀블러 500ml", "화이트"),
    ("접이식 캠핑 의자", "카키"),
    ("면 100% 기본 티셔츠", "L / 네이비"),
    ("휴대용 미니 가습기", "그레이"),
    ("반려동물 급수기", "S 사이즈"),
]
NAME_SAMPLES = ["김민준", "이서연", "박도윤", "최지우", "정하윤", "강서준"]
STATUS_SAMPLES = ["결제완료", "상품준비중", "발송완료"]


class MockCollector(OrderCollector):
    """실제 API 키가 없을 때 화면 확인용 가짜 주문을 만들어주는 수집기."""

    def __init__(self, market):
        self.market = market

    def fetch_new_orders(self, count=None):
        count = count or random.randint(1, 4)
        orders = []
        now = datetime.utcnow()
        for _ in range(count):
            product_name, option_name = random.choice(PRODUCT_SAMPLES)
            quantity = random.randint(1, 3)
            unit_price = random.choice([9900, 15000, 22000, 35000, 48000])
            buyer = random.choice(NAME_SAMPLES)
            order_id = f"{self.market.upper()}-{uuid.uuid4().hex[:10].upper()}"
            ordered_at = now - timedelta(minutes=random.randint(1, 600))
            raw = {
                "productName": product_name,
                "optionName": option_name,
                "quantity": quantity,
                "unitPrice": unit_price,
                "buyerName": buyer,
                "note": "mock data - 테스트 모드에서 생성된 가짜 주문입니다.",
            }
            orders.append(
                {
                    "external_order_id": order_id,
                    "product_name": product_name,
                    "option_name": option_name,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": unit_price * quantity,
                    "buyer_name": buyer,
                    "buyer_tel": "010-0000-0000",
                    "receiver_name": buyer,
                    "receiver_tel": "010-0000-0000",
                    "address": "서울특별시 어딘가구 테스트로 123",
                    "order_status": random.choice(STATUS_SAMPLES),
                    "ordered_at": ordered_at,
                    "raw_json": json.dumps(raw, ensure_ascii=False),
                }
            )
        return orders
