from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_PYTHON_SPECS = (
    pytest.param("3.12", id="python312"),
    pytest.param("3.14", id="python314"),
)
LIBCST_MINIMUM_VERSION = (1, 8, 0)


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is required to provision Python environments")
@pytest.mark.parametrize("python_spec", SUPPORTED_PYTHON_SPECS)
def test_mutmut_operates_in_a_python314_project(tmp_path, python_spec):
    project_dir = tmp_path / f"demo_mutmut_project_{python_spec.replace('.', '')}"
    project_dir.mkdir()

    venv_path = project_dir / ".venv"
    subprocess.run(["uv", "venv", "-p", python_spec, str(venv_path)], check=True)

    python_executable = venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    project_pyproject = textwrap.dedent(
        """
        [build-system]
        requires = ["setuptools"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "demo-mutmut-project"
        version = "0.0.0"
        requires-python = ">={python_spec}"
        dependencies = [
            "pytest",
            "mutmut",
        ]

        [tool.setuptools]
        packages = ["demo_pkg"]
        """
    ).strip()
    (project_dir / "pyproject.toml").write_text(project_pyproject, encoding="utf-8")

    requirements_txt = textwrap.dedent(
        f"""
        -e {REPO_ROOT}
        pytest
        """
    ).strip()
    (project_dir / "requirements.txt").write_text(requirements_txt, encoding="utf-8")

    install_env = os.environ.copy()
    install_env.setdefault("PYO3_USE_ABI3_FORWARD_COMPATIBILITY", "1")
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python_executable),
            "-r",
            str(project_dir / "requirements.txt"),
        ],
        check=True,
        env=install_env,
    )

    subprocess.run(
        [
            str(python_executable),
            "-c",
            textwrap.dedent(
                f"""
                from importlib import metadata

                version_text = metadata.version("libcst")
                numeric_parts: list[int] = []
                for part in version_text.split('.'):
                    digits = ''.join(character for character in part if character.isdigit())
                    if not digits:
                        break
                    numeric_parts.append(int(digits))
                    if len(numeric_parts) == 3:
                        break
                while len(numeric_parts) < 3:
                    numeric_parts.append(0)
                minimum_version = {LIBCST_MINIMUM_VERSION}
                if tuple(numeric_parts) < minimum_version:
                    raise SystemExit(f"libcst {{version_text}} is too old for Python 3.14 support")
                """
            ),
        ],
        check=True,
        env=install_env,
    )

    demo_pkg_dir = project_dir / "demo_pkg"
    demo_pkg_dir.mkdir()
    (demo_pkg_dir / "__init__.py").write_text(
        textwrap.dedent(
            """
            def add(left: int, right: int) -> int:
                return left + right
            """
        ).lstrip(),
        encoding="utf-8",
    )

    tests_dir = project_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_add.py").write_text(
        textwrap.dedent(
            """
            import pytest

            from demo_pkg import add


            @pytest.mark.parametrize(
                ("left", "right", "expected"),
                ((0, 0, 0), (1, 2, 3), (-3, 5, 2), (10, -4, 6)),
            )
            def test_add(left: int, right: int, expected: int) -> None:
                assert add(left, right) == expected
            """
        ).lstrip(),
        encoding="utf-8",
    )

    (project_dir / "setup.cfg").write_text(
        textwrap.dedent(
            """
            [mutmut]
            paths_to_mutate = demo_pkg
            tests_dir = tests
            runner = pytest -q
            """
        ).strip(),
        encoding="utf-8",
    )

    subprocess.run(
        [
            str(python_executable),
            "-m",
            "mutmut",
            "run",
        ],
        cwd=project_dir,
        check=True,
        env=install_env,
    )
