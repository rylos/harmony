# Harmony Hub — Firmware: sintesi operativa

> 2026-11-09. **L'Hub non è stato modificato.** Dettagli completi (reverse engineering, API registry, tabelle, Ghidra, fonti): `firmware/REVERSE_ENGINEERING.md`.

---

## 1. Dispositivo

| Campo | Valore |
|---|---|
| Prodotto | Pimento (Harmony Hub) — SUS product **97**, immagine intended skin 97/106/109 |
| Unità | skin **106**, `remoteId` **<remoteId>**, `accountId` <accountId>, `unit_id` <unitId>, IP `<hub-ip>` |
| Firmware | **4.15.600** (build 440906), canale production |
| Hardware | Atheros **AR9331** MIPS32 BE, 32 MiB RAM, 16 MiB SPI NOR (ST 25P64V6P / Macronix MX25L128), CC2544 RF/IR, CSR8811 BT |
| Sistema | Linux **2.6.31-g89d565c**, uClibc 0.9.30.1, BusyBox, Yocto/Poky "pimentoblue" |
| Porte | **8088** HTTP/WS · **5222** XMPP locale · discovery UDP **5224** → TCP client (5446) |
| UART | `ttyS0 115200`, **TX-only** (nessun input) |

**Nota:** `discoveryinfo.hubId` è lo **skin** (106), non il remoteId. Il parametro `hubId` del handshake WebSocket è il **remoteId** numerico (<remoteId>).

---

## 2. Immagine firmware

SUS: `https://sus.dhg.myharmony.com/softwareupdatesplatform/softwareupdates`
Header: `Origin: https://setup.myharmony.com`, `Logitech-SUS-Key: UV6nr6k8ZqlLYksPWMOlv5qwNU2lo1j8Q57WgwE5`

```bash
G=$(cat /proc/sys/kernel/random/uuid)
curl -s -H "Origin: https://setup.myharmony.com" \
  -H "Logitech-SUS-Key: UV6nr6k8ZqlLYksPWMOlv5qwNU2lo1j8Q57WgwE5" \
  "https://sus.dhg.myharmony.com/softwareupdatesplatform/softwareupdates/product/97/unit/$G/image/latest?types=SysBuild&trigger=usb&channel=production&guid=$G"
```

Immagine: `https://d3pk1wwd3l8fri.cloudfront.net/sus/images/97/4.15.600.440906.hfw2`
`sha256 9eda076d…a0f8029d`, 4.771.065 B.

Struttura: `.hfw2` (ZIP) → `ota-update.EzHex` (ZIP) → `sdigest`, `digest`, `update`, `uImage.bin`, `harmony-image.squashfs` (SquashFS 4.0 **LZMA legacy**, 3.751.936 B, 652 inode). Estrazione rootfs con **sasquatch** (`unsquashfs` standard fallisce).

---

## 3. Firma e boot

- `digest` = righe `SHA1  nome`; la prima riga è `sha1(sdigest)`.
- `sdigest` = **RSA-2048 PKCS#1 v1.5** sul testo del `digest` **senza la riga `sdigest`** (167 B). Verificato con OpenSSL: `pkeyutl -verifyrecover` restituisce esattamente quel testo.
- Chiave pubblica: 294 B DER, anche in `/opt/luaworks/common/key/sdigest_public.der` (per i `.pkg`) e **embedded nell'initramfs `/init`** a `0x42C0B0`.
- Ghidra su `/init`: `FUN_004006ac(signature, digest)` → `FUN_00406aa4` (RSA public-decrypt) → `FUN_0040fc90` (`strcmp`). Log: `Rsa decrypt failed` / `Digest mismatch`. **Nessun ASN.1/hash nel percorso reale.**
- **U-Boot 1.1.4**, default environment, boot a `0x9F010000`, solo **CRC** (`Verifying Checksum`). **Nessun verified boot.**
- `/init` (initramfs nel kernel) monta `mtd:data`/`mtd:cache`, verifica l'OTA, esegue `/tmp/update`, rinomina `ota-update-complete.zip`; poi monta `mtd:root` (squashfs, ro) + `mtd:data` (rw) con **unionfs** `dirs=/mnt/data=rw:/mnt/root=ro`, chroot e `/sbin/init`.

