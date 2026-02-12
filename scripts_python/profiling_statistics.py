#!/usr/bin/env python3
import json
import sqlite3
import subprocess
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
import pstats
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats as scipy_stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
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


def import_single_folder(conn: sqlite3.Connection, folder: Path) -> bool:
    cursor = conn.cursor()
    folder_name = folder.name
    metadata_file = folder / "metatdata.json"

    if not metadata_file.exists():
        return False

    try:
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
    except json.JSONDecodeError:
        return False

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

        conn.commit()
        return True

    except sqlite3.Error:
        conn.rollback()
        return False


def create_histogram(data: np.ndarray, title: str, xlabel: str, output_path: Path):
    if len(data) == 0:
        return

    mean_val = np.mean(data)
    std_val = np.std(data)

    fig, ax = plt.subplots(figsize=(10, 6))

    counts, bins, patches = ax.hist(data, bins=24, alpha=0.7, color="blue", edgecolor="black")

    if std_val > 1e-10 and data.max() > data.min():
        x = np.linspace(data.min(), data.max(), 100)
        normal_curve = scipy_stats.norm.pdf(x, mean_val, std_val) * len(data) * (bins[1] - bins[0])
        ax.plot(x, normal_curve, "g-", linewidth=2, label="Normal Distribution")

    ax.axvline(mean_val, color="red", linestyle="--", linewidth=2, label=f"Mean: {mean_val:.2f}")

    if std_val > 1e-10:
        for i in [-3, 3]:
            val = mean_val + i * std_val
            ax.axvline(
                val,
                color="lightblue",
                linestyle="--",
                linewidth=1.5,
                label=f'{"+3" if i > 0 else "-3"}σ: {val:.2f}',
            )

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Frequency")
    ax.set_title(title)
    ax.legend(title=f"μ={mean_val:.2f}, σ={std_val:.2f}")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def create_scatterplot(
    x_data: np.ndarray, y_data: np.ndarray, title: str, xlabel: str, ylabel: str, output_path: Path
):
    if len(x_data) == 0 or len(y_data) == 0:
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.scatter(x_data, y_data, alpha=0.6, color="blue", edgecolors="black")

    X = x_data.reshape(-1, 1)
    model = LinearRegression()
    model.fit(X, y_data)
    y_pred = model.predict(X)

    slope = model.coef_[0]
    r2 = r2_score(y_data, y_pred)
    mse = mean_squared_error(y_data, y_pred)

    ax.plot(
        x_data,
        y_pred,
        color="lightblue",
        linewidth=2,
        label=f"Slope={slope:.4f}, R²={r2:.4f}, MSE={mse:.4f}",
    )

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def generate_base_charts(conn: sqlite3.Connection, output_dir: Path, pbar: tqdm):
    cursor = conn.cursor()

    charts = [
        ("execution_time_seconds", "Execution Time (seconds)", "hist_execution_time_seconds.png"),
        ("total_function_calls", "Total Function Calls", "hist_total_function_calls.png"),
        ("primitive_calls", "Primitive Calls", "hist_primitive_calls.png"),
        ("total_time_seconds", "Total Time (seconds)", "hist_total_time_seconds.png"),
    ]

    for column, xlabel, filename in charts:
        pbar.set_postfix_str(f"Base histogram: {column}")
        cursor.execute(f"SELECT {column} FROM profiling_runs WHERE {column} IS NOT NULL")
        data = np.array([row[0] for row in cursor.fetchall()])
        if len(data) > 0:
            create_histogram(data, f"Distribution of {xlabel}", xlabel, output_dir / filename)
        pbar.update(1)

    scatterplots = [
        (
            "execution_time_seconds",
            "total_function_calls",
            "Execution Time vs Total Function Calls",
            "Total Function Calls",
            "Execution Time (seconds)",
            "scatter_exectime_by_totalcalls.png",
        ),
        (
            "execution_time_seconds",
            "primitive_calls",
            "Execution Time vs Primitive Calls",
            "Primitive Calls",
            "Execution Time (seconds)",
            "scatter_exectime_by_primcalls.png",
        ),
        (
            "total_time_seconds",
            "total_function_calls",
            "Total Time vs Total Function Calls",
            "Total Function Calls",
            "Total Time (seconds)",
            "scatter_totaltime_by_totalcalls.png",
        ),
        (
            "total_time_seconds",
            "primitive_calls",
            "Total Time vs Primitive Calls",
            "Primitive Calls",
            "Total Time (seconds)",
            "scatter_totaltime_by_primcalls.png",
        ),
    ]

    for y_col, x_col, title, xlabel, ylabel, filename in scatterplots:
        pbar.set_postfix_str(f"Base scatter: {y_col} by {x_col}")
        cursor.execute(
            f"""
            SELECT {y_col}, {x_col}
            FROM profiling_runs 
            WHERE {y_col} IS NOT NULL AND {x_col} IS NOT NULL
        """
        )
        data = cursor.fetchall()
        if len(data) > 0:
            y_data = np.array([row[0] for row in data])
            x_data = np.array([row[1] for row in data])
            create_scatterplot(x_data, y_data, title, xlabel, ylabel, output_dir / filename)
        pbar.update(1)


