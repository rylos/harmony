#!/bin/sh
# Build a custom Pimento rootfs (SquashFS 4.0 LZMA) from a stock 4.15.600
# rootfs. Does not touch the Hub. Inputs (override with env vars):
#   STOCK    extracted stock rootfs (default: firmware/work/stock-rootfs)
#   DROPBEAR static dropbearmulti built by build-dropbear.sh
#   PUBKEY   your SSH public key (required; never commit a private key)
# Output: firmware/work/harmony-image.custom.squashfs
set -e

BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORK="${WORK:-$BASE/work}"
STOCK="${STOCK:-$WORK/stock-rootfs}"
DROPBEAR="${DROPBEAR:-$BASE/dropbearmulti-min}"
PUBKEY="${PUBKEY:-}"
OUT="${OUT:-$WORK/rootfs-custom}"
IMAGE="${IMAGE:-$WORK/harmony-image.custom.squashfs}"
BUILD_EPOCH="${BUILD_EPOCH:-1762700000}"

case "$OUT" in ""|"/") echo "refusing unsafe OUT=$OUT" >&2; exit 1;; esac
[ -n "$PUBKEY" ] || { echo "set PUBKEY=/path/to/your_key.pub" >&2; exit 1; }
[ -d "$STOCK" ] || { echo "missing stock rootfs: $STOCK (extract with sasquatch; see ../firmware.md)" >&2; exit 1; }
[ -f "$DROPBEAR" ] || { echo "missing dropbearmulti: $DROPBEAR (run build-dropbear.sh)" >&2; exit 1; }
[ -f "$PUBKEY" ] || { echo "missing public key: $PUBKEY" >&2; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"
cp -a "$STOCK/." "$OUT/"

install -m 755 "$DROPBEAR" "$OUT/usr/sbin/dropbearmulti"
ln -sf dropbearmulti "$OUT/usr/sbin/dropbear"
ln -sf dropbearmulti "$OUT/usr/sbin/dropbearkey"

# Key-only SSH (rcS starts it when /etc/tdeenable exists).
sed -i 's#^    /usr/sbin/dropbear$#    /usr/sbin/dropbear -s -g -K 300#' "$OUT/etc/init.d/rcS"

# Let rcS generate a per-device host key on first boot.
rm -f "$OUT/etc/dropbear/dropbear_rsa_host_key"

printf '1\n' > "$OUT/etc/tdeenable"
printf 'custom-fw 4.15.600 base\n' > "$OUT/etc/custom-fw"
mkdir -p "$OUT/home/root/.ssh" "$OUT/data"
install -m 600 "$PUBKEY" "$OUT/home/root/.ssh/authorized_keys"
chmod 700 "$OUT/home/root/.ssh"

mksquashfs "$OUT" "$IMAGE" \
    -comp lzma -b 131072 -noappend -all-root -no-xattrs \
    -mkfs-time "$BUILD_EPOCH" -inode-time "$BUILD_EPOCH" >/dev/null

SIZE=$(wc -c < "$IMAGE")
echo "image=$IMAGE"
echo "size=$SIZE partition=4194304 margin=$((4194304 - SIZE))"
sha256sum "$IMAGE"
