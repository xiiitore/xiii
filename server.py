import os
from mcp.server.fastmcp import FastMCP
import core

mcp = FastMCP("verification-controller", stateless_http=True, json_response=True,
              host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

@mcp.tool()
def recompute_check(expression: str, claimed_result: float, rel_tolerance: float = 1e-6) -> dict:
    """Neovisno preračunaj matematički izraz (npr. '1200000/850000') i usporedi s tvrdnjom.
    Koristi prije nego što bilo koji broj proglasiš VERIFIED."""
    try: return core.check_number(expression, claimed_result, rel_tolerance)
    except Exception as e: return {"error": str(e)}

@mcp.tool()
def register_claim(claim: str, source_tool: str = "") -> dict:
    """Upiši tvrdnju/rezultat u evidenciju. Počinje u stanju EXECUTED."""
    return core.register(claim, source_tool)

@mcp.tool()
def advance_claim(claim_id: str, new_state: str, evidence: str = "") -> dict:
    """Unaprijedi tvrdnju točno jedan korak: EXECUTED->VALID->VERIFIED->ACCEPTED,
    ili odbaci s 'REJECTED'. Svaki korak traži dokaz u 'evidence'."""
    return core.advance(claim_id, new_state, evidence)

@mcp.tool()
def get_claim(claim_id: str) -> dict:
    """Vrati stanje i povijest jedne tvrdnje."""
    return core.get(claim_id)

@mcp.tool()
def list_claims() -> list:
    """Popis svih tvrdnji i njihovih stanja."""
    return core.listing()

if __name__ == "__main__":
    mcp.run(transport="streamable-http")   # endpoint: /mcp