def generate_function_charts(conn: sqlite3.Connection, output_dir: Path, pbar: tqdm):
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT DISTINCT f.function_name, f.module_name, f.id, f.is_builtin, f.filename
        FROM functions f
        JOIN function_stats fs ON f.id = fs.function_id
        WHERE f.is_builtin = 0
    """
    )

    functions = cursor.fetchall()

    project_functions = []
    for func_name, module_name, func_id, is_builtin, filename in functions:
        if is_builtin or not filename or filename == "~":
            continue
        if "site-packages" in filename or "/lib/" in filename or "/lib64/" in filename:
            continue
        project_functions.append((func_name, module_name, func_id))

    for func_name, module_name, func_id in project_functions:
        pbar.set_postfix_str(f"Function: {module_name or 'unknown'}_{func_name[:30]}")
        safe_func_name = (
            func_name.replace("/", "_").replace("<", "").replace(">", "").replace(":", "_")
        )
        safe_module_name = (
            (module_name or "unknown")
            .replace("/", "_")
            .replace("<", "")
            .replace(">", "")
            .replace(":", "_")
        )

        func_dir = output_dir / "functions" / f"{safe_module_name}_{safe_func_name}"
        func_dir.mkdir(parents=True, exist_ok=True)

        cursor.execute("SELECT call_count FROM function_stats WHERE function_id = ?", (func_id,))
        call_counts = np.array([row[0] for row in cursor.fetchall()])
        if len(call_counts) > 0:
            create_histogram(
                call_counts,
                f"Call Count Distribution - {func_name}",
                "Call Count",
                func_dir / "hist_call_count.png",
            )

        cursor.execute(
            "SELECT primitive_call_count FROM function_stats WHERE function_id = ?", (func_id,)
        )
        prim_counts = np.array([row[0] for row in cursor.fetchall()])
        if len(prim_counts) > 0:
            create_histogram(
                prim_counts,
                f"Primitive Call Count Distribution - {func_name}",
                "Primitive Call Count",
                func_dir / "hist_primitive_call_count.png",
            )

        cursor.execute(
            "SELECT cumulative_time FROM function_stats WHERE function_id = ?", (func_id,)
        )
        cumulative_times = np.array([row[0] for row in cursor.fetchall()])
        if len(cumulative_times) > 0:
            create_histogram(
                cumulative_times,
                f"Cumulative Time Distribution - {func_name}",
                "Cumulative Time (seconds)",
                func_dir / "hist_cumulative_time.png",
            )

        cursor.execute(
            """
            SELECT cumulative_time, call_count 
            FROM function_stats 
            WHERE function_id = ?
        """,
            (func_id,),
        )
        data = cursor.fetchall()
        if len(data) > 0:
            times = np.array([row[0] for row in data])
            counts = np.array([row[1] for row in data])
            create_scatterplot(
                counts,
                times,
                f"Cumulative Time vs Call Count - {func_name}",
                "Call Count",
                "Cumulative Time (seconds)",
                func_dir / "scatter_cumtime_by_callcount.png",
            )

        cursor.execute(
            """
            SELECT cumulative_time, primitive_call_count 
            FROM function_stats 
            WHERE function_id = ?
        """,
            (func_id,),
        )
        data = cursor.fetchall()
        if len(data) > 0:
            times = np.array([row[0] for row in data])
            prim_counts = np.array([row[1] for row in data])
            create_scatterplot(
                prim_counts,
                times,
                f"Cumulative Time vs Primitive Call Count - {func_name}",
                "Primitive Call Count",
                "Cumulative Time (seconds)",
                func_dir / "scatter_cumtime_by_primcallcount.png",
            )

        pbar.update(1)


def generate_all_charts(db_path: str):
    conn = sqlite3.connect(db_path)
    output_dir = Path(db_path).parent

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(DISTINCT f.id)
        FROM functions f
        JOIN function_stats fs ON f.id = fs.function_id
        WHERE f.is_builtin = 0 
        AND f.filename IS NOT NULL 
        AND f.filename != '~'
        AND f.filename NOT LIKE '%site-packages%'
        AND f.filename NOT LIKE '%/lib/%'
        AND f.filename NOT LIKE '%/lib64/%'
    """
    )
    num_functions = cursor.fetchone()[0]

    total_charts = 8 + num_functions

    with tqdm(total=total_charts, desc="Generating charts") as pbar:
        generate_base_charts(conn, output_dir, pbar)
        generate_function_charts(conn, output_dir, pbar)

    conn.close()


