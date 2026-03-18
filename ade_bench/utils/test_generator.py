"""Utility for generating solution seed tests."""

from pathlib import Path
from typing import Optional

from ade_bench.harness_models import SolutionSeedConfig

EQUALITY_MACRO_FILENAME = "ade_bench_equality_test.sql"

_EQUALITY_MACRO_CONTENT = """\
{% macro ade_bench_equality_test(table_name, answer_keys, cols_to_exclude=[]) %}
    {% if not execute %}
        select 1 where 1=0
    {% else %}
        {% set ns = namespace(matched=false) %}
        {% set actual_rel = load_relation(ref(table_name)) %}

        {% if actual_rel is not none %}
            {% set actual_columns = adapter.get_columns_in_relation(actual_rel) %}
            {% set exclude_lower = cols_to_exclude | map('lower') | list %}

            {%- set actual_col_names = [] -%}
            {%- for col in actual_columns -%}
                {%- if col.name | lower not in exclude_lower -%}
                    {%- do actual_col_names.append(col.name | lower) -%}
                {%- endif -%}
            {%- endfor -%}
            {% set actual_set = actual_col_names | sort %}

            {% for answer_key in answer_keys %}
                {% if not ns.matched %}
                    {% set seed_rel = load_relation(ref(answer_key)) %}
                    {% if seed_rel is not none %}
                        {% set seed_columns = adapter.get_columns_in_relation(seed_rel) %}

                        {%- set seed_col_names = [] -%}
                        {%- for col in seed_columns -%}
                            {%- if col.name | lower not in exclude_lower -%}
                                {%- do seed_col_names.append(col.name | lower) -%}
                            {%- endif -%}
                        {%- endfor -%}
                        {% set seed_set = seed_col_names | sort %}

                        {% if actual_set == seed_set %}
                            {%- set compare_cols = [] -%}
                            {%- for col in actual_columns -%}
                                {%- if col.name | lower not in exclude_lower -%}
                                    {%- do compare_cols.append(col.quoted) -%}
                                {%- endif -%}
                            {%- endfor -%}
                            {% set compare_cols_csv = compare_cols | join(', ') %}

                            {% set query %}
                                with a_minus_b as (
                                    select {{ compare_cols_csv }} from {{ ref(answer_key) }}
                                    except
                                    select {{ compare_cols_csv }} from {{ ref(table_name) }}
                                ),
                                b_minus_a as (
                                    select {{ compare_cols_csv }} from {{ ref(table_name) }}
                                    except
                                    select {{ compare_cols_csv }} from {{ ref(answer_key) }}
                                ),
                                unioned as (
                                    select * from a_minus_b
                                    union all
                                    select * from b_minus_a
                                )
                                select count(*) as diff_count from unioned
                            {% endset %}

                            {% set result = run_query(query) %}
                            {% if result.rows[0][0] == 0 %}
                                {% set ns.matched = true %}
                            {% endif %}
                        {% endif %}
                    {% endif %}
                {% endif %}
            {% endfor %}
        {% endif %}

        {% if ns.matched %}
            select 1 where 1=0
        {% else %}
            select 1
        {% endif %}
    {% endif %}
{% endmacro %}
"""


def get_equality_macro_content() -> str:
    """Return the Jinja macro that implements equality test logic."""
    return _EQUALITY_MACRO_CONTENT


def generate_existence_test(table_name: str) -> str:
    """Generate an existence test for a solution seed table.

    Args:
        table_name: Name of the table to test

    Returns:
        Generated SQL test content
    """
    return f"""{{% set table_name = '{table_name}' %}}



-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
{{% set answer_key = 'solution__' + table_name %}}

{{% set table_a = load_relation(ref(answer_key)) %}}
{{% set table_b = load_relation(ref(table_name)) %}}

{{% if table_a is none or table_b is none %}}
    select 1
{{% else %}}
    select 1 where false
{{% endif %}}
"""


def generate_equality_test(table_name: str, config: Optional[SolutionSeedConfig] = None) -> str:
    """Generate an equality test for a solution seed table.

    Args:
        table_name: Name of the table to test
        config: Optional configuration for column inclusion/exclusion

    Returns:
        Generated SQL test content
    """
    # Build column lists based on config
    cols_to_include = []
    cols_to_exclude = []
    alternates = []

    if config:
        if config.include_columns:
            cols_to_include = config.include_columns
        if config.exclude_columns:
            cols_to_exclude = config.exclude_columns
        if config.alternates:
            alternates = config.alternates

    # Build the list of answer key seed names
    answer_keys = [f"solution__{table_name}"]
    for alt in alternates:
        answer_keys.append(f"solution__{alt}")

    # Format for Jinja list literal
    answer_keys_jinja = ", ".join(f"'{k}'" for k in answer_keys)

    include_list = (
        ",\n    ".join([f"'{col}'" for col in cols_to_include]) if cols_to_include else ""
    )
    exclude_list = (
        ",\n    ".join([f"'{col}'" for col in cols_to_exclude]) if cols_to_exclude else ""
    )

    # Build depends_on comments (needed so dbt builds seeds before this test)
    depends_on_lines = "\n".join(f"-- depends_on: {{{{ ref('{k}') }}}}" for k in answer_keys)

    return f"""-- Define columns to compare
{{% set table_name = '{table_name}' %}}
{{% set answer_keys = [{answer_keys_jinja}] %}}

{{% set cols_to_include = [
    {include_list}
] %}}

{{% set cols_to_exclude = [
    {exclude_list}
] %}}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{{{ ref(table_name) }}}}
{depends_on_lines}

{{{{ ade_bench_equality_test(table_name=table_name, answer_keys=answer_keys, cols_to_exclude=cols_to_exclude) }}}}
"""


def generate_solution_tests(
    table_name: str,
    test_dir: Path,
    config: Optional[SolutionSeedConfig] = None,
    macros_dir: Optional[Path] = None,
) -> None:
    """Generate both equality and existence tests for a solution seed table.

    Args:
        table_name: Name of the table to generate tests for
        test_dir: Directory to write the test files to
        config: Optional configuration for test generation
        macros_dir: Optional directory to write the equality macro to
    """
    # Ensure test directory exists
    test_dir.mkdir(parents=True, exist_ok=True)

    # Get excluded tests from config
    excluded_tests = set()
    if config and config.exclude_tests:
        excluded_tests = set(config.exclude_tests)

    # Generate equality test (unless excluded)
    if "equality_test" not in excluded_tests:
        equality_content = generate_equality_test(table_name, config)
        equality_path = test_dir / f"AUTO_{table_name}_equality.sql"
        equality_path.write_text(equality_content)

        # Write the macro alongside the tests so it can be copied to the dbt project
        if macros_dir is not None:
            macros_dir.mkdir(parents=True, exist_ok=True)
            macro_path = macros_dir / EQUALITY_MACRO_FILENAME
            if not macro_path.exists():
                macro_path.write_text(get_equality_macro_content())

    # Generate existence test (unless excluded)
    if "existence_test" not in excluded_tests:
        existence_content = generate_existence_test(table_name)
        existence_path = test_dir / f"AUTO_{table_name}_existence.sql"
        existence_path.write_text(existence_content)
