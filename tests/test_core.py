# tests/test_core.py —— 不依赖数据库的核心逻辑测试
#
# 运行：.venv/bin/python -m unittest discover -s tests -v

import unittest
from decimal import Decimal
from types import SimpleNamespace

from app.core import to_decimal, to_money_text, to_percent_text, to_ratio_text
from app.schemas.agent import AgentChatRequest
from app.services.analytics_service import (
    calculate_profit,
    calculate_profit_at_price,
    detect_anomalies,
    sort_products,
)
from app.services.simulations import simulate_price


def make_product(
    sale_price: str = "100",
    settlement_price: str | None = "60",
    fee: str | None = "5",
) -> SimpleNamespace:
    """构造一个只包含利润计算所需字段的假商品。"""
    return SimpleNamespace(
        product_code="TEST001",
        pdd_sale_price=Decimal(sale_price),
        settlement_price=(
            Decimal(settlement_price) if settlement_price is not None else None
        ),
        fee=Decimal(fee) if fee is not None else None,
    )


class ConverterTests(unittest.TestCase):
    def test_to_decimal(self):
        self.assertIsNone(to_decimal(None))
        self.assertEqual(to_decimal("12.30"), Decimal("12.30"))

    def test_to_money_text(self):
        self.assertEqual(to_money_text(Decimal("1.005")), "1.01")
        self.assertIsNone(to_money_text(None))

    def test_to_ratio_text(self):
        self.assertEqual(to_ratio_text(Decimal("0.12345")), "0.1235")
        self.assertIsNone(to_ratio_text(None))

    def test_to_percent_text(self):
        self.assertEqual(to_percent_text(Decimal("0.12345")), "12.35%")
        self.assertIsNone(to_percent_text(None))


class ProfitTests(unittest.TestCase):
    def test_calculate_profit(self):
        result = calculate_profit(make_product())
        self.assertEqual(result["pdd_profit"], Decimal("25"))
        self.assertEqual(result["profit_margin"], Decimal("0.25"))

    def test_calculate_profit_at_target_price(self):
        result = calculate_profit_at_price(make_product(), Decimal("90"))
        self.assertEqual(result["pdd_profit"], Decimal("15"))
        self.assertEqual(
            result["profit_margin"],
            Decimal("15") / Decimal("90"),
        )

    def test_zero_price_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_profit(make_product(sale_price="0"))

    def test_missing_cost_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_profit(make_product(settlement_price=None))

    def test_sort_by_profit_margin(self):
        items = [
            {
                "product_code": "A",
                "pdd_profit": Decimal("10"),
                "pdd_sale_price": Decimal("100"),
                "profit_margin": Decimal("0.1"),
            },
            {
                "product_code": "B",
                "pdd_profit": Decimal("20"),
                "pdd_sale_price": Decimal("100"),
                "profit_margin": Decimal("0.2"),
            },
        ]
        ranked = sort_products(items, sort_by="profit_margin")
        self.assertEqual([item["product_code"] for item in ranked], ["B", "A"])

    def test_detect_anomalies(self):
        anomalies = detect_anomalies({
            "pdd_profit": Decimal("-1"),
            "profit_margin": Decimal("-0.1"),
        })
        codes = [item["code"] for item in anomalies]
        self.assertIn("NEGATIVE_PROFIT", codes)
        self.assertIn("LOW_PROFIT_MARGIN", codes)


class SimulationTests(unittest.TestCase):
    def test_simulate_price(self):
        result = simulate_price(make_product(), Decimal("90"))
        self.assertEqual(result["original_profit"], "25.00")
        self.assertEqual(result["simulated_profit"], "15.00")
        self.assertEqual(result["profit_change"], "-10.00")
        self.assertEqual(result["profit_margin"], "0.1667")
        self.assertTrue(result["feasible"])

    def test_target_margin_not_met(self):
        result = simulate_price(
            make_product(),
            Decimal("90"),
            target_margin=Decimal("0.2"),
        )
        self.assertFalse(result["feasible"])
        self.assertEqual(result["violations"][0]["code"], "TARGET_MARGIN_NOT_MET")

    def test_min_price_is_enforced(self):
        with self.assertRaises(ValueError):
            simulate_price(
                make_product(),
                Decimal("90"),
                min_price=Decimal("95"),
            )


class AgentSchemaTests(unittest.TestCase):
    def test_thread_id_is_generated_when_missing(self):
        first = AgentChatRequest(message="查询 B20112320")
        second = AgentChatRequest(message="查询 B20112320")
        self.assertTrue(first.thread_id)
        self.assertNotEqual(first.thread_id, second.thread_id)

    def test_empty_message_is_rejected(self):
        with self.assertRaises(ValueError):
            AgentChatRequest(message="")


if __name__ == "__main__":
    unittest.main()
