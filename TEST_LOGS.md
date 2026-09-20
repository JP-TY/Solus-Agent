# Solus Test Conversation Logs — 6 Rubric Scenarios (live `agentcore invoke` output)

Runtime: `arn:aws:bedrock-agentcore:us-east-1:054833633679:runtime/solus_agent-1T5PxV97sE`
Gateway: `https://solusgateway-sgoy2fibvf.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp` (6 tools, NONE auth)
Memory: `SolusMemory-KdpcFR4z07` (solar_facts + solar_preferences, ACTIVE)

## Test 1 — Order tracking (live `agentcore invoke`) ✅
Command:
```bash
agentcore invoke '{"prompt": "Hi, can you track my order ORD-001? I want to know its status and tracking number.", "customer_id": "CUST-123", "session_id": "t1-live"}'
```
Response (exit 0, new `track_order` agent tool calling the `order_tracker` Lambda in-process):
```
Your order ORD-001 has been SHIPPED. Here are the details:
- Items: 1x Wireless Headphones Pro | Total: $89.99
- Carrier: UPS | Tracking Number: TRK987654321
- Estimated Delivery: 2026-09-22
```
Proves: the deployed agent answers an `agentcore invoke` order-tracking prompt with live tool data and no errors. Screenshot: `screenshots/test1_order_tracking.png`. (Offline pytest coverage: `test_order_get_by_id`, `test_order_customer_orders`, `test_order_not_found`.)

## Test 2 — Refund processing (live `agentcore invoke`) ✅
Command:
```bash
agentcore invoke '{"prompt": "Hi, I would like a refund for order ORD-002, $139.99, because it arrived damaged.", "customer_id": "CUST-123", "session_id": "t2-live"}'
```
Response (exit 0, new `process_refund` agent tool calling the `refund_processor` Lambda in-process):
```
Refund Processed Successfully!
- Order ID: ORD-002 | Refund Amount: $139.99
- Status: Approved (REF-ST2U6QEC)
- Credit Timeline: 3-5 business days
```
Proves: the deployed agent answers an `agentcore invoke` refund prompt with live tool data and no errors; the refund tool schema is declared in `lambda_schema`. Screenshot: `screenshots/test2_refund_processing.png`. (Offline pytest coverage: `test_refund_initiate`, `test_refund_status_and_label`, `test_lambda_schema_valid`.)

## Extra A — Site-survey booking (live Gateway demo, solar adaptation) ✅
Command:
```bash
agentcore invoke '{"prompt": "Hi, I am Maria from Quezon City. Please book an ocular site survey for my GI sheet roof on 2026-10-05. My address is 123 Maginhawa St.", "customer_id": "CUST-123", "session_id": "t1"}'
```
Response (exit 0):
```
Perfect! Your site survey has been successfully booked, Maria. Here are the details:

**Site Survey Confirmation:**
- **Survey ID:** SRV-4QR6BT
- **Date:** October 5, 2026
- **Location:** 123 Maginhawa St., Quezon City
- **Roof Type:** GI (Galvanized Iron) sheet
- **Utility:** Meralco
- **Status:** SCHEDULED ✅
```
Proves: MCPClient API-proxy tool returns well-formed JSON; agent also recalled the PHP 8,500 bill from memory.

## Extra B — Net-metering filing (live Gateway demo, solar adaptation) ✅
Command:
```bash
agentcore invoke '{"prompt": "I want to file a net-metering application with Meralco. My account number is 1234567890 and I want a 5.5 kWp hybrid system.", "customer_id": "CUST-123", "session_id": "t2"}'
```
Response (exit 0):
```
✅ Your net-metering application has been successfully filed with Meralco!
- **Application ID:** NM-J502EZZM
- **Capacity:** 5.5 kWp (hybrid inverter)
- **Status:** FILED
- Technical evaluation: 15-30 days; bi-directional meter after ERC clearance
```
Proves: second distinct Gateway-backed tool (direct Lambda invocation), well-formed response.

