"""Launch real Python processes against one fresh auth database per batch."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile


CHILD = """
from pathlib import Path
import sys
from app.auth.storage import AuthStore

AuthStore(Path(sys.argv[1]), now=int(sys.argv[2]))
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batches", type=int, default=20)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.batches <= 100 or not 2 <= args.workers <= 16:
        parser.error("bounded matrix requires batches 1..100 and workers 2..16")

    environment = dict(os.environ)
    backend = str(Path(__file__).resolve().parents[3] / "backend")
    environment["PYTHONPATH"] = backend
    failures: list[dict[str, object]] = []
    migration_ledgers: list[list[int]] = []

    for batch in range(args.batches):
        with tempfile.TemporaryDirectory(prefix="assemble-auth-process-") as raw:
            database_path = Path(raw) / "auth.sqlite3"
            command = [
                sys.executable,
                "-c",
                CHILD,
                str(database_path),
                str(2_500_000_000 + batch),
            ]

            def construct(_: int) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    command,
                    cwd=Path(__file__).resolve().parents[3],
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )

            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                results = list(executor.map(construct, range(args.workers)))
            for worker, result in enumerate(results):
                if result.returncode:
                    failures.append(
                        {
                            "batch": batch,
                            "worker": worker,
                            "returncode": result.returncode,
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                        }
                    )
            with sqlite3.connect(database_path) as connection:
                migration_ledgers.append(
                    [row[0] for row in connection.execute("SELECT version FROM schema_migrations")]
                )

    output = {
        "batches": args.batches,
        "workers": args.workers,
        "processes": args.batches * args.workers,
        "failures": failures,
        "all_ledgers_exactly_v1": all(ledger == [1] for ledger in migration_ledgers),
    }
    print(json.dumps(output, sort_keys=True))
    return 1 if failures or not output["all_ledgers_exactly_v1"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
