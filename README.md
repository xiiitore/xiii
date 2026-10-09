# Verification Controller (MCP connector)

A small MCP service for bounded arithmetic checks and a local claim ledger.

## Run locally

Set a long, random token before starting the service:

```bash
export MCP_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m pip install -r requirements.txt
python server.py
```

The default bind address is `127.0.0.1`; the service is not exposed to the network by default. The MCP endpoint is `http://127.0.0.1:8000/mcp`. Send the token in the HTTP header `Authorization: Bearer <token>`; it is not part of tool arguments. Never commit the token, and rotate it immediately if exposed.

For a remote deployment, configure a trusted TLS-terminating reverse proxy and explicitly set `ALLOW_REMOTE_BIND=1` and `TRUSTED_TLS_TERMINATION=1` before binding to a non-loopback address. These flags are operator acknowledgements, not proof that TLS is configured correctly. Verify the proxy, restrict direct access to the app port, and do not send credentials over untrusted plaintext HTTP. This shared-token gate is not per-user identity or role-based authorization.

If `MCP_API_TOKEN` is missing, the server refuses to start. Requests to `/mcp` without exactly one valid Bearer token are rejected at the HTTP boundary with status 401. Duplicate and malformed Authorization headers are rejected.

## Data integrity and evaluator limits

- Expressions are length-, AST-size-, nesting-, exponent-, integer-size-, and finite-result-limited.
- Invalid or unreadable existing ledger files fail closed without returning raw filesystem/decoder details.
- Writes use a temporary file, flush/fsync, atomic replacement, and directory fsync.
- Ledger operations are serialized across cooperating POSIX processes with an advisory lock file. The lock must reside on a local filesystem with reliable `flock` semantics; network filesystems and non-POSIX systems are outside the supported concurrency boundary.
- The JSON ledger is still a small local store, not a distributed database. For production multi-worker use, prefer a transactional database with backups and tested restore procedures. Back up both ledger data and deployment configuration securely; test restoration before relying on it.
- Token rotation requires updating the injected secret and restarting/redeploying the service. Use a secret manager or protected environment injection; never put secrets in source control or logs.
- Define an incident procedure for token exposure: revoke/rotate the token, review access logs, preserve relevant audit records, and validate the service configuration before restoring access.
- Evidence fields are audit text, not cryptographic proof. A state transition records evidence text; it does not independently establish that a claim is true.

## Tests

```bash
python -m unittest -v
```

The test suite covers arithmetic, disallowed expressions, resource bounds, non-finite inputs, state transitions, corrupt-ledger handling, atomic persistence, authentication at the MCP ASGI route, and concurrent writers across processes.
