#!/usr/bin/env python3
import json
import sqlite3
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
import pstats
from tqdm import tqdm


def generate_db_path(base_dir: str = "profiling") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stats_dir = Path(base_dir) / "statistics" / timestamp
    stats_dir.mkdir(parents=True, exist_ok=True)
    return str(stats_dir / "base.db")


def create_database(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS profiling_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_name TEXT UNIQUE NOT NULL,
            timestamp DATETIME,
            execution_time_seconds REAL,
            n_concurrent_trials INTEGER,
            disable_diffs BOOLEAN,
            agent_name TEXT,
            cprofile_exists BOOLEAN,
            flamegraph_exists BOOLEAN,
            args_exists BOOLEAN,
            total_function_calls INTEGER,
            primitive_calls INTEGER,
            total_time_seconds REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON profiling_runs(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_agent_name ON profiling_runs(agent_name)")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            line_number INTEGER NOT NULL,
            function_name TEXT NOT NULL,
            module_name TEXT,
            is_builtin BOOLEAN,
            UNIQUE(filename, line_number, function_name)
        )
    """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(function_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_functions_filename ON functions(filename)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_functions_module ON functions(module_name)")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS function_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            function_id INTEGER NOT NULL,
            call_count INTEGER NOT NULL,
            primitive_call_count INTEGER NOT NULL,
            total_time REAL NOT NULL,
            cumulative_time REAL NOT NULL,
            time_per_call REAL,
            cumulative_per_call REAL,
            time_percentage REAL,
            FOREIGN KEY (run_id) REFERENCES profiling_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (function_id) REFERENCES functions(id) ON DELETE CASCADE,
            UNIQUE(run_id, function_id)
        )
    """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_run_id ON function_stats(run_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_stats_function_id ON function_stats(function_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_stats_total_time ON function_stats(total_time DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_stats_cumulative_time ON function_stats(cumulative_time DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_stats_call_count ON function_stats(call_count DESC)"
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS call_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            caller_function_id INTEGER NOT NULL,
            callee_function_id INTEGER NOT NULL,
            call_count INTEGER NOT NULL,
            total_time REAL,
            cumulative_time REAL,
            FOREIGN KEY (run_id) REFERENCES profiling_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (caller_function_id) REFERENCES functions(id) ON DELETE CASCADE,
            FOREIGN KEY (callee_function_id) REFERENCES functions(id) ON DELETE CASCADE,
            UNIQUE(run_id, caller_function_id, callee_function_id)
        )
    """
    )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_calls_run_caller ON call_relationships(run_id, caller_function_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_calls_run_callee ON call_relationships(run_id, callee_function_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_calls_caller ON call_relationships(caller_function_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_calls_callee ON call_relationships(callee_function_id)"
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS top_level_functions (
            run_id INTEGER NOT NULL,
            function_id INTEGER NOT NULL,
            PRIMARY KEY (run_id, function_id),
            FOREIGN KEY (run_id) REFERENCES profiling_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (function_id) REFERENCES functions(id) ON DELETE CASCADE
        )
    """
    )

    conn.commit()
    return conn


def parse_folder_timestamp(folder_name: str) -> Optional[datetime]:
    try:
        return datetime.strptime(folder_name, "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def check_file_exists(folder_path: Path, filename: str) -> bool:
    return (folder_path / filename).exists()


def get_or_create_function(cursor: sqlite3.Cursor, func_tuple: tuple) -> int:
    filename, line_number, function_name = func_tuple

    is_builtin = filename == "~"
    module_name = None
    if not is_builtin and filename:
        module_name = Path(filename).stem

    cursor.execute(
        """
        SELECT id FROM functions 
        WHERE filename = ? AND line_number = ? AND function_name = ?
    """,
        (filename, line_number, function_name),
    )

    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        """
        INSERT INTO functions (filename, line_number, function_name, module_name, is_builtin)
        VALUES (?, ?, ?, ?, ?)
    """,
        (filename, line_number, function_name, module_name, is_builtin),
    )

    return cursor.lastrowid


def import_cprofile_data(cursor: sqlite3.Cursor, run_id: int, prof_path: Path):
    if not prof_path.exists():
        return

    stats = pstats.Stats(str(prof_path))

    cursor.execute(
        """
        UPDATE profiling_runs
        SET total_function_calls = ?,
            primitive_calls = ?,
            total_time_seconds = ?
        WHERE id = ?
    """,
        (stats.total_calls, stats.prim_calls, stats.total_tt, run_id),
    )

    for func_tuple, (cc, nc, tt, ct, callers) in stats.stats.items():
        function_id = get_or_create_function(cursor, func_tuple)

        time_per_call = tt / nc if nc > 0 else 0
        cumulative_per_call = ct / cc if cc > 0 else 0
        time_percentage = (tt / stats.total_tt * 100) if stats.total_tt > 0 else 0

        cursor.execute(
            """
            INSERT INTO function_stats 
            (run_id, function_id, call_count, primitive_call_count, 
             total_time, cumulative_time, time_per_call, cumulative_per_call, time_percentage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                run_id,
                function_id,
                nc,
                cc,
                tt,
                ct,
                time_per_call,
                cumulative_per_call,
                time_percentage,
            ),
        )

        for caller_tuple, caller_stats in callers.items():
            caller_function_id = get_or_create_function(cursor, caller_tuple)

            if isinstance(caller_stats, tuple):
                caller_nc, caller_cc, caller_tt, caller_ct = caller_stats
                cursor.execute(
                    """
                    INSERT INTO call_relationships 
                    (run_id, caller_function_id, callee_function_id, call_count, total_time, cumulative_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (run_id, caller_function_id, function_id, caller_nc, caller_tt, caller_ct),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO call_relationships 
                    (run_id, caller_function_id, callee_function_id, call_count, total_time, cumulative_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (run_id, caller_function_id, function_id, caller_stats, None, None),
                )

    for func_tuple in stats.top_level:
        function_id = get_or_create_function(cursor, func_tuple)
        cursor.execute(
            """
            INSERT OR IGNORE INTO top_level_functions (run_id, function_id)
            VALUES (?, ?)
        """,
            (run_id, function_id),
        )


def import_metadata(summaries_dir: str = "profiling/summaries", base_dir: str = "profiling") -> str:
    summaries_path = Path(summaries_dir)

    if not summaries_path.exists():
        raise FileNotFoundError(f"Summaries directory not found: {summaries_dir}")

    db_path = generate_db_path(base_dir)
    conn = create_database(db_path)
    cursor = conn.cursor()

    imported_count = 0
    skipped_count = 0

    folders = sorted([f for f in summaries_path.iterdir() if f.is_dir()])

    for folder in tqdm(folders, desc="Processing folders"):
        folder_name = folder.name
        metadata_file = folder / "metatdata.json"

        if not metadata_file.exists():
            skipped_count += 1
            continue

        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
        except json.JSONDecodeError:
            skipped_count += 1
            continue

        timestamp = parse_folder_timestamp(folder_name)
        cprofile_exists = check_file_exists(folder, "cProfile.prof")
        flamegraph_exists = check_file_exists(folder, "flamegraph.svg")
        args_exists = check_file_exists(folder, "args")

        try:
            cursor.execute(
                """
                INSERT INTO profiling_runs 
                (folder_name, timestamp, execution_time_seconds, n_concurrent_trials, 
                 disable_diffs, agent_name, cprofile_exists, flamegraph_exists, args_exists)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    folder_name,
                    timestamp,
                    metadata.get("execution_time_seconds"),
                    metadata.get("n_concurrent_trials"),
                    metadata.get("disable_diffs"),
                    metadata.get("agent_name"),
                    cprofile_exists,
                    flamegraph_exists,
                    args_exists,
                ),
            )

            run_id = cursor.lastrowid

            if cprofile_exists:
                prof_path = folder / "cProfile.prof"
                import_cprofile_data(cursor, run_id, prof_path)

            imported_count += 1

        except sqlite3.Error:
            skipped_count += 1
            continue

    conn.commit()
    conn.close()

    tqdm.write(f"\nImport summary: {imported_count} imported, {skipped_count} skipped")
    tqdm.write(f"Database: {db_path}")

    return db_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import profiling summaries into database")
    parser.add_argument(
        "--summaries-dir",
        type=str,
        default="profiling/summaries",
        help="Directory containing profiling summaries (default: profiling/summaries)",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default="profiling",
        help="Base directory for statistics output (default: profiling)",
    )

    args = parser.parse_args()

    try:
        import_metadata(args.summaries_dir, args.base_dir)
    except Exception as e:
        tqdm.write(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
