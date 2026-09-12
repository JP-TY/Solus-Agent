"""Solus infra builder — 100% CLI/API, no console needed.

Steps: role, restapi, gateway, targets, memory, oss, kb, sync, patch
Usage: .venv/bin/python infra/build_cli.py [step ...]  (default: run all, resume via infra/outputs.json)
"""
import gzip
import json
import sys
import time
from pathlib import Path

import boto3
import botocore

REGION = "us-east-1"
ACCOUNT = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
OUT = Path("infra/outputs.json")
SURVEY_ARN = f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:solus-book-site-survey"
NM_ARN = f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:solus-submit-net-metering"
KB_BUCKET = f"solus-kb-{ACCOUNT}"
TITAN_V2 = f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0"


def load_out():
    return json.loads(OUT.read_text()) if OUT.exists() else {}


def save_out(d):
    OUT.write_text(json.dumps(d, indent=2))
    print(f"[outputs] {json.dumps(d, indent=2)}")


def step_role(out):
    if "gatewayRoleArn" in out:
        return out
    iam = boto3.client("iam", region_name=REGION)
    trust = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }
    try:
        r = iam.create_role(RoleName="solus-gateway-exec",
                            AssumeRolePolicyDocument=json.dumps(trust))
        print("created gateway role")
    except iam.exceptions.EntityAlreadyExistsException:
        r = iam.get_role(RoleName="solus-gateway-exec")
        print("gateway role exists")
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": ["lambda:InvokeFunction"],
             "Resource": [SURVEY_ARN, NM_ARN]},
            {"Effect": "Allow", "Action": ["apigateway:GET", "apigateway:HEAD"],
             "Resource": "*"},
            {"Effect": "Allow",
             "Action": ["logs:CreateLogGroup", "logs:CreateLogStream",
                        "logs:PutLogEvents"],
             "Resource": "*"},
        ],
    }
    try:
        iam.put_role_policy(RoleName="solus-gateway-exec",
                            PolicyName="solus-gateway-access",
                            PolicyDocument=json.dumps(policy))
    except Exception as e:
        print("put_role_policy:", e)
    out["gatewayRoleArn"] = r["Role"]["Arn"]
    time.sleep(10)  # IAM propagation
    return out


def openapi_spec():
    invoke_uri = (f"arn:aws:apigateway:{REGION}:lambda:path/2015-03-31"
                  f"/functions/{SURVEY_ARN}/invocations")
    def integration():
        return {"x-amazon-apigateway-integration": {
            "uri": invoke_uri, "httpMethod": "POST",
            "type": "aws_proxy", "passthroughBehavior": "when_no_match"}}
    return {
        "openapi": "3.0.1",
        "info": {"title": "SolusSurveyAPI", "version": "1"},
        "paths": {
            "/surveys": {
                "post": {"operationId": "book_survey",
                         "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}},
                         "responses": {"200": {"description": "OK"}},
                         **integration()}},
            "/surveys/{survey_id}": {
                "get": {"operationId": "get_survey",
                        "parameters": [{"name": "survey_id", "in": "path",
                                        "required": True, "schema": {"type": "string"}}],
                        "responses": {"200": {"description": "OK"}},
                        **integration()}},
            "/customers/{customer_id}/surveys": {
                "get": {"operationId": "get_customer_surveys",
                        "parameters": [{"name": "customer_id", "in": "path",
                                        "required": True, "schema": {"type": "string"}}],
                        "responses": {"200": {"description": "OK"}},
                        **integration()}},
        },
    }


def step_restapi(out):
    if "restApiId" in out:
        return out
    agw = boto3.client("apigateway", region_name=REGION)
    spec = json.dumps(openapi_spec()).encode()
    try:
        r = agw.import_rest_api(body=spec, failOnWarnings=False)
    except Exception as e:
        print("import_rest_api failed:", e)
        raise
    api_id = r["id"]
    lam = boto3.client("lambda", region_name=REGION)
    try:
        lam.add_permission(
            FunctionName="solus-book-site-survey", StatementId="apigw-proxy",
            Action="lambda:InvokeFunction", Principal="apigateway.amazonaws.com",
            SourceArn=f"arn:aws:execute-api:{REGION}:{ACCOUNT}:{api_id}/*/*/*")
    except lam.exceptions.ResourceConflictException:
        pass
    agw.create_deployment(restApiId=api_id, stageName="prod")
    out["restApiId"] = api_id
    out["restApiStage"] = "prod"
    print("REST API:", api_id)
    return out


