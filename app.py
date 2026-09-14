import os
import threading
import webbrowser

from src.web.app import create_app
from src.config.loader import load_settings
from src.web.port_utils import choose_available_port

app=create_app()

def _open_browser(url):
    try:webbrowser.open(url,new=2)
    except Exception:pass

if __name__=='__main__':
    s=load_settings()
    cloud_port=os.getenv('PORT')

    if cloud_port:
        port=int(cloud_port)
    else:
        preferred=int(s['app'].get('port',5130))
        end=int(s['app'].get('port_search_end',5199))
        if bool(s['app'].get('port_auto_fallback',True)):
            port=choose_available_port(preferred,end)
        else:
            port=preferred

    url=f"http://127.0.0.1:{port}"
    print()
    print("="*58)
    print(f" NEXUS MARKET AGENT V{s['app']['version']} - LIVE PAPER")
    print("="*58)
    if not cloud_port and port!=int(s['app'].get('port',5130)):
        print(f" Puerto {s['app'].get('port')} ocupado.")
        print(f" NEXUS seleccionó automáticamente el puerto {port}.")
    print(f" Abriendo: {url}")
    print(" Para cerrar NEXUS presiona CTRL+C.")
    print("="*58)
    print()

    if not cloud_port:
        threading.Timer(1.2,_open_browser,args=(url,)).start()

    app.run(host='0.0.0.0',port=port,debug=False,use_reloader=False)
