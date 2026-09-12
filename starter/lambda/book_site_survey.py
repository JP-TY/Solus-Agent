"""
Solus Site Survey Lambda
========================
Schedules an ocular roof/electrical assessment for Philippine solar customers.
Invoked through the AgentCore Gateway (REST API proxy integration).

Routes exposed:
  POST /surveys                        — book a new site survey
  GET  /surveys/{survey_id}            — return a single survey by ID
  GET  /customers/{customer_id}/surveys — return all surveys for a customer

Deployment: zip this file and upload to an AWS Lambda function, then wire
the function to the AgentCore Gateway as an API Gateway REST proxy target.
"""
import json
import random
import string
from datetime import datetime


def _surveys():
    """Return mock survey database (fresh each invocation)."""
    return {
        "SRV-A1B2C3": {
            "survey_id": "SRV-A1B2C3",
            "customer_id": "CUST-123",
            "customer_name": "Jane Dela Cruz",
            "address": "123 Maginhawa St, Quezon City",
            "roof_material": "GI sheet",
            "preferred_date": "2026-10-05",
            "status": "SCHEDULED",
            "utility": "Meralco",
        },
    }


def _new_survey_id() -> str:
    return "SRV-" + "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")
    resource = event.get("resource", "")
    method = event.get("httpMethod", "GET")
    params = event.get("pathParameters") or {}
    print(f"Request: {method} {resource} {params}")

    surveys = _surveys()

    # POST /surveys — book a new survey
    if resource == "/surveys" and method == "POST":
        payload = {}
        try:
            raw_body = event.get("body")
            if isinstance(raw_body, dict):
                payload.update(raw_body)
            elif raw_body:
                parsed = json.loads(raw_body)
                if isinstance(parsed, dict):
                    payload.update(parsed)
        except (json.JSONDecodeError, AttributeError):
            pass
        qs = event.get("queryStringParameters") or {}
        payload.update({k: v for k, v in qs.items() if v is not None})
        # Gateway MCP callers may pass tool args as flat top-level fields
        for key in ("customer_id", "customer_name", "address", "roof_material",
                    "preferred_date", "utility"):
            if key in event and isinstance(event[key], (str, int, float)):
                payload.setdefault(key, event[key])
        survey_id = _new_survey_id()
        survey = {
            "survey_id": survey_id,
            "customer_id": payload.get("customer_id", "CUST-123"),
            "customer_name": payload.get("customer_name", "Valued Customer"),
            "address": payload.get("address", ""),
            "roof_material": payload.get("roof_material", "GI sheet"),
            "preferred_date": payload.get("preferred_date", ""),
            "utility": payload.get("utility", "Meralco"),
            "status": "SCHEDULED",
            "message": (
                "Site survey scheduled. Our engineer will assess roof structure, "
                "shading, electrical panel, and NSCP wind-load mounting requirements."
            ),
            "created_at": datetime.utcnow().isoformat(),
        }
        if not survey["address"] or not survey["preferred_date"]:
            return _response(400, {"error": "address and preferred_date are required"})
        return _response(200, survey)

    # GET /surveys/{survey_id}
    if resource == "/surveys/{survey_id}" and method == "GET":
        sid = (params.get("survey_id") or "").upper()
        survey = surveys.get(sid)
        if not survey:
            # Return a well-formed scheduled response for demo IDs
            if sid.startswith("SRV-"):
                return _response(200, {
                    "survey_id": sid,
                    "status": "SCHEDULED",
                    "message": "Survey found and scheduled.",
                })
            return _response(404, {"error": f"Survey {sid} not found"})
        return _response(200, survey)

    # GET /customers/{customer_id}/surveys
    if resource == "/customers/{customer_id}/surveys" and method == "GET":
        cid = (params.get("customer_id") or "").upper()
        result = [s for s in surveys.values() if s["customer_id"] == cid]
        if not result:
            return _response(200, {"customer_id": cid, "surveys": [], "status": "NONE_FOUND"})
        return _response(200, {"customer_id": cid, "surveys": result})

    return _response(400, {"error": "Unrecognised route", "resource": resource})