## Test 3 — Knowledge Base (RAG) ✅ grounded retrieval (re-run on current deployment)
Command:
```bash
agentcore invoke '{"prompt": "Use search_knowledge_base once to find the 550W panel specs and ERC export credit rule, then answer briefly with no other tools.", "customer_id": "CUST-123", "session_id": "t3-live2"}'
```
Response (exit 0) — grounded in `SolusKB` (`EG5YRCZGER`, Pinecone-backed) via the Retrieve API:
```
- Solus-550M: 550W, 21.3% efficiency, 25-year power warranty, typhoon-rated 280+ km/h
- Deye SUN-5K-SG04LP3 hybrid inverter for the 5.5 kWp system
- Self-consumption: full retail rate (PHP 11-13/kWh Meralco)
- Exported surplus: avoided generation cost (PHP 5-7/kWh), NOT retail
- 5.12 kWh LiFePO4 SOLUS-WALL-5K for brownout backup
```
Proves: `search_knowledge_base` calls Retrieve, joins chunks, returns grounded catalog text (the tool also carries the KB_ID guard clause: empty/missing KB_ID returns a descriptive configuration message). Note: this sandbox denies all AWS-native KB stores (`aoss:*`, `es:*`, `s3vectors:*`, `rds:*` per IAM simulation), so the KB runs on Pinecone serverless (free tier, us-east-1, 1024-dim cosine) — same Retrieve API and rubric code path.

## Test 4 — Long-term memory, two sessions (same customer) ✅ (re-run on current deployment)
Profile stored across earlier sessions under `CUST-123` (name, utility, bill, roof, backup priority, concise preference). Recall session:
```bash
agentcore invoke '{"prompt": "Do you remember my name, utility, bill, roof type, and backup priority? And my communication preference?", "customer_id": "CUST-123", "session_id": "mem-B-live"}'
```
Response (exit 0):
```
Your Name: Maria (also known as Jane) | Utility: Meralco | Monthly Bill: PHP 8,500 (~425 kWh)
Roof Type: GI sheet, facing south | Backup Priority: 5.12 kWh LiFePO4 top priority
Communication Preference: concise responses
Also recalled: NM-J502EZZM filing + Oct 5 survey booking
```
Proves: cross-session recall via `retrieve_customer_context` + `create_event` (name variant comes from earlier sessions under the same customer ID). Note: a fresh-ID probe the same day returned no stored facts — expected, since extraction only stores what prior sessions actually saved.

## Test 5 — Code Interpreter calculation ✅ (re-run on current deployment)
Command:
```bash
agentcore invoke '{"prompt": "I am a Gold member with 4250 points. My Meralco usage is about 425 kWh per month. Calculate my discount on a $150 order and size my solar system with payback.", "customer_id": "CUST-123", "session_id": "t5-live"}'
```
Response (exit 0): Final Price **$99.00**, Total Savings **$51.00**, Remaining **349 points** (4000 redeemed + 99 earned), tier 10% — all matching the sandbox-executed code. Plus solar sizing/payback (4.47 yrs) from the same `executeCode` run. Proves: real `code_session(REGION).invoke("executeCode", …, clearContext=True)` path with all four required fields.

## Test 6 — Browser tool ✅ (re-run on current deployment)
Command:
```bash
agentcore invoke '{"prompt": "Go to https://company.meralco.com.ph/news-and-advisories/rates-archives and tell me the latest generation charge or page title you find.", "customer_id": "CUST-123", "session_id": "t6-live"}'
```
Response (exit 0): live page title **"Rates Archives"** retrieved from the Meralco site via `AgentCoreBrowser`, plus the "Generation" section and September 2026 rates. Proves live web retrieval.

## Evidence screenshots

- Test 1 (order tracking): ![T1](screenshots/test1_order_tracking.png)
- Test 2 (refund processing): ![T2](screenshots/test2_refund_processing.png)
- Test 3 (knowledge base RAG): ![T3](screenshots/test3_knowledge_base.png)
- Test 4 (memory, two sessions): ![T4](screenshots/test4_memory.png)
- Test 5 (code interpreter): ![T5](screenshots/test5_code_interpreter.png)
- Test 6 (browser): ![T6](screenshots/test6_browser.png)
- Extra A (live survey booking): ![XA](screenshots/gateway_survey_booking.png)
- Extra B (live net-metering filing): ![XB](screenshots/gateway_net_metering.png)
- Offline pytest (13 passed): ![pytest](screenshots/test_results.png)
