"""Regression tests for DbtParser's dbt-fusion output handling.

The Fusion 2.x fixtures are lifted verbatim from tmux panes captured by the CI
"Check Regressions" workflow (run 36637759578) after dbt Fusion 2.0.6 changed its
console format. The Fusion 1.x fixtures reproduce the examples the parser was
originally written against.
"""

from ade_bench.parsers.base_parser import UnitTestStatus
from ade_bench.parsers.dbt_parser import DbtParser

FUSION_V1_ALL_PASS = """
[ade-bench] expected_test_count=2
Passed [  1.66s] test  PUBLIC_dbt_test__audit.columns_in_project_snowflake
Passed [  0.21s] test  PUBLIC_dbt_test__audit.rows_in_project_snowflake
Finished 'test' target 'dev' with 2 warnings in 7s 625ms
"""

FUSION_V1_ONE_FAIL = """
[ade-bench] expected_test_count=2
Passed [  1.66s] test  PUBLIC_dbt_test__audit.columns_in_project_snowflake
Failed [  0.50s] test  PUBLIC_dbt_test__audit.some_failing_test
Finished 'test' target 'dev' with 1 error and 2 warnings in 6s 233ms
"""

# airbnb001, sage agent: 10 tests, all pass. Leading whitespace is how the
# progress renderer right-aligns the status column in the captured pane.
FUSION_V2_ALL_PASS = """
[ade-bench] expected_test_count=10
       dbt 2.0.6
   Loading profiles.yml
                                                                     Passed test  AUTO_daily_agg_reviews_existence [1 of 10 in 0.01s]
                                                                     Passed test  AUTO_dim_hosts_existence [2 of 10 in 0.01s]
                                                                     Passed test  AUTO_dim_listings_existence [3 of 10 in 0.01s]
                                                                     Passed test  AUTO_dim_listings_hosts_existence [4 of 10 in 0.01s]
                                                                     Passed test  AUTO_mom_agg_reviews_existence [5 of 10 in 0.01s]
                                                                     Passed test  AUTO_daily_agg_reviews_equality [6 of 10 in 0.08s]
                                                                     Passed test  AUTO_wow_agg_reviews_equality [7 of 10 in 0.10s]
                                                                     Passed test  AUTO_monthly_agg_reviews_equality [8 of 10 in 0.10s]
                                                                     Passed test  AUTO_dim_listings_hosts_equality [9 of 10 in 0.20s]
                                                                     Passed test  AUTO_mom_agg_reviews_equality [10 of 10 in 0.20s]
===================================================================== Errors and Warnings ======================================================================
[warning] [UnusedResourceConfigPath (dbt1097)]: Configuration paths exist in your dbt_project.yml file which do not apply to any resources.
There are 2 unused configuration paths:
- seeds.airbnb.RAW_LISTINGS
- seeds.airbnb.broken_model_results
====================================================================== Execution Summary =======================================================================
Finished 'test' with 1 warning for target 'dev' [716ms]
Processed: 10 tests
Summary: 10 total | 10 success
[ade-bench] Checking for failing equality tests...
[ade-bench] No failing equality tests found
"""

# asana001, none agent: both tests fail. Failed lines carry the test path. The
# "Test Failures" section is informational; the parser reads the per-test lines.
FUSION_V2_ALL_FAIL = """
[ade-bench] expected_test_count=2
       dbt 2.0.6
   Loading profiles.yml
                                                                     Failed test  AUTO_asana__task_existence (tests/AUTO_asana__task_existence.sql) [1 of 2 in 0.02s]
                                                                     Failed test  AUTO_asana__task_equality (tests/AUTO_asana__task_equality.sql) [2 of 2 in 0.01s]
======================================================================== Test Failures =========================================================================
Test failed (1 failed row(s)): AUTO_asana__task_equality
Test failed (1 failed row(s)): AUTO_asana__task_existence
====================================================================== Execution Summary =======================================================================
Finished 'test' with 4 warnings and 2 errors for target 'dev' [1.2s]
Processed: 2 tests
Summary: 2 total | 2 error
[ade-bench] Checking for failing equality tests...
[ade-bench] Found 1 failing equality test(s): ['AUTO_asana__task_equality']
"""

# helixops_saas004, none agent: mixed pass/fail.
FUSION_V2_MIXED = """
[ade-bench] expected_test_count=4
                                                                     Passed test  AUTO_int_workspace_roster_existence [1 of 4 in 0.01s]
                                                                     Passed test  AUTO_dim_accounts_existence [2 of 4 in 0.01s]
                                                                     Failed test  AUTO_int_workspace_roster_equality (tests/AUTO_int_workspace_roster_equality.sql) [3 of 4 in 0.03s]
                                                                     Passed test  AUTO_dim_accounts_equality [4 of 4 in 0.04s]
======================================================================== Test Failures =========================================================================
Test failed (1 failed row(s)): AUTO_int_workspace_roster_equality
====================================================================== Execution Summary =======================================================================
Finished 'test' with 1 error for target 'dev' [349ms]
Processed: 4 tests
Summary: 4 total | 3 success | 1 error
"""

# airbnb010, none agent: the selector matched nothing, so no tests ran and the
# only Summary line in the pane belongs to the preceding `dbt seed`.
FUSION_V2_NOTHING_RAN = """
Finished 'seed' with 6 warnings for target 'dev' [1.1s]
Processed: 3 seeds
Summary: 3 total | 2 success | 1 warn
[ade-bench] expected_test_count=4
       dbt 2.0.6
[warning] [NoNodesForSelectionCriteria (dbt1092)]: The selection criterion 'test_type:singular' does not match any enabled nodes
[warning] [NoNodesSelected (dbt1601)]: Nothing to do. Try checking your model configs and model specification args
====================================================================== Execution Summary =======================================================================
Finished 'test' with 7 warnings for target 'dev' [795ms]
[ade-bench] Checking for failing equality tests...
[ade-bench] No failing equality tests found
"""


