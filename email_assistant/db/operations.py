from email_assistant.db.utils import (
    get_engine,
    execute_query,
)
from email_assistant.utils.email_passwords import encode_string
from sqlalchemy import text
from contextlib import contextmanager
import pandas as pd
import logging

# Configure logging
logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    """Context manager for handling database connections in Lambda environment

    Creates and manages a database connection optimized for Lambda execution environment,
    ensuring proper connection cleanup regardless of normal execution or exceptions.

    Yields:
        SQLAlchemy Connection: An active database connection

    Raises:
        Exception: Propagates any database connection errors

    Note:
        This context manager is designed to be used with the 'with' statement,
        providing automatic connection cleanup to prevent connection leaks in
        Lambda, which can lead to performance issues over time.
    """
    engine = get_engine()
    connection = engine.connect()
    try:
        yield connection
    except Exception as e:
        logger.error(f"Transaction error: {e}")
        raise
    finally:
        connection.close()


def get_df_from_query(query):
    """Execute a query and return results as a pandas DataFrame

    Runs a SQL query against the database and converts the results into a
    pandas DataFrame for easier data manipulation and analysis.

    Args:
        query (str): The SQL query to execute

    Returns:
        pandas.DataFrame: DataFrame containing the query results

    Raises:
        Exception: Any database or query execution errors

    Note:
        - Uses the get_connection context manager to ensure proper connection handling
        - Optimized for Lambda to ensure connections are properly managed
        - Converts database rows to DataFrame for easier data manipulation
    """
    query = text(query)
    try:
        with get_connection() as conn:
            df = pd.read_sql(query, con=conn)
            logger.info(f"Query returned {len(df)} rows")
            return df
    finally:
        # Ensure we clean up resources even if there's an error
        pass


def insert_from_df(df, table_name, batch_size=100):
    """Append data from dataframe df to the table table_name with batching

    Inserts pandas DataFrame rows into a database table, using an optimized
    batching approach to prevent timeouts in Lambda environments when dealing
    with larger datasets.

    Args:
        df (pandas.DataFrame): DataFrame containing the data to insert
        table_name (str): Name of the database table to insert into
        batch_size (int, optional): Number of rows to insert in each batch. Defaults to 100.
            Smaller batch sizes reduce memory usage and prevent timeouts.

    Returns:
        None

    Note:
        - Uses the get_connection context manager to ensure proper connection handling
        - For large DataFrames, data is inserted in smaller batches to avoid Lambda timeouts
        - For smaller DataFrames (size <= batch_size), data is inserted in a single operation
        - All operations use the SQLAlchemy to_sql method with 'append' mode
    """
    try:
        with get_connection() as conn:
            # Use smaller batch size for Lambda to avoid timeouts
            if len(df) > batch_size:
                for i in range(0, len(df), batch_size):
                    chunk = df.iloc[i : i + batch_size]
                    chunk.to_sql(
                        name=table_name, con=conn, if_exists="append", index=False
                    )
                    logger.info(
                        f"Inserted batch {i//batch_size + 1} of {(len(df) // batch_size) + 1} into {table_name}"
                    )
            else:
                df.to_sql(name=table_name, con=conn, if_exists="append", index=False)
                logger.info(f"Inserted {len(df)} rows into {table_name}")
    finally:
        # Ensure we don't leave any idle connections
        pass


def insert_new_user(user_name, user_email):
    """Insert a new user into the users table"""
    try:
        query = """
        INSERT INTO users (username, email)
        VALUES (%s, %s)
        """
        params = (user_name, user_email)
        return execute_query(query, params)
    finally:
        # Handle any cleanup if needed
        pass


def insert_new_email(
    email,
    user_id,
    email_provider,
    pwd=None,
    imap_login=None,
    imap_pwd=None,
    imap_port=None,
    imap_server=None,
    disconnected=False,
    last_error=None,
):
    """Insert a new email account into the email_accounts table

    This function adds a new email account to the database with the provided credentials
    and configuration. It handles secure password storage by encoding sensitive
    information before storing in the database.

    Args:
        email (str): The email address to add
        user_id (int): The ID of the user who owns this email account
        email_provider (str): The provider of the email service (e.g., 'gmail', 'outlook')
        pwd (str, optional): Password for the email account. Will be encrypted before storage.
        imap_login (str, optional): Login username for IMAP connection (if different from email)
        imap_pwd (str, optional): IMAP-specific password. Will be encrypted before storage.
        imap_port (int, optional): Port number for IMAP connection
        imap_server (str, optional): IMAP server address
        disconnected (bool, optional): Whether the account is in disconnected state. Defaults to False.
        last_error (str, optional): Last error message if the account failed to connect

    Returns:
        int: Number of rows affected (1 if successful)

    Note:
        Passwords are encrypted before storage using the encode_string function.
        For OAuth-authenticated providers, pwd may be an OAuth token.
    """
    try:
        query = """
        INSERT INTO email_accounts (email, user_id, email_provider, pwd, imap_login, imap_pwd, imap_port, disconnected, last_error, imap_server)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            email,
            user_id,
            email_provider,
            encode_string(pwd) if pwd else None,
            imap_login,
            encode_string(imap_pwd) if imap_pwd else None,
            imap_port,
            disconnected,
            last_error,
            imap_server,
        )

        return execute_query(query, params)
    finally:
        # Handle any cleanup if needed
        pass
