import json
import math
import os
import tempfile
import unittest
from unittest.mock import patch

import core


class SafeEvalTests(unittest.TestCase):
    def test_arithmetic_and_functions(self):
        self.assertEqual(core.safe_eval("2 + 3 * 4"), 14)
        self.assertAlmostEqual(core.safe_eval("sqrt(9) + pi"), 3 + math.pi)

    def test_rejects_code_and_unknown_names(self):
        for expression in ("__import__('os')", "x + 1", "open('x')", "2 ** 1000"):
            with self.subTest(expression=expression), self.assertRaises((ValueError, TypeError)):
                core.safe_eval(expression)

    def test_rejects_long_or_complex_expression(self):
        with self.assertRaises(ValueError):
            core.safe_eval("1" * (core.MAX_EXPRESSION_LENGTH + 1))
        with self.assertRaises(ValueError):
            core.safe_eval("+".join(["1"] * 80))

    def test_rejects_non_finite_results(self):
        for expression in ("1e309", "exp(10000)", "1 / 0"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                core.safe_eval(expression)

    def test_claim_and_tolerance_validation(self):
        for claimed in (True, float("nan"), float("inf"), "2"):
            with self.subTest(claimed=claimed), self.assertRaises(ValueError):
                core.check_number("2", claimed)
        for tolerance in (-1, float("nan"), 2):
            with self.subTest(tolerance=tolerance), self.assertRaises(ValueError):
                core.check_number("2", 2, tolerance)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "ledger.json")
        self.patch = patch.object(core, "PATH", self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_register_and_sequential_transitions(self):
        item = core.register("2 + 2 = 4", "unit-test")
        self.assertEqual(item["state"], "EXECUTED")
        self.assertIn("error", core.advance(item["id"], "VERIFIED", "evidence"))
        self.assertEqual(core.advance(item["id"], "VALID", "calculation")["state"], "VALID")
        self.assertEqual(core.advance(item["id"], "VERIFIED", "independent check")["state"], "VERIFIED")
        self.assertEqual(core.advance(item["id"], "ACCEPTED", "review")["state"], "ACCEPTED")
        self.assertEqual(core.get(item["id"])["state"], "ACCEPTED")

    def test_rejection_requires_reason_and_is_terminal(self):
        item = core.register("claim")
        self.assertIn("error", core.advance(item["id"], "REJECTED", ""))
        core.advance(item["id"], "REJECTED", "contradictory evidence")
        self.assertIn("error", core.advance(item["id"], "VALID", "retry"))

    def test_corrupt_ledger_fails_closed_without_detail_leak(self):
        with open(self.path, "w", encoding="utf-8") as stream:
            stream.write("{broken")
        with self.assertRaisesRegex(RuntimeError, "^ledger cannot be read safely$"):
            core.listing()

    def test_save_is_valid_json_and_lock_file_is_created(self):
        core.register("persist")
        with open(self.path, encoding="utf-8") as stream:
            self.assertIsInstance(json.load(stream), dict)
        self.assertEqual(set(os.listdir(self.temp.name)), {"ledger.json", "ledger.json.lock"})


if __name__ == "__main__":
    unittest.main()
