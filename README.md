# Verification Controller (MCP connector)

A small MCP service for bounded arithmetic checks and a local claim ledger.

## Run locally

Set a long, random token before starting the service:

```bash
export MCP_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m pip install -r requirements.txt
python server.py
```

The MCP endpoint is `http://localhost:8000/mcp`. Send the token in the HTTP header `Authorization: Bearer <token>`; it is not part of tool arguments. Use HTTPS in any remote deployment, never commit the token, and rotate it immediately if exposed. Keep the service on a private network or behind a trusted reverse proxy. This shared-token gate is not per-user identity or role-based authorization.

If `MCP_API_TOKEN` is missing, the server refuses to start. Requests without a valid Bearer token are rejected at the HTTP boundary with status 401.

## Data integrity and evaluator limits

- Expressions are length-, AST-size-, nesting-, exponent-, integer-size-, and finite-result-limited.
- Invalid or unreadable existing ledger files fail closed; they are never silently treated as an empty ledger.
- Writes use a temporary file plus atomic replacement. A process-local lock serializes threads in one process.
- The JSON ledger is a single-process local store. It is not safe for multiple server processes sharing one file, and persistence depends on the deployment's mounted storage. Use a transactional database for multi-worker or production use.
- Evidence fields are audit text, not cryptographic proof. A state transition records evidence text; it does not independently establish that a claim is true.

## Tests

```bash
python -m unittest -v
```

The test suite covers arithmetic, disallowed expressions, resource bounds, non-finite inputs, state transitions, corrupt-ledger handling, and atomic persistence.
