"""
Solus Net-Metering Lambda
=========================
Files initial Net-Metering / interconnection applications to Philippine
distribution utilities (Meralco, VECO, Davao Light).
Invoked directly by the AgentCore Gateway (not through API Gateway).

How tool routing works:
  AgentCore Gateway passes the tool name in the Lambda client context under
  the key "bedrockAgentCoreToolName". The value has the format:
    "TargetName___toolName"
  This handler strips the prefix and branches on the bare tool name.

Tools handled:
  submit_net_metering        — file an initial application
  check_net_metering_status  — look up status of an existing application
  get_interconnection_checklist — documentary requirements per DU

Tool schema is declared in lambda_schema (JSON file in the same directory).
"""
import json
import random
import string
from datetime import datetime


def _new_application_id() -> str:
    return "NM-" + "".join(
        random.choices(string.ascii_uppercase + string.digits, k=8)
    )


def lambda_handler(event, context):
    raw_tool = ""
    if context.client_context and context.client_context.custom:
        raw_tool = context.client_context.custom.get("bedrockAgentCoreToolName", "")

    tool = raw_tool.split("___", 1)[-1] if "___" in raw_tool else raw_tool
    # Local/test fallback: allow explicit tool field in event
    if not tool:
        tool = event.get("tool", "submit_net_metering")

    print(f"Tool called: {tool} | Event: {json.dumps(event)}")

    if tool == "submit_net_metering":
        app_id = _new_application_id()
        return {
            "statusCode": 200,
            "body": json.dumps({
                "application_id": app_id,
                "customer_id": event.get("customer_id"),
                "distribution_utility": event.get("distribution_utility", "Meralco"),
                "account_number": event.get("account_number"),
                "capacity_kwp": event.get("capacity_kwp", 0),
                "inverter_type": event.get("inverter_type", "hybrid"),
                "status": "FILED",
                "message": (
                    "Net-metering application filed. DU technical evaluation "
                    "typically takes 15-30 days; bi-directional meter installation "
                    "follows ERC compliance clearance."
                ),
                "created_at": datetime.utcnow().isoformat(),
            }),
        }

    if tool == "check_net_metering_status":
        return {
            "statusCode": 200,
            "body": json.dumps({
                "application_id": event.get("application_id"),
                "status": "PENDING_EVALUATION",
                "eta": "15-30 days",
            }),
        }

    if tool == "get_interconnection_checklist":
        du = event.get("distribution_utility", "Meralco")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "distribution_utility": du,
                "checklist": [
                    "Single-line diagram signed by PRC-licensed engineer",
                    "Inverter IEC/ERC compliance certificates with anti-islanding",
                    "Proof of ownership or authorization for premises",
                    "Latest DU electric bill and account number",
                    "ERC Certificate of Compliance application form",
                ],
            }),
        }

    return {
        "statusCode": 400,
        "body": json.dumps({"error": f"Unknown tool: {tool}"}),
    }
