# Solus-Agent

Solus is a Philippine rooftop-solar concierge built on **Amazon Bedrock AgentCore**.
It tracks orders, processes refunds, books ocular site surveys, files
net-metering applications, answers product questions from a knowledge base,
remembers customers across sessions, does loyalty + solar math in a sandboxed
code interpreter, and can browse the web for live Meralco rate info.

Runtime: `solus_agent` (us-east-1) · Model: Nova 2 Lite · SDK: Strands Agents

## Architecture

```
User ──▶ AgentCore Runtime (starter/main.py, Strands agent)
              ├──▶ MCP Gateway ──▶ REST API ──▶ book_site_survey / order_tracker (Lambda)
              │                 └─▶ direct invoke ──▶ submit_net_metering / refund_processor (Lambda)
              ├──▶ search_knowledge_base ──▶ Bedrock KB (Pinecone-backed Retrieve API)
              ├──▶ Memory hook ──▶ AgentCore Memory (retrieve_customer_context / save_support_interaction)
              ├──▶ calculate_loyalty_discount ──▶ Code Interpreter sandbox (executeCode)
              └──▶ AgentCoreBrowser ──▶ live web lookup
Frontend (Vite + React, CopilotKit UI, Amplify auth) ──▶ Runtime
```

## How it fits together

- `starter/main.py` — the AgentCore Runtime agent. Registers the MCP Gateway
  tools, a Bedrock knowledge-base search, an AgentCore Memory hook
  (`retrieve_customer_context` / `save_support_interaction`), a
  `calculate_loyalty_discount` code-interpreter tool that also sizes the solar
  system, and an `AgentCoreBrowser` tool.
- `starter/lambda/` — `book_site_survey` and `order_tracker` (behind REST API
  Gateway targets) and `submit_net_metering` / `refund_processor` (direct
  Lambda targets), plus the `lambda_schema` tool definitions.
- `starter/product_catalog.txt` — panel / inverter / battery catalog and
  ERC net-metering rules ingested into the knowledge base.
- `infra/` — helper scripts that built the Gateway, REST API, knowledge base
  and memory; `infra/outputs.json` records the deployed IDs.
- `terraform/modules/solus-lambdas` — Terraform module for the Lambdas.
- `frontend/` — Vite + React chat skeleton (CopilotKit UI, Amplify auth).
- `tests/` — offline pytest suite, no AWS calls needed.
- `TEST_LOGS.md` — full conversation logs for all 6 rubric scenarios.
- `reflection.md` — what I built, what broke, and what I'd change for production.
- `screenshots/` — terminal-output evidence images, one per test.

## Rubric coverage

| Requirement | Where it lives |
|---|---|
| Test 1 — Order tracking | `starter/lambda/order_tracker.py`, `tests/test_solus.py::test_order_*` |
| Test 2 — Refund processing | `starter/lambda/refund_processor.py` + `lambda_schema`, `test_refund_*` |
| Test 3 — Knowledge base (RAG) | `search_knowledge_base` in `starter/main.py`, `starter/product_catalog.txt` |
| Test 4 — Long-term memory | `MemoryHook` in `starter/main.py` (`retrieve_customer_context` / `save_support_interaction`) |
| Test 5 — Loyalty discount calc | `calculate_loyalty_discount` via Code Interpreter `executeCode` |
| Test 6 — Browser tool | `AgentCoreBrowser` in `starter/main.py` |
| Reflection (200–400 words) | `reflection.md` |

## Run it

Prerequisites: Python 3.13+, `uv`, AWS credentials with Bedrock AgentCore
access (only needed for live runs — the test suite runs fully offline).

```bash
# offline tests (no AWS needed)
.venv/bin/python -m pytest tests/test_solus.py -v

# local agent
uv run starter/main.py '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'

# against the deployed runtime
agentcore invoke '{"prompt": "Hi, I am Maria from Quezon City. Book an ocular site survey for my GI sheet roof on 2026-10-05.", "customer_id": "CUST-123", "session_id": "t1"}'
```

## Test evidence

Offline suite: 13 passed — ![pytest](screenshots/test_results.png)

Runs (`TEST_LOGS.md`):

