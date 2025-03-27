import imaplib
import socket


def check_imap_access(
    sender_email: str, password: str, imap_server: str, imap_port: str
):
    """
    Check if the IMAP connection to the email server is successful.

    This function attempts to connect to the IMAP server using the provided
    email address, password, server address, and port number. It performs
    various checks to ensure the connection is successful and handles different
    error scenarios.

    Args:
        sender_email (str): The email address to check
        password (str): The password for the email account
        imap_server (str): The IMAP server address
        imap_port (str): The IMAP server port number
    """
    error_imap = ""
    try:
        imap_port = int(imap_port)
        # Attempt to connect to the server
        mail = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=3)
    except socket.gaierror:
        error_imap = f"Error: Unable to resolve IMAP server {imap_server}. Please check the server address."
        return False, error_imap
    except socket.timeout:
        error_imap = f"Error: Connection to the IMAP server {imap_server} timed out. Please check the server or your network."
        return False, error_imap
    except Exception as e:
        error_imap = f"Error: Unable to connect to IMAP server {imap_server} on port {imap_port}. Details: {e}"
        return False, error_imap
    try:
        # Attempt to log in
        mail.login(sender_email, password)
        print(f"Imap to {sender_email} confirmed.")
        return True, error_imap
    except imaplib.IMAP4.error:
        error_imap = f"Error: Authentication failed for {sender_email}. Please check your email address and password and ensure that IMAP is enabled"
        return False, error_imap
    except Exception:
        error_imap = f"Error: Authentication failed for {sender_email}. Please verify the IMAP parameters with your email provider and ensure that IMAP is enabled."
        return False, error_imap
    finally:
        # Clean up the connection if successfully created
        try:
            mail.logout()
        except Exception:
            pass
