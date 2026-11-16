"""도메인 패키지끼리 서로 import 하지 않는지 검사한다."""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"
DOMAINS = sorted(
    p.name for p in APP.iterdir() if p.is_dir() and (p / "__init__.py").exists()
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text("utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


@pytest.mark.parametrize("package", DOMAINS)
def test_package_imports_only_core_and_itself(package: str) -> None:
    # core 는 어떤 도메인도 모르고, 도메인은 core 와 자기 자신만 안다.
    allowed = {"core", package}
    violations = [
        f"{path.relative_to(APP)}: {module}"
        for path in (APP / package).rglob("*.py")
        for module in _imported_modules(path)
        if module.startswith("app.") and module.split(".")[1] not in allowed
    ]
    assert violations == []


def test_domains_include_core_and_studyroom() -> None:
    assert {"core", "studyroom"} <= set(DOMAINS)
