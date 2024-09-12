from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


class AESEncryptor:
    """
    A Encryptor to encrypt and decrypt Langflow API key
    """

    def __init__(self, key):
        self.key = key

    def encrypt(self, plaintext):
        cipher = AES.new(self.key, AES.MODE_CBC)
        ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))
        return cipher.iv + ciphertext

    def decrypt(self, ciphertext):
        iv = ciphertext[: AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext[AES.block_size :]), AES.block_size)
        return plaintext
