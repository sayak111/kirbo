import socket
import threading
import struct
import json
import protocol
import security
import db_manager

# Generate static server Diffie-Hellman parameters once on boot
print("[SERVER] Initializing Diffie-Hellman parameters...")
dh_master = security.DHHandshake()
SERVER_DH_PARAMS = dh_master.parameters
print("[SERVER] DH Parameters ready.")

HOST = "0.0.0.0"
PORT = 3000

def handle_client(client_sock, client_addr):
    print(f"[NEW CONNECTION] Connected from {client_addr}")
    cipher = None

    try:
        # 1. Initiate Encrypted Handshake
        dh_session = security.DHHandshake(parameters=SERVER_DH_PARAMS)
        param_bytes = dh_session.get_parameters_bytes()
        pub_bytes = dh_session.get_public_bytes()

        # Send [Param Length (4 bytes)] + [Parameters] + [Public Key]
        init_payload = struct.pack("!I", len(param_bytes)) + param_bytes + pub_bytes
        protocol.send_msg(client_sock, protocol.OP_DH_HANDSHAKE, init_payload)

        # Receive Client Public Key
        opcode, client_pub_bytes = protocol.recv_msg(client_sock)
        if opcode != protocol.OP_DH_HANDSHAKE or not client_pub_bytes:
            print("[SECURITY ERROR] Handshake failed.")
            client_sock.close()
            return

        session_key = dh_session.generate_session_key(client_pub_bytes)
        cipher = security.SymmetricCipher(session_key)
        print(f"[SECURITY] Encrypted session established with {client_addr}")

        # 2. Main Socket Message Event Loop
        while True:
            opcode, payload = protocol.recv_msg(client_sock, cipher=cipher)
            if opcode is None:
                print(f"[CLIENT DISCONNECTED] {client_addr}")
                break

            try:
                data = json.loads(payload.decode('utf-8'))
            except Exception:
                data = {}

            # Handle User Registration
            if opcode == protocol.OP_REGISTER:
                username = data.get("username", "").strip()
                password = data.get("password", "").strip()

                success, msg = db_manager.register_user(username, password)
                res_payload = json.dumps({"success": success, "message": msg}).encode('utf-8')
                protocol.send_msg(client_sock, protocol.OP_REGISTER_RESP, res_payload, cipher=cipher)

            # Handle User Login
            elif opcode == protocol.OP_LOGIN:
                username = data.get("username", "").strip()
                password = data.get("password", "").strip()

                success, user_info_or_msg = db_manager.authenticate_user(username, password)
                if success:
                    res_payload = json.dumps({
                        "success": True,
                        "message": "Login successful!",
                        "user": user_info_or_msg
                    }).encode('utf-8')
                else:
                    res_payload = json.dumps({
                        "success": False,
                        "message": str(user_info_or_msg)
                    }).encode('utf-8')

                protocol.send_msg(client_sock, protocol.OP_LOGIN_RESP, res_payload, cipher=cipher)

    except Exception as e:
        print(f"[ERROR] Client error: {e}")
    finally:
        client_sock.close()


def main():
    db_manager.init_db()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")

    while True:
        client_sock, client_addr = server.accept()
        t = threading.Thread(target=handle_client, args=(client_sock, client_addr), daemon=True)
        t.start()

if __name__ == "__main__":
    main()