| # | Scenario | Screenshot |
|---|----------|------------|
| 1 | Order tracking (API-proxy Lambda) | ![T1](screenshots/test1_order_tracking.png) |
| 2 | Refund processing (Lambda target) | ![T2](screenshots/test2_refund_processing.png) |
| 3 | Knowledge-base RAG (550W specs + ERC rule) | ![T3](screenshots/test3_knowledge_base.png) |
| 4 | Long-term memory across two sessions | ![T4](screenshots/test4_memory.png) |
| 5 | Code-interpreter math (discount + sizing) | ![T5](screenshots/test5_code_interpreter.png) |
| 6 | Browser lookup (Meralco rates page) | ![T6](screenshots/test6_browser.png) |
| A | Extra live demo: site-survey booking | ![XA](screenshots/gateway_survey_booking.png) |
| B | Extra live demo: net-metering filing | ![XB](screenshots/gateway_net_metering.png) |

## Attribution & Honor Code

This submission is my own work. It builds on the Udacity project starter,
which was provided and approved for use in this project:

- `starter/lambda/order_tracker.py` and `starter/lambda/refund_processor.py`
  are adapted from the starter code (also noted in each file's header), as are
  the `initiate_refund` / `check_refund_status` / `get_return_label` entries in
  `starter/lambda/lambda_schema`.
- Everything else — the Solus solar adaptation (`book_site_survey`,
  `submit_net_metering`, `product_catalog.txt`), the agent in `starter/main.py`
  (Gateway wiring, knowledge-base search, memory hook, code-interpreter math,
  browser tool), the infrastructure scripts, Terraform module, frontend, test
  suite, logs, screenshots, reflection, and this README — is my own work
  written for this submission.

I affirm that I have read Udacity's definition of plagiarism, that this
submission is my own work, and that all content obtained from other sources is
attributed above.

### Learning resources & references

Beyond the starter code, the following documentation and public references were
consulted and integrated into the build (listed by where they were applied):

- **Strands Agents SDK docs** ([strandsagents.com](https://strandsagents.com/)) — agent construction, `@tool` authoring, the
  `MCPClient` + `HookProvider`/`register_hooks` pattern, and `AgentCoreBrowser`
  from `strands-tools` (all wired in `starter/main.py`).
- **Amazon Bedrock AgentCore docs** ([docs.aws.amazon.com/bedrock-agentcore](https://docs.aws.amazon.com/bedrock-agentcore/)) — `BedrockAgentCoreApp` runtime shape and
  `@app.entrypoint`, `MemoryClient` strategies/namespaces, Gateway targets and
  MCP tool routing via `bedrockAgentCoreToolName`, and the Code Interpreter
  `code_session(...).invoke("executeCode", ...)` call.
- **Model Context Protocol docs** ([modelcontextprotocol.io](https://modelcontextprotocol.io/), [Python SDK](https://github.com/modelcontextprotocol/python-sdk)) — `streamable_http_client` used
  to connect the Strands `MCPClient` to the Gateway URL.
- **Amazon Bedrock Knowledge Bases docs** ([knowledge-base user guide](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)) — S3 data source setup, Titan Embed
  Text v2 as the embedding model, the Retrieve API, and the Pinecone storage
  configuration (all automated in `infra/build_kb.py` after the native
  OpenSearch Serverless path was denied in this sandbox).
- **Pinecone docs** ([docs.pinecone.io](https://docs.pinecone.io/)) — serverless index model (1024-dim cosine) behind the
  Secrets Manager credential referenced in `infra/outputs.json`.
- **boto3 / botocore docs** ([boto3.amazonaws.com](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)) — STS identity resolution and the AgentCore control
  plane calls automated in `infra/build_cli.py` (roles, REST API, Gateway,
  targets, memory).
- **CopilotKit** ([docs.copilotkit.ai](https://docs.copilotkit.ai/)), **AWS Amplify** ([docs.amplify.aws](https://docs.amplify.aws/)), and **AWS SDK for JavaScript** ([API reference](https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/)) — chat UI,
  auth scaffolding, and the `bedrock-agentcore` client in `frontend/`.
- **Terraform AWS provider docs** ([registry.terraform.io](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)) — Lambda packaging and IAM in
  `terraform/modules/solus-lambdas`.
- **Public domain references** — ERC net-metering rules ([erc.gov.ph](https://www.erc.gov.ph/)), Meralco rate pages
  ([company.meralco.com.ph](https://company.meralco.com.ph/), retrieved live in Test 6), and vendor datasheets behind the panel/inverter
  figures in `starter/product_catalog.txt`.

## Teardown (stop idle spend)

After capturing evidence: destroy the runtime, Gateway, memory, REST API,
Lambdas and S3 bucket (the NONE-auth Gateway and broad demo roles are
class-only shortcuts — production needs Cognito/JWT auth, per-target
credentials and alarms on tool-error rates).
