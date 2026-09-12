"""Solus KB builder — Bedrock KB + S3 sync (two vector-store paths).

Path A (OSS, needs aoss:* — NOT granted in this sandbox, kept for portability):
  oss_policies, oss_collection, oss_index, kb_role, kb, datasource, sync
Path B (Pinecone, works here — needs PINECONE_API_KEY + PINECONE_HOST env):
  pinecone_secret, kb_role_pinecone, kb_pinecone, datasource, sync
Usage: .venv/bin/python infra/build_kb.py [step ...]
Resume via infra/outputs.json.
"""
import json
import sys
import time
from pathlib import Path

import boto3
import botocore.auth
import botocore.awsrequest
import requests

REGION = "us-east-1"
ACCOUNT = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
CALLER_ARN = boto3.client("sts", region_name=REGION).get_caller_identity()["Arn"]
# assumed-role/voclabs/<session> -> role/voclabs
ROLE_ARN = "arn:aws:iam::{}:role/{}".format(
    ACCOUNT, CALLER_ARN.split(":assumed-role/")[1].rsplit("/", 1)[0])
OUT = Path("infra/outputs.json")
KB_BUCKET = f"solus-kb-{ACCOUNT}"
COLL_NAME = "solus-kb"
INDEX_NAME = "solus-index"
TITAN_V2 = f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0"


def load_out():
    return json.loads(OUT.read_text())


def save_out(d):
    OUT.write_text(json.dumps(d, indent=2))
    print(json.dumps({k: v for k, v in d.items()
                      if k in ("kbId", "dataSourceId", "collectionId",
                               "collectionEndpoint", "kbRoleArn")}, indent=2))


def signed_put(url, body):
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    req = botocore.awsrequest.AWSRequest(method="PUT", url=url,
                                        data=json.dumps(body),
                                        headers={"Content-Type": "application/json"})
    botocore.auth.SigV4Auth(creds, "aoss", REGION).add_auth(req)
    prepped = req.prepare()
    return requests.put(prepped.url, data=prepped.body,
                        headers=dict(prepped.headers), timeout=60)


def step_oss_policies(out):
    if "ossPolicies" in out:
        return out
    oss = boto3.client("opensearchserverless", region_name=REGION)
    enc = {"Rules": [{"ResourceType": "collection",
                      "Resource": [f"collection/{COLL_NAME}*"]}],
           "AWSOwnedKey": True}
    net = [{"Rules": [{"ResourceType": "dashboard",
                       "Resource": [f"collection/{COLL_NAME}*"]},
                      {"ResourceType": "collection",
                       "Resource": [f"collection/{COLL_NAME}*"]}],
            "AllowFromPublic": True}]
    oss.create_security_policy(name=f"{COLL_NAME}-enc", type="encryption",
                               policy=json.dumps(enc))
    oss.create_security_policy(name=f"{COLL_NAME}-net", type="network",
                               policy=json.dumps(net))
    print("oss security policies ok")
    out["ossPolicies"] = True
    return out


def step_oss_collection(out):
    if "collectionId" in out:
        return out
    oss = boto3.client("opensearchserverless", region_name=REGION)
    kb_role = out.get("kbRoleArn", f"arn:aws:iam::{ACCOUNT}:role/solus-kb-role")
    access = [{"Rules": [{"Resource": [f"collection/{COLL_NAME}*",
                                        f"index/{COLL_NAME}*"],
                          "Permission": ["aoss:*"],
                          "ResourceType": ["collection", "index"]}],
               "Principal": [ROLE_ARN, kb_role]}]
    oss.create_access_policy(name=f"{COLL_NAME}-access", type="data",
                             policy=json.dumps(access))
    r = oss.create_collection(name=COLL_NAME, type="VECTORSEARCH")
    out["collectionId"] = r["createCollectionDetail"]["id"]
    out["collectionArn"] = r["createCollectionDetail"]["arn"]
    print("collection creating:", out["collectionId"])
    for i in range(40):
        c = oss.batch_get_collection(ids=[out["collectionId"]]
                                     )["collectionDetails"][0]
        print(i, c["status"])
        if c["status"] == "ACTIVE":
            out["collectionEndpoint"] = c["collectionEndpoint"]
            break
        time.sleep(15)
    return out


