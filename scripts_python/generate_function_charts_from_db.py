#!/usr/bin/env python3
import sys
import sqlite3
import argparse
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats as scipy_stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from tqdm import tqdm


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


def generate_charts_from_database(db_path: str):
    db_file = Path(db_path)

    if not db_file.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    output_dir = db_file.parent

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

    tqdm.write(f"\nCharts generated in: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate charts from profiling database")
    parser.add_argument("database", type=str, help="Path to profiling database (base.db)")

    args = parser.parse_args()

    try:
        generate_charts_from_database(args.database)
    except Exception as e:
        tqdm.write(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
