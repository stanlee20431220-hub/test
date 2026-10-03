import json
from datetime import datetime

from extensions import db

MARKETS = [
    ("naver", "네이버 스마트스토어"),
    ("coupang", "쿠팡"),
    ("gmarket", "지마켓/옥션(ESM+)"),
]

MARKET_LABELS = dict(MARKETS)


class MarketAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    market = db.Column(db.String(20), unique=True, nullable=False)
    client_id = db.Column(db.String(300))
    client_secret = db.Column(db.String(300))
    use_mock = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def label(self):
        return MARKET_LABELS.get(self.market, self.market)

    @property
    def is_configured(self):
        return bool(self.client_id and self.client_secret)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    market = db.Column(db.String(20), nullable=False)
    external_order_id = db.Column(db.String(100), nullable=False)

    product_name = db.Column(db.String(300))
    option_name = db.Column(db.String(300))
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Integer, default=0)
    total_price = db.Column(db.Integer, default=0)

    buyer_name = db.Column(db.String(100))
    buyer_tel = db.Column(db.String(50))
    receiver_name = db.Column(db.String(100))
    receiver_tel = db.Column(db.String(50))
    address = db.Column(db.String(500))

    order_status = db.Column(db.String(50))
    ordered_at = db.Column(db.DateTime)
    collected_at = db.Column(db.DateTime, default=datetime.utcnow)

    raw_json = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint("market", "external_order_id", name="uq_market_order"),
    )

    @property
    def market_label(self):
        return MARKET_LABELS.get(self.market, self.market)


class DetailPage(db.Model):
    """상세페이지 마법사로 만든 결과물."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    theme = db.Column(db.String(20), default="mint", nullable=False)
    product_json = db.Column(db.Text, nullable=False, default="{}")
    content_json = db.Column(db.Text, nullable=False, default="{}")
    images_json = db.Column(db.Text, nullable=False, default="[]")
    generated_by = db.Column(db.String(20), default="template")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def product(self):
        return json.loads(self.product_json)

    @property
    def content(self):
        return json.loads(self.content_json)

    @content.setter
    def content(self, value):
        self.content_json = json.dumps(value, ensure_ascii=False)

    @property
    def images(self):
        return json.loads(self.images_json)

    @images.setter
    def images(self, value):
        self.images_json = json.dumps(value)