def step_oss_index(out):
    if "ossIndex" in out:
        return out
    mapping = {
        "settings": {"index.knn": True},
        "mappings": {"properties": {
            "vector": {"type": "knn_vector", "dimension": 1024,
                       "method": {"name": "hnsw", "engine": "faiss"}},
            "text": {"type": "text"},
            "metadata": {"type": "text", "index": False},
        }},
    }
    resp = signed_put(out["collectionEndpoint"] + f"/{INDEX_NAME}", mapping)
    print("index:", resp.status_code, resp.text[:300])
    assert resp.status_code in (200, 201), resp.text
    out["ossIndex"] = INDEX_NAME
    return out


def step_kb_role(out):
    if "kbRoleArn" in out:
        return out
    iam = boto3.client("iam", region_name=REGION)
    trust = {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Service": "bedrock.amazonaws.com"},
        "Action": "sts:AssumeRole"}]}
    try:
        r = iam.create_role(RoleName="solus-kb-role",
                            AssumeRolePolicyDocument=json.dumps(trust))
    except iam.exceptions.EntityAlreadyExistsException:
        r = iam.get_role(RoleName="solus-kb-role")
    coll_arn = out.get(
        "collectionArn", f"arn:aws:aoss:{REGION}:{ACCOUNT}:collection/*")
    index_arn = coll_arn.replace(":collection/", ":index/") \
        if ":collection/" in coll_arn and not coll_arn.endswith("/*") \
        else f"arn:aws:aoss:{REGION}:{ACCOUNT}:index/*/*"
    policy = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow",
         "Action": ["s3:GetObject", "s3:ListBucket"],
         "Resource": [f"arn:aws:s3:::{KB_BUCKET}",
                      f"arn:aws:s3:::{KB_BUCKET}/*"]},
        {"Effect": "Allow", "Action": ["bedrock:InvokeModel"],
         "Resource": [TITAN_V2]},
        {"Effect": "Allow", "Action": ["aoss:APIAccessAll"],
         "Resource": [coll_arn, index_arn]},
    ]}
    iam.put_role_policy(RoleName="solus-kb-role", PolicyName="solus-kb-access",
                        PolicyDocument=json.dumps(policy))
    out["kbRoleArn"] = r["Role"]["Arn"]
    time.sleep(10)
    return out


def step_kb(out):
    if "kbId" in out:
        return out
    agent = boto3.client("bedrock-agent", region_name=REGION)
    r = agent.create_knowledge_base(
        name="SolusKB",
        description="Solus solar catalog + PH net-metering reference",
        roleArn=out["kbRoleArn"],
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {"embeddingModelArn": TITAN_V2}},
        storageConfiguration={
            "type": "OPENSEARCH_SERVERLESS",
            "opensearchServerlessConfiguration": {
                "collectionArn": out["collectionArn"],
                "vectorIndexName": INDEX_NAME,
                "fieldMapping": {"vectorField": "vector",
                                 "textField": "text",
                                 "metadataField": "metadata"}}})
    out["kbId"] = r["knowledgeBase"]["knowledgeBaseId"]
    print("kb:", out["kbId"])
    return out


def step_datasource(out):
    if "dataSourceId" in out:
        return out
    agent = boto3.client("bedrock-agent", region_name=REGION)
    r = agent.create_data_source(
        knowledgeBaseId=out["kbId"], name="solus-catalog",
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {
                "bucketArn": f"arn:aws:s3:::{KB_BUCKET}",
                "inclusionPrefixes": ["product_catalog.txt"]}})
    out["dataSourceId"] = r["dataSource"]["dataSourceId"]
    print("datasource:", out["dataSourceId"])
    return out


