"""
Snapshots all of Tackety's SQLite databases using SQLite's own online
backup API (sqlite3.Connection.backup()) rather than a raw file copy.

Why not just `cp conversations.db backup/`: the server runs with
PRAGMA journal_mode=WAL (see session_manager.py) - under WAL, a plain
file copy taken mid-write can capture the main DB file and its -wal
file in an inconsistent state, producing a backup that looks fine but
is subtly corrupt. The backup API copies a transactionally-consistent
snapshot while the source database stays fully usable (readers and
writers keep working) throughout the copy.

Usage:
    python engine/backup.py                    # backs up to ./backups/<timestamp>/
    python engine/backup.py --out /path/to/dir  # explicit destination
    python engine/backup.py --data-dir /path    # if TACKETY_DATA_DIR was overridden

Intended to be run manually or from a cron/scheduled task - it is not
started automatically by the server.
"""
import argparse
import os
import sqlite3
import sys


def _default_data_dir():
    return os.getenv("TACKETY_DATA_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def backup_database(source_path: str, dest_path: str):
    """Copies one SQLite database via the online backup API. No-ops
    (with a message) if the source file doesn't exist yet - a fresh
    install may not have created every database file."""
    if not os.path.exists(source_path):
        print(f"  skip: {source_path} does not exist yet")
        return False

    source_conn = sqlite3.connect(source_path)
    dest_conn = sqlite3.connect(dest_path)
    try:
        source_conn.backup(dest_conn)
    finally:
        source_conn.close()
        dest_conn.close()
    print(f"  {os.path.basename(source_path)} -> {dest_path}")
    return True


def run_backup(data_dir: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    print(f"Backing up SQLite databases from {data_dir} to {out_dir}\n")

    databases = ["conversations.db", "issues.db", "support.db", "knowledge.db"]
    backed_up = 0
    for db_name in databases:
        source = os.path.join(data_dir, db_name)
        dest = os.path.join(out_dir, db_name)
        if backup_database(source, dest):
            backed_up += 1

    # The preprocessed context files aren't databases, but they're just
    # as necessary to restore a working deployment (regenerating them
    # requires re-running setup_docs.py against your original source
    # docs, which you may not still have on hand) - copy them too.
    for context_file in ["company_context.txt", "product_context.txt", "management_rules.txt"]:
        source = os.path.join(data_dir, context_file)
        if os.path.exists(source):
            with open(source, "r", encoding="utf-8") as f:
                content = f.read()
            with open(os.path.join(out_dir, context_file), "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  {context_file} -> {out_dir}")

    print(f"\nDone. {backed_up} database(s) backed up to {out_dir}")
    if backed_up == 0:
        print("WARNING: nothing was backed up - is TACKETY_DATA_DIR / --data-dir correct?")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Back up Tackety's SQLite databases.")
    parser.add_argument("--data-dir", default=_default_data_dir(),
                         help="Source data directory (default: $TACKETY_DATA_DIR or engine/data)")
    parser.add_argument("--out", default=None,
                         help="Destination directory (default: ./backups/<UTC timestamp>/)")
    args = parser.parse_args()

    if args.out:
        out_dir = args.out
    else:
        # Timestamp is deliberately not datetime.now() at import/module
        # scope - computed here, at actual invocation time, which is
        # fine for a CLI script (unlike the workflow-script restriction
        # this repo's other automation is subject to).
        from datetime import datetime, timezone
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = os.path.join("backups", stamp)

    run_backup(args.data_dir, out_dir)
