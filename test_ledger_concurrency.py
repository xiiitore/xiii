"""Regression test proving concurrent processes do not lose ledger updates."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CrossProcessLedgerTests(unittest.TestCase):
    def test_concurrent_registers_are_not_lost(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = str(Path(directory) / "ledger.json")
            env = os.environ.copy()
            env["LEDGER_PATH"] = ledger
            script = (
                "import core; "
                "[core.register(f'claim-{i}', 'multiprocess-test') for i in range(20)]"
            )
            workers = [
                subprocess.Popen([sys.executable, "-c", script], env=env)
                for _ in range(6)
            ]
            for worker in workers:
                self.assertEqual(worker.wait(timeout=30), 0)
            with open(ledger, encoding="utf-8") as stream:
                data = json.load(stream)
            self.assertEqual(len(data), 120)
            self.assertEqual(len({item["id"] for item in data.values()}), 120)


if __name__ == "__main__":
    unittest.main()
