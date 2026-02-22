import re
from ade_bench.parsers.base_parser import BaseParser, UnitTestStatus, ParserResult


class DbtParser(BaseParser):
    # Pattern to match individual test result lines for standard dbt
    # Examples:
    # "1 of 2 PASS test_one ........................................................... [PASS in 0.01s]"
    # "2 of 2 FAIL 1 test_two ......................................................... [FAIL 1 in 0.00s]"
    DBT_LEGACY_TEST_RESULT_PATTERN = (
        r"\d+\s+of\s+\d+\s+(PASS|FAIL|ERROR)(?:\s+\d+)?\s+(\S+)\s+\.+\s+\[(PASS|FAIL|ERROR)"
    )

    # Pattern to match individual test result lines for dbt-fusion
    # Examples:
    # "Passed [  1.66s] test  PUBLIC_dbt_test__audit.columns_in_project_snowflake"
    # "Failed [  0.50s] test  PUBLIC_dbt_test__audit.some_failing_test"
    DBT_FUSION_TEST_RESULT_PATTERN = r"(Passed|Failed)\s+\[\s*([\d.]+)s\]\s+test\s+(\S+)"

    # Pattern to match the summary line for standard dbt
    # Handles both formats: with and without NO-OP field
    DBT_LEGACY_TEST_SUMMARY_PATTERN = r"Done\.\s+PASS=(\d+)\s+WARN=(\d+)\s+ERROR=(\d+)\s+SKIP=(\d+)(?:\s+NO-OP=(\d+))?\s+TOTAL=(\d+)"

    # Pattern to match the summary line for dbt-fusion
    # Examples:
    # "Finished 'test' target 'dev' with 2 warnings in 7s 625ms"
    # "Finished 'test' target 'dev' with 1 error and 2 warnings in 6s 233ms"
    DBT_FUSION_SUMMARY_PATTERN = r"Finished\s+'test'\s+target\s+'(\w+)'\s+with\s+(?:(?:(\d+)\s+errors?(?:\s+and\s+(\d+)\s+warnings?)?)|(?:(\d+)\s+warnings?))\s+in\s+(\d+)s\s+(\d+)ms"

    # Pattern to match the expected test count line from run-dbt-test.sh
    # Example: "[ade-bench] expected_test_count=2"
    EXPECTED_TEST_COUNT_PATTERN = r"\[ade-bench\] expected_test_count=(\d+)"

    def __init__(self, parser_type: str = "dbt", **kwargs):
        """
        Initialize DbtParser with explicit parser type.

        Args:
            parser_type: Either "dbt" or "dbt-fusion" to specify which format to expect
            **kwargs: Additional arguments passed to BaseParser
        """
        super().__init__(**kwargs)
        self.parser_type = parser_type

    def _create_status_message(
        self,
        results: dict,
        summary_data: dict | None,
        has_compilation_error: bool,
        expected_test_count: int | None = None,
    ) -> str:
        """
        Create the final status message based on parsed results.

        The PASS/FAIL logic here mirrors harness._is_resolved() exactly:
        - FAIL if dbt_compile failed
        - FAIL if no test results (excluding dbt_compile)
        - FAIL if fewer tests ran than expected_test_count
        - FAIL if any test failed
        - PASS otherwise

        The counts shown include dbt_compile in the totals.
        expected_test_count (from run-tests.sh) does NOT include dbt_compile.
        """

        def _z(val: int) -> str:
            return f"{val:2d}"

        # Case 1: Compilation error
        if has_compilation_error:
            return "FAIL - dbt compilation error found"

        test_results = {k: v for k, v in results.items() if k != "dbt_compile"}

        # Step 1: Get the two types of results (excluding dbt_compile for comparison)
        individual_results = {
            "pass": sum(1 for status in test_results.values() if status == UnitTestStatus.PASSED),
            "fail": sum(1 for status in test_results.values() if status == UnitTestStatus.FAILED),
            "total": sum(
                1
                for status in test_results.values()
                if status in [UnitTestStatus.PASSED, UnitTestStatus.FAILED]
            ),
        }

        summary_results = None
        if summary_data:
            if self.parser_type == "dbt":
                summary_results = {
                    "pass": summary_data["pass"],
                    "fail": summary_data["error"],
                    "total": summary_data["total"],
                }
            elif self.parser_type == "dbt-fusion":
                # For dbt-fusion, we need to calculate test count from individual results
                assumed_total = sum(1 for status in test_results.values())
                summary_results = {
                    "fail": summary_data["fail"],
                    "total": assumed_total,
                    "pass": assumed_total - summary_data["fail"],
                }

        # Step 2: If neither, say no results
        if individual_results["total"] == 0 and (
            summary_results is None or summary_results["total"] == 0
        ):
            return "ERROR - no dbt test results found"

        # Step 3: Get counts from individual results or fall back to summary
        if individual_results["total"] > 0:
            pass_count = individual_results["pass"]
            fail_count = individual_results["fail"]
            test_count = individual_results["total"]  # excluding dbt_compile
        elif summary_results is not None:
            pass_count = summary_results["pass"]
            fail_count = summary_results["fail"]
            test_count = summary_results["total"]  # excluding dbt_compile
        else:
            return "ERROR - no dbt test results found"

        # Step 4: Build warnings list
        warnings = []

        # Check if individual and summary results don't match
        if individual_results["total"] > 0 and summary_results is not None:
            if (
                individual_results["pass"] != summary_results["pass"]
                or individual_results["fail"] != summary_results["fail"]
                or individual_results["total"] != summary_results["total"]
            ):
                warnings.append("mismatch between individual and summary results")

        # Only summary exists and has results
        elif (
            individual_results["total"] == 0
            and summary_results is not None
            and summary_results["total"] > 0
        ):
            warnings.append("no individual results found")

        # Only individual exists (this is NOT normal for dbt)
        elif (
            individual_results["total"] > 0
            and summary_results is None
            and self.parser_type == "dbt"
        ):
            warnings.append("no summary results found")

        # Only individual exists (this IS normal for dbt-fusion)
        elif (
            individual_results["total"] > 0
            and summary_results is None
            and self.parser_type == "dbt-fusion"
        ):
            pass  # No warning needed

        # Check if fewer tests ran than expected
        if expected_test_count is not None and test_count < expected_test_count:
            missing_count = expected_test_count - test_count
            warnings.append(f"{missing_count} test result(s) not found")

        # Construct warnings string
        warning_str = ""
        if warnings:
            warning_str = " [ WARNING: " + "; ".join(warnings) + " ]"

        # Determine PASS/FAIL using same logic as harness._is_resolved()
        # This ensures the log message matches the final result
        is_pass = fail_count == 0 and (
            expected_test_count is None or test_count >= expected_test_count
        )
        message_lead = "PASS" if is_pass else "FAIL"

        # Check if dbt_compile is in results (it's added for dbt projects)
        has_dbt_compile = "dbt_compile" in results
        compile_offset = 1 if has_dbt_compile else 0

        # Include dbt_compile in the displayed totals if present
        # dbt_compile always passes if we get here (compilation error handled above)
        pass_displayed = pass_count + compile_offset

        # Use expected total (plus dbt_compile if present) if available, otherwise use actual
        if expected_test_count is not None:
            total_displayed = expected_test_count + compile_offset
        else:
            total_displayed = test_count + compile_offset

        return f"{message_lead} - dbt test results - Pass:{_z(pass_displayed)}, Fail:{_z(fail_count)}, Total:{_z(total_displayed)}{warning_str}"

    def _has_test_results(self, content: str) -> bool:
        """Check if the content contains actual test results (not just compilation errors)."""
        # Look for test result lines or summary lines (both standard dbt and dbt-fusion formats)
        return bool(
            re.search(self.DBT_LEGACY_TEST_RESULT_PATTERN, content)
            or re.search(self.DBT_LEGACY_TEST_SUMMARY_PATTERN, content)
            or re.search(self.DBT_FUSION_TEST_RESULT_PATTERN, content)
            or re.search(self.DBT_FUSION_SUMMARY_PATTERN, content)
        )

    def _get_expected_test_count(self, content: str) -> int | None:
        """Get the expected test count from the '[ade-bench] expected_test_count=N' line."""
        match = re.search(self.EXPECTED_TEST_COUNT_PATTERN, content)
        return int(match.group(1)) if match else None

    def parse(self, content: str) -> ParserResult:
        # Check for compilation error - this should only happen when dbt fails to run at all
        # If we see test results, even with failures, compilation succeeded
        has_compilation_error = "Compilation Error" in content and not self._has_test_results(
            content
        )

        # Get expected test count from the "[ade-bench] expected_test_count=N" line
        expected_test_count = self._get_expected_test_count(content)

        # Initialize results
        results = {}
        if has_compilation_error:
            results = {"dbt_compile": UnitTestStatus.FAILED}
        else:
            results = {"dbt_compile": UnitTestStatus.PASSED}

        # Parse based on parser type
        if self.parser_type == "dbt":
            # Parse legacy dbt test results
            for match in re.finditer(self.DBT_LEGACY_TEST_RESULT_PATTERN, content):
                status = match.group(1)  # PASS, FAIL, or ERROR
                test_name = match.group(2)  # test name

                if status == "PASS":
                    results[test_name] = UnitTestStatus.PASSED
                elif status in ["FAIL", "ERROR"]:
                    results[test_name] = UnitTestStatus.FAILED

            # Parse legacy dbt summary
            summary_matches = list(re.finditer(self.DBT_LEGACY_TEST_SUMMARY_PATTERN, content))
            summary_data = None
            if summary_matches:
                summary_match = summary_matches[-1]
                summary_data = {
                    "pass": int(summary_match.group(1)),
                    "warn": int(summary_match.group(2)),
                    "error": int(summary_match.group(3)),
                    "skip": int(summary_match.group(4)),
                    "total": int(summary_match.group(6)),
                }

        elif self.parser_type == "dbt-fusion":
            # Parse dbt-fusion test results
            for match in re.finditer(self.DBT_FUSION_TEST_RESULT_PATTERN, content):
                status = match.group(1)  # Passed or Failed
                test_name = match.group(3)  # test name

                if status == "Passed":
                    results[test_name] = UnitTestStatus.PASSED
                elif status == "Failed":
                    results[test_name] = UnitTestStatus.FAILED

            # Parse dbt-fusion summary
            summary_matches = list(re.finditer(self.DBT_FUSION_SUMMARY_PATTERN, content))
            summary_data = None
            if summary_matches:
                summary_match = summary_matches[-1]
                # Group 2: errors (if present)
                # Group 3: warnings (if errors are present)
                # Group 4: warnings only (if no errors)
                # Group 5: seconds
                # Group 6: milliseconds
                errors = int(summary_match.group(2)) if summary_match.group(2) else 0
                warnings_with_errors = int(summary_match.group(3)) if summary_match.group(3) else 0
                warnings_only = int(summary_match.group(4)) if summary_match.group(4) else 0

                summary_data = {
                    "fail": errors,  # Map errors to fail for consistency
                    "warn": warnings_with_errors if errors > 0 else warnings_only,
                }

        # Now construct the final status message based on the parsed results
        status_message = self._create_status_message(
            results, summary_data, has_compilation_error, expected_test_count
        )

        return ParserResult(
            test_results=results,
            status_message=status_message,
            expected_test_count=expected_test_count,
        )
