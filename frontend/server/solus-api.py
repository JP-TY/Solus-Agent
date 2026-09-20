"""
Solus API bridge (stdlib http.server, no framework).

Serves the built frontend (../dist) and two JSON routes:
  GET  /api/health
  POST /api/solus/invocations  {prompt, customer_id, session_id} -> {text}

Auth model: the browser never holds AWS credentials. This server invokes the
deployed AgentCore runtime through the project's own sanctioned path
(bedrock_agentcore_starter_toolkit invoke_bedrock_agentcore, the same code the
`agentcore invoke` CLI uses) with ambient server credentials.

Callers may attach `Authorization: Bearer <Cognito ID token>`; when
COGNITO_USER_POOL_ID + COGNITO_CLIENT_ID are set, the token is verified
against the pool JWKS (RS256, PyJWT) before invoking. When unset (local dev),
requests are accepted on loopback only and the customer id comes from the
request body.

Env: AWS_REGION (default us-east-1), SOLUS_RUNTIME_ARN, PORT (default 8787),
     COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID (optional, enables JWT check).
"""

import json
import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import jwt

DIR = Path(__file__).resolve().parent
DIST = DIR / ".." / "dist"
PORT = int(os.environ.get("PORT", "8787"))
REGION = os.environ.get("AWS_REGION", "us-east-1")
RUNTIME_ARN = os.environ.get(
    "SOLUS_RUNTIME_ARN",
    "arn:aws:bedrock-agentcore:us-east-1:054833633679:runtime/solus_agent-1T5PxV97sE",
)
POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")

_jwks_client = None


def get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        from jwt import PyJWKClient

        _jwks_client = PyJWKClient(
            f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}/.well-known/jwks.json"
        )
    return _jwks_client


def verify_cognito_jwt(token):
    """Verify a Cognito ID token, or accept dev-local requests when unconfigured."""
    if not POOL_ID or not CLIENT_ID:
        return {"sub": "dev-local", "email": None}
    key = get_jwks_client().get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        key.key,
        algorithms=["RS256"],
        issuer=f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}",
        audience=CLIENT_ID,
    )
    return {"sub": payload.get("sub"), "email": payload.get("email")}


def invoke_agent(prompt, customer_id, session_id):
    """Invoke via the same sanctioned path as `agentcore invoke`."""
    from bedrock_agentcore_starter_toolkit.operations.runtime.invoke import (
        invoke_bedrock_agentcore,
    )

    result = invoke_bedrock_agentcore(
        config_path=Path.cwd().parent / ".bedrock_agentcore.yaml",
        payload={"prompt": prompt, "customer_id": customer_id},
        session_id=session_id,
    )
    content = result.response
    if isinstance(content, dict) and "response" in content:
        content = content["response"]
    if isinstance(content, list):
        content = "".join(
            c.decode("utf-8", errors="replace") if isinstance(c, bytes) else str(c)
            for c in content
        )
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "response" in parsed:
                content = parsed["response"]
            elif isinstance(parsed, str):
                content = parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return str(content)


MIME = {".js": "text/javascript", ".css": "text/css", ".html": "text/html"}


class Handler(BaseHTTPRequestHandler):
    server_version = "SolusBridge/1.0"

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/health":
            self._json(200, {"ok": True, "auth": "cognito" if POOL_ID else "dev-local"})
            return
        if self.path.startswith("/api/"):
            self._json(404, {"error": "unknown api route"})
            return
        target = (DIST / self.path.lstrip("/").split("?")[0]).resolve()
        if not str(target).startswith(str(DIST.resolve())):
            self.send_response(403)
            self.end_headers()
            return
        if self.path in ("/", ""):
            target = DIST / "index.html"
        if not target.is_file():
            target = DIST / "index.html"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/api/solus/invocations":
            self._json(404, {"error": "unknown api route"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, OSError) as e:
            self._json(400, {"error": f"bad request: {e}"})
            return
        prompt = str(body.get("prompt") or "")
        if not prompt:
            self._json(400, {"error": "prompt is required"})
            return
        auth = self.headers.get("Authorization", "").removeprefix("Bearer").strip()
        try:
            user = verify_cognito_jwt(auth) if auth else {"sub": "dev-local", "email": None}
        except Exception as e:
            self._json(401, {"error": f"invalid token: {e}"})
            return
        try:
            session_id = str(body.get("session_id") or "")
            if len(session_id) < 33:
                session_id = f"web-{int(time.time())}-{session_id}"[:64].ljust(33, "0")
            text = invoke_agent(
                prompt,
                str(body.get("customer_id") or user["sub"] or "CUST-123"),
                session_id,
            )
        except Exception as e:
            self._json(502, {"error": f"runtime invoke failed: {e}"})
            return
        self._json(200, {"text": text, "user": user.get("email") or user.get("sub")})


if __name__ == "__main__":
    os.chdir(DIR.parent)
    print(
        f"solus-api on 127.0.0.1:{PORT} (auth={'cognito' if POOL_ID else 'dev-local'})",
        flush=True,
    )
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
