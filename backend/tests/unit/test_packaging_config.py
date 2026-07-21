from pathlib import Path
import tomllib


PYPROJECT_PATH = Path(__file__).parents[2] / "pyproject.toml"


def load_pyproject() -> dict:
    with PYPROJECT_PATH.open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)


def test_setuptools_package_discovery_only_includes_app_packages() -> None:
    package_find = load_pyproject()["tool"]["setuptools"]["packages"]["find"]

    assert package_find == {
        "where": ["."],
        "include": ["app*"],
        "exclude": ["data*", "tests*"],
    }


def test_dev_dependencies_use_supported_httpx_package() -> None:
    dev_dependencies = load_pyproject()["project"]["optional-dependencies"]["dev"]

    assert "httpx>=0.27,<1" in dev_dependencies
    assert not any(dependency.startswith("httpx2") for dependency in dev_dependencies)
