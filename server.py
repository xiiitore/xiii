import hmac
import os

from mcp.server.fastmcp import FastMCP
import core

mcp = FastMCP(
    "verification-controller",
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
)
_API_TOKEN = os.environ.get("MCP_API_TOKEN", "")


def _authorize(access_token: str) -> None:
    if not _API_TOKEN:
        raise RuntimeError("MCP_API_TOKEN nije konfiguriran; servis je zatvoren")
    if not isinstance(access_token, str) or not hmac.compare_digest(access_token, _API_TOKEN):
        raise PermissionError("neautoriziran zahtjev")


@mcp.tool()
def recompute_check(expression: str, claimed_result: float, rel_tolerance: float = 1e-6,
                    access_token: str = "") -> dict:
    """Neovisno preračunaj izraz. Potreban je MCP_API_TOKEN."""
    _authorize(access_token)
    try:
        return core.check_number(expression, claimed_result, rel_tolerance)
    except (ValueError, TypeError, ArithmeticError) as exc:
        return {"error": str(exc)}


@mcp.tool()
def register_claim(claim: str, source_tool: str = "", access_token: str = "") -> dict:
    """Upiši tvrdnju u ledger. Potreban je MCP_API_TOKEN."""
    _authorize(access_token)
    return core.register(claim, source_tool)


@mcp.tool()
def advance_claim(claim_id: str, new_state: str, evidence: str = "",
                  access_token: str = "") -> dict:
    """Promijeni stanje tvrdnje za jedan korak uz obavezni dokazni zapis."""
    _authorize(access_token)
    return core.advance(claim_id, new_state, evidence)


@mcp.tool()
def get_claim(claim_id: str, access_token: str = "") -> dict:
    """Vrati stanje i povijest tvrdnje. Potreban je MCP_API_TOKEN."""
    _authorize(access_token)
    return core.get(claim_id)


@mcp.tool()
def list_claims(access_token: str = "") -> list:
    """Vrati popis tvrdnji. Potreban je MCP_API_TOKEN."""
    _authorize(access_token)
    return core.listing()


if __name__ == "__main__":
    if not _API_TOKEN:
        raise SystemExit("Postavi MCP_API_TOKEN prije pokretanja; servis se neće pokrenuti otvoren.")
    mcp.run(transport="streamable-http")
