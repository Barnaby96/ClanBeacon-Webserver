"""Run ClanBeacon's two pytest groups with their required working directories."""

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

PROTECTED = {
    "utils/osrs_quest_data.py":
        "238362f39d12381d84e54411f3b923cb9f0a229337932e8fc1e155d8a331d851",
    "data/osrs_requirement_reviews_v1.json":
        "b2bf915d50d854fb46e28839cfbac0a1735c41441990d0beab7a199716496bd6",
}

# Each group executes in its own Python process.
CHILD_RUNNER = r"""
import os
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
expected_count = int(sys.argv[2])
test_paths = sys.argv[3:]

sys.dont_write_bytecode = True

from dotenv import load_dotenv
load_dotenv(root / ".env", override=False)

assert os.environ.get("PGDATABASE") == "danbot_test"

local_hosts = {"", "localhost", "127.0.0.1", "::1"}

host = (os.getenv("PGHOST") or "").strip().lower()
hostaddr = (os.getenv("PGHOSTADDR") or "").strip().lower()

assert host in local_hosts, "Non-local database host refused"
assert hostaddr in local_hosts, "Non-local host address refused"
assert not os.getenv("PGSERVICE"), "PostgreSQL service override refused"

import psycopg2

real_connect = psycopg2.connect
connection_count = [0]

def guarded_connect(*args, **kwargs):
    if args:
        raise RuntimeError("Positional database connection refused")

    name = kwargs.get("dbname", kwargs.get("database"))
    target_host = (
        kwargs.get("host") or ""
    ).strip().lower()
    target_addr = (
        kwargs.get("hostaddr") or ""
    ).strip().lower()

    if name != "danbot_test":
        raise RuntimeError("Non-test database connection refused")

    if os.getenv("PGDATABASE") != "danbot_test":
        raise RuntimeError("PGDATABASE was changed")

    if target_host not in local_hosts:
        raise RuntimeError("Non-local database host refused")

    if target_addr not in local_hosts:
        raise RuntimeError("Non-local database address refused")

    connection_count[0] += 1
    return real_connect(*args, **kwargs)

psycopg2.connect = guarded_connect

import pytest

class Audit:
    collected = 0
    passed = 0
    failed = 0
    skipped = 0
    errors = 0

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            if report.passed:
                self.passed += 1
            elif report.failed:
                self.failed += 1
            elif report.skipped:
                self.skipped += 1
        elif report.failed:
            self.errors += 1

audit = Audit()

result = pytest.main(
    test_paths + [
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
    ],
    plugins=[audit],
)

print("\n=== GROUP RESULT ===", flush=True)
print("Working directory:", Path.cwd(), flush=True)
print("Collected:", audit.collected, flush=True)
print("Passed:", audit.passed, flush=True)
print("Failed:", audit.failed, flush=True)
print("Errors:", audit.errors, flush=True)
print("Skipped:", audit.skipped, flush=True)
print("Database connections:", connection_count[0], flush=True)

success = (
    int(result) == 0
    and audit.collected == expected_count
    and audit.passed == expected_count
    and audit.failed == 0
    and audit.errors == 0
    and audit.skipped == 0
)

if not success:
    raise SystemExit("GROUP FAILED")

print("GROUP PASS", flush=True)
"""


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_protected_files():
    for relative, expected in PROTECTED.items():
        path = ROOT / relative

        if fingerprint(path) != expected:
            raise RuntimeError(
                f"Protected file fingerprint mismatch: {relative}"
            )


def discover_tests():
    modules = sorted({
        *TESTS.rglob("test_*.py"),
        *TESTS.rglob("*_test.py"),
    })

    osrs = [
        path for path in modules
        if path.parent == TESTS
        and path.name.startswith("test_osrs_")
    ]

    other = [
        path for path in modules
        if path not in osrs
    ]

    if (len(modules), len(osrs), len(other)) != (116, 66, 50):
        raise RuntimeError(
            "Unexpected test inventory: "
            f"{len(modules)} total, "
            f"{len(osrs)} OSRS, "
            f"{len(other)} other"
        )

    return osrs, other


def main():
    parser = argparse.ArgumentParser(
        description="Run the complete ClanBeacon regression suite."
    )

    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--check",
        action="store_true",
        help="Inspect configuration without running tests.",
    )
    selection.add_argument(
        "--run",
        action="store_true",
        help="Run the complete suite, including test-database resets.",
    )
    selection.add_argument(
        "--osrs-only",
        action="store_true",
        help="Run only the 1,057 OSRS tests.",
    )

    args = parser.parse_args()

    if not (TESTS / "conftest.py").is_file():
        raise RuntimeError("ClanBeacon test directory not found")

    verify_protected_files()
    osrs, other = discover_tests()

    print("=== CLANBEACON REGRESSION RUNNER ===", flush=True)
    print("Repository:", ROOT, flush=True)
    print("OSRS: 66 modules / 1,057 tests", flush=True)
    print("Other: 50 modules / 688 tests", flush=True)
    print("Expected total: 1,745 tests", flush=True)
    print("Protected source fingerprints: PASS", flush=True)

    if args.check:
        print("\nRUNNER CHECK PASS", flush=True)
        print("No tests, database connections or writes")
        return

    environment = os.environ.copy()
    environment["PGDATABASE"] = "danbot_test"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTHONPATH"] = (
        str(ROOT)
        + os.pathsep
        + environment.get("PYTHONPATH", "")
    )

    environment.pop("PYTEST_ADDOPTS", None)

    groups = (
        (
            "OSRS",
            ROOT,
            [str(path.relative_to(ROOT)) for path in osrs],
            1057,
        ),
        (
            "OTHER CLANBEACON",
            TESTS,
            [path.name for path in other],
            688,
        ),
    )

    if args.osrs_only:
        groups = groups[:1]

    try:
        for name, directory, paths, expected in groups:
            print(f"\n=== RUNNING {name} TESTS ===", flush=True)
            print("Working directory:", directory, flush=True)

            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    CHILD_RUNNER,
                    str(ROOT),
                    str(expected),
                    *paths,
                ],
                cwd=str(directory),
                env=environment,
                check=False,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"{name} regression failed "
                    f"(exit code {result.returncode})"
                )

    finally:
        verify_protected_files()
        print(
            "\nProtected source fingerprints unchanged: PASS",
            flush=True,
        )

    if args.osrs_only:
        print("\n=== OSRS-ONLY CLANBEACON REGRESSION ===")
        print("OSRS: 1,057 / 1,057 PASS")
        print("Other tests: NOT RUN")
        print("TOTAL EXECUTED: 1,057 / 1,057 PASS")
    else:
        print("\n=== COMPLETE CLANBEACON REGRESSION ===")
        print("OSRS: 1,057 / 1,057 PASS")
        print("Other: 688 / 688 PASS")
        print("TOTAL: 1,745 / 1,745 PASS")

    print("Database restricted to local danbot_test")
    print("No source activation or deployment")


if __name__ == "__main__":
    main()
