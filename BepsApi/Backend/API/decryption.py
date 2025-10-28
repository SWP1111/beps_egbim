from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import logging
import log_config

# 암호화 파라미터 설정
ITERATIONS = 10000
KEY_SIZE = 32
IV_SIZE = 16
SALT_SIZE = 16

def decrypt(cipher_text, password):
    # Base64 디코딩
    try:
        cipher_bytes = base64.b64decode(cipher_text)
    except Exception as e:
        logging.error(f"Base64 decoding error: {e}")
        return None
    
    logging.debug(f"Decoded byte length: {len(cipher_bytes)}")

    # 암호문에서 Salt 추출
    salt = cipher_bytes[:SALT_SIZE]
    encrypted_data = cipher_bytes[SALT_SIZE:]

    logging.debug(f"Salt (hex): {salt.hex()}")
    logging.debug(f"Encrypted data length: {len(encrypted_data)} bytes")

    # PBKDF2로 키와 IV 생성
    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE + IV_SIZE,
            salt=salt,
            iterations=ITERATIONS,
            backend=default_backend()
        )
        key_iv = kdf.derive(password.encode())
        key = key_iv[:KEY_SIZE]
        iv = key_iv[KEY_SIZE:]
    except Exception as e:
        logging.debug(f"Key derivation error: {e}")
        return None

    logging.debug(f"Derived key (hex): {key.hex()}")
    logging.debug(f"Derived IV (hex): {iv.hex()}")

    # AES 복호화
    try:
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
    except Exception as e:
        logging.error(f"Decryption error: {e}")
        return None

    logging.debug(f"Decrypted padded data (hex): {decrypted_padded_data.hex()}")

    # PKCS7 패딩 제거
    try:
        unpadder = padding.PKCS7(128).unpadder()
        decrypted_data = unpadder.update(decrypted_padded_data) + unpadder.finalize()
    except ValueError as e:
        logging.error(f"Padding removal error: {e}")
        return None

    logging.debug(f"Decrypted data (after unpadding): {decrypted_data}")

    # 최종 복호화된 텍스트 반환
    try:
        return decrypted_data.decode('utf-8')
    except UnicodeDecodeError as e:
        logging.error(f"UTF-8 decoding error: {e}")
        return None