**Conseguenza:** la firma è solo userspace. Con root si scrivono direttamente `mtd:kernel`/`mtd:root`; U-Boot non verifica. `/etc` è scrivibile via overlay; il **copy-up** permette di sovrascrivere file stock senza riflashare.

---

## 4. Partizioni (16 MiB)

| # | Nome | Offset | Size | Contenuto |
|---|---|---|---|---|
| 0 | `mtd:u-boot` | `0x000000` | 64 KiB | U-Boot 1.1.4 |
| 1 | `mtd:kernel` | `0x010000` | 960 KiB | `uImage.bin` (kernel + initramfs) |
| 2 | `mtd:kernel2` | `0x100000` | 960 KiB | seconda copia kernel (non usata dal bootlog) |
| 3 | `mtd:root` | `0x1F0000` | 4 MiB | `harmony-image.squashfs` |
| 4 | `mtd:data` | `0x5F0000` | 5 MiB | overlay rw (`/etc`, `/data`, `/pkg`) |
| 5 | `mtd:cache` | `0xAF0000` | 5 MiB | `/cache` (OTA, log, backup) |
| 6 | `mtd:mfg` | `0xFF0000` | 64 KiB | cert + chiave privata per-unità |

**Non toccare `mtd:mfg`** (cert/chiave cloud) né `mtd:data` (configurazione). L'immagine OTA (4,77 MB) sta nella cache da 5 MiB con ~460 KiB di margine.

---

## 5. API locale e catena di root nota

- **WebSocket** `ws://hub:8088/?domain=svcs.myharmony.com&hubId=<remoteId>`; envelope `{"hubId":...,"timeout":N,"hbus":{"id","cmd","params"}}`.
- **HTTP POST** `:8088/` con `Origin` contenente `.myharmony.com` (controllo sintattico); `setup.account?getProvisionInfo` è senza auth.
- **XMPP** `:5222` con SASL PLAIN; account guest hardcoded (`guest`/`guest`) e bypass `1111`. Attivo solo se l'app abilita XMPP; sull'unità è aperto.

**Catena di root su 4.15.600 (non eseguita qui):**
1. accesso locale via WS o XMPP guest;
2. `harmony.log?put` concatena il `fileName` senza normalizzare → `../etc/tdeenable` crea `/etc/tdeenable`;
3. `works/system.tdeEnable` controlla l'esistenza del file: si apre `connect.jsonfiletransfer?get|put` (altrimenti `594`);
4. si stagea un package Lua in `/pkg/<nome>` + chunk in `/data/<nome>_stage/`;
5. `harmony.automation?discover` con `gatewayType=<nome>` carica ed esegue il Lua **come root**;
6. il payload installa Dropbear in `/data/rootssh`, `/usr/sbin/dropbear`, `authorized_keys`; `rcS` riavvia SSH al boot.

**Variante USB (ipotetica, NON testata):** la HAL registra `/tde/enable` (handler `libhal_tde_enable_write`: crea `/etc/tdeenable` se il primo byte è `1`) e `/sys/dropbear` (path `/usr/sbin/dropbearmulti`, crea il symlink `/usr/sbin/dropbear`). Se la file API HID/USB accetta queste scritture, sarebbe root con accesso fisico senza XMPP/log. Da verificare solo su unità di test.

---

## 6. Sicurezza (sintesi)

- **CVE-2018-15720/15721** (XMPP hardcoded/auth bypass): codice ancora presente; mitigazione di configurazione (XMPP opt-in), non rimozione.
- **CVE-2018-15722** (command injection time): mitigato dal match `%d*-%d*-%d* %d*:%d*:%d*` prima di `date -s`.
- **CVE-2018-15723** (command injection HTTP): il check `Origin` ferma il CSRF del browser, non un client LAN che invia l'header. L'API locale è **non autenticata by design**.
- **TLS:** wolfSSL senza verifica cert/hostname nel layer Lua; FireEye 2018 confermava certificati ignorati. Trattare il canale cloud come non autenticato.
- **Host key SSH stock condivisa:** `/etc/dropbear/dropbear_rsa_host_key` pre-generata 2017 (md5 `d9aac27a…b9f59e`); il rootfs custom la rimuove e la rigenera.
- **Password root:** `/etc/passwd` MD5-crypt (`$1$TNKRrJnc$…`).

---

## 7. Firmware open: verdetto

