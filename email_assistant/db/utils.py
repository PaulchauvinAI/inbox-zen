import psycopg2
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

HOST = os.getenv("HOST")
USER = os.getenv("DB_USER")
PWD = os.getenv("DB_PWD")
DB = os.getenv("DB")
# Parse PORT to ensure it's a clean integer value by removing comments and quotes
PORT = os.getenv("PORT", "5432")

# Global variables to store connections across Lambda invocations
# This takes advantage of container reuse in AWS Lambda
_engine = None
_engine_created_time = 0
ENGINE_MAX_AGE = 300  # 5 minutes in seconds


def get_engine():
    """
    Get a SQLAlchemy engine, optimized for Lambda environment.

    In AWS Lambda, we can reuse connections during the lifetime of a container,
    but we shouldn't maintain long-lived connection pools since the container
    can be frozen/terminated at any time.
    """
    global _engine, _engine_created_time

    # Check if engine exists and isn't too old
    current_time = time.time()
    if _engine is None or (current_time - _engine_created_time) > ENGINE_MAX_AGE:
        if _engine is not None:
            logger.info("Closing stale database engine")
            _engine.dispose()

        logger.info("Creating new database engine")
        _engine = create_engine(
            f"postgresql://{USER}:{PWD}@{HOST}:{PORT}/{DB}?sslmode=require",
            # Don't use connection pooling for Lambda
            pool_pre_ping=True,  # Verify connection is still active
            pool_size=1,  # Minimal pool for Lambda
            max_overflow=0,  # No additional connections
            pool_recycle=ENGINE_MAX_AGE,  # Recycle connections after 5 minutes
        )
        _engine_created_time = current_time

    return _engine


def get_conn():
    """Get a psycopg2 connection to the database, optimized for Lambda."""
    try:
        conn = psycopg2.connect(
            host=HOST,
            database=DB,
            user=USER,
            password=PWD,
            port=PORT,
            sslmode="require",
            # Set shorter timeouts for Lambda environment
            connect_timeout=5,
            # Set TCP keepalives
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise


def execute_query(query, params=None, max_retries=3):
    """Execute a database query with proper error handling and retries.

    This function is optimized for AWS Lambda environments, ensuring proper
    connection management and implementing a retry mechanism for transient
    database errors.

    Args:
        query (str): SQL query to execute
        params (tuple, optional): Parameters for the query to prevent SQL injection
        max_retries (int): Maximum number of retry attempts for transient errors

    Returns:
        int: Number of affected rows from the query

    Raises:
        psycopg2.OperationalError: After max_retries attempts for transient database errors
        Exception: For other database errors that aren't retryable

    Note:
        This function properly manages database connections in Lambda,
        ensuring connections are closed even if exceptions occur.
    """
    conn = None
    cursor = None
    retries = 0

    while retries <= max_retries:
        try:
            conn = get_conn()
            cursor = conn.cursor()

            if params is None:
                cursor.execute(query)
            else:
                cursor.execute(query, params)

            conn.commit()
            return cursor.rowcount  # Return number of affected rows

        except psycopg2.OperationalError as e:
            # Operational errors are usually transient and can be retried
            retries += 1
            logger.warning(
                f"Database operational error (attempt {retries}/{max_retries}): {e}"
            )
            if retries > max_retries:
                logger.error(f"Max retries exceeded for query: {query}")
                raise
        except Exception as e:
            logger.error(f"Database error executing query: {e}")
            raise
        finally:
            # Clean up resources properly - important in Lambda to not leave connections open
            if cursor:
                cursor.close()
            if conn:
                conn.close()


def execute_batch(query, params_list):
    """Execute a batch of queries with the same SQL but different parameters.

    This function is optimized for AWS Lambda environments, ensuring proper
    connection management while executing multiple similar operations efficiently.
    It uses executemany for better performance when inserting/updating multiple records.

    Args:
        query (str): SQL query template to execute
        params_list (list): List of parameter tuples, one for each execution

    Returns:
        int: Number of affected rows from the batch operation

    Raises:
        Exception: For any database errors that occur during execution

    Note:
        - The function will perform no operation if params_list is empty
        - Connections are properly closed even if exceptions occur
        - The entire batch is rolled back if any individual operation fails
    """
    if not params_list:
        return 0

    conn = None
    cursor = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # Use executemany for batch operations
        cursor.executemany(query, params_list)
        conn.commit()
        return cursor.rowcount

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error executing batch query: {e}")
        raise
    finally:
        # Important to close connections in Lambda
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Function to explicitly close all database connections before Lambda terminates
def cleanup_db_resources():
    """Close database connections when Lambda execution is finishing"""
    global _engine
    if _engine is not None:
        logger.info("Closing database engine")
        _engine.dispose()
        _engine = None


if __name__ == "__main__":
    conn = get_conn()
    pass
