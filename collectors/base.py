class OrderCollector:
    """모든 마켓 수집기가 따라야 하는 공통 형태."""

    def fetch_new_orders(self):
        """새로 들어온 주문을 딕셔너리 리스트로 반환한다.

        각 딕셔너리는 models.Order 의 컬럼과 같은 키를 사용한다:
        external_order_id, product_name, option_name, quantity,
        unit_price, total_price, buyer_name, buyer_tel,
        receiver_name, receiver_tel, address, order_status,
        ordered_at(datetime), raw_json(str)
        """
        raise NotImplementedError
