#!/bin/sh
# Flash harmony-image.custom.squashfs to the Pimento "root" MTD partition.
# Run as root, from /data or /cache, with this whole directory present.
# It backs up the current rootfs to /data/backup before writing.
set -e

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
IMG="${1:-$DIR/harmony-image.custom.squashfs}"
MTDWRITE="$DIR/mtdwrite"

[ -x "$MTDWRITE" ] || { echo "missing $MTDWRITE" >&2; exit 1; }
[ -f "$IMG" ] || { echo "missing image $IMG" >&2; exit 1; }

LINE=$(grep -E 'mtd[0-9]+:.*"root"' /proc/mtd | sed -n '1p')
[ -n "$LINE" ] || { echo "no MTD partition named root" >&2; exit 1; }
DEV="/dev/$(echo "$LINE" | cut -d: -f1)"

BACKUP_DIR="${BACKUP_DIR:-/cache/backup}"
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$BACKUP_DIR/root-$STAMP.bin"

echo "root partition: $DEV"
echo "backup: $BACKUP"
"$MTDWRITE" --backup "$DEV" "$BACKUP"
/bin/busybox sync

echo "writing: $IMG -> $DEV"
"$MTDWRITE" --write "$DEV" "$IMG" --yes --verify --squashfs
/bin/busybox sync

echo "done. Reboot to boot the new rootfs."
echo "backup kept at $BACKUP"
