import ast
from pathlib import Path

def test_frontend_proxy_has_get_post_put_delete_handlers():
    source = Path("frontend/server.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = {
                item.name: item for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if "do_GET" in methods and "do_POST" in methods:
                matches.append(methods)

    assert len(matches) == 1
    assert "do_PUT" in matches[0]
    assert "do_DELETE" in matches[0]
    put_source = ast.get_source_segment(source, matches[0]["do_PUT"])
    assert put_source is not None
    assert "PUT" in put_source
    delete_source = ast.get_source_segment(source, matches[0]["do_DELETE"])
    assert delete_source is not None
    assert "DELETE" in delete_source
