#!/usr/bin/env python3
"""One-shot project setup for QPath.

Run this once after cloning the repository:

    python setup_project.py            # Windows / any OS   (or: python3 setup_project.py)

What it does (idempotent: safe to re-run at any time):

  1. Checks prerequisites: Python >= 3.12, Node.js >= 20.19 (or >= 22.12), npm.
  2. Creates the backend virtual environment  (backend/.venv).
  3. Installs the backend (editable, with dev extras for tests/lint).
  4. Installs the frontend dependencies       (frontend/node_modules, via `npm ci`).
  5. Creates backend/.env and frontend/.env from their .env.example files
     (never overwrites an existing file unless --force-env is given).
  6. Initialises the SQLite database and seeds the reference data / quiz questions.
  7. Optionally loads the recorded SerpApi sample data (--with-data), runs the
     test suites (--run-tests) and/or starts both dev servers (--start).

This script only needs a Python 3 interpreter to *launch*; it uses the standard
library only. It will locate a suitable Python 3.12+ itself to build the venv.

Examples:
    python setup_project.py                 # standard setup
    python setup_project.py --with-data     # + load offline sample market data
    python setup_project.py --run-tests     # + run backend and frontend tests
    python setup_project.py --start         # + launch backend and frontend servers
    python setup_project.py --backend-only  # skip everything frontend
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

MIN_PYTHON = (3, 12)
BACKEND_PORT = 8000
FRONTEND_PORT = 5173

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = BACKEND / ".venv"
IS_WINDOWS = os.name == "nt"
VENV_PYTHON = VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")

# --------------------------------------------------------------------------- #
# Pretty output
# --------------------------------------------------------------------------- #


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if IS_WINDOWS:
        # Windows 10+ terminals understand ANSI once VT processing is enabled.
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return False
    return True


_COLOR = _supports_color()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def step(n: int, total: int, title: str) -> None:
    print(f"\n{_c('1;36', f'[{n}/{total}]')} {_c('1', title)}")


def ok(msg: str) -> None:
    print(f"  {_c('32', 'OK')}   {msg}")


def info(msg: str) -> None:
    print(f"  {_c('34', '..')}   {msg}")


def warn(msg: str) -> None:
    print(f"  {_c('33', 'WARN')} {msg}")


def die(msg: str, hint: str = "") -> None:
    print(f"\n{_c('1;31', 'ERROR')} {msg}", file=sys.stderr)
    if hint:
        print(textwrap.indent(textwrap.dedent(hint).strip("\n"), "      "), file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """Run a command, streaming its output; abort the setup on failure."""
    shown = " ".join(str(c) for c in cmd)
    info(f"$ {shown}")
    try:
        subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=env, check=True)
    except FileNotFoundError:
        die(f"Command not found: {cmd[0]}")
    except subprocess.CalledProcessError as exc:
        die(f"Command failed (exit code {exc.returncode}): {shown}")


def capture(cmd: list[str]) -> str | None:
    """Return stdout of a command, or None if it is missing / fails."""
    try:
        out = subprocess.run(
            [str(c) for c in cmd], capture_output=True, text=True, timeout=30, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def python_version_of(cmd: list[str]) -> tuple[int, int] | None:
    out = capture([*cmd, "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"])
    if not out:
        return None
    try:
        major, minor = out.split()[:2]
        return int(major), int(minor)
    except ValueError:
        return None


def find_python() -> list[str]:
    """Locate a Python >= 3.12 interpreter (as an argv prefix)."""
    candidates: list[list[str]] = []
    if sys.version_info >= MIN_PYTHON:
        candidates.append([sys.executable])
    for minor in (14, 13, 12):
        candidates.append([f"python3.{minor}"])
    candidates += [["python3"], ["python"]]
    if IS_WINDOWS:
        candidates += [["py", "-3.14"], ["py", "-3.13"], ["py", "-3.12"], ["py", "-3"]]
    for cand in candidates:
        if shutil.which(cand[0]) is None:
            continue
        version = python_version_of(cand)
        if version and version >= MIN_PYTHON:
            return cand
    system = platform.system()
    hints = {
        "Windows": "winget install Python.Python.3.12     (or https://www.python.org/downloads/)",
        "Darwin": "brew install python@3.12               (or https://www.python.org/downloads/)",
        "Linux": (
            "Debian/Ubuntu: sudo apt install python3.12 python3.12-venv\n"
            "Fedora:        sudo dnf install python3.12\n"
            "Arch:          sudo pacman -S python\n"
            "Any distro:    https://www.python.org/downloads/  (or use pyenv / uv)"
        ),
    }
    die(
        f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ was not found on this machine.",
        "Install it, open a NEW terminal and re-run this script:\n\n"
        + hints.get(system, "https://www.python.org/downloads/"),
    )
    raise SystemExit(1)  # unreachable; keeps type checkers happy


def node_ok(version_text: str) -> bool:
    """Vite 7 (used by the frontend) needs Node ^20.19 or >=22.12."""
    try:
        major, minor = (int(p) for p in version_text.lstrip("v").split(".")[:2])
    except ValueError:
        return False
    return (major == 20 and minor >= 19) or (major == 22 and minor >= 12) or major >= 23


def npm_command() -> str | None:
    return shutil.which("npm.cmd" if IS_WINDOWS else "npm") or shutil.which("npm")


def copy_env(example: Path, target: Path, force: bool) -> None:
    rel = target.relative_to(ROOT)
    if not example.exists():
        warn(f"{example.relative_to(ROOT)} not found; skipping {rel}")
        return
    if target.exists() and not force:
        ok(f"{rel} already exists (kept as is)")
        return
    if target.exists():
        backup = target.with_name(target.name + ".bak")
        shutil.copy2(target, backup)
        info(f"backed up old file to {backup.relative_to(ROOT)}")
    shutil.copy2(example, target)
    ok(f"created {rel} from {example.name}")


def port_free(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) != 0


# Run inside the venv, from backend/: create tables, seed reference data and the
# quiz, and (optionally) ingest the recorded SerpApi fixtures. Uses the app's own
# code paths, so it behaves exactly like the server's startup + admin endpoint.
DB_BOOTSTRAP = r"""
import sys
from app.core.config import get_settings
from app.db.seed import seed_quiz_questions, seed_reference_data
from app.db.session import SessionLocal, init_db

