import unittest
from unittest.mock import patch

import server


class BearerAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_or_invalid_token_is_rejected_at_http_boundary(self):
        async def app(scope, receive, send):
            raise AssertionError("unauthorized request reached MCP app")

        middleware = server.BearerAuthMiddleware(app, server._token_is_valid)
        sent = []

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "path": "/mcp",
            "headers": [(b"authorization", b"Bearer wrong")],
        }
        with patch.object(server, "_API_TOKEN", "expected-secret"):
            await middleware(scope, None, send)
        self.assertEqual(sent[0]["status"], 401)
        self.assertIn((b"www-authenticate", b"Bearer"), sent[0]["headers"])

    async def test_valid_token_reaches_mcp_app(self):
        reached = []

        async def app(scope, receive, send):
            reached.append(True)

        middleware = server.BearerAuthMiddleware(app, server._token_is_valid)
        async def send(message):
            raise AssertionError("valid request should be handled by app")

        scope = {
            "type": "http",
            "path": "/mcp",
            "headers": [(b"authorization", b"Bearer expected-secret")],
        }
        with patch.object(server, "_API_TOKEN", "expected-secret"):
            await middleware(scope, None, send)
        self.assertEqual(reached, [True])

    async def test_missing_config_rejects_even_if_header_is_present(self):
        scope = {
            "type": "http",
            "path": "/mcp",
            "headers": [(b"authorization", b"Bearer expected-secret")],
        }
        with patch.object(server, "_API_TOKEN", ""):
            self.assertFalse(server._token_is_valid(scope))


if __name__ == "__main__":
    unittest.main()
