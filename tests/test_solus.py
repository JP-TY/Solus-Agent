"""Offline tests for Solus artifacts (no AWS calls)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "starter" / "lambda"))

from book_site_survey import lambda_handler as survey_handler
from submit_net_metering import lambda_handler as nm_handler
from order_tracker import lambda_handler as order_handler
from refund_processor import lambda_handler as refund_handler


class FakeCtx:
    def __init__(self, tool=""):
        self.client_context = type(
            "C", (), {"custom": {"bedrockAgentCoreToolName": tool}}
        )()


def test_survey_post_requires_fields():
    event = {"resource": "/surveys", "httpMethod": "POST", "body": json.dumps({})}
    resp = survey_handler(event, None)
    assert resp["statusCode"] == 400


def test_survey_post_ok():
    event = {
        "resource": "/surveys",
        "httpMethod": "POST",
        "body": json.dumps({
            "customer_id": "CUST-123",
            "customer_name": "Jane",
            "address": "Quezon City",
            "roof_material": "GI sheet",
            "preferred_date": "2026-10-05",
            "utility": "Meralco",
        }),
    }
    resp = survey_handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["survey_id"].startswith("SRV-")
    assert body["status"] == "SCHEDULED"


def test_survey_get_by_id():
    event = {
        "resource": "/surveys/{survey_id}",
        "httpMethod": "GET",
        "pathParameters": {"survey_id": "SRV-ABC123"},
    }
    resp = survey_handler(event, None)
    assert resp["statusCode"] == 200


def test_net_metering_submit():
    event = {
        "customer_id": "CUST-123",
        "distribution_utility": "Meralco",
        "account_number": "1234567890",
        "capacity_kwp": 5.5,
        "inverter_type": "hybrid",
    }
    resp = nm_handler(event, FakeCtx("SolusTarget___submit_net_metering"))
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["application_id"].startswith("NM-")
    assert body["status"] == "FILED"


def test_net_metering_checklist():
    event = {"distribution_utility": "VECO"}
    resp = nm_handler(event, FakeCtx("SolusTarget___get_interconnection_checklist"))
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body["checklist"]) >= 3


def test_lambda_schema_valid():
    schema = json.loads(
        Path(__file__).resolve().parents[1]
        .joinpath("starter/lambda/lambda_schema").read_text()
    )
    names = {t["name"] for t in schema}
    assert {"submit_net_metering", "check_net_metering_status",
            "get_interconnection_checklist"} <= names
    assert {"initiate_refund", "check_refund_status",
            "get_return_label"} <= names


def test_order_get_by_id():
    event = {
        "resource": "/orders/{order_id}",
        "httpMethod": "GET",
        "pathParameters": {"order_id": "ORD-001"},
    }
    resp = order_handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "SHIPPED"
    assert body["tracking_number"] == "TRK987654321"


def test_order_customer_orders():
    event = {
        "resource": "/customers/{customer_id}/orders",
        "httpMethod": "GET",
        "pathParameters": {"customer_id": "CUST-123"},
    }
    resp = order_handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body["orders"]) == 2


def test_order_not_found():
    event = {
        "resource": "/orders/{order_id}",
        "httpMethod": "GET",
        "pathParameters": {"order_id": "ORD-999"},
    }
    resp = order_handler(event, None)
    assert resp["statusCode"] == 404


def test_refund_initiate():
    event = {"order_id": "ORD-002", "amount": 139.99, "reason": "damaged"}
    resp = refund_handler(event, FakeCtx("SolusTarget___initiate_refund"))
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["refund_id"].startswith("REF-")
    assert body["status"] == "APPROVED"


def test_refund_status_and_label():
    resp = refund_handler(
        {"refund_id": "REF-ABC12345"},
        FakeCtx("SolusTarget___check_refund_status"))
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["status"] == "PROCESSING"
    resp = refund_handler(
        {"order_id": "ORD-001"},
        FakeCtx("SolusTarget___get_return_label"))
    assert resp["statusCode"] == 200
    assert "label_url" in json.loads(resp["body"])


def test_catalog_has_solar_sections():
    text = Path(__file__).resolve().parents[1].joinpath(
        "starter/product_catalog.txt").read_text()
    for needle in ["550W", "Deye", "5.12 kWh", "avoided generation cost",
                   "4.5", "280", "Meralco", "VECO", "Davao Light"]:
        assert needle in text, needle


def test_main_rubric_patterns():
    src = Path(__file__).resolve().parents[1].joinpath("starter/main.py").read_text()
    for needle in [
        "BedrockAgentCoreApp()", "@app.entrypoint", "app.run()",
        "MCPClient", "streamable_http_client", "create_all_tools", "list_tools_sync",
        "@tool", "def search_knowledge_base", "_bedrock_runtime.retrieve",
        "KB_ID is empty or missing", "def get_namespaces",
        "namespaceTemplates", "class MemoryHook(HookProvider)",
        "register_hooks", "retrieve_customer_context", "save_support_interaction",
        "create_event", "def calculate_loyalty_discount",
        "earn_rates", "tier_rates", "points_redeemed", "tier_discount_pct",
        "final_total", "remaining_points", 'code_session(REGION).invoke("executeCode"',
        "clearContext", "AgentCoreBrowser", "agent_core_browser.browser",
    ]:
        assert needle in src, needle
