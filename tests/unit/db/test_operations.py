import unittest
from unittest.mock import patch, MagicMock, call
import pandas as pd
from email_assistant.db.operations import (
    get_connection,
    get_df_from_query,
    insert_from_df,
    insert_new_user,
    insert_new_email,
)


class TestDBOperations(unittest.TestCase):

    @patch("email_assistant.db.operations.get_engine")
    def test_get_connection(self, mock_get_engine):
        """Test that get_connection correctly yields a connection and closes it."""
        # Setup mock engine and connection
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_get_engine.return_value = mock_engine
        mock_engine.connect.return_value = mock_connection

        # Test normal execution
        with get_connection() as conn:
            self.assertEqual(conn, mock_connection)

        # Verify connection was closed
        mock_connection.close.assert_called_once()

        # Test exception handling
        mock_connection.reset_mock()
        with self.assertRaises(Exception):
            with get_connection() as conn:
                self.assertEqual(conn, mock_connection)
                raise Exception("Test exception")

        # Verify connection was still closed even after exception
        mock_connection.close.assert_called_once()

    @patch("email_assistant.db.operations.get_connection")
    @patch("email_assistant.db.operations.pd.read_sql")
    def test_get_df_from_query(self, mock_read_sql, mock_get_connection):
        """Test that get_df_from_query correctly executes a query and returns a DataFrame."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_context = MagicMock(__enter__=MagicMock(return_value=mock_conn))
        mock_get_connection.return_value = mock_context

        # Setup mock DataFrame
        expected_df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
        mock_read_sql.return_value = expected_df

        # Execute function
        result_df = get_df_from_query("SELECT * FROM test_table")

        # Verify query was converted to text
        mock_read_sql.assert_called_once()
        self.assertEqual(mock_read_sql.call_args[1]["con"], mock_conn)

        # Verify DataFrame was returned
        pd.testing.assert_frame_equal(result_df, expected_df)

    @patch("email_assistant.db.operations.get_connection")
    @patch("email_assistant.db.operations.pd.DataFrame.to_sql")
    def test_insert_from_df_small_batch(self, mock_to_sql, mock_get_connection):
        """Test inserting a small DataFrame (less than batch size)."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_context = MagicMock(__enter__=MagicMock(return_value=mock_conn))
        mock_get_connection.return_value = mock_context

        # Create test DataFrame
        test_df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})

        # Execute function
        insert_from_df(test_df, "test_table")

        # Verify to_sql was called once with the right parameters
        mock_to_sql.assert_called_once_with(
            name="test_table", con=mock_conn, if_exists="append", index=False
        )

    @patch("email_assistant.db.operations.get_connection")
    @patch("email_assistant.db.operations.pd.DataFrame.to_sql")
    def test_insert_from_df_large_batch(self, mock_to_sql, mock_get_connection):
        """Test inserting a large DataFrame (more than batch size)."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_context = MagicMock(__enter__=MagicMock(return_value=mock_conn))
        mock_get_connection.return_value = mock_context

        # Create test DataFrame with 150 rows (more than default batch size of 100)
        test_df = pd.DataFrame({"col1": range(150), "col2": ["a"] * 150})

        # Execute function with small batch size
        insert_from_df(test_df, "test_table", batch_size=50)

        # Verify to_sql was called three times (once for each batch)
        self.assertEqual(mock_to_sql.call_count, 3)

        # Verify calls to to_sql with the right parameters
        mock_to_sql.assert_has_calls(
            [
                call(name="test_table", con=mock_conn, if_exists="append", index=False),
                call(name="test_table", con=mock_conn, if_exists="append", index=False),
                call(name="test_table", con=mock_conn, if_exists="append", index=False),
            ]
        )

    @patch("email_assistant.db.operations.execute_query")
    def test_insert_new_user(self, mock_execute_query):
        """Test that insert_new_user correctly builds and executes the query."""
        # Execute function
        insert_new_user("test_user", "test@example.com")

        # Verify execute_query was called with the right SQL and parameters
        expected_query = """
        INSERT INTO users (username, email)
        VALUES (%s, %s)
        """
        expected_params = ("test_user", "test@example.com")
        mock_execute_query.assert_called_once_with(expected_query, expected_params)

    @patch("email_assistant.db.operations.encode_string")
    @patch("email_assistant.db.operations.execute_query")
    def test_insert_new_email(self, mock_execute_query, mock_encode_string):
        """Test that insert_new_email correctly builds and executes the query with password encoding."""
        # Setup encode_string mock
        mock_encode_string.side_effect = lambda x: f"encoded_{x}" if x else None

        # Execute function with all parameters
        insert_new_email(
            email="test@example.com",
            user_id=1,
            email_provider="gmail",
            pwd="password123",
            imap_login="test@example.com",
            imap_pwd="imap_password",
            imap_port=993,
            imap_server="imap.gmail.com",
            disconnected=False,
            last_error=None,
        )

        # Verify passwords were encoded
        mock_encode_string.assert_has_calls(
            [call("password123"), call("imap_password")]
        )

        # Verify execute_query was called with the right SQL and parameters
        expected_query = """
        INSERT INTO email_accounts (email, user_id, email_provider, pwd, imap_login, imap_pwd, imap_port, disconnected, last_error, imap_server)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        expected_params = (
            "test@example.com",
            1,
            "gmail",
            "encoded_password123",
            "test@example.com",
            "encoded_imap_password",
            993,
            False,
            None,
            "imap.gmail.com",
        )
        mock_execute_query.assert_called_once_with(expected_query, expected_params)

    @patch("email_assistant.db.operations.encode_string")
    @patch("email_assistant.db.operations.execute_query")
    def test_insert_new_email_minimal_params(
        self, mock_execute_query, mock_encode_string
    ):
        """Test that insert_new_email works with minimal required parameters."""
        # Execute function with minimal parameters
        insert_new_email(email="test@example.com", user_id=1, email_provider="gmail")

        # Verify encode_string was not called (no passwords)
        mock_encode_string.assert_not_called()

        # Verify execute_query was called with the right SQL and parameters
        expected_query = """
        INSERT INTO email_accounts (email, user_id, email_provider, pwd, imap_login, imap_pwd, imap_port, disconnected, last_error, imap_server)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        expected_params = (
            "test@example.com",
            1,
            "gmail",
            None,
            None,
            None,
            None,
            False,
            None,
            None,
        )
        mock_execute_query.assert_called_once_with(expected_query, expected_params)


if __name__ == "__main__":
    unittest.main()
