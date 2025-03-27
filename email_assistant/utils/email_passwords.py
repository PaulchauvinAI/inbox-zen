# Utils for encoding and decoding of email accounts passwords
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get the cryptography key from environment variables
KEY = os.getenv("CRYPTO_KEY")


def generate_key(password):
    # unused
    salt = b"salt_"  # Generate a random salt
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    key = str(base64.urlsafe_b64encode(kdf.derive(password.encode())))
    return key


def encode_string(string, key=KEY):
    """
    Encrypts a string using Fernet symmetric encryption.

    Args:
        string (str): The plaintext string to encrypt
        key (str, optional): The encryption key. Defaults to the CRYPTO_KEY from environment.

    Returns:
        str: Base64-encoded encrypted string or None if input is None
    """
    if string is None:
        return string
    fernet = Fernet(key)
    encoded_bytes = fernet.encrypt(string.encode())
    encoded_string = base64.urlsafe_b64encode(encoded_bytes).decode()
    return encoded_string


def decode_string(encoded_string, key=KEY):
    """
    Decrypts a string that was encrypted with encode_string.

    Args:
        encoded_string (str): The encrypted string to decrypt
        key (str, optional): The encryption key. Defaults to the CRYPTO_KEY from environment.

    Returns:
        str: Decrypted plaintext string or None if input is None
    """
    if encoded_string is None:
        return encoded_string
    fernet = Fernet(key)
    encoded_bytes = base64.urlsafe_b64decode(encoded_string)
    decoded_string = fernet.decrypt(encoded_bytes).decode()
    return decoded_string


if __name__ == "__main__":
    # Example usage

    original_string = "Hello, World!"

    encoded_string = encode_string(original_string, KEY)
    decoded_string = decode_string(encoded_string, KEY)

    assert decoded_string == original_string
    print(KEY)
