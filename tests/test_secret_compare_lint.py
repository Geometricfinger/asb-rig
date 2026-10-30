"""M-04 lint: secrets, MACs, tags, hashes, signatures, fingerprints, nonces and passphrases are
never compared with == / != (timing side channel); use security.ct.equal / hmac.compare_digest."""
import ast, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "oiris"
SECRETY = re.compile(r"(secret|passphrase|password|master|mac|tag|digest|hmac|sig(nature)?|fingerprint|(^|_)fp$|"
                     r"nonce|token|(^|_)key$|subkey|priv|h_this|h_prev|(^|_)head$|wrapped)", re.I)
# names that look secret-ish but hold public, non-secret values
PUBLIC = re.compile(r"(^|_)(len|n|count|kind|type|mode|name|status|state|version|v|scope|level|purpose)$", re.I)


def _name(n: ast.AST) -> str | None:
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        return n.attr
    if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str):
        return n.slice.value
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("digest", "hexdigest"):
        return "digest"
    return None


def _secret(n: ast.AST) -> bool:
    nm = _name(n)
    return bool(nm and SECRETY.search(nm) and not PUBLIC.search(nm))


def _public_literal(n: ast.AST) -> bool:
    return isinstance(n, ast.Constant) and (n.value is None or isinstance(n.value, (bool, int, float)))


def violations(src: str, path: str = "<src>") -> list[str]:
    out = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Compare):
            continue
        sides = [node.left, *node.comparators]
        for op, a, b in zip(node.ops, sides, sides[1:]):
            if not isinstance(op, (ast.Eq, ast.NotEq)):
                continue
            if (_secret(a) or _secret(b)) and not (_public_literal(a) or _public_literal(b)):
                out.append(f"{path}:{node.lineno}: {ast.unparse(node)}")
    return out


def test_lint_catches_bad_comparisons():
    assert violations("ok = tag == expected_tag")
    assert violations("if mac != other: pass")
    assert violations("x = hmac.new(k, m, sha256).digest() == h")
    assert violations("ok = d['fingerprint'] == peer")
    assert violations("ok = self.master == key")


def test_lint_allows_safe_forms():
    assert not violations("ok = hmac.compare_digest(tag, expected_tag)")
    assert not violations("ok = key is None")
    assert not violations("ok = len(key) == 32")
    assert not violations("ok = key_len == 32")
    assert not violations("ok = token == None")


def test_no_secret_compared_with_equality_in_oiris():
    bad = []
    for p in sorted(ROOT.rglob("*.py")):
        bad += violations(p.read_text(encoding="utf-8"), str(p.relative_to(ROOT.parent)))
    assert not bad, "secret compared with ==/!= (use security.ct.equal):\n" + "\n".join(bad)
