import argparse
import subprocess
import sys
from pathlib import Path


def is_elf(path: Path) -> bool:
    """Dosyanın ELF formatında (çalıştırılabilir/kütüphane) olup olmadığını kontrol eder."""
    try:
        if not path.is_file() or path.is_symlink():
            return False
        with open(path, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except Exception:  # noqa: BLE001
        return False


def patch(path: Path):
    if not is_elf(path):
        return
    try:
        pf = subprocess.run(
            [
                "patchelf",
                "--set-interpreter",
                "/opt/usr/lib/ld-linux-x86-64.so.2",
                str(path),
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        print(f"Başarıyla yamalandı: {path}")
    except subprocess.CalledProcessError as pf:
        print(
            f"Yamalama HATASI ({path.name}) - Kod: {pf.returncode} Detay: {pf.stderr.strip()}"
        )


def patch_package(pack: str):
    """Paket adına göre kurulan/güncellenen dosyaları xbps-query ile bulur ve yamar."""
    print(f"'{pack}' paketine ait dosyalar taranıyor ve yamalanıyor...")
    try:
        res = subprocess.run(
            ["xbps-query", "-r", "/opt", "-f", pack],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in res.stdout.splitlines():
            line = line.strip()
            if line:
                p = Path(line)
                if p.exists():
                    patch(p)
    except subprocess.CalledProcessError:
        print(
            f"'{pack}' paket dosyaları sorgulanamadı, glob taramasına geçiliyor..."
        )
        patch_glob()


def patch_glob():
    """Glob kullanarak /opt altındaki tüm ELF dosyalarını yamar."""
    print("/opt altındaki tüm dosyalar glob ile taranıyor ve yamalanıyor...")
    for p in Path("/opt").rglob("*"):
        if is_elf(p):
            patch(p)


def xbps_manage(op: str, packs: str | list[str] | None = None):
    """xbps için sarmalayıcı

    Args:
        op (str): işlem
        packs (str | list[str] | None, optional): paket adı. Defaults to None.
    """
    if packs is None:
        pack_list = []
    elif isinstance(packs, str):
        pack_list = [p.strip() for p in packs.split() if p.strip()]
    else:
        pack_list = packs

    try:
        match op:
            case "yükle" | "yukle" | "install":
                if not pack_list:
                    print("Hata: Yüklenecek en az bir paket belirtilmedi.")
                    sys.exit(1)

                cmd = ["xbps-install", "-r", "/opt", "-y"] + pack_list
                subprocess.run(cmd, check=True)

                for pack in pack_list:
                    patch_package(pack)

            case "kaldır" | "kaldir" | "remove":
                if not pack_list:
                    print("Hata: Kaldırılacak en az bir paket belirtilmedi.")
                    sys.exit(1)

                cmd = ["xbps-remove", "-r", "/opt", "-y"] + pack_list
                subprocess.run(cmd, check=True)

            case "güncelle" | "guncelle" | "update":
                cmd = ["xbps-install", "-r", "/opt", "-u", "-y"] + pack_list
                subprocess.run(cmd, check=True)

                if pack_list:
                    for pack in pack_list:
                        patch_package(pack)
                else:
                    patch_glob()

            case "ara" | "search":
                if not pack_list:
                    print("Hata: Aranacak kelime/paket belirtilmedi.")
                    sys.exit(1)

                for pack in pack_list:
                    cmd = ["xbps-query", "-r", "/opt", "-s", pack]
                    subprocess.run(cmd, check=True)

            case _:
                print(f"Bilinmeyen komut: {op}")
                sys.exit(1)

    except subprocess.CalledProcessError as e:
        print(f"İşlem sırasında hata oluştu (Kod: {e.returncode})")
        sys.exit(e.returncode)


def tan_main():
    parser = argparse.ArgumentParser(
        description="/opt dizini için glibc yamalı XBPS paket yöneticisi aracı."
    )
    parser.add_argument(
        "op",
        type=str,
        choices=[
            "yükle",
            "yukle",
            "install",
            "kaldır",
            "kaldir",
            "remove",
            "güncelle",
            "guncelle",
            "update",
            "ara",
            "search",
        ],
        help="Yapılacak işlem (yükle, kaldır, güncelle, ara)",
    )
    parser.add_argument(
        "packages",
        nargs="*",
        help="İşlem yapılacak paket adı veya adları (boş bırakılabilir)",
    )

    args = parser.parse_args()
    xbps_manage(args.op, args.packages)


if __name__ == "__main__":
    tan_main()