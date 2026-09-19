"""Offline tests for Solus artifacts (no AWS calls)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "starter" / "lambda"))

from book_site_survey import lambda_handler as survey_handler
from submit_net_metering import lambda_handler as nm_handler


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
        "Knowledge base not configured", "def get_namespaces",
        "namespaceTemplates", "class MemoryHook(HookProvider)",
        "register_hooks", "retrieve_customer_context", "save_support_interaction",
        "create_event", "def calculate_loyalty_discount",
        "earn_rates", "tier_rates", "points_redeemed", "tier_discount_pct",
        "final_total", "remaining_points", 'code_session(REGION).invoke("executeCode"',
        "clearContext", "AgentCoreBrowser", "agent_core_browser.browser",
    ]:
        assert needle in src, needle
