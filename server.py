""""MCP server with HTTP Bearer-token authentication at the transport boundary."""
import hmac
import json
import os

import uvicorn
from mcp.server.fastmcp import FastMCP

import core

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 8000))
_API_TOKEN = os.environ.get("MCP_API_TOKEN", "")

mcp = FastMCP(
    "verification-controller",
    stateless_http=True,
    json_response=True,
    host=HOST,
    port=PORT,
)


def _token_is_valid(scope) -> bool:
    """Validate exactly one Authorization: Bearer header without exposing secrets."""
    if not _API_TOKEN:
        return False
    authorization_values = [
        value for name, value in scope.get("headers", [])
        if name.lower() == b"authorization"
    ]
    # Ambiguous duplicate credentials are rejected rather than choosing one.
    if len(authorization_values) != 1:
        return False
    try:
        supplied = authorization_values[0].decode("latin-1")
    except (AttributeError, UnicodeDecodeError):
        return False
    scheme, separator, credential = supplied.partition(" ")
    if not separator or scheme.lower() != "bearer" or not credential:
        return False
    return hmac.compare_digest(credential, _API_TOKEN)


class BearerAuthMiddleware:
    """Small ASGI middleware protecting the MCP HTTP endpoint."""

    def __init__(self, app, token_is_valid):
        self.app = app
        self.token_is_valid = token_is_valid

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            if not self.token_is_valid(scope):
                body = json.dumps({"error": "unauthorized"}).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode("ascii")),
                        (b"www-authenticate", b"Bearer"),
                        (b"cache-control", b"no-store"),
                    ],
                })
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


@mcp.tool()
def recompute_check(expression: str, claimed_result: float, rel_tolerance: float = 1e-6) -> dict:
    """Recompute a bounded mathematical expression and compare it with a claim."""
    try:
        return core.check_number(expression, claimed_result, rel_tolerance)
    except (ValueError, TypeError, ArithmeticError) as exc:
        return {"error": str(exc)}


@mcp.tool()
def register_claim(claim: str, source_tool: str = "") -> dict:
    """Record a claim in the ledger with initial state EXECUTED."""
    return core.register(claim, source_tool)


@mcp.tool()
def advance_claim(claim_id: str, new_state: str, evidence: str = "") -> dict:
    """Advance a claim one state at a time or reject it with a reason."""
    return core.advance(claim_id, new_state, evidence)


@mcp.tool()
def get_claim(claim_id: str) -> dict:
    """Return the current state and history of one claim."""
    return core.get(claim_id)


@mcp.tool()
def list_claims() -> list:
    """List claim IDs, text, and current states."""
    return core.listing()


if __name__ == "__main__":
    if not _API_TOKEN:
        raise SystemExit("Set MCP_API_TOKEN before starting; refusing to run without authentication.")
    app = BearerAuthMiddleware(mcp.streamable_http_app(), _token_is_valid)
    uvicorn.run(app, host=HOST, port=PORT)
