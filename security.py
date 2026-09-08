import os
import time
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

print("[DEBUG security.py] Initializing security module...")
start_time = time.time()

# Generate valid 2048-bit DH parameters once on module load.
print("[DEBUG security.py] Generating static global 2048-bit DH parameters (this may take a moment)...")
_GLOBAL_DH_PARAMS = dh.generate_parameters(generator=2, key_size=2048)
print(f"[DEBUG security.py] Global DH parameters ready in {time.time() - start_time:.2f} seconds.")


class DHHandshake:
    def __init__(self, parameters=None):
        print("[DEBUG DHHandshake] Starting new DH Handshake instance...")
        if parameters is None:
            print("[DEBUG DHHandshake] Using default global DH parameters.")
            self.parameters = DHHandshake.get_default_parameters()
        else:
            print("[DEBUG DHHandshake] Using provided custom DH parameters.")
            self.parameters = parameters
            
        print("[DEBUG DHHandshake] Generating private/public keypair...")
        self.private_key = self.parameters.generate_private_key()
        self.public_key = self.private_key.public_key()
        print("[DEBUG DHHandshake] Keypair generated successfully.")

    @staticmethod
    def get_default_parameters():
        return _GLOBAL_DH_PARAMS

    @staticmethod
    def load_parameters_bytes(param_bytes: bytes):
        print(f"[DEBUG DHHandshake] Parsing DER parameter bytes (Length: {len(param_bytes)} bytes)...")
        params = serialization.load_der_parameters(param_bytes)
        print("[DEBUG DHHandshake] DER parameters parsed successfully.")
        return params

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
        print(f"[DEBUG DHHandshake] Deriving session key from peer public key ({len(peer_public_bytes)} bytes)...")
        peer_public_key = serialization.load_der_public_key(peer_public_bytes)
        shared_secret = self.private_key.exchange(peer_public_key)

        key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'handshake data',
        ).derive(shared_secret)
        print("[DEBUG DHHandshake] Shared AES-256 session key generated successfully.")
        return key


class SymmetricCipher:
    def __init__(self, key: bytes):
        print(f"[DEBUG SymmetricCipher] Initializing AESGCM cipher with key length {len(key)} bytes.")
        self.aesgcm = AESGCM(key)

    def encrypt(self, data: bytes) -> bytes:
        nonce = os.urandom(12)
        encrypted = nonce + self.aesgcm.encrypt(nonce, data, None)
        print(f"[DEBUG SymmetricCipher] Encrypted {len(data)} bytes of plaintext -> {len(encrypted)} bytes ciphertext.")
        return encrypted

    def decrypt(self, encrypted_bytes: bytes) -> bytes:
        if len(encrypted_bytes) < 12:
            print("[DEBUG SymmetricCipher ERROR] Payload too short for nonce extraction!")
            raise ValueError("Encrypted message too short")
        decrypted = self.aesgcm.decrypt(encrypted_bytes[:12], encrypted_bytes[12:], None)
        print(f"[DEBUG SymmetricCipher] Decrypted {len(encrypted_bytes)} bytes ciphertext -> {len(decrypted)} bytes plaintext.")
        return decrypted