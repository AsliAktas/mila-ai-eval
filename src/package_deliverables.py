# -*- coding: utf-8 -*-
"""
Teslim paketini zip'ler.

- Varsayılan olarak deliverables/ klasörünü zip'ler.
- Zip'e Excel ve CSV çıktıları da eklenir (mila_eval.xlsx, preds_mila.csv).
- Kullanım:
    python src/package_deliverables.py --dir deliverables --out mila-deliverables
    # veya ekstra dosyaları özelleştirerek:
    python src/package_deliverables.py --dir deliverables --out mila-deliverables --extras outputs/eval/mila_eval.xlsx outputs/predictions/preds_mila.csv
"""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="deliverables", help="Paketlenecek klasör (PDF'ler burada)")
    ap.add_argument(
        "--extras",
        nargs="*",
        default=["outputs/eval/mila_eval.xlsx", "outputs/predictions/preds_mila.csv"],
        help="Zip'e ayrıca eklenecek dosyalar (Excel/CSV vb.)",
    )
    ap.add_argument("--out", default="mila-deliverables", help="zip dosya adı (uzantısız)")
    args = ap.parse_args()

    root = Path(args.dir)
    if not root.exists():
        raise SystemExit(f"[ERR] Klasör yok: {root.resolve()}")

    # Excel/CSV gibi ekleri deliverables altına kopyala (aynı adla)
    for extra in args.extras:
        p = Path(extra)
        if not p.exists():
            print(f"[warn] Ek dosya bulunamadı: {p}")
            continue
        target = root / p.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        print(f"[OK] Eklendi: {p} -> {target}")

    zip_path = shutil.make_archive(args.out, "zip", root_dir=str(root))
    print(f"[OK] Zip hazır: {zip_path}")

if __name__ == "__main__":
    main()
