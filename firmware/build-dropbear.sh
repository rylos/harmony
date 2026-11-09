#!/bin/sh
# Build a static MIPS32/uClibc Dropbear server+keygen for the Harmony Hub
# Pimento rootfs. Downloads the Bootlin toolchain and Dropbear source into
# firmware/work/ (gitignored). Output: firmware/dropbearmulti-min.
set -e

BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORK="${WORK:-$BASE/work}"
TOOLCHAIN="${TOOLCHAIN:-$WORK/toolchains/mips32--uclibc--stable}"
TC_NAME="mips32--uclibc--stable-2017.05-toolchains-1-1"
TC_URL="https://toolchains.bootlin.com/downloads/releases/toolchains/mips32/tarballs/$TC_NAME.tar.bz2"
DB_VERSION="2025.89"
DB_URL="https://matt.ucc.asn.au/dropbear/releases/dropbear-$DB_VERSION.tar.bz2"

mkdir -p "$WORK/toolchains" "$WORK/src"

if [ ! -x "$TOOLCHAIN/bin/mips-buildroot-linux-uclibc-gcc" ]; then
    TARBALL="$WORK/toolchains/$TC_NAME.tar.bz2"
    [ -f "$TARBALL" ] || curl -L -o "$TARBALL" "$TC_URL"
    tar -C "$WORK/toolchains" -xf "$TARBALL"
fi
[ -x "$TOOLCHAIN/bin/mips-buildroot-linux-uclibc-gcc" ] || {
    echo "toolchain not found after extraction: $TOOLCHAIN" >&2
    exit 1
}

cd "$WORK/src"
[ -f "dropbear-$DB_VERSION.tar.bz2" ] || curl -L -o "dropbear-$DB_VERSION.tar.bz2" "$DB_URL"
rm -rf "dropbear-$DB_VERSION"
tar -xf "dropbear-$DB_VERSION.tar.bz2"
cd "dropbear-$DB_VERSION"

PATH="$TOOLCHAIN/bin:$PATH"
export PATH
./configure \
    --host=mips-buildroot-linux-uclibc \
    --disable-zlib --disable-pam \
    --disable-lastlog --disable-utmp --disable-utmpx \
    --disable-wtmp --disable-wtmpx \
    --disable-loginfunc --disable-pututline --disable-pututxline \
    CC=mips-buildroot-linux-uclibc-gcc \
    CFLAGS="-Os -static" LDFLAGS="-static"
make -j"$(nproc)" MULTI=1 PROGRAMS="dropbear dropbearkey" dropbearmulti
mips-buildroot-linux-uclibc-strip dropbearmulti
install -m 755 dropbearmulti "$BASE/dropbearmulti-min"
echo "built: $BASE/dropbearmulti-min"
sha256sum "$BASE/dropbearmulti-min"