def step_sync(out):
    agent = boto3.client("bedrock-agent", region_name=REGION)
    jobs = agent.list_ingestion_jobs(
        knowledgeBaseId=out["kbId"],
        dataSourceId=out["dataSourceId"])["ingestionJobSummaries"]
    running = [j for j in jobs if j["status"] in ("STARTING", "IN_PROGRESS")]
    if not running:
        r = agent.start_ingestion_job(
            knowledgeBaseId=out["kbId"], dataSourceId=out["dataSourceId"])
        jid = r["ingestionJob"]["ingestionJobId"]
        print("ingestion started:", jid)
    else:
        jid = running[0]["ingestionJobId"]
        print("ingestion already running:", jid)
    for i in range(60):
        j = agent.get_ingestion_job(
            knowledgeBaseId=out["kbId"], dataSourceId=out["dataSourceId"],
            ingestionJobId=jid)["ingestionJob"]
        print(i, j["status"])
        if j["status"] == "COMPLETE":
            out["kbSynced"] = True
            break
        assert j["status"] not in ("FAILED",), j
        time.sleep(20)
    return out


def step_pinecone_secret(out):
    if "pineconeSecretArn" in out:
        return out
    import os
    api_key = os.environ.get("PINECONE_API_KEY", "")
    assert api_key, "Set PINECONE_API_KEY env var"
    sm = boto3.client("secretsmanager", region_name=REGION)
    try:
        r = sm.create_secret(Name="solus-pinecone-key",
                             SecretString=json.dumps({"apiKey": api_key}))
    except sm.exceptions.ResourceExistsException:
        sm.put_secret_value(SecretId="solus-pinecone-key",
                            SecretString=json.dumps({"apiKey": api_key}))
        r = sm.describe_secret(SecretId="solus-pinecone-key")
    out["pineconeSecretArn"] = r["ARN"]
    print("secret:", out["pineconeSecretArn"])
    return out


def step_kb_role_pinecone(out):
    iam = boto3.client("iam", region_name=REGION)
    policy = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow",
         "Action": ["s3:GetObject", "s3:ListBucket"],
         "Resource": [f"arn:aws:s3:::{KB_BUCKET}",
                      f"arn:aws:s3:::{KB_BUCKET}/*"]},
        {"Effect": "Allow", "Action": ["bedrock:InvokeModel"],
         "Resource": [TITAN_V2]},
        {"Effect": "Allow", "Action": ["secretsmanager:GetSecretValue"],
         "Resource": [out["pineconeSecretArn"]]},
    ]}
    iam.put_role_policy(RoleName="solus-kb-role",
                        PolicyName="solus-kb-pinecone",
                        PolicyDocument=json.dumps(policy))
    out["kbRoleArn"] = f"arn:aws:iam::{ACCOUNT}:role/solus-kb-role"
    time.sleep(10)
    return out


def step_kb_pinecone(out):
    if "kbId" in out and out.get("kbStore") == "pinecone":
        return out
    import os
    host = os.environ.get("PINECONE_HOST", "")
    assert host, "Set PINECONE_HOST env var (index host URL)"
    agent = boto3.client("bedrock-agent", region_name=REGION)
    out.pop("kbId", None)
    out.pop("dataSourceId", None)
    out.pop("kbSynced", None)
    r = agent.create_knowledge_base(
        name="SolusKB",
        description="Solus solar catalog + PH net-metering reference (Pinecone)",
        roleArn=out["kbRoleArn"],
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {"embeddingModelArn": TITAN_V2}},
        storageConfiguration={
            "type": "PINECONE",
            "pineconeConfiguration": {
                "connectionString": host,
                "credentialsSecretArn": out["pineconeSecretArn"],
                "namespace": "solus",
                "fieldMapping": {"textField": "text",
                                 "metadataField": "metadata"}}})
    out["kbId"] = r["knowledgeBase"]["knowledgeBaseId"]
    out["kbStore"] = "pinecone"
    print("kb:", out["kbId"])
    return out


STEPS = {"oss_policies": step_oss_policies, "oss_collection": step_oss_collection,
         "oss_index": step_oss_index, "kb_role": step_kb_role, "kb": step_kb,
         "datasource": step_datasource, "sync": step_sync,
         "pinecone_secret": step_pinecone_secret,
         "kb_role_pinecone": step_kb_role_pinecone,
         "kb_pinecone": step_kb_pinecone}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(STEPS)
    out = load_out()
    for name in wanted:
        print(f"===== step: {name} =====")
        out = STEPS[name](out)
        save_out(out)
    print("DONE")