with_data = sys.argv[1] == "1"
init_db()
with SessionLocal() as db:
    seed_reference_data(db)
    seed_quiz_questions(db)
print("database initialised and reference data seeded")

if with_data:
    settings = get_settings()
    if not settings.serpapi_use_fixtures:
        print("SERPAPI_USE_FIXTURES is false in backend/.env -> skipping sample data "
              "(it would spend live SerpApi credits).")
        sys.exit(0)
    from pathlib import Path
    from app.integrations.serpapi.client import SerpApiClient
    from app.services import ingestion_service

    fixture_dir = Path(settings.serpapi_fixture_dir) if settings.serpapi_fixture_dir else None
    for region in ("global", "india"):
        client = SerpApiClient(settings, SessionLocal, fixture_dir=fixture_dir)
        try:
            with SessionLocal() as db:
                run = ingestion_service.refresh_jobs(
                    db, client, mode="bootstrap", region=region
                )
                details = run.details or {}
                print(f"sample jobs ({region}): status={run.status} "
                      f"postings_seen={details.get('postings_seen', 0)}")
        finally:
            client.close()
"""


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #


def check_repo_layout(args: argparse.Namespace) -> None:
    missing = [
        p
        for p in (BACKEND / "pyproject.toml", FRONTEND / "package.json")
        if not p.exists() and not (args.backend_only and p.parent == FRONTEND)
    ]
    if missing:
        die(
            "This does not look like the Qpath repository root.",
            "Missing: " + ", ".join(str(m.relative_to(ROOT)) for m in missing)
            + "\nRun the script from inside the cloned repo (it lives next to backend/ and frontend/).",
        )


def setup_prerequisites(args: argparse.Namespace) -> list[str]:
    python_cmd = find_python()
    version = python_version_of(python_cmd)
    ok(f"Python {version[0]}.{version[1]}  ({' '.join(python_cmd)})" if version else "Python found")

    if args.backend_only:
        info("Skipping Node.js check (--backend-only)")
        return python_cmd

    node = shutil.which("node")
    node_version = capture([node, "--version"]) if node else None
    npm = npm_command()
    if not node_version or not npm:
        hints = {
            "Windows": "winget install OpenJS.NodeJS.LTS   (or https://nodejs.org/)",
            "Darwin": "brew install node@22               (or https://nodejs.org/)",
            "Linux": (
                "Use your package manager, or nvm:\n"
                "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash\n"
                "nvm install 22"
            ),
        }
        die(
            "Node.js and npm were not found.",
            "Install Node.js 22 LTS (>= 20.19 works too), open a NEW terminal and re-run:\n\n"
            + hints.get(platform.system(), "https://nodejs.org/")
            + "\n\n(Or re-run with --backend-only to set up just the API.)",
        )
    if not node_ok(node_version):
        die(
            f"Node.js {node_version} is too old for the frontend (needs >= 20.19 or >= 22.12).",
            "Upgrade Node.js (https://nodejs.org/ or `nvm install 22`) and re-run this script.",
        )
    ok(f"Node.js {node_version}, npm {capture([npm, '--version']) or '?'}")
    return python_cmd


def setup_backend(python_cmd: list[str]) -> None:
    if VENV_PYTHON.exists() and (python_version_of([str(VENV_PYTHON)]) or (0, 0)) >= MIN_PYTHON:
        ok("virtual environment already exists (backend/.venv)")
    else:
        if VENV.exists():
            warn("existing backend/.venv is broken or too old; recreating it")
            shutil.rmtree(VENV, ignore_errors=True)
        info("creating virtual environment backend/.venv")
        try:
            subprocess.run([*python_cmd, "-m", "venv", str(VENV)], check=True)
        except subprocess.CalledProcessError:
            shutil.rmtree(VENV, ignore_errors=True)
            die(
                "Could not create the virtual environment.",
                "On Debian/Ubuntu the venv module ships separately:\n"
                "    sudo apt install python3-venv   (or python3.12-venv)\n"
                "Then re-run this script.",
            )
    try:  # upgrading pip is a nicety, never a reason to abort
        subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"],
                       cwd=str(BACKEND), check=True)
    except subprocess.CalledProcessError:
        warn("could not upgrade pip; continuing with the bundled version")
    info("installing backend dependencies (this can take a minute)")
    run([VENV_PYTHON, "-m", "pip", "install", "-e", ".[dev]"], cwd=BACKEND)
    ok("backend dependencies installed")


def setup_frontend() -> None:
    npm = npm_command()
    assert npm is not None
    lockfile = FRONTEND / "package-lock.json"
    if lockfile.exists():
        info("installing frontend dependencies with `npm ci` (this can take a minute)")
        try:
            subprocess.run([npm, "ci"], cwd=str(FRONTEND), check=True)
        except subprocess.CalledProcessError:
            warn("`npm ci` failed; falling back to `npm install`")
            run([npm, "install"], cwd=FRONTEND)
    else:
        run([npm, "install"], cwd=FRONTEND)
    ok("frontend dependencies installed")


def setup_env_files(args: argparse.Namespace) -> None:
    copy_env(BACKEND / ".env.example", BACKEND / ".env", args.force_env)
    if not args.backend_only:
        copy_env(FRONTEND / ".env.example", FRONTEND / ".env", args.force_env)


def setup_database(with_data: bool) -> None:
    (BACKEND / "data").mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    run([VENV_PYTHON, "-c", DB_BOOTSTRAP, "1" if with_data else "0"], cwd=BACKEND, env=env)
    ok("database ready at backend/data/pathfinder.db")


def run_tests(args: argparse.Namespace) -> None:
    run([VENV_PYTHON, "-m", "pytest", "-q"], cwd=BACKEND)
    ok("backend tests passed")
    if not args.backend_only:
        npm = npm_command()
        assert npm is not None
        run([npm, "run", "test", "--", "--run"], cwd=FRONTEND)
        ok("frontend tests passed")


def start_servers(args: argparse.Namespace) -> None:
    for port, name in ((BACKEND_PORT, "backend"), (FRONTEND_PORT, "frontend")):
        if name == "frontend" and args.backend_only:
            continue
        if not port_free(port):
            die(f"Port {port} ({name}) is already in use.", "Stop whatever is using it and retry.")

    procs: list[subprocess.Popen] = []
    popen_kwargs: dict = {}
    if not IS_WINDOWS:
        popen_kwargs["start_new_session"] = True
    try:
        procs.append(
            subprocess.Popen(
                [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--reload",
                 "--port", str(BACKEND_PORT)],
                cwd=str(BACKEND),
                **popen_kwargs,
            )
        )
        if not args.backend_only:
            npm = npm_command()
            assert npm is not None
            procs.append(subprocess.Popen([npm, "run", "dev"], cwd=str(FRONTEND), **popen_kwargs))
        print(f"\n  Backend : http://localhost:{BACKEND_PORT}   (API docs: /docs)")
        if not args.backend_only:
            print(f"  Frontend: http://localhost:{FRONTEND_PORT}")
        print("  Press Ctrl+C to stop both servers.\n")
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        warn("a server exited; shutting the other one down")
    except KeyboardInterrupt:
        print("\nStopping servers...")
    finally:
        for p in procs:
            if p.poll() is None:
                try:
                    if IS_WINDOWS:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True
                        )
                    else:
                        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    pass


def print_next_steps(args: argparse.Namespace) -> None:
    activate = r"backend\.venv\Scripts\activate" if IS_WINDOWS else "source backend/.venv/bin/activate"
    uvicorn_path = r".venv\Scripts\uvicorn" if IS_WINDOWS else ".venv/bin/uvicorn"
    lines = [
        "",
        _c("1;32", "Setup complete!"),
        "",
        "Start the app (two terminals):",
        f"  1) Backend : cd backend && {uvicorn_path} app.main:app --reload --port {BACKEND_PORT}",
        f"  2) Frontend: cd frontend && npm run dev          -> http://localhost:{FRONTEND_PORT}",
        "",
        "...or let this script launch both:   python setup_project.py --start",
        "",
        f"Python venv activation (optional): {activate}",
        "Config lives in backend/.env (offline fixture mode by default; add GEMINI_API_KEY /",
        "GEMINI_MODEL there to enable the AI-backed features, see README.md).",
    ]
    if args.backend_only:
        lines.insert(4, "(frontend was skipped: --backend-only)")
    if not args.with_data:
        lines += [
            "",
            "Tip: re-run with --with-data to preload the recorded sample job-market data,",
            "     or press the refresh button in the UI / call POST /api/v1/admin/refresh/jobs.",
        ]
    print("\n".join(lines))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Set up QPath from scratch after cloning the repo.",
    )
    p.add_argument("--with-data", action="store_true",
                   help="load the recorded (offline) SerpApi sample job data into the database")
    p.add_argument("--run-tests", action="store_true", help="run backend + frontend tests after setup")
    p.add_argument("--start", action="store_true", help="start backend and frontend dev servers when done")
    p.add_argument("--backend-only", action="store_true", help="skip Node.js / frontend setup")
    p.add_argument("--force-env", action="store_true",
                   help="overwrite existing .env files (old ones are backed up as .env.bak)")
    p.add_argument("--clean", action="store_true",
                   help="delete backend/.venv, frontend/node_modules and the local database first")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    os.chdir(ROOT)
    print(_c("1", "QPath - project setup"))
    print(f"  repo: {ROOT}\n  system: {platform.system()} {platform.machine()}")

    check_repo_layout(args)

    if args.clean:
        for path in (VENV, FRONTEND / "node_modules", BACKEND / "data"):
            if path.exists():
                info(f"removing {path.relative_to(ROOT)}")
                shutil.rmtree(path, ignore_errors=True)

    total = 5 + (1 if args.run_tests else 0)
    n = 0

    n += 1
    step(n, total, "Checking prerequisites")
    python_cmd = setup_prerequisites(args)

    n += 1
    step(n, total, "Backend: virtual environment + dependencies")
    setup_backend(python_cmd)

    n += 1
    step(n, total, "Frontend: npm dependencies")
    if args.backend_only:
        info("skipped (--backend-only)")
    else:
        setup_frontend()

    n += 1
    step(n, total, "Environment files")
    setup_env_files(args)

    n += 1
    step(n, total, "Database: create tables, seed reference data" + (" + sample jobs" if args.with_data else ""))
    setup_database(args.with_data)

    if args.run_tests:
        n += 1
        step(n, total, "Running tests")
        run_tests(args)

    print_next_steps(args)

    if args.start:
        start_servers(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
