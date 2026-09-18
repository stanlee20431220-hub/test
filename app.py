import os

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

from collectors.mock import MockCollector
from collectors.naver import NaverApiError, NaverCollector
from extensions import db
from models import MARKETS, MarketAccount, Order

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///orders.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        _ensure_market_accounts()

    register_routes(app)
    return app


def _ensure_market_accounts():
    existing = {m.market for m in MarketAccount.query.all()}
    for market, _label in MARKETS:
        if market not in existing:
            db.session.add(MarketAccount(market=market, use_mock=True))
    db.session.commit()


def register_routes(app):
    @app.route("/")
    def dashboard():
        market_filter = request.args.get("market", "")
        status_filter = request.args.get("status", "")
        keyword = request.args.get("q", "")

        query = Order.query
        if market_filter:
            query = query.filter(Order.market == market_filter)
        if status_filter:
            query = query.filter(Order.order_status == status_filter)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                db.or_(
                    Order.product_name.like(like),
                    Order.buyer_name.like(like),
                    Order.external_order_id.like(like),
                )
            )
        orders = query.order_by(Order.ordered_at.desc()).limit(300).all()

        accounts = MarketAccount.query.all()
        statuses = [
            row[0]
            for row in db.session.query(Order.order_status).distinct().all()
            if row[0]
        ]

        return render_template(
            "dashboard.html",
            orders=orders,
            markets=MARKETS,
            accounts=accounts,
            statuses=statuses,
            market_filter=market_filter,
            status_filter=status_filter,
            keyword=keyword,
        )

    @app.route("/collect", methods=["POST"])
    def collect():
        market = request.form.get("market")
        account = MarketAccount.query.filter_by(market=market).first()
        if account is None:
            flash("알 수 없는 마켓입니다.", "error")
            return redirect(url_for("dashboard"))

        try:
            if account.use_mock:
                collector = MockCollector(market)
            elif market == "naver":
                if not account.is_configured:
                    flash("먼저 설정 화면에서 네이버 Client ID / Secret을 입력해주세요.", "error")
                    return redirect(url_for("settings"))
                collector = NaverCollector(account.client_id, account.client_secret)
            else:
                flash(f"{account.label} 실제 연동은 아직 준비 중입니다. 테스트 모드를 사용해주세요.", "error")
                return redirect(url_for("dashboard"))

            new_orders = collector.fetch_new_orders()
        except NaverApiError as exc:
            flash(f"네이버 주문 수집 중 오류가 발생했습니다: {exc}", "error")
            return redirect(url_for("dashboard"))
        except Exception as exc:  # noqa: BLE001
            flash(f"주문 수집 중 알 수 없는 오류가 발생했습니다: {exc}", "error")
            return redirect(url_for("dashboard"))

        added = 0
        for data in new_orders:
            already = Order.query.filter_by(
                market=market, external_order_id=data["external_order_id"]
            ).first()
            if already:
                continue
            db.session.add(Order(market=market, **data))
            added += 1
        db.session.commit()

        flash(f"{account.label}에서 새 주문 {added}건을 수집했습니다.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        if request.method == "POST":
            market = request.form.get("market")
            account = MarketAccount.query.filter_by(market=market).first()
            if account is None:
                flash("알 수 없는 마켓입니다.", "error")
                return redirect(url_for("settings"))

            account.client_id = request.form.get("client_id", "").strip()
            account.client_secret = request.form.get("client_secret", "").strip()
            account.use_mock = request.form.get("use_mock") == "on"
            db.session.commit()
            flash(f"{account.label} 설정을 저장했습니다.", "success")
            return redirect(url_for("settings"))

        accounts = MarketAccount.query.all()
        return render_template("settings.html", accounts=accounts)


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
else:
    app = create_app()
