"""
Database schema information and table definitions for exploring database structure.

Tables in the database:
- profiles: User profile information
- stripe_customers: Stripe customer information
- contact_requests: Contact request information
- email_accounts: Email account information
- outlook_states: Outlook authentication states
- received_emails: Received email information
"""

import logging
from psycopg2 import sql
from contextlib import contextmanager
from email_assistant.db.utils import get_conn

# Configure logging
logger = logging.getLogger(__name__)


@contextmanager
def get_cursor():
    """Context manager for database cursors with proper error handling

    Creates a database connection and cursor, manages the transaction lifecycle,
    and ensures proper cleanup regardless of execution outcome. Automatically
    commits successful transactions and rolls back failed ones.

    Yields:
        psycopg2.cursor: A database cursor object for executing SQL commands

    Raises:
        Exception: Re-raises any database errors after performing rollback

    Example:
        ```
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()
        ```

    Note:
        Connections and cursors are always properly closed in the finally block,
        making this safe to use in Lambda environments where connection leaks can be problematic.
    """
    conn = None
    cursor = None
    try:
        conn = get_conn()
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


class DatabaseSchema:
    """Utility class to interact with database schema information"""

    @staticmethod
    def get_tables():
        """Get all tables in the public schema"""
        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """
            )
            return [table[0] for table in cursor.fetchall()]

    @staticmethod
    def get_table_columns(table_name, include_details=True):
        """Get column information for a specific table

        Args:
            table_name: Name of the table to inspect
            include_details: If True, include detailed type information
                            If False, only return column names (faster)
        """
        with get_cursor() as cursor:
            if include_details:
                cursor.execute(
                    sql.SQL(
                        """
                        SELECT column_name, data_type, character_maximum_length, 
                               numeric_precision, numeric_scale
                        FROM information_schema.columns 
                        WHERE table_name = {}
                        ORDER BY ordinal_position
                    """
                    ).format(sql.Literal(table_name))
                )
                return cursor.fetchall()
            else:
                # Faster query when only column names are needed
                cursor.execute(
                    sql.SQL(
                        """
                        SELECT column_name
                        FROM information_schema.columns 
                        WHERE table_name = {}
                        ORDER BY ordinal_position
                    """
                    ).format(sql.Literal(table_name))
                )
                return [col[0] for col in cursor.fetchall()]

    @staticmethod
    def get_table_constraints(table_name):
        """Get constraint information for a specific table"""
        with get_cursor() as cursor:
            # Get primary key constraints
            cursor.execute(
                sql.SQL(
                    """
                    SELECT kcu.column_name, tc.constraint_type
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_catalog = kcu.constraint_catalog
                      AND tc.constraint_schema = kcu.constraint_schema
                      AND tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_name = {}
                      AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
                    ORDER BY kcu.ordinal_position
                    """
                ).format(sql.Literal(table_name))
            )
            return cursor.fetchall()

    @staticmethod
    def get_column_defaults_and_nullable(table_name):
        """Get default values and nullable status for columns in a table"""
        with get_cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    """
                    SELECT column_name, column_default, is_nullable, data_type
                    FROM information_schema.columns
                    WHERE table_name = {}
                    ORDER BY ordinal_position
                    """
                ).format(sql.Literal(table_name))
            )
            return cursor.fetchall()

    @staticmethod
    def get_tables_and_columns(include_details=True):
        """Get all tables and their column information

        Args:
            include_details: If True, include detailed type information
                            If False, only return column names (faster)
        """
        tables = DatabaseSchema.get_tables()
        result = {}

        for table_name in tables:
            result[table_name] = DatabaseSchema.get_table_columns(
                table_name, include_details
            )

        return result

    @staticmethod
    def format_data_type(data_type, char_max_length, numeric_precision, numeric_scale):
        """Format the data type for display"""
        if data_type == "character varying" and char_max_length is not None:
            return f"varchar({char_max_length})"
        elif (
            data_type == "numeric"
            and numeric_precision is not None
            and numeric_scale is not None
        ):
            return f"numeric({numeric_precision},{numeric_scale})"
        else:
            return data_type

    @staticmethod
    def print_schema():
        """Print the database schema in a readable format"""
        tables_and_columns = DatabaseSchema.get_tables_and_columns()

        for table, columns in tables_and_columns.items():
            print(f"Table: {table}")
            for column in columns:
                (
                    column_name,
                    data_type,
                    char_max_length,
                    numeric_precision,
                    numeric_scale,
                ) = column
                formatted_type = DatabaseSchema.format_data_type(
                    data_type, char_max_length, numeric_precision, numeric_scale
                )
                print(f"  Column: {column_name}, Type: {formatted_type}")
            print()

    @staticmethod
    def generate_create_table_sql(table_name):
        """Generate SQL CREATE TABLE statement for a specific table"""
        columns = DatabaseSchema.get_table_columns(table_name)
        constraints = DatabaseSchema.get_table_constraints(table_name)
        defaults_nullable = DatabaseSchema.get_column_defaults_and_nullable(table_name)

        # Map column names to their constraint types
        constraint_map = {}
        for col_name, constraint_type in constraints:
            constraint_map[col_name] = constraint_type

        # Map column names to default values and nullable status
        defaults_map = {}
        for col_name, default, nullable, data_type in defaults_nullable:
            defaults_map[col_name] = {
                "default": default,
                "nullable": nullable,
                "data_type": data_type,
            }

        sql_lines = [f"CREATE TABLE {table_name} ("]
        column_definitions = []

        for column in columns:
            (
                column_name,
                data_type,
                char_max_length,
                numeric_precision,
                numeric_scale,
            ) = column

            formatted_type = DatabaseSchema.format_data_type(
                data_type, char_max_length, numeric_precision, numeric_scale
            )

            column_def = f"    {column_name} {formatted_type}"

            # Add constraints
            if column_name in constraint_map:
                if constraint_map[column_name] == "PRIMARY KEY":
                    column_def += " PRIMARY KEY"
                elif constraint_map[column_name] == "UNIQUE":
                    column_def += " UNIQUE"

            # Add nullable constraint
            if column_name in defaults_map:
                if defaults_map[column_name]["nullable"] == "NO":
                    column_def += " NOT NULL"

                # Add default values if they exist
                if defaults_map[column_name]["default"] is not None:
                    default_val = defaults_map[column_name]["default"]
                    # Handle serial types specially
                    if "nextval" in str(default_val) and defaults_map[column_name][
                        "data_type"
                    ] in ("integer", "bigint"):
                        if defaults_map[column_name]["data_type"] == "integer":
                            column_def = f"    {column_name} SERIAL"
                        else:
                            column_def = f"    {column_name} BIGSERIAL"
                    else:
                        column_def += f" DEFAULT {default_val}"

            column_definitions.append(column_def)

        sql_lines.append(",\n".join(column_definitions))
        sql_lines.append(");")

        return "\n".join(sql_lines)

    @staticmethod
    def generate_migration_script(output_file=None):
        """Generate SQL migration script for all tables"""
        tables = DatabaseSchema.get_tables()
        sql_statements = []

        for table_name in tables:
            sql = DatabaseSchema.generate_create_table_sql(table_name)
            sql_statements.append(f"-- Table: {table_name}")
            sql_statements.append(sql)
            sql_statements.append("\n")

        complete_script = "\n".join(sql_statements)

        # Write to file if specified
        if output_file:
            with open(output_file, "w") as f:
                f.write(complete_script)
            print(f"Migration script written to {output_file}")

        return complete_script


def get_tables_and_columns():
    """Get all tables and their columns"""
    return DatabaseSchema.get_tables_and_columns()


def format_data_type(data_type, char_max_length, numeric_precision, numeric_scale):
    """Format a data type for display"""
    return DatabaseSchema.format_data_type(
        data_type, char_max_length, numeric_precision, numeric_scale
    )


def generate_migration_script(output_file=None):
    """Generate SQL migration script for all tables"""
    return DatabaseSchema.generate_migration_script(output_file)


if __name__ == "__main__":
    # Print the full schema
    print("Database Schema Information:")
    print("===========================")
    DatabaseSchema.print_schema()

    # Generate migration script
    output_file = "database_migration.sql"
    print(f"\nGenerating migration script to {output_file}...")
    DatabaseSchema.generate_migration_script(output_file)

    # Print summary
    tables_and_columns = DatabaseSchema.get_tables_and_columns()
    print(
        f"\nSummary: Found {sum(len(columns) for columns in tables_and_columns.values())} columns in {len(tables_and_columns)} tables"
    )
