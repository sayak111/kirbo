import socket
import struct
import threading
import protocol
import security

def receive_loop(sock, cipher):
    while True:
        opcode, payload = protocol.recv_msg(sock, cipher=cipher)
        if opcode is None:
            print("\n[DISCONNECTED] Connection lost or invalid decryption.")
            break

        msg = payload.decode(errors="ignore")
        if opcode == protocol.OP_LOBBY_RESPONSE:
            print(f"\n[SERVER RESPONSE] {msg}")
        elif opcode == protocol.OP_CHAT_MSG:
            print(f"\n[LOBBY CHAT] {msg}")
        elif opcode == protocol.OP_ERROR:
            print(f"\n[SERVER ERROR] {msg}")

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(("127.0.0.1", 3000))
        print("[CONNECTED] Connected to server.")
    except Exception as e:
        print(f"Could not connect: {e}")
        return

    # --- שלב 2: Diffie-Hellman Handshake ---
    opcode, init_payload = protocol.recv_msg(sock)
    if opcode != protocol.OP_DH_HANDSHAKE:
        print("Handshake error!")
        return
    
    # חילוץ הפרמטרים והמפתח של השרת
    param_len = struct.unpack("!I", init_payload[:4])[0]
    param_bytes = init_payload[4 : 4 + param_len]
    server_pub_bytes = init_payload[4 + param_len :]
    
    # טעינת הפרמטרים ויצירת האובייקט בלקוח
    server_params = security.DHHandshake.load_parameters_bytes(param_bytes)
    dh = security.DHHandshake(parameters=server_params)
    
    # שליחת המפתח הציבורי של הלקוח לשרת
    protocol.send_msg(sock, protocol.OP_DH_HANDSHAKE, dh.get_public_bytes())
    
    # חישוב המפתח הסודי המשותף
    session_key = dh.generate_session_key(server_pub_bytes)
    cipher = security.SymmetricCipher(session_key)
    print("[SECURITY] Handshake completed. Connection is now ENCRYPTED.")
    # ----------------------------------------

    threading.Thread(target=receive_loop, args=(sock, cipher), daemon=True).start()

    print("\nCommands:\n 1 - Create Lobby\n 2 - Join Lobby\n 3 - Send Message\n q - Quit")

    while True:
        choice = input("\nEnter command: ").strip()

        if choice == "1":
            protocol.send_msg(sock, protocol.OP_CREATE_LOBBY, b"", cipher=cipher)
        elif choice == "2":
            lobby_id = input("Enter Lobby ID: ").strip()
            protocol.send_msg(sock, protocol.OP_JOIN_LOBBY, lobby_id.encode(), cipher=cipher)
        elif choice == "3":
            msg = input("Message: ").strip()
            protocol.send_msg(sock, protocol.OP_CHAT_MSG, msg.encode(), cipher=cipher)
        elif choice.lower() == "q":
            break

    sock.close()

if __name__ == "__main__":
    main()