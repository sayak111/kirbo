import os
import warnings
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Suppress cryptography deprecation warning for FFDH
warnings.filterwarnings("ignore", message=".*Diffie-Hellman.*")

# Generate mathematically valid 2048-bit DH parameters natively via OpenSSL
_GLOBAL_DH_PARAMS = dh.generate_parameters(generator=2, key_size=2048)


class DHHandshake:
    def __init__(self, parameters=None):
        if parameters is None:
            self.parameters = DHHandshake.get_default_parameters()
        else:
            self.parameters = parameters

        self.private_key = self.parameters.generate_private_key()
        self.public_key = self.private_key.public_key()

    @staticmethod
    def get_default_parameters():
        return _GLOBAL_DH_PARAMS

    @staticmethod
    def load_parameters_bytes(param_bytes: bytes):
        return serialization.load_der_parameters(param_bytes)

    def get_parameters_bytes(self) -> bytes:
        return self.parameters.parameter_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.ParameterFormat.PKCS3
        )

    def get_public_bytes(self) -> bytes:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def generate_session_key(self, peer_public_bytes: bytes) -> bytes:
        peer_public_key = serialization.load_der_public_key(peer_public_bytes)
        shared_secret = self.private_key.exchange(peer_public_key)

        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'handshake data',
        ).derive(shared_secret)


class SymmetricCipher:
    def __init__(self, key: bytes):
        self.aesgcm = AESGCM(key)

    def encrypt(self, data: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + self.aesgcm.encrypt(nonce, data, None)

    def decrypt(self, encrypted_bytes: bytes) -> bytes:
        if len(encrypted_bytes) < 12:
            raise ValueError("Encrypted message too short")
        return self.aesgcm.decrypt(encrypted_bytes[:12], encrypted_bytes[12:], None)
