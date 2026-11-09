#!/bin/sh
# Build the static MIPS32/uClibc MTD flasher (firmware/mtdwrite) from mtdwrite.c.
# Requires the Bootlin toolchain downloaded by build-dropbear.sh (or TOOLCHAIN=).
set -e

BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORK="${WORK:-$BASE/work}"
TOOLCHAIN="${TOOLCHAIN:-$WORK/toolchains/mips32--uclibc--stable}"
CC="$TOOLCHAIN/bin/mips-buildroot-linux-uclibc-gcc"
STRIP="$TOOLCHAIN/bin/mips-buildroot-linux-uclibc-strip"

[ -x "$CC" ] || { echo "missing toolchain: $CC (run build-dropbear.sh first or set TOOLCHAIN)" >&2; exit 1; }
"$CC" -Wall -Wextra -Os -static -o "$BASE/mtdwrite" "$BASE/mtdwrite.c"
"$STRIP" "$BASE/mtdwrite"
echo "built: $BASE/mtdwrite"
sha256sum "$BASE/mtdwrite"
