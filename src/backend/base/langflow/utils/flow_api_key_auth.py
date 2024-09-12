from aes_encryptor import AESEncryptor
import jwt
import datetime


def generate_flow_token(flow_id, expiration_time):
    # Generate a Secret key for JWT and store it in the database
    jwt_secret = ""

    # Generate a Token ID and store it in the database
    token_id = ""

    # Generate a JWT token with the Token ID, Flow ID and Expiration Time
    payload = {
        "token_id": token_id,
        "flow_id": flow_id,
        "expiration_time": datetime.datetime.utcnow() + datetime.timedelta(hours=expiration_time),  # Expires in 1 hour
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    encrypted_token = AESEncryptor.encrypt(token)
    return encrypted_token


def authenticate_flow_token(ciphertext):
    # Secret key for JWT
    jwt_secret = ""

    # Get the 128-bit key from database
    key = ""

    # Initialize the LangflowApiKeyManager with the key
    encryptor = AESEncryptor(key)

    # Decrypt the ciphertext back to plaintext(JWT?)
    decrypted_token = encryptor.decrypt(ciphertext)

    # Verify the plaintext is a valid JWT
    try:
        decoded_token = jwt.decode(decrypted_token, jwt_secret, algorithms="HS256")
        return decoded_token
    except jwt.ExpiredSignatureError:
        return "Token has expired"
    except jwt.InvalidTokenError:
        return "Invalid token"
