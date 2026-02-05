"""
Snowflake setup functions.
"""

import logging
import os
from typing import Dict, Any, Optional
from .setup_utils import generate_task_snowflake_credentials

try:
    import snowflake.connector

    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False
    snowflake = None


def _execute_queries(cursor, queries: str, logger: logging.Logger):
    """Execute multiple SQL queries separated by semicolons."""
    for query in queries.split(";"):
        query = query.strip()
        if query:  # Skip empty queries
            try:
                cursor.execute(query)
            except Exception as e:
                logger.error(f"Error executing Snowflake query: {query[:100]}... - {e}")
                raise


def _get_snowflake_connection():
    """Get Snowflake connection using environment variables for setup operations."""
    if not SNOWFLAKE_AVAILABLE:
        raise RuntimeError(
            "Snowflake connector not available. Please install snowflake-connector-python."
        )

    # Get Snowflake credentials from environment
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    password = os.getenv("SNOWFLAKE_PASSWORD")

    if not all([account, user, password]):
        raise ValueError(
            "Missing required Snowflake credentials. Please set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and SNOWFLAKE_PASSWORD environment variables."
        )

    # Extract account identifier
    if ".snowflakecomputing.com" in account:
        account_id = account.replace(".snowflakecomputing.com", "")
    else:
        account_id = account

    conn = snowflake.connector.connect(account=account_id, user=user, password=password)

    return conn


def _clone_database(
    source_db: str, target_db: str, logger: logging.Logger
) -> tuple[bool, Optional[str]]:
    """Clone a Snowflake database.

    Returns:
        Tuple of (success, error_message). error_message is None on success.
    """
    try:
        with _get_snowflake_connection() as conn:
            cursor = conn.cursor()

            # Check if source database exists
            check_source_query = f"SHOW DATABASES LIKE '{source_db}'"
            cursor.execute(check_source_query)
            source_exists = cursor.fetchone() is not None

            if not source_exists:
                error_msg = f"Source database '{source_db}' does not exist. Run 'ade migrate duckdb-to-snowflake' first."
                logger.error(error_msg)
                return False, error_msg

            # Drop target database if it exists
            drop_target_query = f"DROP DATABASE IF EXISTS {target_db}"
            cursor.execute(drop_target_query)

            # Clone the database
            clone_query = f"CREATE DATABASE {target_db} CLONE {source_db}"
            cursor.execute(clone_query)

            return True, None

    except Exception as e:
        error_msg = f"Failed to clone database '{source_db}' to '{target_db}': {e}"
        logger.error(error_msg)
        return False, error_msg


def _create_user_and_role(
    creds: Dict[str, str], logger: logging.Logger
) -> tuple[bool, Optional[str]]:
    """Create user and role for the database.

    Returns:
        Tuple of (success, error_message). error_message is None on success.
    """
    try:
        with _get_snowflake_connection() as conn:
            cursor = conn.cursor()

            # Use the target database
            use_db_query = f"USE DATABASE {creds['database']}"
            cursor.execute(use_db_query)

            # Drop and create role
            admin_role = os.getenv("SNOWFLAKE_ROLE")
            if not admin_role:
                error_msg = "SNOWFLAKE_ROLE environment variable not set"
                logger.error(error_msg)
                return False, error_msg

            role_query = f"""
                DROP ROLE IF EXISTS {creds['role']};
                CREATE ROLE {creds['role']};
                GRANT ROLE {creds['role']} TO ROLE {admin_role};
            """
            _execute_queries(cursor, role_query, logger)

            # Create grants query template
            grants_template = """
                GRANT USAGE ON WAREHOUSE {warehouse} to {role};
                GRANT USAGE ON DATABASE {database} TO ROLE {role};
                GRANT CREATE SCHEMA ON DATABASE {database} TO ROLE {role};
                GRANT CREATE TABLE ON ALL SCHEMAS IN DATABASE {database} TO ROLE {role};
                GRANT CREATE TABLE ON FUTURE SCHEMAS IN DATABASE {database} TO ROLE {role};
                GRANT CREATE VIEW ON ALL SCHEMAS IN DATABASE {database} TO ROLE {role};
                GRANT CREATE VIEW ON FUTURE SCHEMAS IN DATABASE {database} TO ROLE {role};
                GRANT USAGE, MODIFY ON ALL SCHEMAS IN DATABASE {database} TO ROLE {role};
                GRANT USAGE, MODIFY ON FUTURE SCHEMAS IN DATABASE {database} TO ROLE {role};
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {database}.PUBLIC TO ROLE {role};
                GRANT SELECT, INSERT, UPDATE, DELETE ON FUTURE TABLES IN SCHEMA {database}.PUBLIC TO ROLE {role};
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL VIEWS IN SCHEMA {database}.PUBLIC TO ROLE {role};
                GRANT SELECT, INSERT, UPDATE, DELETE ON FUTURE VIEWS IN SCHEMA {database}.PUBLIC TO ROLE {role};
                GRANT OWNERSHIP ON DATABASE {database} TO ROLE {role} COPY CURRENT GRANTS;
                GRANT OWNERSHIP ON ALL SCHEMAS IN DATABASE {database} TO ROLE {role} COPY CURRENT GRANTS;
                GRANT OWNERSHIP ON ALL TABLES IN DATABASE {database} TO ROLE {role} COPY CURRENT GRANTS;
                GRANT OWNERSHIP ON ALL VIEWS IN DATABASE {database} TO ROLE {role} COPY CURRENT GRANTS;
            """

            # Grant privileges to task role
            task_grants_query = grants_template.format(
                warehouse=creds["warehouse"], database=creds["database"], role=creds["role"]
            )
            _execute_queries(cursor, task_grants_query, logger)

            # Drop and create user
            user_query = f"""
                DROP USER IF EXISTS {creds['user']};
                CREATE USER {creds['user']}
                PASSWORD = '{creds['password']}'
                TYPE = LEGACY_SERVICE
                DEFAULT_ROLE = {creds['role']};
                GRANT ROLE {creds['role']} TO USER {creds['user']};
            """
            _execute_queries(cursor, user_query, logger)

            return True, None

    except Exception as e:
        error_msg = f"Failed to create user and role: {e}"
        logger.error(error_msg)
        return False, error_msg


def setup_snowflake(
    terminal,
    session,
    task_id: str,
    variant: Dict[str, Any],
    trial_handler,
    logger: logging.Logger = None,
) -> tuple[bool, Optional[str]]:
    """Setup Snowflake by cloning database and creating user/role.

    Args:
        terminal: Terminal instance
        session: Tmux session
        task_id: Task identifier
        variant: Variant configuration
        trial_handler: Trial handler instance
        logger: Logger instance for recording errors

    Returns:
        Tuple of (success, error_message). error_message is None on success.
    """
    # Fallback to module-level logger if none provided
    if logger is None:
        logger = logging.getLogger(__name__)

    creds = generate_task_snowflake_credentials(task_id)
    source_db = variant.get("db_name")
    target_db = creds["database"]

    # Clone the database
    success, error_msg = _clone_database(source_db, target_db, logger)
    if not success:
        return False, error_msg

    # Create user and role
    success, error_msg = _create_user_and_role(creds, logger)
    if not success:
        return False, error_msg

    return True, None