def step_gateway(out):
    if "gatewayId" in out:
        return out
    ctl = boto3.client("bedrock-agentcore-control", region_name=REGION)
    r = ctl.create_gateway(name="SolusGateway",
                           description="Solus solar Gateway (NONE auth, class project)",
                           roleArn=out["gatewayRoleArn"],
                           protocolType="MCP",
                           authorizerType="NONE")
    out["gatewayId"] = r["gatewayId"]
    out["gatewayUrl"] = r.get("gatewayUrl", "")
    print("gateway:", r["gatewayId"], out["gatewayUrl"])
    return out


def step_targets(out):
    if "surveyTargetId" in out and "nmTargetId" in out:
        return out
    ctl = boto3.client("bedrock-agentcore-control", region_name=REGION)
    gid = out["gatewayId"]
    if "surveyTargetId" not in out:
        filters = [
            {"filterPath": "/surveys", "methods": ["POST"]},
            {"filterPath": "/surveys/*", "methods": ["GET"]},
            {"filterPath": "/customers/*", "methods": ["GET"]},
        ]
        api_gw_cfg = {
            "restApiId": out["restApiId"],
            "stage": out["restApiStage"],
            "apiGatewayToolConfiguration": {"toolFilters": filters},
        }
        target_cfg = {"mcp": {"apiGateway": api_gw_cfg}}
        r = ctl.create_gateway_target(
            gatewayIdentifier=gid, name="survey-api",
            description="Site survey REST API (API Gateway target)",
            targetConfiguration=target_cfg,
        )
        out["surveyTargetId"] = r["targetId"]
        print("survey target:", r["targetId"])
    if "nmTargetId" not in out:
        schema = json.loads(Path("starter/lambda/lambda_schema").read_text())
        nm_lambda_cfg = {
            "lambdaArn": NM_ARN,
            "toolSchema": {"inlinePayload": schema},
        }
        nm_target_cfg = {"mcp": {"lambda": nm_lambda_cfg}}
        nm_creds = [{"credentialProviderType": "GATEWAY_IAM_ROLE"}]
        r = ctl.create_gateway_target(
            gatewayIdentifier=gid, name="net-metering",
            description="Net-metering Lambda (direct invocation target)",
            targetConfiguration=nm_target_cfg,
            credentialProviderConfigurations=nm_creds)
        out["nmTargetId"] = r["targetId"]
        print("nm target:", r["targetId"])
    return out


def step_memory(out):
    if "memoryId" in out:
        return out
    ctl = boto3.client("bedrock-agentcore-control", region_name=REGION)
    r = ctl.create_memory(
        name="SolusMemory",
        description="Solus solar customer memory",
        eventExpiryDuration=365,
        memoryStrategies=[
            {"semanticMemoryStrategy": {
                "name": "solar_facts",
                "description": "Solar customer facts",
                "namespaceTemplates": ["cs_agent/{actorId}/facts"]}},
            {"userPreferenceMemoryStrategy": {
                "name": "solar_preferences",
                "description": "Solar customer preferences",
                "namespaceTemplates": ["cs_agent/{actorId}/preferences"]}},
        ])
    out["memoryId"] = r.get("memoryId") or r.get("memory", {}).get("id")
    print("memory:", out["memoryId"])
    return out


STEPS = {"role": step_role, "restapi": step_restapi, "gateway": step_gateway,
         "targets": step_targets, "memory": step_memory}


if __name__ == "__main__":
    wanted = sys.argv[1:] or list(STEPS)
    out = load_out()
    for name in wanted:
        print(f"===== step: {name} =====")
        try:
            out = STEPS[name](out)
        except KeyError:
            print(f"unknown step {name}, skipping")
        save_out(out)
    print("DONE")
