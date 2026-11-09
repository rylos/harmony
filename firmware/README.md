# Firmware tools (Pimento / Harmony Hub 4.15.600)

Scripts and sources to build a **custom rootfs** for the Logitech Harmony Hub
(Pimento, AR9331) and to flash it from an existing root shell. The stock
kernel, HAL, Lua service, modules and `mtd:mfg` are preserved.

Read `../firmware.md` first; the full reverse-engineering notes are in
`REVERSE_ENGINEERING.md`.

## Prerequisites

- Linux host with `mksquashfs`, `curl`, `tar`, `make`, `gcc` build deps.
- The stock `4.15.600.440906.hfw2` image (from the SUS; not committed) and its
  rootfs extracted with `sasquatch`:
  `STOCK=/path/to/rootfs`.
- Your SSH **public** key. Private keys never go in this repo.

`build-dropbear.sh` downloads the Bootlin MIPS32/uClibc toolchain and Dropbear
2025.89 into `firmware/work/` (gitignored).

## Build

```sh
./build-dropbear.sh
STOCK=/path/to/rootfs PUBKEY=/path/to/key.pub ./build-custom-rootfs.sh
./build-mtdwrite.sh
./make-bundle.sh
```

Outputs:

- `work/harmony-image.custom.squashfs` — SquashFS 4.0 LZMA, must fit the 4 MiB
  `mtd:root` partition.
- `work/custom-fw-4.15.600/` — image + `mtdwrite` + `mtdwrite.c` +
  `flash-rootfs.sh` + `README.txt` + `SHA256SUMS`.

## Flash (from a root shell on the Hub)

```sh
# copy work/custom-fw-4.15.600/ to /data/custom-fw (or /cache/custom-fw)
sha256sum -c SHA256SUMS
sh flash-rootfs.sh
```

The script backs up `mtd:root` to `/cache/backup/root-<date>.bin`, writes the
image with `mtdwrite --write ... --yes --verify --squashfs`, and syncs.
Copy the backup off the Hub before rebooting.

## Restore

If the Hub still boots:

```sh
mtdwrite --write /dev/mtd3 /cache/backup/root-<date>.bin --yes --verify
```

The root partition is `mtd3` in the 16 MiB layout (u-boot 0, kernel 1,
kernel2 2, root 3). If the Hub does not boot, hardware recovery is required:
the UART is TX-only and Dropbear will not start from a broken rootfs.

## Warnings

- Not tested on real hardware in this repository; validate on a test unit or
  with an SPI/JTAG programmer.
- Never touch `mtd:mfg` (per-unit certificate/private key), `mtd:data`
  (configuration) or `mtd:cache` unless you know what you are doing.
- The image contains only your **public** key; keep the private key off the Hub
  and out of git.
