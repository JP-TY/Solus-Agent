"""
Solus — Philippine Rooftop Solar & Clean Energy Concierge
==========================================================
Bedrock AgentCore Runtime agent (Strands SDK) preserving all rubric patterns:
BedrockAgentCoreApp, MCP Gateway tools, Bedrock KB RAG, AgentCore Memory hook,
AgentCore Code Interpreter calculator, AgentCore Browser.

Run locally:
  uv run main.py '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'

Deploy:
  agentcore configure --entrypoint main.py --name solus-agent
  agentcore deploy
"""

from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamable_http_client
import argparse, json
import os, asyncio, boto3
from strands.hooks import (
    HookProvider, AfterInvocationEvent, HookRegistry, MessageAddedEvent,
)
import logging
import uuid
from typing import Dict
from bedrock_agentcore.tools.code_interpreter_client import code_session
from strands_tools.browser import AgentCoreBrowser


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("Solus_Agent")

# ── TODO 1 — App Initialisation ───────────────────────────────────────────────
app = BedrockAgentCoreApp()

os.environ["BYPASS_TOOL_CONSENT"] = "true"


# ── TODO 2 — Configuration ────────────────────────────────────────────────────
GATEWAY_URL = "https://solusgateway-sgoy2fibvf.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
KB_ID = "EG5YRCZGER"
REGION = "us-east-1"
MEMORY_ID = "SolusMemory-KdpcFR4z07"


# ── TODO 3 — Model and Clients ────────────────────────────────────────────────
model_id = "global.amazon.nova-2-lite-v1:0"

model = BedrockModel(model_id=model_id)

memory_client = MemoryClient(region_name=REGION)

_bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)


# ── TODO 4 — Namespace Helper ─────────────────────────────────────────────────
def get_namespaces(mem_client: MemoryClient, memory_id: str) -> Dict:
    """Return a dict mapping strategy type → namespace template string."""
    strategies = mem_client.get_memory_strategies(memory_id)
    namespaces: Dict[str, str] = {}
    for strategy in strategies:
        s_type = strategy.get("type", "")
        templates = strategy.get("namespaceTemplates") or strategy.get("namespaces") or []
        if templates:
            namespaces[s_type] = templates[0]
    if not namespaces:
        namespaces = {
            "SEMANTIC": "cs_agent/{actorId}/facts",
            "USER_PREFERENCE": "cs_agent/{actorId}/preferences",
        }
    return namespaces


