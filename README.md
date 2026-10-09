# Verification Controller (MCP connector)

A small MCP service for bounded arithmetic checks and a local claim ledger.

## Run locally

Set a long, random token before starting the service:

```bash
export MCP_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m pip install -r requirements.txt
python server.py
```

The MCP endpoint is `http://localhost:8000/mcp`. Each tool call requires the same token in its `access_token` argument. Use HTTPS in any remote deployment; do not put the token in source control, public prompts, logs, or screenshots. Rotate it immediately if exposed. This shared-token mechanism is a basic gate, not per-user identity, role-based authorization, or a substitute for network restrictions. Prefer a private network or a trusted reverse proxy with transport-level authentication for deployed services.

If `MCP_API_TOKEN` is missing, the server refuses to start. Unauthorized calls are rejected.

## Data integrity and evaluator limits

- Expressions are length-, AST-size-, nesting-, exponent-, integer-size-, and finite-result-limited.
- Invalid or unreadable existing ledger files fail closed; they are never silently treated as an empty ledger.
- Writes use a temporary file plus atomic replacement. A process-local lock serializes threads in one process.
- The JSON ledger is still a single-process local store. It is not safe for multiple server processes sharing one file, and persistence depends on the deployment's mounted storage. Use a transactional database for multi-worker or production use.
- Evidence fields are audit text, not cryptographic proof. A state transition records a claim about evidence; it does not independently establish that the claim is true.

## Tests

```bash
python -m unittest -v
```

The test suite covers arithmetic, disallowed expressions, resource bounds, non-finite inputs, state transitions, corrupt-ledger handling, and atomic persistence.
