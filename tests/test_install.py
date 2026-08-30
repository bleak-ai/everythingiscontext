from pathlib import Path

import pytest

from gcontext import cli
from gcontext import secrets


def make_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "context").mkdir(parents=True)
    return project


def make_package(tmp_path: Path, manifest: str) -> Path:
    package = tmp_path / "sample-package"
    package.mkdir()
    (package / "package.yaml").write_text(manifest)
    (package / "guide.md").write_text("Package guide\n")
    return package


def run_install(monkeypatch, package: Path, project: Path, *extra: str) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["gcontext", "install", str(package), "--project", str(project), *extra],
    )
    cli.main()


def test_parse_dotenv() -> None:
    content = """
    # comment
    API_KEY = "secret value"
    TOKEN='token-value'
    EMPTY =
    """

    assert secrets.parse_dotenv(content) == {
        "API_KEY": "secret value",
        "TOKEN": "token-value",
        "EMPTY": "",
    }


def test_install_local_package(tmp_path, monkeypatch) -> None:
    project = make_project(tmp_path)
    package = make_package(tmp_path, "name: sample\nversion: 1.0.0\n")

    run_install(monkeypatch, package, project)

    installed = project / "context" / "packages" / package.name
    assert (installed / "package.yaml").read_text() == "name: sample\nversion: 1.0.0\n"
    assert (installed / "guide.md").read_text() == "Package guide\n"


def test_install_secrets_check(tmp_path, monkeypatch, capsys) -> None:
    project = make_project(tmp_path)
    (project / "secrets.env").write_text("PRESENT=value\n")
    package = make_package(
        tmp_path,
        "name: sample\nversion: 1.0.0\nsecrets:\n  - PRESENT\n  - MISSING\n",
    )

    with pytest.raises(SystemExit) as exc:
        run_install(monkeypatch, package, project)

    assert exc.value.code == 1
    assert "MISSING" in capsys.readouterr().err


def test_install_skip_secrets(tmp_path, monkeypatch) -> None:
    project = make_project(tmp_path)
    package = make_package(
        tmp_path,
        "name: sample\nversion: 1.0.0\nsecrets:\n  - MISSING\n",
    )

    run_install(monkeypatch, package, project, "--skip-secrets")

    assert (project / "context" / "packages" / package.name).is_dir()


def test_install_with_deps(tmp_path, monkeypatch) -> None:
    project = make_project(tmp_path)
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"example\"\nversion = \"0.1.0\"\n"
    )
    package = make_package(
        tmp_path,
        "name: sample\nversion: 1.0.0\ndeps:\n  - requests>=2\n  - pyyaml>=6\n",
    )
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: None)

    run_install(monkeypatch, package, project)

    pyproject = (project / "pyproject.toml").read_text()
    assert "[project.optional-dependencies]" in pyproject
    assert 'packages = ["requests>=2", "pyyaml>=6"]' in pyproject


def test_install_config_template(tmp_path, monkeypatch) -> None:
    project = make_project(tmp_path)
    package = make_package(tmp_path, "name: sample\nversion: 1.0.0\n")
    (package / "config.yaml.template").write_text("setting: REQUIRED\n")

    run_install(monkeypatch, package, project)

    assert (project / "local" / "config.yaml").read_text() == "setting: REQUIRED\n"


def test_install_requires_context_folder(tmp_path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "gcontext.yaml").write_text("name: legacy\n")
    package = make_package(tmp_path, "name: sample\nversion: 1.0.0\n")

    with pytest.raises(SystemExit) as exc:
        run_install(monkeypatch, package, project)

    assert exc.value.code == 1
    assert "set up the context standard first" in capsys.readouterr().err
