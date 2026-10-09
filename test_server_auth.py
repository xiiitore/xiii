import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

import server


class ServerAuthTests(unittest.TestCase):
    def setUp(self):
        self.token_patch = patch.object(server, "_API_TOKEN", "test-secret")
        self.token_patch.start()
        self.app = server.BearerAuthMiddleware(
            server.mcp.streamable_http_app(), server._token_is_valid
        )
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.token_patch.stop()

    def test_real_mcp_route_rejects_missing_and_wrong_credentials(self):
        self.assertEqual(self.client.post("/mcp", json={}).status_code, 401)
        self.assertEqual(
            self.client.post("/mcp", json={}, headers={"Authorization": "Bearer wrong"}).status_code,
            401,
        )

    def test_real_mcp_route_accepts_authentication_before_protocol_validation(self):
        response = self.client.post(
            "/mcp",
            json={},
            headers={"Authorization": "Bearer test-secret"},
        )
        self.assertNotEqual(response.status_code, 401)

    def test_duplicate_and_malformed_authorization_headers_are_rejected(self):
        cases = [
            [(b"authorization", b"Bearer test-secret"),
             (b"authorization", b"Bearer test-secret")],
            [(b"authorization", b"Basic test-secret")],
            [(b"authorization", b"Bearer")],
            [(b"authorization", b"Bearer test-secret ")],
        ]
        for headers in cases:
            with self.subTest(headers=headers):
                self.assertFalse(server._token_is_valid({"headers": headers}))

    def test_bearer_scheme_is_case_insensitive(self):
        self.assertTrue(server._token_is_valid({
            "headers": [(b"authorization", b"bEaReR test-secret")]
        }))

    def test_wrong_path_is_not_mistaken_for_the_protected_mcp_route(self):
        response = self.client.post("/not-mcp", json={})
        self.assertEqual(response.status_code, 404)

    def test_remote_bind_requires_explicit_security_acknowledgements(self):
        with self.assertRaises(SystemExit):
            server.validate_deployment_config("0.0.0.0", {})
        self.assertTrue(server.validate_deployment_config(
            "0.0.0.0",
            {"ALLOW_REMOTE_BIND": "1", "TRUSTED_TLS_TERMINATION": "1"},
        ))
        self.assertTrue(server.validate_deployment_config("127.0.0.1", {}))


if __name__ == "__main__":
    unittest.main()