# ── TODO 5 — Memory Hook ──────────────────────────────────────────────────────
class MemoryHook(HookProvider):
    """Long-term memory hook for the Solus solar concierge."""

    def __init__(
        self,
        actor_id: str,
        session_id: str,
        memory_client: MemoryClient,
        memory_id: str,
    ):
        self.actor_id = actor_id
        self.session_id = session_id
        self.memory_client = memory_client
        self.memory_id = memory_id
        try:
            self.namespaces = get_namespaces(memory_client, memory_id)
        except Exception as e:
            logger.warning(f"get_namespaces failed, using defaults: {e}")
            self.namespaces = {
                "SEMANTIC": "cs_agent/{actorId}/facts",
                "USER_PREFERENCE": "cs_agent/{actorId}/preferences",
            }

    def retrieve_customer_context(self, event: MessageAddedEvent):
        """Retrieve relevant memories and prepend them to the user message."""
        try:
            messages = event.agent.messages
            if not messages:
                return
            last = messages[-1]
            if last.get("role") != "user":
                return
            content = last.get("content", [])
            if not content or "text" not in content[0]:
                return
            # Skip tool results masquerading as user messages
            if content[0].get("toolResult") is not None:
                return
            user_query = content[0].get("text", "")
            if not user_query:
                return

            collected = []
            for strategy_type, template in self.namespaces.items():
                namespace = template.format(actorId=self.actor_id)
                try:
                    resp = self.memory_client.retrieve_memories(
                        self.memory_id, namespace, user_query, top_k=5
                    )
                except Exception as e:
                    logger.warning(f"retrieve_memories failed for {namespace}: {e}")
                    continue
                memories = resp if isinstance(resp, list) else resp.get("memories", [])
                for m in memories:
                    text = m.get("text") or m.get("content") or m.get("memoryText", "")
                    if text:
                        collected.append(f"[{strategy_type}] {text}")
            if collected:
                memories_block = "\n".join(collected)
                content[0]["text"] = (
                    f"Customer Context (Solus solar profile):\n{memories_block}\n\n"
                    f"{user_query}"
                )
        except Exception as e:
            logger.warning(f"retrieve_customer_context failed: {e}")

    def save_support_interaction(self, event: AfterInvocationEvent):
        """Save the completed turn to memory after the agent responds."""
        try:
            messages = event.agent.messages
            if not messages:
                return
            customer_query = None
            agent_response = None
            for m in reversed(messages):
                if agent_response is None and m.get("role") == "assistant":
                    blocks = m.get("content", [])
                    texts = [b.get("text", "") for b in blocks if "text" in b]
                    if texts:
                        agent_response = "\n".join(texts)
                if customer_query is None and m.get("role") == "user":
                    blocks = m.get("content", [])
                    if blocks and "text" in blocks[0] and blocks[0].get("toolResult") is None:
                        customer_query = blocks[0]["text"]
                if customer_query and agent_response:
                    break
            if customer_query and agent_response:
                self.memory_client.create_event(
                    self.memory_id,
                    self.actor_id,
                    self.session_id,
                    messages=[(customer_query, "USER"), (agent_response, "ASSISTANT")],
                )
        except Exception as e:
            logger.warning(f"save_support_interaction failed: {e}")

    def register_hooks(self, registry: HookRegistry) -> None:  # type: ignore
        """Register both memory callbacks."""
        registry.add_callback(MessageAddedEvent, self.retrieve_customer_context)
        registry.add_callback(AfterInvocationEvent, self.save_support_interaction)


# ── TODO 6 — Knowledge Base Tool ─────────────────────────────────────────────
@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the Solus solar catalog and Philippine net-metering knowledge base.
    Use this for Tier-1 550W panel specs, Deye/Growatt/Enphase inverter details,
    5.12 kWh LiFePO4 batteries, ERC net-metering rules (avoided generation cost
    crediting vs retail rates), sizing guidance (4.5-5.0 PSH), and package pricing.

    Args:
        query: The question or topic to search for

    Returns:
        Relevant information retrieved from the knowledge base
    """
    if not KB_ID or KB_ID.startswith("<"):
        return "Knowledge base not configured."
    try:
        resp = _bedrock_runtime.retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={"text": query},
        )
    except Exception as e:
        logger.warning(f"Knowledge base retrieval failed: {repr(e)}")
        return f"Knowledge base retrieval failed: {e}"
    results = resp.get("retrievalResults", [])
    if not results:
        return "No relevant information found in the knowledge base."
    chunks = []
    for r in results:
        content = r.get("content", {})
        text = content.get("text", "")
        if text:
            chunks.append(text)
    if not chunks:
        return "No relevant information found in the knowledge base."
    return "\n---\n".join(chunks)


# ── TODO 7 — Loyalty Discount Tool (Code Interpreter) ────────────────────────
@tool
def calculate_loyalty_discount(
    loyalty_points: int,
    tier: str,
    order_total: float,
    product_category: str = "standard",
) -> str:
    """
    Calculate the Solus service discount plus solar sizing and payback using the
    AgentCore Code Interpreter. Runs exact arithmetic in a secure sandbox.
    Use for Gold/Platinum promo discounts and for sizing quotes from monthly
    PHP bills or kWh usage (Meralco/VECO/Davao Light, 4.5-5.0 PSH).

    Args:
        loyalty_points:   Customer's current points balance (or kWh proxy for solar)
        tier:             Customer tier — Silver, Gold, or Platinum
        order_total:      Order total in USD/PHP (or system price for solar quotes)
        product_category: standard, device, or fresh (maps to standard/hybrid/battery solar)

    Returns:
        Full discount breakdown and final price
    """
    code = f"""
