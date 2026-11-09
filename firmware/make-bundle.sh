#!/bin/sh
# Assemble a flashable bundle from the built image and flasher.
# Output: firmware/work/custom-fw-4.15.600/
set -e

BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORK="${WORK:-$BASE/work}"
IMG="${IMG:-$WORK/harmony-image.custom.squashfs}"
MTDWRITE="${MTDWRITE:-$BASE/mtdwrite}"
OUT="${OUT:-$WORK/custom-fw-4.15.600}"

[ -f "$IMG" ] || { echo "missing image: $IMG (run build-custom-rootfs.sh)" >&2; exit 1; }
[ -x "$MTDWRITE" ] || { echo "missing mtdwrite: $MTDWRITE (run build-mtdwrite.sh)" >&2; exit 1; }

mkdir -p "$OUT"
cp "$IMG" "$OUT/harmony-image.custom.squashfs"
cp "$MTDWRITE" "$OUT/mtdwrite"
cp "$BASE/mtdwrite.c" "$OUT/mtdwrite.c"
cp "$BASE/flash-rootfs.sh" "$OUT/flash-rootfs.sh"
chmod 755 "$OUT/mtdwrite" "$OUT/flash-rootfs.sh"

cat > "$OUT/README.txt" <<'EOF'
Harmony Hub Pimento — rootfs custom (base 4.15.600)
===================================================

COSA È
- Rootfs SquashFS 4.0 LZMA da scrivere in mtd:root (4 MiB).
- Mantiene kernel 2.6.31, HAL, servizio LuaQ, moduli e mtd:mfg stock.
- Aggiunge Dropbear statico key-only, /etc/tdeenable, /etc/custom-fw e la
  VOSTRA authorized_keys (la PUBKEY usata nella build).
- NON è un firmware completamente open.

ATTENZIONE
- Scrivere mtd:root può rendere l'Hub non avviabile. La UART è TX-only:
  se il rootfs non boota, serve recovery hardware (UART/JTAG/SPI).
- Fare il backup e copiarlo FUORI dall'Hub prima di scrivere.
- Non toccare mtd:mfg, mtd:data, mtd:cache, mtd:kernel.

INSTALLAZIONE (da shell root)
1. Copiare questa directory in /data/custom-fw (≈4,08 MB) o /cache/custom-fw.
2. sha256sum -c SHA256SUMS
3. sh flash-rootfs.sh
   (backup in /cache/backup/root-<data>.bin, poi write + verify)
4. Copiare il backup fuori dall'Hub.
5. reboot
6. ssh -i <vostra-chiave> root@<hub-ip>
   Verificare: cat /etc/custom-fw ; dmesg ; servizio Lua.

RIPRISTINO
- Se il sistema boota: sh flash-rootfs.sh /cache/backup/root-<data>.bin
- Se non boota: recovery hardware; il backup su /cache non è raggiungibile.

FILE
- harmony-image.custom.squashfs  rootfs da scrivere in mtd:root
- mtdwrite                      flasher MTD statico MIPS (backup/write/verify)
- mtdwrite.c                    sorgente del flasher
- flash-rootfs.sh              wrapper: trova mtd:root, backup, write, verify
- SHA256SUMS                   hash dei file
EOF

cd "$OUT"
sha256sum harmony-image.custom.squashfs mtdwrite mtdwrite.c flash-rootfs.sh > SHA256SUMS
echo "bundle: $OUT"
sha256sum -c SHA256SUMS
