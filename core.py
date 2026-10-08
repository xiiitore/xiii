"""Logika bez vanjskih ovisnosti: sigurni izračun + evidencija tvrdnji (ledger)."""
import ast, json, math, operator, os, time, uuid

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
       ast.USub: operator.neg, ast.UAdd: operator.pos}
FUNCS = {n: getattr(math, n) for n in ("sqrt", "log", "log10", "exp", "sin", "cos", "tan", "floor", "ceil")}
FUNCS.update(abs=abs, round=round, min=min, max=max)
CONSTS = {"pi": math.pi, "e": math.e}

def safe_eval(expr: str) -> float:
    def ev(n):
        if isinstance(n, ast.Expression): return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
        if isinstance(n, ast.Name) and n.id in CONSTS: return CONSTS[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            r = ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(r) > 100: raise ValueError("eksponent prevelik")
            return OPS[type(n.op)](ev(n.left), r)
        if isinstance(n, ast.UnaryOp) and type(n.op) in OPS: return OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS and not n.keywords:
            return FUNCS[n.func.id](*[ev(a) for a in n.args])
        raise ValueError("nedozvoljen izraz")
    return ev(ast.parse(expr.strip(), mode="eval"))

def check_number(expr, claimed, rel_tol=1e-6):
    actual = safe_eval(expr)
    ok = math.isclose(actual, claimed, rel_tol=rel_tol, abs_tol=1e-9)
    return {"expression": expr, "claimed": claimed, "recomputed": actual, "match": ok,
            "abs_diff": abs(actual - claimed)}

ORDER = ["EXECUTED", "VALID", "VERIFIED", "ACCEPTED"]
PATH = os.environ.get("LEDGER_PATH", "ledger.json")

def _load():
    try:
        with open(PATH) as f: return json.load(f)
    except Exception: return {}

def _save(d):
    with open(PATH, "w") as f: json.dump(d, f, ensure_ascii=False, indent=1)

def register(claim, source_tool=""):
    d = _load(); cid = uuid.uuid4().hex[:8]
    d[cid] = {"id": cid, "claim": claim, "source_tool": source_tool, "state": "EXECUTED",
              "history": [{"state": "EXECUTED", "evidence": "", "t": time.time()}]}
    _save(d); return d[cid]

def advance(cid, new_state, evidence):
    d = _load(); c = d.get(cid)
    if not c: return {"error": "nepoznat id"}
    if new_state == "REJECTED":
        c["state"] = "REJECTED"
    else:
        if new_state not in ORDER: return {"error": f"stanje mora biti jedno od {ORDER} ili REJECTED"}
        if c["state"] == "REJECTED": return {"error": "odbačena tvrdnja se ne može unaprijediti"}
        if ORDER.index(new_state) != ORDER.index(c["state"]) + 1:
            return {"error": f"preskakanje nije dopušteno: {c['state']} -> {new_state}"}
        if not evidence.strip(): return {"error": "dokaz (evidence) je obavezan"}
        c["state"] = new_state
    c["history"].append({"state": c["state"], "evidence": evidence, "t": time.time()})
    d[cid] = c; _save(d); return c

def get(cid): return _load().get(cid, {"error": "nepoznat id"})
def listing(): return [{"id": c["id"], "claim": c["claim"], "state": c["state"]} for c in _load().values()]