def run_profiling_session(script_path: str, extra_args: list) -> bool:
    cmd = [script_path, "--n-concurrent-trials", "10"] + extra_args
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def get_latest_summary_folder(summaries_dir: Path) -> Optional[Path]:
    folders = sorted([f for f in summaries_dir.iterdir() if f.is_dir()])
    return folders[-1] if folders else None


def run_profiling_and_import(
    n_runs: int = 200,
    max_retries: int = 10,
    profiling_script: str = "./scripts_bash/start_profiling_session.sh",
    extra_args: list = None,
    summaries_dir: str = "profiling/summaries",
    base_dir: str = "profiling",
) -> str:
    extra_args = extra_args or []
    summaries_path = Path(summaries_dir)
    summaries_path.mkdir(parents=True, exist_ok=True)

    db_path = generate_db_path(base_dir)
    conn = create_database(db_path)
    conn.close()

    successful_runs = 0
    total_attempts = 0

    with tqdm(total=n_runs, desc="Profiling runs") as pbar:
        while successful_runs < n_runs and total_attempts < n_runs + max_retries:
            pbar.set_postfix_str(f"Attempt {total_attempts + 1}")
            total_attempts += 1

            if run_profiling_session(profiling_script, extra_args):
                latest_folder = get_latest_summary_folder(summaries_path)
                if latest_folder:
                    conn = sqlite3.connect(db_path)
                    if import_single_folder(conn, latest_folder):
                        successful_runs += 1
                        pbar.update(1)
                        pbar.set_postfix_str(f"Success {successful_runs}/{n_runs}")
                    conn.close()

    tqdm.write(
        f"\nCompleted {successful_runs}/{n_runs} successful runs in {total_attempts} attempts"
    )
    tqdm.write(f"Database: {db_path}")

    generate_all_charts(db_path)

    return db_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run profiling sessions and generate statistical analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--n-runs",
        type=int,
        default=200,
        help="Number of successful profiling runs to complete (default: 200)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=10,
        help="Maximum retry attempts beyond n-runs (default: 10)",
    )
    parser.add_argument(
        "--profiling-script",
        type=str,
        default="./scripts_bash/start_profiling_session.sh",
        help="Path to profiling script",
    )
    parser.add_argument(
        "--summaries-dir",
        type=str,
        default="profiling/summaries",
        help="Directory where profiling summaries are stored",
    )
    parser.add_argument(
        "--base-dir", type=str, default="profiling", help="Base directory for statistics output"
    )

    args, extra_args = parser.parse_known_args()

    try:
        run_profiling_and_import(
            n_runs=args.n_runs,
            max_retries=args.max_retries,
            profiling_script=args.profiling_script,
            extra_args=extra_args,
            summaries_dir=args.summaries_dir,
            base_dir=args.base_dir,
        )
    except Exception as e:
        tqdm.write(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