def _tests_only(result):
    return {k: v for k, v in result.test_results.items() if k != "dbt_compile"}


def test_fusion_v1_all_pass_still_parses():
    result = DbtParser(parser_type="dbt-fusion").parse(FUSION_V1_ALL_PASS)
    assert set(_tests_only(result).values()) == {UnitTestStatus.PASSED}
    assert len(_tests_only(result)) == 2
    assert result.status_message.startswith("PASS")


def test_fusion_v1_failure_still_parses():
    result = DbtParser(parser_type="dbt-fusion").parse(FUSION_V1_ONE_FAIL)
    tests = _tests_only(result)
    assert tests["PUBLIC_dbt_test__audit.some_failing_test"] == UnitTestStatus.FAILED
    assert result.status_message.startswith("FAIL")
    assert "mismatch" not in result.status_message


def test_fusion_v2_all_pass():
    result = DbtParser(parser_type="dbt-fusion").parse(FUSION_V2_ALL_PASS)
    tests = _tests_only(result)
    assert len(tests) == 10
    assert set(tests.values()) == {UnitTestStatus.PASSED}
    assert result.expected_test_count == 10
    assert result.status_message == "PASS - dbt test results - Pass:11, Fail: 0, Total:11"


def test_fusion_v2_all_fail():
    result = DbtParser(parser_type="dbt-fusion").parse(FUSION_V2_ALL_FAIL)
    tests = _tests_only(result)
    assert tests == {
        "AUTO_asana__task_existence": UnitTestStatus.FAILED,
        "AUTO_asana__task_equality": UnitTestStatus.FAILED,
    }
    assert result.status_message == "FAIL - dbt test results - Pass: 1, Fail: 2, Total: 3"


def test_fusion_v2_mixed():
    result = DbtParser(parser_type="dbt-fusion").parse(FUSION_V2_MIXED)
    tests = _tests_only(result)
    assert len(tests) == 4
    assert tests["AUTO_int_workspace_roster_equality"] == UnitTestStatus.FAILED
    assert sum(1 for v in tests.values() if v == UnitTestStatus.PASSED) == 3
    assert result.status_message == "FAIL - dbt test results - Pass: 4, Fail: 1, Total: 5"


def test_fusion_v2_seed_summary_before_real_test_run_is_ignored():
    # A pane normally holds the `dbt seed` Summary followed by the `dbt test` Summary; only
    # the latter may feed summary_data, otherwise the counts mismatch and a warning appears.
    content = FUSION_V2_NOTHING_RAN.split("[ade-bench] expected_test_count=4")[0] + FUSION_V2_MIXED
    result = DbtParser(parser_type="dbt-fusion").parse(content)
    assert len(_tests_only(result)) == 4
    assert result.status_message == "FAIL - dbt test results - Pass: 4, Fail: 1, Total: 5"


def test_fusion_v2_warned_test_is_not_counted_as_passed():
    # Fusion prints "Warned" for a warn-severity test with failing rows. As with WARN in
    # dbt Core, it is neither a pass nor a fail; expected_test_count then keeps the task
    # unresolved rather than letting it pass on the remaining tests.
    content = FUSION_V2_MIXED.replace(
        "Failed test  AUTO_int_workspace_roster_equality (tests/AUTO_int_workspace_roster_equality.sql)",
        "Warned test  AUTO_int_workspace_roster_equality",
    ).replace("Summary: 4 total | 3 success | 1 error", "Summary: 4 total | 3 success | 1 warn")
    result = DbtParser(parser_type="dbt-fusion").parse(content)
    tests = _tests_only(result)
    assert "AUTO_int_workspace_roster_equality" not in tests
    assert len(tests) == 3 and result.expected_test_count == 4
    assert result.status_message.startswith("FAIL")
    assert "1 test result(s) not found" in result.status_message


def test_fusion_v2_summary_with_hyphenated_label_and_no_target():
    # Fusion's Summary labels include "no-op", and "for target" is optional in its formatter.
    content = FUSION_V2_ALL_PASS.replace(
        "Finished 'test' with 1 warning for target 'dev' [716ms]",
        "Finished 'test' successfully [716ms]",
    ).replace("Summary: 10 total | 10 success", "Summary: 10 total | 10 success | 2 no-op")
    result = DbtParser(parser_type="dbt-fusion").parse(content)
    assert result.status_message == "PASS - dbt test results - Pass:11, Fail: 0, Total:11"


def test_fusion_v2_nothing_ran_reports_no_results():
    # The `dbt seed` Summary line must not be mistaken for test results.
    result = DbtParser(parser_type="dbt-fusion").parse(FUSION_V2_NOTHING_RAN)
    assert _tests_only(result) == {}
    assert result.status_message == "ERROR - no dbt test results found"


def test_legacy_dbt_parser_unaffected():
    content = """
[ade-bench] expected_test_count=2
1 of 2 PASS test_one ........................................................... [PASS in 0.01s]
2 of 2 FAIL 1 test_two ......................................................... [FAIL 1 in 0.00s]
Done. PASS=1 WARN=0 ERROR=1 SKIP=0 TOTAL=2
"""
    result = DbtParser(parser_type="dbt").parse(content)
    tests = _tests_only(result)
    assert tests == {"test_one": UnitTestStatus.PASSED, "test_two": UnitTestStatus.FAILED}
    assert result.status_message.startswith("FAIL")
