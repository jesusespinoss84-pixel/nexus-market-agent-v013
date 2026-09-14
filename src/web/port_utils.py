import socket

def port_is_available(port, host="127.0.0.1"):
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        sock.bind((host,int(port)))
        return True
    except OSError:
        return False
    finally:
        try:sock.close()
        except Exception:pass

def choose_available_port(preferred=5130, end=5199, host="127.0.0.1"):
    preferred=int(preferred); end=max(preferred,int(end))
    for port in range(preferred,end+1):
        if port_is_available(port,host):
            return port
    raise OSError(f"No hay puertos libres entre {preferred} y {end}.")
