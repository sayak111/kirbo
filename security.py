import os
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class DHHandshake:
    def __init__(self, parameters=None):
        if parameters is None:
            # השרת מייצר פרמטרים חדשים
            self.parameters = dh.generate_parameters(generator=2, key_size=2048)
        else:
            # הלקוח טוען את הפרמטרים שקיבל מהשרת
            self.parameters = parameters
            
        self.private_key = self.parameters.generate_private_key()
        self.public_key = self.private_key.public_key()

    def get_parameters_bytes(self) -> bytes:
        """אריזת הפרמטרים לבייטים לשליחה ברשת"""
        return self.parameters.parameter_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.ParameterFormat.PKCS3
        )

    @staticmethod
    def load_parameters_bytes(param_bytes: bytes):
        """טעינת פרמטרים שהתקבלו ברשת"""
        return serialization.load_der_parameters(param_bytes)

    def get_public_bytes(self) -> bytes:
        """אריזת המפתח הציבורי לבייטים"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def generate_session_key(self, peer_public_bytes: bytes) -> bytes:
        peer_public_key = serialization.load_der_public_key(peer_public_bytes)
        shared_secret = self.private_key.exchange(peer_public_key)

        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'handshake data',
        ).derive(shared_secret)

        return derived_key


class SymmetricCipher:
    def __init__(self, key: bytes):
        self.aesgcm = AESGCM(key)

    def encrypt(self, data: bytes) -> bytes:
        nonce = os.urandom(12)
        encrypted_payload = self.aesgcm.encrypt(nonce, data, None)
        return nonce + encrypted_payload

    def decrypt(self, encrypted_bytes: bytes) -> bytes:
        if len(encrypted_bytes) < 12:
            raise ValueError("Encrypted message too short")
        
        nonce = encrypted_bytes[:12]
        ciphertext = encrypted_bytes[12:]
        return self.aesgcm.decrypt(nonce, ciphertext, None)