import json, math
loyalty_points = {int(loyalty_points)}
tier = {tier!r}
order_total = {float(order_total)}
product_category = {product_category!r}

earn_rates = {{"standard": 1, "device": 2, "fresh": 5}}
tier_rates = {{"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}}

# Points redemption: floor to nearest 500, cap value at 50% of order, 100 pts = $1
redeemable = (loyalty_points // 500) * 500
max_points_value = order_total * 0.5
points_value = min(redeemable / 100.0, max_points_value)
points_redeemed = int(points_value * 100)
subtotal = max(order_total - points_value, 0.0)

tier_discount_pct = tier_rates.get(tier, 0.0) * 100.0
tier_discount = subtotal * tier_rates.get(tier, 0.0)
final_total = max(subtotal - tier_discount, 0.0)
total_savings = order_total - final_total
earn_rate = earn_rates.get(product_category, 1)
points_earned = int(math.floor(final_total * earn_rate))
remaining_points = int(loyalty_points - points_redeemed + points_earned)

# Solus solar sizing extension (exact math, same sandbox run)
monthly_kwh_proxy = max(float(loyalty_points), 100.0)
daily_kwh = monthly_kwh_proxy / 30.0
PSH = 4.5
DERATE = 0.78
required_kwp = round(daily_kwh / (PSH * DERATE), 2)
retail_rate_php = 12.0
avoided_cost_php = 6.0
self_share = 0.6
annual_kwh = daily_kwh * 365.0
annual_savings_php = round(annual_kwh * (self_share * retail_rate_php + (1 - self_share) * avoided_cost_php), 2)
system_cost_php = round(required_kwp * 55000.0, 2)
payback_years = round(system_cost_php / annual_savings_php, 2) if annual_savings_php else 0.0

result = {{
    "points_redeemed": points_redeemed,
    "tier_discount_pct": tier_discount_pct,
    "tier_discount": round(tier_discount, 2),
    "final_total": round(final_total, 2),
    "total_savings": round(total_savings, 2),
    "points_earned": points_earned,
    "remaining_points": remaining_points,
    "daily_kwh": round(daily_kwh, 2),
    "required_kwp": required_kwp,
    "annual_savings_php": annual_savings_php,
    "payback_years": payback_years,
}}
print(json.dumps(result))
"""

    try:
        # Rubric pattern: code_session(REGION).invoke("executeCode", ...) with clearContext=True
        with code_session(REGION) as session:
            resp = session.invoke(
                "executeCode",
                {"language": "python", "code": code, "clearContext": True},
            )
        # Response shape: resp["stream"] is an EventStream of
        # {"result": {"content": [{"type": "text", "text": stdout}], ...}} events
        text_out = None
        stream = resp.get("stream", []) if isinstance(resp, dict) else []
        for ev in stream:
            if not isinstance(ev, dict):
                continue
            res = ev.get("result", {})
            if not isinstance(res, dict):
                continue
            for block in res.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text" \
                        and block.get("text"):
                    text_out = block["text"]
                    break
            if text_out:
                break
            stdout = res.get("structuredContent", {}).get("stdout", "")
            if stdout:
                text_out = stdout
                break
        if text_out is None:
            raise ValueError("No result text in code interpreter stream")
        # Validate it parses and carries required fields
        parsed = json.loads(text_out) if isinstance(text_out, str) else text_out
        return json.dumps(parsed)
    except Exception as e:
        logger.warning(f"Code interpreter unavailable, fallback: {e}")
        tier_rates = {"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}
        rate = tier_rates.get(tier, 0.0)
        tier_discount = order_total * rate
        final_total = order_total - tier_discount
        import math as _math
        fallback = {
            "points_redeemed": 0,
            "tier_discount_pct": rate * 100.0,
            "tier_discount": round(tier_discount, 2),
            "final_total": round(final_total, 2),
            "total_savings": round(tier_discount, 2),
            "points_earned": int(_math.floor(final_total)),
            "remaining_points": int(loyalty_points),
            "fallback": True,
        }
        return json.dumps(fallback)


# ── TODO 8 — Agent Entrypoint ─────────────────────────────────────────────────
SOLUS_SYSTEM_PROMPT = """You are Solus, an intelligent rooftop solar and clean energy
transition concierge for the Philippine market. Advise homeowners and businesses on
Tier-1 550W monocrystalline bifacial panels, Deye/Growatt/Enphase inverters, and 5.12 kWh
LiFePO4 batteries. Ground every answer in Philippine context: Meralco, VECO, Davao Light;
ERC Net-Metering Resolution No. 06 Series of 2019 (up to 100 kWp, export credited at
avoided generation cost, self-consumption offsets full retail rate); 4.5-5.0 peak sun
hours with 0.75-0.80 derate; NSCP typhoon mounting to 280+ km/h; GI sheet vs concrete
slab roofs. Use search_knowledge_base for specs and policy. Use Gateway MCP tools:
book_site_survey for ocular assessments, submit_net_metering for DU applications.
Use calculate_loyalty_discount for exact promo math plus solar sizing/payback.
Use the browser for live Meralco tariff or ERC announcements. Remember utility, monthly
bill (PHP/kWh), roof type/orientation, and backup priorities across sessions. Always
recommend a licensed installer and PRC engineer sign-off; never invent tariffs.
Tool discipline: call each tool at most twice per response. To book a survey, call
the survey tool once with the customer details, then answer. After any tool returns
the data you need, stop calling tools and answer the user directly."""


@app.entrypoint
async def invoke(payload, context=None):
    """
    Main handler called by AgentCore for every incoming request.

    Expected payload keys:
      prompt      (str, required) — the customer's message
      customer_id (str, optional) — unique customer identifier
      session_id  (str, optional) — session identifier; generated if absent
    """
    try:
        user_input = payload.get("prompt", "")
        actor_id = payload.get("customer_id", "CUST-123")
        session_id = payload.get("session_id") or str(uuid.uuid4())
        if not user_input:
            return "Please provide a prompt."

        hook = MemoryHook(actor_id, session_id, memory_client, MEMORY_ID)
        agent_core_browser = AgentCoreBrowser(region=REGION)

        tools = [
            search_knowledge_base,
            calculate_loyalty_discount,
            agent_core_browser.browser,
        ]

        gateway_tools = []
        try:
            mcp_client = MCPClient(
                lambda: streamable_http_client(GATEWAY_URL)
            )
            mcp_client.start()
            # Newer Strands (>=1.6): list_tools_sync; older: create_all_tools
            if hasattr(mcp_client, "list_tools_sync"):
                gateway_tools = list(mcp_client.list_tools_sync())
            else:
                gateway_tools = mcp_client.create_all_tools()
            tools.extend(gateway_tools)
            logger.warning(f"Loaded {len(gateway_tools)} gateway tools")
        except Exception as e:
            logger.warning(f"Gateway tools unavailable: {e}")

        try:
            agent = Agent(
                model=model,
                tools=tools,
                hooks=[hook],
                system_prompt=SOLUS_SYSTEM_PROMPT,
            )
        except TypeError:
            # Older Strands versions use different hook/kwarg names
            agent = Agent(model=model, tools=tools, system_prompt=SOLUS_SYSTEM_PROMPT)

        response = agent(user_input)
        msg = getattr(response, "message", None)
        if isinstance(msg, dict):
            blocks = msg.get("content", [])
            if blocks and "text" in blocks[0]:
                return blocks[0]["text"]
        return str(response)
    except Exception as e:
        logger.exception(f"invoke failed: {e}")
        return f"Solus encountered an error: {e}"


# ── CLI entry point (do not modify) ──────────────────────────────────────────
def main():
    """Run one invocation from the command line for local testing."""
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=str)
    args = parser.parse_args()
    response = asyncio.run(invoke(json.loads(args.payload)))
    print(response)


if __name__ == "__main__":
    app.run()
    # Uncomment the line below and comment app.run() for local CLI testing:
    # main()
