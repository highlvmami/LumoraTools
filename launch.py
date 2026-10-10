"""PyInstaller giriş noktası (paket içi göreli içe aktarmalar yüzünden app.py doğrudan çalıştırılamaz)."""
from aracmerkezi.app import main

if __name__ == "__main__":
    main()
