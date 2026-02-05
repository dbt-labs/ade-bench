"""Utility for generating solution seed tests."""
from pathlib import Path
from typing import Optional

from ade_bench.harness_models import SolutionSeedConfig


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

{{% set table_a = adapter.get_relation(database=target.database, schema=target.schema, identifier=answer_key) %}}
{{% set table_b = adapter.get_relation(database=target.database, schema=target.schema, identifier=table_name) %}}

{{% if table_a is none or table_b is none %}}
    select 1
{{% else %}}
    select 1 where false
{{% endif %}}
"""


def generate_equality_test(
    table_name: str,
    config: Optional[SolutionSeedConfig] = None
) -> str:
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

    # Format columns as lists
    include_list = ",\n    ".join([f"'{col}'" for col in cols_to_include]) if cols_to_include else ""
    exclude_list = ",\n    ".join([f"'{col}'" for col in cols_to_exclude]) if cols_to_exclude else ""

#######################################################
# Standard test with no alternates
#######################################################
    if not alternates:
        return f"""-- Define columns to compare
{{% set table_name = '{table_name}' %}}

{{% set cols_to_include = [
    {include_list}
] %}}

{{% set cols_to_exclude = [
    {exclude_list}
] %}}



-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
{{% set answer_key = 'solution__' + table_name %}}

-- depends_on: {{{{ ref(answer_key) }}}}
-- depends_on: {{{{ ref(table_name) }}}}

{{% set table_a = adapter.get_relation(database=target.database, schema=target.schema, identifier=answer_key) %}}
{{% set table_b = adapter.get_relation(database=target.database, schema=target.schema, identifier=table_name) %}}

{{% if table_a is none or table_b is none %}}
    select 1
{{% else %}}
    {{{{ dbt_utils.test_equality(
        model=ref(answer_key),
        compare_model=ref(table_name),
        compare_columns=cols_to_include,
        exclude_columns=cols_to_exclude
    ) }}}}
{{% endif %}}
"""

#######################################################
# Test with alternates
#######################################################
    # Build answer key variables
    answer_keys = [table_name] + alternates

    # Create text blocks
    jinja_vars_block = ""
    depends_on_block = ""
    check_relation_block = ""
    test_cte_block = ""
    row_count_block = ""
    union_block = ""

    for i, alternate_name in enumerate(answer_keys):
        numbered_key = f"answer_key_{i+1}"

        union_statement = "\n\tunion all" if i < len(answer_keys) - 1 else ""

        jinja_vars_block += f"{{% set {numbered_key} = 'solution__{alternate_name}' %}}\n"
        depends_on_block += f"-- depends_on: {{{{ ref({numbered_key}) }}}}\n"
        check_relation_block += f"{{% set {numbered_key}_table = adapter.get_relation(database=target.database, schema=target.schema, identifier={numbered_key}) %}}\n"

        test_cte_block += f"""
{numbered_key}_test as (
    {{% if submitted_table is none or {numbered_key}_table is none %}}
        select 1
    {{% else %}}
        {{{{ dbt_utils.test_equality(
            model=ref({numbered_key}),
            compare_model=ref(table_name),
            compare_columns=cols_to_include,
            exclude_columns=cols_to_exclude
        ) }}}}
    {{% endif %}}
),
"""

        row_count_block += f"""
{numbered_key}_row_count as (
    select
        '{alternate_name}' as seed_table,
        count(*) as row_count
    from {numbered_key}_test
),
"""

        union_block += f"""
    select
        c.seed_table,
        c.row_count,
        t.*
    from {numbered_key}_row_count c
    left join {numbered_key}_test t
        on 1=1
    {union_statement}
"""




    FINAL_QUERY =f"""-- Define columns to compare
{{% set table_name = '{table_name}' %}}
{jinja_vars_block}

{{% set cols_to_include = [
    {include_list}
] %}}

{{% set cols_to_exclude = [
    {exclude_list}
] %}}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{{{ ref(table_name) }}}}
{depends_on_block}

{{% set submitted_table = adapter.get_relation(database=target.database, schema=target.schema, identifier=table_name) %}}
{check_relation_block}

with
{test_cte_block}

{row_count_block}

combined as (
    {union_block}
),

final as (
    select *, min(row_count) over () min_row_count from combined
)

select * from final where min_row_count != 0 and row_count != 0
"""

    return FINAL_QUERY



def generate_solution_tests(
    table_name: str,
    test_dir: Path,
    config: Optional[SolutionSeedConfig] = None
) -> None:
    """Generate both equality and existence tests for a solution seed table.

    Args:
        table_name: Name of the table to generate tests for
        test_dir: Directory to write the test files to
        config: Optional configuration for test generation
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

    # Generate existence test (unless excluded)
    if "existence_test" not in excluded_tests:
        existence_content = generate_existence_test(table_name)
        existence_path = test_dir / f"AUTO_{table_name}_existence.sql"
        existence_path.write_text(existence_content)