- **OTA/package ufficiale: NO** — firma RSA-2048, chiave privata solo Logitech.
- **Con root: SÌ** — scrittura diretta delle MTD; U-Boot solo CRC.
- **Bootloader:** riscrivibile in teoria (`mtd:u-boot`, 64 KiB), ma **sconsigliato**: UART TX-only, nessun recovery USB se il bootloader è rotto; servono JTAG/programmatore SPI.
- **Via a basso rischio:** root + overlay copy-up (file stock shadowati in `mtd:data`) o rootfs custom con kernel/HAL stock.
- **Firmware davvero open:** richiede rootfs from-scratch (BusyBox + HAL stock + moduli) o kernel/initramfs custom con BSP AR9331 e driver CC2544/IR/LED/BT (rischio brick).

---

## 8. Rootfs custom (artefatto pronto)

| Voce | Valore |
|---|---|
| Immagine (build locale, non committata) | `firmware/work/harmony-image.custom.squashfs` |
| Dimensione | **3.977.216 B** |
| sha256 | dipende dalla chiave pubblica installata; hash di riferimento non committato |
| Formato | SquashFS 4.0 LZMA (comp id 2), block 128 KiB, 569 inode |
| Margine `mtd:root` | **217.088 B** (partizione 4.194.304 B) |
| Contenuto | rootfs stock 4.15.600 + Dropbear 2025.89 static (`-s -g -K 300`), `/etc/tdeenable`, `/etc/custom-fw`, `authorized_keys` (la tua chiave pubblica) |
| Host key | stock rimossa; `rcS` la rigenera al primo boot (per-unità) |
| Bundle | `firmware/work/custom-fw-4.15.600/` (creato da `firmware/make-bundle.sh`): immagine + `mtdwrite` + `mtdwrite.c` + `flash-rootfs.sh` + `README.txt` + `SHA256SUMS` |
| Build | `firmware/build-custom-rootfs.sh` (richiede `STOCK`, `DROPBEAR`, `PUBKEY`) |

**Chiave:** il repo non include chiavi. Impostare `PUBKEY=/path/alla_tua.pub`; la chiave privata resta fuori dal repo. L'immagine di riferimento usava una chiave ed25519 di test.

**Installazione (piano, NON eseguito):**
1. copiare `firmware/work/custom-fw-4.15.600/` in `/data/custom-fw` (≈4,08 MB; se `/data` è pieno usare `/cache/custom-fw`);
2. verificare `sha256sum -c SHA256SUMS`;
3. `sh flash-rootfs.sh` → backup in `/cache/backup/root-<data>.bin` e scrittura con `mtdwrite --write … --yes --verify --squashfs`;
4. copiare il backup fuori dall'Hub via SSH;
5. `reboot`; SSH con la tua chiave, verificare `/etc/custom-fw`, `dmesg`, servizio Lua;
6. sostituire subito `authorized_keys`.

**Ripristino:** se il sistema boota, `mtdwrite --write /dev/mtd3 /cache/backup/root-<data>.bin --yes --verify`. Se non boota, recovery hardware (UART TX-only).

**Attenzione:** bundle (≈4,08 MB) e backup (4 MB) non stanno entrambi nella stessa partizione da 5 MiB; tenerli in `/data` e `/cache` separatamente o salvare il backup via SSH.

**Verificato:** formato SquashFS compatibile (stessa compression id/block size), estrazione `sasquatch`, SSH end-to-end in QEMU/chroot (Dropbear key-only, root). **Non verificato:** boot reale, `rcS`, HAL/IR/RF/BT, OTA, factory reset.

---

## 9. File e fonti

- Archivio completo: `firmware/REVERSE_ENGINEERING.md`.
- Immagine stock: `4.15.600.440906.hfw2` (dal SUS, **non committata**; rootfs estratto con `sasquatch`).
- Bundle custom: `firmware/work/custom-fw-4.15.600/` (generato, non committato).
- Fonti: FireEye/Mandiant 2018; OpenWrt oldwiki Pimento; Tenable/CVE-2018-15720/21/22/23; `Ripthulhu/harmony-hub-root`; `Ripthulhu/harmony-hub-control`; decompilazione MyHarmony/RRT/firmware 4.15.600 e analisi Ghidra/OpenSSL 2026-11-09.

> **Regola operativa:** nessuna scrittura sull'Hub senza backup verificato e recovery hardware. La UART è TX-only: un rootfs/kernel rotto non è recuperabile da seriale.
