"""Bounded arithmetic evaluation and a durable claim ledger.

The local JSON ledger uses POSIX advisory file locking to prevent lost updates
across cooperating processes. Use a local filesystem; network filesystems and
non-POSIX platforms are outside the supported concurrency boundary.
"""
import ast
import json
import math
import operator
import os
import tempfile
import threading
import time
import uuid

from ledger_lock import locked_ledger

MAX_EXPRESSION_LENGTH = 512
MAX_AST_NODES = 64
MAX_AST_DEPTH = 16
MAX_INTEGER_BITS = 256
MAX_ABS_EXPONENT = 100
MAX_ABS_BASE_FOR_POWER = 1_000_000

OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
FUNCS = {n: getattr(math, n) for n in (
    "sqrt", "log", "log10", "exp", "sin", "cos", "tan", "floor", "ceil"
)}
FUNCS.update(abs=abs, round=round, min=min, max=max)
CONSTS = {"pi": math.pi, "e": math.e}
_LEDGER_LOCK = threading.RLock()


def safe_eval(expr: str) -> float:
    """Evaluate a small arithmetic expression with AST and resource limits."""
    if not isinstance(expr, str):
        raise TypeError("izraz mora biti tekst")
    if not expr.strip() or len(expr) > MAX_EXPRESSION_LENGTH:
        raise ValueError("izraz je prazan ili prelazi dopuštenu duljinu")
    try:
        tree = ast.parse(expr, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ValueError("neispravan matematički izraz") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise ValueError("izraz ima previše AST čvorova")

    def ev(node, depth=0):
        if depth > MAX_AST_DEPTH:
            raise ValueError("izraz je previše ugniježđen")
        if isinstance(node, ast.Expression):
            value = ev(node.body, depth + 1)
        elif isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if isinstance(node.value, int) and node.value.bit_length() > MAX_INTEGER_BITS:
                raise ValueError("numerički literal je prevelik")
            value = node.value
        elif isinstance(node, ast.Name) and node.id in CONSTS:
            value = CONSTS[node.id]
        elif isinstance(node, ast.BinOp) and type(node.op) in OPS:
            left = ev(node.left, depth + 1)
            right = ev(node.right, depth + 1)
            if isinstance(node.op, ast.Pow):
                if abs(right) > MAX_ABS_EXPONENT:
                    raise ValueError("eksponent prevelik")
                if abs(left) > MAX_ABS_BASE_FOR_POWER and right > 1:
                    raise ValueError("baza potenciranja prevelika")
            value = OPS[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            value = OPS[type(node.op)](ev(node.operand, depth + 1))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS and not node.keywords:
            value = FUNCS[node.func.id](*[ev(arg, depth + 1) for arg in node.args])
        else:
            raise ValueError("nedozvoljen izraz")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("rezultat nije broj")
        if isinstance(value, int) and value.bit_length() > MAX_INTEGER_BITS:
            raise ValueError("rezultat je prevelik")
        if not math.isfinite(value):
            raise ValueError("rezultat nije konačan broj")
        return value

    try:
        return ev(tree)
    except (ArithmeticError, OverflowError) as exc:
        raise ValueError("aritmetički izračun nije uspio") from exc


def check_number(expr, claimed, rel_tol=1e-6):
    if isinstance(claimed, bool) or not isinstance(claimed, (int, float)) or not math.isfinite(claimed):
        raise ValueError("claimed rezultat mora biti konačan broj")
    if isinstance(rel_tol, bool) or not isinstance(rel_tol, (int, float)) or not math.isfinite(rel_tol) or rel_tol < 0 or rel_tol > 1:
        raise ValueError("relativna tolerancija mora biti konačan broj u rasponu [0, 1]")
    actual = safe_eval(expr)
    ok = math.isclose(actual, claimed, rel_tol=rel_tol, abs_tol=1e-9)
    return {"expression": expr, "claimed": claimed, "recomputed": actual,
            "match": ok, "abs_diff": abs(actual - claimed)}


ORDER = ["EXECUTED", "VALID", "VERIFIED", "ACCEPTED"]
PATH = os.environ.get("LEDGER_PATH", "ledger.json")


def _load():
    """Missing ledger means empty; corruption or I/O errors fail closed."""
    try:
        with open(PATH, encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        # Do not echo filesystem paths or raw decoder details to callers.
        raise RuntimeError("ledger cannot be read safely") from None
    if not isinstance(data, dict):
        raise RuntimeError("ledger format is invalid")
    return data


def _save(data):
    directory = os.path.dirname(os.path.abspath(PATH))
    fd, temporary = tempfile.mkstemp(prefix=".ledger-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, PATH)
        # Persist the directory entry where supported by the local filesystem.
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        try:
            if os.path.exists(temporary):
                os.unlink(temporary)
        except OSError:
            pass


@locked_ledger(lambda: PATH)
def register(claim, source_tool=""):
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("claim mora biti neprazan tekst")
    if not isinstance(source_tool, str):
        raise TypeError("source_tool mora biti tekst")
    with _LEDGER_LOCK:
        data = _load()
        cid = uuid.uuid4().hex
        item = {"id": cid, "claim": claim, "source_tool": source_tool,
                "state": "EXECUTED",
                "history": [{"state": "EXECUTED", "evidence": "", "t": time.time()}]}
        data[cid] = item
        _save(data)
        return item


@locked_ledger(lambda: PATH)
def advance(cid, new_state, evidence):
    if not isinstance(evidence, str):
        raise TypeError("evidence mora biti tekst")
    with _LEDGER_LOCK:
        data = _load()
        claim = data.get(cid)
        if not claim:
            return {"error": "nepoznat id"}
        if new_state == "REJECTED":
            if not evidence.strip():
                return {"error": "razlog odbacivanja je obavezan"}
        else:
            if new_state not in ORDER:
                return {"error": f"stanje mora biti jedno od {ORDER} ili REJECTED"}
            if claim["state"] == "REJECTED":
                return {"error": "odbačena tvrdnja se ne može unaprijediti"}
            if ORDER.index(new_state) != ORDER.index(claim["state"]) + 1:
                return {"error": f"preskakanje nije dopušteno: {claim['state']} -> {new_state}"}
            if not evidence.strip():
                return {"error": "dokaz (evidence) je obavezan"}
        claim["state"] = new_state
        claim["history"].append({"state": new_state, "evidence": evidence, "t": time.time()})
        _save(data)
        return claim


@locked_ledger(lambda: PATH)
def get(cid):
    with _LEDGER_LOCK:
        return _load().get(cid, {"error": "nepoznat id"})


@locked_ledger(lambda: PATH)
def listing():
    with _LEDGER_LOCK:
        return [{"id": item["id"], "claim": item["claim"], "state": item["state"]}
                for item in _load().values()]
