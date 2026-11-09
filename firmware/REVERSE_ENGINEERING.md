> **Nota:** snapshot storico del 2026-11-09. Le directory di scratch (`work/`, `build/toolchains`, `build/dropbear`, `build/rootfs-custom`, `build/test-extract-*`) sono state ripulite; gli artefatti finali sono in `build/custom-fw-4.15.600/`. La sintesi operativa è `../firmware.md`.

# Harmony Hub — Firmware: acquisizione, reverse engineering, firmware open

> Documento di lavoro. Obiettivo: analizzare il firmware dell'Hub **di Marco** (Pimento, fw **4.15.600**) per (1) scrivere un controller open e ottimizzato per uso personale e (2) valutare la fattibilità di un **firmware open** (caricabile dal bootloader / riscrivibilità del bootloader). **Tutto in sola lettura: l'Hub NON è stato modificato.** Le uniche interazioni con il dispositivo sono state comandi read-only (`find-hub`, `sysinfo`, `status`) e un test di apertura porta TCP.
>
> Compagno di `HARMONY_APK_PROTOCOL_ANALYSIS.md` (protocollo client lato app). Questo doc copre il lato **server/firmware**.
>
> Ultimo aggiornamento: **2026-11-09**, seconda passata: immagine riesumata e verificata, initramfs del kernel estratta, firma OTA verificata con OpenSSL, API registry ricavato da `apilistener.lua`, catena di root nota ricostruita dal codice e confrontata con i tool community, analisi Ghidra del binario `update`.

---

## 0. Stato e metodo (TL;DR)

| Domanda | Risposta |
|---|---|
| Il firmware ufficiale è firmato? | **Sì.** `sdigest` = RSA-2048 su `digest`; stessa chiave pubblica per OTA e pacchetti `.pkg`. Senza la chiave privata Logitech non si passa dall'OTA/package manager. |
| Il bootloader verifica il kernel? | **No, solo CRC.** U-Boot 1.1.4, ambiente di default, boot a `0x9F010000`; il bootlog OEM mostra solo `Verifying Checksum`. Nessuna firma. |
| Con root si può mettere un firmware custom? | **Sì, plausibile.** La firma è controllata solo da `/init` (initramfs) e dal tool userspace `update`; con root si scrivono direttamente `mtd:kernel` / `mtd:root` bypassando entrambi. |
| Il bootloader è riscrivibile? | **In teoria sì** (`mtd:u-boot`, 64 KiB, scrivibile da root); **in pratica sconsigliato** senza programmatore SPI/JTAG: la UART è TX-only e un brick non è recuperabile da USB. |
| Alternativa a basso rischio | **Root + servizio in user space** (stile `harmony-hub-control`): kernel, HAL e driver stock, custom code in `/data`. Già provato su 4.15.600. |
| Cosa manca per chiudere la fattibilità | Dump read-only di `mtd:u-boot`, `mtd:kernel2`, `mtd:mfg` e `/proc/mtd` da shell root, più il bootlog UART completo. |

**Metodo di questa passata:** estrazione dell'immagine `.hfw2` → `.EzHex` → SquashFS; `strings` su tutti i file LuaQ (il servizio è **bytecode**, non sorgente); verifica della firma con OpenSSL; estrazione dell'initramfs embedded nel kernel; Ghidra 12.1 headless su `update` e `/init` (MIPS32 BE); confronto con i progetti community `Ripthulhu/harmony-hub-root` e `Ripthulhu/harmony-hub-control`, che documentano la catena di root su 4.15.600.

**Stato pratica:** rootfs custom **costruito e riproducibile** (§11): 3.977.216 B, sha256 `132856ae…`, margine 217 KiB, con Dropbear 2025.89 key-only e `mtdwrite` separato. **Non flashato e non testato su hardware**: serve un backup e un piano di recovery (UART/JTAG/SPI).

---

## 1. Dispositivo

| Campo | Valore |
|---|---|
| Prodotto | **Pimento** (Harmony Hub / Harmony Ultimate Hub) → skin **97**; l'immagine dichiara `INTENDED SKIN 97/106/109` |
| Unità di Marco | `friendlyName` "<friendlyName>" · `productId` "Pimento" · **skin 106** (Home Hub) · `hubId` 106 · `remoteId` **<remoteId>** · `accountId` <accountId> |
| Identificativi | `unit_id` <unitId> · `uuid` <uuid> |
| IP | `<hub-ip>` (DHCP statico) |
| Firmware | **4.15.600** (build 440906), canale `production` |
| SoC | **Atheros AR9331** (MIPS32 big-endian, 24Kc), 32 MiB RAM, **16 MiB SPI NOR** |
| Flash | 16 MiB SPI NOR: ST **25P64V6P** / S25FL064P (OpenWrt) oppure Macronix **MX25L128** (wikidevi, revisioni diverse); settori 64 KiB |
| Radio | AR9331 1×1 2.4 GHz (Wi-Fi) · **TI CC2544** 2.4 GHz (RF/IR) · **CSR8811** Bluetooth · 6 LED IR + 2 jack mini-IR blaster 2,5 mm |
| Sistema | Linux **2.6.31-g89d565c**, uClibc 0.9.30.1, BusyBox, Yocto/Poky "pimentoblue" |
| Porte osservate | **8088/tcp** HTTP + WebSocket · **5222/tcp** XMPP locale · discovery UDP **5224** → risposta TCP del client (default 5446) |
| UART | Pads su PCB, `ttyS0 115200`; secondo FireEye **TX-only** (nessun input) |
| USB | HID `046d:c129` (vendor/product riportati anche da `sysinfo`) |

**Correzione rispetto alla prima passata:** `sysinfo` dell'unità riporta `skin=106`, non 97. Il product SUS è 97; l'immagine è la stessa per 97/106/109. Il campo `hubId` in `discoveryinfo` vale 106 (è lo skin), mentre il parametro `hubId` del handshake WebSocket è il **remoteId numerico** (<remoteId>): il controller attuale usa `REMOTE_ID` e funziona.

**Conferma esterna:** su un Pimento con skin 97, `discoveryinfo` riporta `hubId=97` e un `remoteId` numerico separato (es. <remoteId-example>), quindi `hubId` = skin e il handshake WS usa il remoteId — coerente con la nostra unità (skin/hubId 106, remoteId <remoteId>).

`susChannel` = production; `mode` = 3; `openApiVersion` = 2; `protocolVersion` = `{XMPP="1.0", HTTP="1.0", RF="1.0", WEBSOCKET="1.0"}`; `oohEnabled` = true.

---

## 2. Come procurare l'immagine (ricostruito, riproducibile)

L'immagine **non** ha un URL statico pubblico: si ottiene dal **SUS** (Software Update Server). Catena ricostruita decompilando MyHarmony + il Remote Recovery Tool.

### Server e client
- **SUS**: `https://sus.dhg.myharmony.com` — base path reale `/softwareupdatesplatform/softwareupdates/`
- **Discovery**: `https://svcs.myharmony.com/Discovery/Discovery.svc` (variante CloudFront: `https://cf-svcs.myharmony.com/Discovery/Discovery.svc`)
- **Setup/RRT web**: `https://setup.myharmony.com` · **Asset**: `https://files.myharmony.com`
- MyHarmony desktop (CEF+Silverlight): `https://app.myharmony.com/prod/win/1.0/MyHarmony.zip` (35 MB) / `MyHarmony-App.msi`
- RRT: `setup.myharmony.com/remoterecoverytool/DefaultRRT.html` → per-modello `recover.aspx?<modello>{factory|latest}` → carica il Silverlight **`ClientBin/UpdateLatestFirmwareTool.xap`** (ricompilato 2025-01-10). Dentro: `UpdateLatestFirmwareTool.dll` (flow) + `Web.Driver.dll` (proxy SUS + driver USB).

### API SUS (chiave inclusa)
Header obbligatori: `Origin: https://setup.myharmony.com` e **`Logitech-SUS-Key: UV6nr6k8ZqlLYksPWMOlv5qwNU2lo1j8Q57WgwE5`** (hardcoded in `UpdateLatestFirmwareTool.dll`; senza → 403 Forbidden). Il SUS oggi è un backend **nginx + Express (Node)**.

Template URL (da `GetSUSFirmwareRequestURI`):
```
{SUS}/softwareupdatesplatform/softwareupdates/product/{productId}/unit/{unitId}/image/latest?types={ImageType}&trigger=usb&channel={channel}[&sysBuild={fw}&criticalOnly={bool}]&guid={GUID}[&streams={stream}]
```
- `productId` = **skin** (Pimento = **97**); `unitId` = GUID qualsiasi (tracking); `ImageType` ∈ `Config|SysBuild|AppBuild|None`; `channel`=`production`.
- **Osservazione 2026-11-09:** con `channel=production` i valori provati di `types` (`Config|SysBuild|AppBuild|None`) e `trigger` (`usb|factory|recovery|rrt|ota`) restituiscono **sempre la stessa immagine 4.15.600**; per Pimento il SUS ha una sola immagine per prodotto/canale e `ImageType` nella risposta è sempre `1` (SysBuild). Non esiste un endpoint di listing (`/image` → 404), solo `image/latest`. Non sono stati provati canali diversi da `production`.
- Endpoint alternativo senza unit: `product/{id}/image/latest` → risposta `GetLatestImageResult`.

Comando riproducibile (sola lettura):
```bash
SUS=https://sus.dhg.myharmony.com/softwareupdatesplatform/softwareupdates
G=$(cat /proc/sys/kernel/random/uuid)
curl -s -H "Origin: https://setup.myharmony.com" \
     -H "Logitech-SUS-Key: UV6nr6k8ZqlLYksPWMOlv5qwNU2lo1j8Q57WgwE5" \
     "$SUS/product/97/unit/$G/image/latest?types=SysBuild&trigger=usb&channel=production&guid=$G"
```
Risposta (2026-11-09):
```json
{"GetLatestImageUpdateResult":{"Id":"4.15.600","ProductId":"97","ImageType":1,
 "Size":4771065,"IsCritical":true,"CanUpdateOta":false,
 "URI":"https://d3pk1wwd3l8fri.cloudfront.net/sus/images/97/4.15.600.440906.hfw2",
 "URI2":"https://dhg-prod-sus-suss3bucket-1d3ewoswtrcur.s3.amazonaws.com/sus/images/97/4.15.600.440906.hfw2"}}
```

### Mappa skin → prodotto (da `UpdateLatestFirmwareTool.dll`)
`97`=Harmony Hub (Pimento) · `99`=Touch · `100`=Ultimate · `102`=Ultimate One · `105/108`=Ultimate Home · `106`=Harmony Home Hub · `111`=Elite/Pro · `112`=950.

### Service account WCF (bonus)
`{svcs}/UserAccountDirectorPlatform/UserAccountDirector.svc/json2/GetGlobalRemote` e `/SubmitUserDataLogs`. Namespace `http://www.logitech.com/2009/08/Harmony.Web.Data.Web/`. Service romdata (config): `IRomDataLibrary` (`RequestRomDataT`, `RequestOperationDataT`).

### Chiavi hardcoded nel firmware (per completezza)
| Chiave | Dove | Uso |
|---|---|---|
| `UV6nr6k8ZqlLYksPWMOlv5qwNU2lo1j8Q57WgwE5` | `UpdateLatestFirmwareTool.dll` | header `Logitech-SUS-Key` per il SUS (RRT) |
| `YZ8WWjUdCFvhfhWOlTg0JosLAlyhhzoRlmckXEn7` | `tasks/harmonywebservices/proxy/softwareupdate.lua` | header `Logitech-SUS-Key` per `SoftwareUpdateService/GetUpdates` |
| `485f377a-04e2-466a-9580-29517c7dee09` | `tasks/connectserver/transport/cloudapi.lua` | header `Logitech-API-Key` verso `CloudApi/*` |
| `Twl7yp6E250m35VwG65wNAvaaV8yaL5l` | `tasks/automation/apihandler/automation.lua` | `?key=` verso l'API gateway dell'automazione |
| `sdigest_public.der` | rootfs + initramfs | chiave pubblica RSA-2048 di OTA e pacchetti `.pkg` |

Nessuna chiave privata è presente nel firmware (solo la pubblica). La chiave privata OTA Non è quindi ricavabile dall'immagine.

---

## 3. Struttura dell'immagine `4.15.600.440906.hfw2`

`.hfw2` = **ZIP** → `.EzHex` = **ZIP** → payload.

```
4.15.600.440906.hfw2 (ZIP, 4.771.065 B, sha256 9eda076d…a0f8029d, md5 d59613c4…b0655379da)
├─ Description.xml            manifest: FILE ota-update.EzHex, PATH /fw/otaupdate,
│                             OPERATIONTYPE=firmwareupgrade, INTENDED skin 97/106/109
│                             CHECKSUM MD5 = 1de1190ba404f37380774f838eb74d3b
│                             ↑ è l'MD5 di ota-update.EzHex, NON del .hfw2
└─ ota-update.EzHex (ZIP, 4.769.907 B, sha256 ce552416…a7767d25)
   ├─ sdigest               256 B  sha1 dd909b7a…  = firma RSA-2048 (vedi §3.1)
   ├─ digest                217 B  sha1 dd909b7a…  = elenco SHA1 dei file
   ├─ update                127.068 B  sha1 9376451e…  ELF MIPS32 BE statico stripped
   ├─ uImage.bin            951.019 B  sha1 4d48b569…  U-Boot uImage, LZMA
   └─ harmony-image.squashfs 3.751.936 B sha1 d14915ed… SquashFS 4.0 LZMA legacy
```

`digest` (formato `SHA1  nome`, con `sha1(sdigest)` come prima riga):
```
dd909b7a3d23a83214dab887dd4afe5024b23dd5  sdigest
9376451ec9f97a0cc113ea014bddd41f6156d562  update
4d48b5698e732941c61ccb72122b6f1450e27902  uImage.bin
d14915eded74a18ba52c08688ba402e32d7ce571  harmony-image.squashfs
```
Gli SHA1 di `update`, `uImage.bin` e `harmony-image.squashfs` corrispondono ai file estratti: il `digest` è coerente.

### 3.1 Firma: cosa firma davvero `sdigest`

Verificato con OpenSSL, non solo con `strings`:

```bash
# chiave pubblica: 294 B DER, RSA-2048, modulo 00:be:51:aa:61:2f:67:62:ef:…
openssl rsa -pubin -inform DER -in sdigest_public.der -pubout -out pub.pem
# "public decrypt" della firma
openssl pkeyutl -verifyrecover -pubin -inkey pub.pem -in sdigest -out recovered.bin
# recovered.bin == digest senza la prima riga (quella di sdigest), 167 byte
cmp <(tail -c +51 digest) recovered.bin   # identico
```

Quindi:
- `sdigest` è una **firma RSA-2048 PKCS#1 v1.5 sul testo grezzo del `digest`**, non un `DigestInfo` ASN.1 e non un hash del digest.
- Il payload firmato è il `digest` **senza la riga `sdigest`** (167 B); la riga `sdigest` è solo l'auto-hash del file.
- I messaggi `Error: This is not a valid ASN.1 file` / `rsa ctx is NULL` presenti nei binari appartengono a un percorso legacy o non usato per questo pacchetto: la verifica reale è il confronto del plaintext RSA con il testo del digest.
- **Conferma Ghidra su `/init`:** `FUN_004006ac(signature, digest)` chiama `FUN_00406aa4` (RSA public-decrypt con la chiave DER embedded a `0x42C0B0`, 294 B) e poi `FUN_0040fc90` (un `strcmp` byte-a-byte) tra il plaintext e il digest; log `Rsa decrypt failed` se il decrypt fallisce, `Digest mismatch` se il confronto non è zero. La chiave è embedded nell'initramfs, non letta da file.
- La **stessa chiave pubblica** è:
  - in `/opt/luaworks/common/key/sdigest_public.der` (294 B) per i pacchetti `.pkg` (`signature.verifyPublic`);
  - **embedded nell'initramfs `/init`** del kernel a offset `114864` (stessi 294 B, stesso modulo). È quindi `/init` il vero gate OTA.
- `update` contiene le stringhe del codice di verifica ma **non contiene la chiave**: la verifica effettiva avviene in `/init` prima di eseguire `/tmp/update`.

### 3.2 Kernel (`uImage.bin`)
- `uImage` U-Boot legacy, nome **"Pimento Kernel Image"**, OS Linux/MIPS, compressione **LZMA**.
- Load address `0x80002000`, entry point `0x801CB980`, header CRC `0xCBBBCBC9`, data CRC `0x15DA310D`, data 2025-08-12 13:54:22.
- Dentro: Linux **2.6.31-g89d565c** (gcc 4.5.0, build 2025-08-12 19:23:51 IST) + **initramfs cpio embedded** (due archivi; `/init` ELF statico MIPS, 127.412 B, sha1 `5fe53dfc…`).
- Il kernel è ricompilato nel 2025 ma la versione resta 2.6.31 (BSP AR9331).

### 3.3 Rootfs
- SquashFS 4.0 **LZMA legacy**, 652 inode, 3.751.936 B, creato 2025-08-12 13:58:22.
- `unsquashfs` standard fallisce (`lzma uncompress failed error 9`); serve **sasquatch** (installato). Estratto: 14 MB.
- Contiene `/opt/luaworks` (servizio), `/usr/bin/hal` (HAL), `/lib/modules/2.6.31-g89d565c/`, `/lib/firmware/`, `/etc`, `/usr`, `/bin`, `/sbin`.
- Curiosità: `/etc/mtab` è stato copiato dal **build host**, non dal device: elenca `/dev/nvme0n1p2` btrfs, systemd, `/home/marco/Games`, ecc. Nessun impatto, ma è un leak di igiene di build.

---

## 4. Boot, partizioni MTD e overlay

### 4.1 U-Boot
- **U-Boot 1.1.4** (confermato da FireEye e dal bootlog OpenWrt), ambiente **"Using default environment"**: nessuna env persistita in flash, `bootcmd` compilato.
- Bootlog OEM (hardware identico): `Booting image at 9f010000 … Verifying Checksum at 0x9f010040 … OK`. **Solo CRC**, nessuna firma.
- UART `ttyS0 115200`, ma secondo FireEye il circuito è **TX-only**: si vede il boot, non si può interrompere l'autoboot da seriale.
- `kernel2` (960 KiB) è una seconda partizione kernel, non usata dal bootlog (U-Boot parte da `0x9F010000`); probabile backup/alternativa, da verificare con dump.

### 4.2 Partizioni (layout 16 MiB, il solo compatibile con la flash da 16 MiB)
Stringa `mtdparts` nel kernel:
```
ar7240-nor0:64k(u-boot),960k(kernel),960k(kernel2),4096k(root),5120k(data),5120k(cache),64k(mfg)
```
| # | Nome | Offset | Dimensione | Contenuto |
|---|---|---|---|---|
| 0 | `mtd:u-boot` | `0x000000` | 64 KiB | U-Boot 1.1.4 (+ eventuale env) |
| 1 | `mtd:kernel` | `0x010000` | 960 KiB | `uImage.bin` (kernel + initramfs) |
| 2 | `mtd:kernel2` | `0x100000` | 960 KiB | seconda copia/backup kernel (non usata dal bootlog) |
| 3 | `mtd:root` | `0x1F0000` | 4096 KiB | `harmony-image.squashfs` (lower, ro) |
| 4 | `mtd:data` | `0x5F0000` | 5120 KiB | overlay rw (jffs2/ubifs): `/etc`, `/data`, `/pkg`… |
| 5 | `mtd:cache` | `0xAF0000` | 5120 KiB | `/cache` (OTA, log, factoryreset) |
| 6 | `mtd:mfg` | `0xFF0000` | 64 KiB | dati di manifattura per-unità (cert + chiave privata) |

Somma = 16 MiB esatti. Il kernel contiene anche i layout per flash da 4/8 MiB (altri modelli AR7240); per Pimento vale quello da 16 MiB. I nomi `mtd:log` e `mtd:ubi` presenti in `update`/`/init` sono generici per altre varianti: **non** compaiono nel layout Pimento.

La cache da 5 MiB deve contenere `ota-update.zip` (4,77 MB): margine ~460 KiB (meno l'overhead jffs2). Un'immagine sensibilmente più grande non ci starebbe; il download a chunk e il rename in `/cache` sono quindi anche un vincolo di spazio, non solo di rete.

### 4.3 Initramfs `/init`: il vero regista del boot
Stringhe e comportamento di `/init` (ELF MIPS statico, embedded nel kernel):

1. monta `mtd:data` e `mtd:cache`;
2. se esiste `/mnt/cache/factoryreset` → **factory reset** (cancella data/cache) e reboot;
3. se esiste `/mnt/cache/ota-update.zip`:
   - estrae l'archivio in `/tmp`, verifica `sdigest`/`digest` con la chiave RSA embedded (`[init] Rsa decrypt failed`, `[init] Digest mismatch`);
   - esegue `/tmp/update` (`[init] Updater: /tmp/update`);
   - rinomina `ota-update.zip` → `ota-update-complete.zip`;
   - reboot;
4. monta `mtd:root` (squashfs) su `/mnt/root` e `mtd:data` su `/mnt/data`;
5. monta **unionfs** su `/mnt/union` con `dirs=/mnt/data=rw:/mnt/root=ro`, sposta i mount (`/proc`, `/sys`, `/cache`) dentro l'union, `chroot` e `exec /sbin/init`.

Conseguenze:
- **`/etc` è scrivibile** attraverso l'overlay unionfs: un file creato in `/etc` finisce in `mtd:data/etc` e persiste ai reboot. È il motivo per cui `/etc/tdeenable` funziona e persiste.
- Il rootfs squashfs (lower) è immutabile; ogni modifica finisce in `mtd:data` (upper).
- **Copy-up:** scrivendo un path già presente nel lower (es. `/opt/luaworks/tasks/connectserver/netservicestarter.lua`, `/usr/sbin/dropbear`), unionfs crea il file nell'upper e questo **shadowa** il rootfs senza riflashare nulla. È così che `harmony-hub-control` patcha i listener stock (`netservicestarter.lua`, `hbushttpserverconnector.lua`, `xmppserverconnector.lua`) e installa il wrapper dropbear. Limite: 5 MiB di upper (`mtd:data`) condivisi con `/data`, `/etc`, `/pkg`.
- Un firmware update **non** cancella `/etc/tdeenable` né `/data/*` (vedi §8.3), ma un **factory reset** sì.
- `mtd:mfg` non è montato: viene letto dal servizio via `openMtd("mfg")` (Lua) e usato per skin, unitId, cert e chiave privata.

### 4.4 Kernel cmdline
Stringa di default nel kernel:
```
console=ttyS0,115200 root=01:00 rd_start=0x80600000 rd_size=8388608 init=/sbin/init
```
L'initramfs embedded esegue `/init`, che a sua volta fa chroot ed `exec /sbin/init`. `root=01:00` (ram0) è il ramdisk; il rootfs vero è montato da `/init` via unionfs.

### 4.5 Dati di manifattura (`mtd:mfg`)
Formato binario proprietario, magic `harmony!` seguito da coppie **length-prefixed** (4 B big-endian per la lunghezza):
```
unitid, arch, skin, usb_vendor_id, usb_product_id, hw_ver, key, cert
```
Nel template di default (`/opt/luaworks/tasks/mfg/data/pimento-20111201145455-000000.mfg`, 1622 B):
- `unitid` 21 B, `arch` "0x11", `skin` "0x61" (=97), `usb_vendor_id` "0x046D", `usb_product_id` "0xC129", `hw_ver` "00.00";
- `key` 608 B = **chiave privata RSA-1024 DER** (template, non quella per-unità);
- `cert` 834 B = certificato PEM.

Sul device reale il file in `mtd:mfg` contiene la coppia **univoca** dell'unità, usata per `AddRemoteByCertificate` / handshake cloud. **Non cancellare mai `mtd:mfg`**: senza cert/chiave l'Hub non può autenticarsi al cloud e non è recuperabile dal firmware.

### 4.6 Factory reset e recovery
- Il factory reset si attiva scrivendo `/mnt/cache/factoryreset` (la HAL espone il path `/sys/factoryreset`; via USB si scrive lo stesso path); `/init` cancella data/cache al reboot.
- Recovery USB (tool community): HID `046d:c129`, protocollo LTCP raw, path `/fw/otaupdate`, `/sys/reboot`, `/sys/factoryreset`, `/sys/wifi/*`, `/rf/deviceinfo`. Scrive un `.hfw2`/EzHex **firmato**; non è un canale per firmware custom.
- Se il kernel/rootfs è corrotto, il recovery USB dipende dal servizio Linux: se non boota, serve UART/JTAG/programmatore SPI. La UART è TX-only → **nessun recupero interattivo**.

---

## 5. Architettura del firmware

### 5.1 Il servizio è in LuaQ (bytecode, non sorgente)
Il cuore è `/opt/luaworks/` (framework "luaworks", Lua 5.1 + VM custom). I file `.lua` sono **bytecode LuaQ** (header `LuaQ`), non sorgente: nomi di funzioni, moduli e stringhe sono intatti e leggibili con `strings`, ma non si decompilano con i tool Lua standard. La tabella dei comandi e i messaggi sono comunque ricostruibili con affidabilità.

Task principali in `/opt/luaworks/tasks/`:
- **connectserver/** — server locale (8088/5222) e cloud:
  - `apihandler/`: `deviceinfo`, `discoveryinfo`, `jsonfiletransfer`, `pair`, `unpair`, `ping`, `powerstate`, `resync`, `rf`, `ssdp`, `statedigest`, `sysinfo`, `system`
  - `transport/`: `hbushttpserverconnector` (HTTP/WS :8088), `ltcpserverconnector` (LTCP locale), `xmppserverconnector` (XMPP :5222), `discovery` (UDP 5224), `ssdpdiscovery`, `cloudapi`, `pubnub`, `packagemgr`, `firmwarecheck`
  - `core/`: `engine`, `clientconnections`, `verifiers`, `policymgr`, `utils`, `websocketconnection`, `xmppconnection`, `discoveryinfo`, `hubInfo`
  - `xmppclient/`: client XMPP verso `connect.logitech.com` (Verse)
- **harmonyengine/** — attività, azioni, IR/RF/BT, timer, timezone, power-on
- **activityengine/** — attività, regole, condizioni schedule/sun/timer/state
- **automation/** — Home Automation e plugin (hue, lifx, insteon, ecobee, honeywell, august, hunterdouglas…)
- **harmonywebservices/** — proxy cloud (`softwareupdate`, `sync`, `preferencemanager`, `statedigest`, `session`, `resourcemanager`, `accountmanager`, `discovery`)
- **crashlog/** — log, crash, usage, upload Loggly
- **mfg/** — lettura dati di manifattura; **setup/** — provisioning, sync, canali; **eventqueue/** — coda azioni/eventi; **watchdog/**

### 5.2 HAL e moduli nativi
- `/usr/bin/hal` (MIPS, dinamico uClibc) gestisce IR (`ir_send`, `ir_send_repeat`, `ir_read`), RF CC2544 (`hot_*`), Bluetooth HID (BlueZ/DBus), LED, Wi-Fi (wpa_ctrl), USB, OTA (`/fw/otaupdate`), file API (open/read/write/close), MTD.
- Moduli nativi in `/opt/lib/luaworks.so.0.0.0`: `socket`, `socket.wolfssl`, `crypto`, `signature`, `irdecoder`, `json`, `mime`, `system`, `lfs`, `bit`, `base64`.
- Moduli kernel: `athrs_gmac`, `ath_i2s`, `cc2544`, `ath_udc`, `gadgetfs`, `asf`, `adf`, `ath_hal`, `ath_rate_atheros`, `ath_dev`, `umac`, `ehci-hcd`, `usbcore`. **Non strippati** (symtab presenti): utili per RE. `cc2544.ko` è `license=GPL v2`, autori Logitech (fonte richiedibile).
- Firmware blob: `cc2544.bin`, `csr8811-a06/a08.psr`, `cc2544.version`.

### 5.3 Interfaccia HBUS/HAL (interna)
Il servizio parla con la HAL via **LTCP** su `127.0.0.1:16716` (loopback), frame da **64 byte**, hello `0x06`, poi JSON:
```
{"id":1,"cmd":"<comando>","data":{…},"timeout":N}
```
Comandi HBUS osservati (namespace): `sys.info`, `sys.led`, `sys.reboot`, `sys.otaupdate`, `wifi.status`, `rf.info`, `rf.pairing`, `rf.unpair`, `hid.setdevice`, `hid.report`, `ir.cap`, `hot.1.*` (proxy verso il servizio), `tde.powerstate`.

Tabella dei file virtuali HAL (path → comando; registrata in `.data`, entry `/tde/enable` a `0x462E28`):
```
/sys/sysinfo      sys.info          /sys/reboot       sys.reboot
/sys/logread      sys.logread       /fw/otaupdate     sys.otaupdate
/ir/ir_cap        ir.cap            /ir/ir_send       ir.send
/ir/ir_loopback   ir.loopback       /ir/ir_test       ir.test
/sys/wifi/*       wifi.*            /rf/hid           tde.rfhid
/rf/pairing       rf.pairing        /rf/unpair        rf.unpair
/rf/deviceinfo    rf.info           /rf/hot           hot.*
/sys/ping         sys.ping          /sys/led          sys.led
/data/resource    data.resource     /sys/hlapi        (hlapi)
/proc             sys.proc          /tde/buttons      tde.buttons
/tde/leds         tde.leds          /tde/usbdet       tde.usbdet
/sys/factoryreset sys.factoryreset  /tde/flag         tde.flag
/etc/tdeflag      (flag file)       /tde/enable       (scrive /etc/tdeenable)
/tde/memtester    tde.memtester     /etc/memtester    (memtester)
/sys/dropbear     sys.dropbear      /usr/sbin/dropbearmulti
/hid/setdevice    hid.setdevice     /hid/report       hid.report
/bt/*             bt.*/bthid.*      /sys/mac          tde.mac
/sys/mfg          sys.mfg           /sys/jam24        sys.jam24
```
Queste path sono la superficie della **file API** della HAL (usata internamente dal servizio Lua e dal bridge USB); `/tde/enable` e `/sys/dropbear` sono i punti sensibili descritti in §9.3.
L'IR viene inviato con path `/rf/hot/1/ir/ir_send` (o `/ir/ir_send`), con `fire_command`, `ports`, `keyLatency`; la HAL pilota i 6 LED IR via CC2544. Il tasto Pair è su `/dev/input/event0` (EV_KEY code 30, valori 1/0); il LED/TDE su `/sys/class/input/input0/led` e `/sys/class/input/input0/tde`.

### 5.4 Storage dei dati
- `/data` = directory dell'overlay: i file creati qui finiscono nell'upper `mtd:data` (montato su `/mnt/data`), non nel rootfs squashfs.
- `/data/resources/<Nome>.json` (es. `AutomationConfig.json`, `CapabilityList.json`, `ProtocolList.json`, `Context.json`, `index.json`), `/data/luaworks/provision`, `/data/*.json` di preferenze (`preferences`).
- `/cache` = mtd:cache (OTA, log, `factoryreset`, `harmony-recovery`, ecc.).
- `/pkg` = directory creata nell'upper per i pacchetti/plugin (manifest + `.lua` + installer).
- `/etc` = lower squashfs + upper data; i file creati a runtime finiscono in `/mnt/data/etc`.

---

## 6. API locale: trasporti, autenticazione, comandi

### 6.1 Trasporti
| Trasporto | Endpoint | Note |
|---|---|---|
| **WebSocket** | `ws://hub:8088/?domain=svcs.myharmony.com&hubId=<remoteId>` | usato dall'app e dal controller; handshake validato su `hubId` (remoteId) e `domain` |
| **HTTP POST** | `http://hub:8088/` | `Content-Type: application/json` (o `application/octet-stream` per HBUS binario); Origin richiesto: deve contenere `.myharmony.com` |
| **XMPP** | `hub:5222` | SASL PLAIN; account guest hardcoded (`guest`/`guest`, token base64 `Z3Vlc3QAZ3Vlc3QA`), bypass `1111`; attivo solo se `enableXMPP` è impostato dall'app |
| **LTCP** | `127.0.0.1:<port>` | locale, per HAL/app; non esposto in LAN |
| **Discovery** | UDP `5224` → TCP client (5446) | probe `_logitech-reverse-bonjour._tcp.local.\n<port>`; risposta `chiave:valore;…` |

**Envelope WebSocket/HTTP:**
```json
{"hubId":"<remoteId>","timeout":30,
 "hbus":{"id":"msg-1","cmd":"harmony.engine?getCurrentActivity","params":{}}}
```
Il controller attuale omette `hubId` e funziona; il campo è facoltativo lato server. La risposta è `{"hbus":{"id":"…","cmd":"…","code":"200","msg":"OK","data":…}}` oppure un evento push senza `id`.

**Envelope XMPP:**
```xml
<iq type='get' id='xr-1' from='client'>
  <oa xmlns='connect.logitech.com' mime='connect.sysinfo?get'>{}</oa>
</iq>
```
La risposta è `<iq …><oa xmlns='connect.logitech.com' mime='…' code='200' errorcode='' errorstring=''>…</oa></iq>`.

**HTTP speciale:** `POST /` con `cmd=setup.account?provision` o `setup.account?getProvisionInfo` è gestito prima dell'autenticazione (provisioning). `OPTIONS` per CORS; `GET` per WS/SSDP.
**Quirk `connect.ping`:** via WebSocket risponde normalmente; via HTTP POST con un body minimale (`{"id":"124","cmd":"connect.ping"}`) il firmware 4.15 risponde **417** con `{"code":"417"}`. Il controller considera raggiungibile l'Hub se riceve un JSON con `code` (vedi `ping_http`), non solo 200. Il body atteso dal firmware è nella forma `status=alive:uuid=…` (vedi `apihandler/ping.lua`).

### 6.2 Autenticazione e policy
- Ogni comando registrato ha un **verifier** (`Default` o specifico). Il verifier `Default` controlla `transport`, token/`access_token`, e la **policy** (`CloudApi/accessPolicy`) per comando, device, attività e livello (`read`/`write`/`challenge`).
- Il layer `verifiers` definisce scope per trasporto: `ltcp`, `ltcp.luaworks`, `ltcp.luadraws`, `ltcp.rf`, `ltcp.bt`, `ltcp.btle`, `ltcp.usb`, `usb`, `hal_http`, `websocket`, `xmpp`, `hbus_http`, `http`, `callback_http`, `pubnub`, `remote`, `internal`, `exempt`, `local`. Per `hbus_http`, `xmpp`, `callback_http` e `hbus_pubsub` esistono **token di default hardcoded** (`default_hbus_http;;`, `default_xmpp;;`, `default_hbus_pubsub;;`, `callbacK_http` — typo nel codice); i token che iniziano con `default_` non possono essere inviati esplicitamente dal client, ma vengono applicati dal server. I trasporti locali `ltcp.*`/`usb`/`hal_http` sono trattati come locali/exempt.
- I trasporti "cloud" (`remote`, `internal`, `http`, `pubnub`) richiedono token/policy reali.
- **In pratica la LAN è fidata:** il controller attuale e i tool community parlano con :8088 e :5222 senza credenziali Logitech. Il check `Origin` (`.myharmony.com`) e il `hubId` sono controlli sintattici, non autenticazione: un client locale può inviare l'header e il remoteId appresi via discovery.
- Il challenge (`generateChallenge`/`validateChallenge`, HMAC-SHA1 + AES, `/etc/challenge`) è usato solo per i trasporti che lo richiedono; non blocca l'API locale.

### 6.3 Registro completo dei comandi (`tasks/apilistener.lua`)
Il file `apilistener.lua` registra ogni comando → modulo/handler → verifier. Ecco l'elenco completo (nome comando = `cmd` nel payload):

```
# connect / pairing / stato
connect.deviceinfo?get
connect.discoveryinfo?get
connect.jsonfiletransfer?get            (gate: /etc/tdeenable)
connect.jsonfiletransfer?put            (gate: /etc/tdeenable)
connect.pair
connect.unpair
connect.ping
connect.resync
connect.rf?pair
connect.rf?info
connect.ssdp?scan
connect.ssdp?lastscanresults
connect.ssdp?startbgndscan
connect.ssdp?pollbgndscan
connect.ssdp?stopbgndscan
connect.statedigest?get
connect.statedigest?update
connect.sysinfo?get
connect.powerstate?get

# harmony engine (attività, device, IR/BT, tempo)
harmony.engine?startactivity
harmony.engine?holdaction
harmony.engine?changechannel
harmony.engine?getcurrentactivity
harmony.engine?setdevicestate
harmony.engine?getallactivities
harmony.engine?getallhadevices
harmony.engine?config
harmony.engine?getconfighash
harmony.engine?helpsync
harmony.engine?helpdiscretes
harmony.engine?isfilepresent
harmony.engine?setdisplaydeviceon
harmony.engine?bluetoothpairing
harmony.engine?bluetoothunpairing
harmony.engine?bluetoothdisconnect
harmony.engine?geteventqueuecount
harmony.engine?sethiddevice
harmony.engine?setsleeptimer
harmony.engine?gettimerinterval
harmony.engine?gettime
harmony.engine?setremotetime
harmony.engine?settimezone
harmony.engine?pairingbutton
harmony.engine?allpoweron
harmony.engine?wlanstatus
harmony.engine?startippair
harmony.engine?finishippair
harmony.engine?addipdevice
harmony.engine?pairstatus
harmony.engine?setcommand
control.button?press
control.button?fire
control.button?release
control.button?hold

# activity engine / automazione
harmony.activityengine?runactivity
harmony.activityengine?locationupdate
harmony.activityengine?suntimes
harmony.automation?discover
harmony.automation?pair
harmony.automation?getstate
harmony.automation?setstate
harmony.automation?remove
harmony.automation?toggle
harmony.automation?refresh
harmony.automation?status
harmony.automation?addprogram
harmony.automation?adddevice
harmony.automation?removedevice
harmony.automation?getutilitymenu
harmony.automation?indicate
harmony.automation?identify

# firmware / pacchetti
harmony.firmware?updateneeded
harmony.firmware?updateinprogress
harmony.firmware?packageinstall
harmony.firmware?packageremove
harmony.firmware?packagemanifest
harmony.firmware                            (default)
setup.firmware                              (default)
setup.firmware?updateneeded
setup.firmware?updateinprogress
setup.firmware?packageinstall
setup.firmware?packageremove
setup.firmware?packagemanifest
setup.firmware?reboot

# setup / provisioning / sync
setup.account?updatesla
setup.account?provision
setup.account?isprovisioned
setup.account?autoprovisionfromhub
setup.account?getProvisionInfo
setup.configchanged
setup.setlanguage
setup.sync?begin
setup.sync?end
setup.sync?contentchanged
setup.sync?deleteresources
setup.syncremotechanges
setup.content?getchannels
setup.content?syncchannels
setup.content?getallmetadata
setup.content?getbtsettings

# manual sync
harmony.manualsync?issyncrequired
harmony.manualsync?state
harmony.manualsync?start

# proxy cloud (usato dal servizio, non dall'app)
proxy.abort
proxy.error
proxy.finished
proxy.request
proxy.resource?get
proxy.resource?put
proxy.response

# log / crash
harmony.log?create
harmony.log?put
harmony.log?run
harmony.log?usage
harmony.log?reset
harmony.log?enable
harmony.log?disable

# sistema
harmony.system?systeminfo
harmony.system?usagelog
```

Alias `vnd.logitech.*` (accettati dal trasporto LTCP/app): `vnd.logitech.setup/vnd.logitech.account?provision`, `vnd.logitech.setup/vnd.logitech.sync`, `vnd.logitech.harmony/vnd.logitech.control.button?press|release|pressType|sequenceFinished`, `vnd.logitech.control/vnd.logitech.button?press&hidCode=…`. Il server normale usa la forma `namespace?comando`.

### 6.4 Parametri dei comandi più utili
| Comando | Parametri principali | Risposta |
|---|---|---|
| `harmony.engine?startactivity` | `activityId` (string), `async`, `timestamp`, `args.rule` | `200`; eventi `startActivityFinished`/statedigest |
| `harmony.engine?holdaction` | `action` (JSON string: `{"deviceId","command","type":"IRCommand"}` oppure `{"sequenceId"}`), `status` = `press`/`hold`/`release`/`pressrelease`, `timestamp` (ms dalla connessione) | fire-and-forget; errori 565/566 |
| `control.button?press/release/hold/fire` | `deviceId`, `command`, `timestamp`, `state/value` per HA, `timestamp` per il moving average | `200`/`561`/`504` |
| `harmony.engine?setdevicestate` | `deviceId`, `state` (lista di `{name,value}`), `skipIr` | `200`, `560`, `565` |
| `harmony.engine?changechannel` | `channel` (numero/string), `deviceId` opzionale | `200`, `565`, `567` |
| `harmony.engine?getcurrentactivity` | – | activityId, `activityStatus` |
| `harmony.engine?config` | `verb:"get"` | `Devices` e `Activities` (ruoli, programmi, regole, ordine); la `ProtocolList` è una risorsa separata in `/data/resources` |
| `harmony.engine?setsleeptimer` | `interval` (secondi; `-1` annulla) | `200`/`412`/`504`; `0` spegne subito |
| `harmony.engine?gettime` | – | `utcTime` |
| `harmony.engine?settimezone` | `timezoneid` | `200`/`504` |
| `harmony.engine?isfilepresent` | `fileName` | `200` + presenza (oracolo) |
| `harmony.engine?getconfighash` | – | hash config |
| `connect.statedigest?get` | `format:"json"` | digest completo (`activityStatus`, devices, ecc.) |
| `connect.statedigest?update` | `currentVersion`, `value` | `200`/`304`/`504` |
| `connect.sysinfo?get` | – | `fw_ver`, `skin`, `unit_id`, `usb_*`, `arch`, `hw_ver` |
| `connect.discoveryinfo?get` | – | `ip`, `port`, `remoteId`, `email`, `uuid`, `protocolVersion`, `discoveryServerUri`, … |
| `connect.powerstate?get` | – | `tde.powerstate` HBUS |
| `connect.rf?info` / `connect.rf?pair` | – / `timeout` | info RF / pairing |
| `connect.pair` / `connect.unpair` | `clientId` | `200` + `status=succeeded`, `protocolVersion`, `hubId`, `remoteId`, `friendlyName` |
| `setup.account?getProvisionInfo` | – | `email`, `activeRemoteId`, `discoveryServer`, `susChannel`, `mode`, `language`, `accountId` |
| `setup.firmware?reboot` | – | reboot |
| `harmony.firmware?updateneeded` | – | `updateNeeded=false:current_fw_version=…` |

### 6.5 Codici di risposta (estratto dal codice)
| Codice | Significato |
|---|---|
| `100` | Continue (in corso) |
| `200` | OK |
| `201` | log upload disabilitato / creato |
| `202` | sync o attività in corso |
| `203` | download firmware in corso |
| `204` | no content / force update |
| `301`/`304` | risorsa spostata / not modified |
| `400.1` | NoOrigin (HTTP) |
| `400.2` | InvalidOrigin |
| `400.3` | NoContentType |
| `400.4` | InvalidContentType |
| `401.1` | token `default_` non ammesso |
| `401.2` | policy out of scope / comando negato |
| `401.3` | challenge richiesto |
| `401.4` | challenge non valido/scaduto |
| `401.5` | problema di policy |
| `401.6` | JSON del challenge non valido |
| `404` | non trovato / nessuna attività |
| `412` | attività non in corso / stato non valido / timer non valido |
| `417` | messaggio vuoto/non valido (HTTP) |
| `500` | errore server / comando non valido |
| `501` | verb non valido / non provisioned / parametri mancanti |
| `502` | Pimento non in hub mode |
| `503` | link loss / HBUS non raggiungibile |
| `504` | argomenti insufficienti |
| `505` | argomento obbligatorio mancante |
| `510` | Hub non pronto |
| `551` | Hub non provisioned |
| `552` | lookup discovery fallito |
| `553` | sync fallita / errore risorse |
| `560` | config account non disponibile |
| `561` | stato bottone non valido |
| `562` | richiesta ritardata non processata |
| `563` | sequenza non trovata |
| `564` | attività non in corso |
| `565` | device non trovato |
| `566` | comando non trovato per il device |
| `567` | attività non trovata / nessuna attività corrente |
| `569` | attività non trovata per activityId |
| `580` | nessun gateway discovered |
| `581` | errore secret data |
| `582` | pairing fallito |
| `583` | stato automazione non recuperabile |
| `584` | stato automazione non impostabile |
| `585` | remove gateway fallito |
| `587` | device non trovato (automazione) |
| `588` | refresh fallito |
| `589` | argomenti toggle errati |
| `590` | UID IP device non trovato |
| `591` | lista canali non recuperabile |
| `592` | plugin non trovato / non pronto |
| `594` | jsonfiletransfer disabilitato in production (manca `/etc/tdeenable`) |
| `595`/`596`/`597` | jsonfiletransfer: manca file/path/content |
| `598` | jsonfiletransfer: errore decode/write |
| `599` | parametri obbligatori mancanti |
| `600` | errore risposta proxy |

I codici `510`, `5504`, `100/200.2` sono gestiti dal trasporto con retry/timeout (vedi `HARMONY_APK_PROTOCOL_ANALYSIS.md`).

---

## 7. Servizi cloud e protocollo remoto

### 7.1 Endpoint
| Servizio | Path (via Discovery `getServiceUrl`) |
|---|---|
| Discovery | `https://svcs.myharmony.com/Discovery/Discovery.svc` · CF: `https://cf-svcs.myharmony.com/Discovery/Discovery.svc` |
| Login SOAP | `https://svcs.myharmony.com/HarmonyPlatform/AuthenticationService.svc` (`Login`) |
| Cloud API | `CloudApi/login`, `CloudApi/accessPolicy`, `CloudApi/message`, `CloudApi/postHubWifi` |
| Firmware | `SoftwareUpdateService/GetUpdates` |
| Risorse | `ContentService/User`, `ContentService/Device`, `ContentService/Service`, `ContentImageService/Image` |
| Automazione | `HomeAutomationService/Config` |
| Installer | `InstallerService/installerinfo` |
| Log | `LoggingService/SubmitUsageData`, `Loggly/EmbeddedClient` |
| Pairing | `RemoteManager/SavePairings`, `AuthenticationService/AddRemoteByCertificate` |
| Ora | `TimeServer/current` |
| Notifiche | `http://tobasco.dynamite.myharmony.com/harmony/notify` (email) |
| Internet check | `ping.myharmony.com` |

### 7.2 XMPP cloud
- Client in `tasks/connectserver/xmppclient/` basato su **Verse**; server `connect.logitech.com`, JID/password dal provisioning, porta da discovery (`connect_port`).
- Il servizio locale XMPP (:5222) è separato: serve l'app in LAN e accetta SASL PLAIN con account guest hardcoded. È attivo solo se l'app abilita XMPP (preferenza `enableXMPP`); sull'Hub di Marco la porta 5222 è aperta.
- `logitechconnect.lua` gestisce i messaggi `<iq>` con `xmlns='connect.logitech.com'` e `mime` = comando; stesso schema del trasporto locale.

### 7.3 PubNub
`tasks/connectserver/transport/pubnub.lua` implementa publish/subscribe; chiavi/canali arrivano dal discovery/provisioning (non hardcoded nel firmware). `pubnubwrapper.lua` inoltra eventi/risposte ai client e gestisce le sottoscrizioni con scadenza.

### 7.4 TLS
`works/http.lua` + `works/ssl.lua` usano **wolfSSL** (`socket.wolfssl`, `sslContextClient`). Nel layer Lua non si vedono opzioni di verifica certificato/hostname; FireEye nel 2018 documentò che l'Hub **ignora i certificati non validi**. Non è stato ritestato nel 2026, ma il codice non mostra `verify`/`cafile`/`hostname check`: trattare il canale cloud come **non autenticato** (MITM possibile).

---

## 8. Aggiornamento firmware e pacchetti

### 8.1 Flusso OTA lato Hub
1. `firmwarecheck` (task orario) o `setup.firmware?check` → `SoftwareUpdateService/GetUpdates` con `sysBuild`, `productId`, `channel`, `unitId`, `skinId`, `trigger`.
2. Confronto versioni (major/minor/revision); se nuova, scarica il `.hfw2` a chunk (`Range: bytes=…`) e **estrae `ota-update.EzHex`** con un filtro zip; salva `/cache/tempOta<version>.zip`.
3. Rinomina in **`/cache/ota-update.zip`**; scrive `/etc/fwUpdate.json`; reboot.
4. Al boot, `/init` verifica `sdigest` (RSA) e `digest` (SHA1), estrae in `/tmp`, esegue `/tmp/update`.
5. `update` scrive `uImage.bin` → `mtd:kernel` e `harmony-image.squashfs` → `mtd:root`, poi cancella `/mnt/data/{bin,lib,opt,sbin,usr}` (file stale dell'overlay), sync e rename `ota-update-complete.zip`.
6. `/init` monta il nuovo rootfs/unionfs e avvia `/sbin/init`. `rcS` rimuove `ota-update-complete.zip`.

`update` supporta anche `u-boot.bin` → `mtd:u-boot`, `livedemo.squashfs` → `mtd:log`, `mtd:data`, `mtd:ubi`; **il pacchetto di produzione non li contiene**. La scrittura MTD include erase, bad-block handling e `MEMSETBADBLOCK`.

### 8.2 Firma e limiti
- Firma OTA e pacchetti `.pkg` usano la **stessa chiave RSA-2048** (`sdigest_public.der`), privata solo Logitech.
- `packagemgr.installUpdate` per i `.pkg`: estrae `sdigest`, calcola `sha1sum`, verifica con `signature.verifyPublic` e la chiave in `/opt/luaworks/common/key/sdigest_public.der`; poi esegue l'`installer` indicato nel `manifest.json`.
- **Senza la chiave privata non si installa nulla via OTA/package manager.** Il package manager è quindi inutile per un firmware open, ma la sua catena di caricamento (`/pkg`, `getPlugIn`, `harmony.automation?discover`) è utile per eseguire codice **dopo** il root.

### 8.3 Persistenza e update
- Un firmware update **non** tocca `mtd:mfg`, `/data/codex`, `/data/rootssh`, `/etc/tdeenable`; cancella solo `bin/lib/opt/sbin/usr` in `/mnt/data`. Quindi un root installato in `/data` e `/etc` sopravvive all'OTA (verificato dal tool community; da riconfermare su update reali).
- Un **factory reset** cancella `mtd:data` e `mtd:cache`: root, dropbear, `/etc/tdeenable`, `/pkg`, preferenze e risorse spariscono. Va rifatto tutto.
- `mtd:mfg` va preservato: senza cert/chiave l'Hub non si autentica al cloud.

---

## 9. Sicurezza: superficie d'attacco e catena di root nota

> Questa sezione documenta il comportamento del firmware e la catena resa pubblica dal progetto `Ripthulhu/harmony-hub-root`, testata su 4.15.600. **Non è stata eseguita in questa sessione**: l'Hub è rimasto read-only.

### 9.1 CVE 2018 e stato in 4.15.600
| CVE | Descrizione | Stato nel codice 4.15.600 |
|---|---|---|
| CVE-2018-15720 | account XMPP hardcoded → accesso all'API locale | **codice ancora presente** (`guest`/`guest`, token `Z3Vlc3QAZ3Vlc3QA`). Il server parte solo se l'app abilita XMPP; sull'Hub di Marco :5222 è aperta. Mitigazione di configurazione, non rimozione. |
| CVE-2018-15721 | auth bypass XMPP con richiesta craftata | **codice ancora presente** (`authenticate`, `1111`, `AUTH_GUEST/AUTH_YES`): il login guest è accettato. Stessa mitigazione: XMPP opt-in. |
| CVE-2018-15722 | OS command injection via time update (`date -s`) | **mitigato**: `discovery.lua` estrae con `string.match(utc, "%d*-%d*-%d* %d*:%d*:%d*")` prima di `date -s "…"`; restano solo digit/space/`:`/`-`, niente metacaratteri. Resta la manipolazione dell'ora. |
| CVE-2018-15723 | application-level command injection via HTTP | **controllo Origin sintattico**: `checkOrigin` cerca `.myharmony.com` nell'header. Un client LAN può inviare l'header; il check ferma il CSRF del browser, non un attaccante locale. L'API locale resta **non autenticata by design**. |

### 9.2 Catena di root nota (4.15.600)
1. **Accesso locale all'API**: WebSocket :8088 (hubId/remoteId + domain) oppure XMPP :5222 con login guest (`guest`/`guest`). Non serve la password Logitech.
2. **Scrittura arbitraria via `harmony.log?put`**: il codice concatena il `fileName` fornito dal client con la directory dei log senza normalizzare il path; il tool community sfrutta `../etc/tdeenable` per scrivere `/etc/tdeenable` (overlay unionfs, persistente). Il servizio gira come root.
3. **Gate TDE**: `works/system.tdeEnable` controlla l'esistenza di `/etc/tdeenable`; quando c'è, `connect.jsonfiletransfer?get|put` smette di rispondere `594 Cannot access this API in production mode` e permette lettura/scrittura di file arbitrari (`path=../../etc&file=…`).
4. **Staging di un package Lua**: si scrive `/pkg/<nome>/manifest.json`, `/pkg/<nome>/<nome>.lua` (loader) e i chunk in `/data/<nome>_stage/`; poi `harmony.automation?discover` con `{"gatewayType":"<nome>"}` carica ed esegue il Lua **come root**.
5. **Installazione persistente**: il payload scrive `/data/rootssh/bin/dropbearmulti`, `/usr/sbin/dropbear` (wrapper), `/usr/sbin/dropbearkey`, `/home/root/.ssh/authorized_keys`, `/etc/tdeenable`; avvia dropbear. Al boot `rcS` vede `/etc/tdeenable` + `/usr/sbin/dropbear` e riavvia SSH.
6. **File toccati** (dal README del tool):
   ```
   /etc/tdeenable
   /data/rootssh/bin/dropbearmulti
   /data/rootssh/bin/dropbear       (symlink)
   /data/rootssh/bin/dropbearkey    (symlink)
   /usr/sbin/dropbear               (wrapper)
   /usr/sbin/dropbearkey            (wrapper)
   /home/root/.ssh/authorized_keys
   /etc/dropbear/dropbear_rsa_host_key  (se manca)
   ```

**Perché funziona:** `/etc` è nell'upper unionfs (scrivibile), `tdeEnable` è solo un test di esistenza, `jsonfiletransfer` non valida il path, e `harmony.automation?discover` carica un modulo Lua da `/pkg` senza firma. Non c'è bisogno di sfruttare il kernel o il bootloader.

**Variante USB (ipotetica, NON testata):** con accesso fisico, la file API HID può teoricamente scrivere `/usr/sbin/dropbearmulti` (alla chiusura la HAL crea il symlink `/usr/sbin/dropbear`), `/home/root/.ssh/authorized_keys` e `/tde/enable` (`1`); al reboot `rcS` avvierebbe Dropbear. Se confermata, sarebbe una catena di root **senza XMPP/log**, ma richiede accesso fisico e modifica l'Hub; il tool community dichiara il root USB non implementato. Non eseguire su un'unità di produzione.

### 9.3 Altre osservazioni
- **Host key SSH condivisa:** `/etc/dropbear/dropbear_rsa_host_key` è pre-generata nel 2017 e inclusa nell'immagine (426 B, md5 `d9aac27a8004f801f8ee473318b9f59e`). Se non viene rigenerata, **tutti gli Hub 4.15.600 condividono la stessa host key**. `rcS` la rigenera solo se manca.
- **Password root:** `/etc/passwd` ha `root:$1$TNKRrJnc$lnWpxZUFZ2cLT37.aOpPq0` (MD5-crypt), niente `/etc/shadow`. Non è più vuota come nel 2018; con dropbear key-only non serve.
- **Dropbear in produzione:** `rcS` lo avvia solo se `/etc/tdeenable` è leggibile **e** `/usr/sbin/dropbear` è eseguibile. Nell'immagine stock `/usr/sbin/dropbear` non c'è: il wrapper va installato.
- **TDE hardware:** `/sys/class/input/input0/tde`. Se vale `1` e `/sbin/nart` esiste, parte il bootmode manifattura (IP fisso `192.168.1.108` su eth1, `modules.tde`, `nart`). **`nart` non è presente nell'immagine**: il ramo è morto e, con flag TDE=1, `rcS.local` fa fino a 5 reboot poi prosegue normale. `iperf` è assente (il ramo memtester, attivato da `/etc/memtester`, tenta di avviarlo e fallisce), mentre `memtester` è presente.
- **USB file API:** il bridge HID community apre path arbitrari (`/fw/otaupdate`, `/sys/reboot`, `/sys/factoryreset`, `/sys/wifi/*`, `/rf/deviceinfo`) con comandi raw LTCP `0x01 open`, `0x03 write`, `0x04 read`, `0x07 close`. In teoria un `open("W")` su `/etc/tdeenable` sarebbe un secondo primitivo di root; **non testato** (modificherebbe il device). Il tool ufficiale non lo usa per il root.
- **File virtuali HAL `/tde/enable` e `/sys/dropbear`:** la HAL registra una tabella di file virtuali (entry `/tde/enable` a `0x462E28`, handler `libhal_tde_enable_openread`/`write`). `libhal_tde_enable_write(param, len, data)` crea `/etc/tdeenable` se `len > 0` e `data[0] == '1'` (apertura `0x102`, modo `0644`); `/sys/dropbear` ha come path alternativo `/usr/sbin/dropbearmulti` e `libhal_filesystem_close` crea il symlink `/usr/sbin/dropbear` quando si chiude quel file. La stessa file API è usata dal bridge USB. **Se** la file API USB permette di scrivere `/usr/sbin/dropbearmulti` e `/tde/enable`, un attaccante con accesso USB fisico potrebbe ottenere root senza la catena XMPP/log. **Non testato**: richiede accesso fisico, modifica l'Hub e non è implementato dal tool community (che dichiara il root USB non implementato). Da verificare solo su un'unità di test.
- **`squashfs` del rootfs** è read-only, ma l'overlay è scrivibile: la superficie di persistenza è `mtd:data` (5 MiB). Attenzione allo spazio: log, stage e package competono per 5 MiB.
- **`/etc/mtab`** nel rootfs è del build host (nvme/btrfs/systemd): leak di igiene, non di sicurezza.
- **`fwUpdate.json`** in `/etc` e `/cache/ota-update.log` contengono versioni/URL e stato download: utili per diagnosi, non segreti.

---

## 10. Firmware open: fattibilità (DOMANDA #1)

### 10.1 Verdetto aggiornato
- **Firmware open via canale ufficiale (OTA/package): NO.** Firma RSA-2048 obbligatoria su OTA e `.pkg`, stessa chiave, privata solo Logitech. Il package manager verifica con `signature.verifyPublic`; l'OTA verifica in `/init` prima di eseguire `update`.
- **Firmware open con root: SÌ, tecnicamente plausibile.** La firma è solo userspace: il gate è `/init` (initramfs), mentre `update` si limita a scrivere le MTD. Con root si scrive direttamente `mtd:kernel` e `mtd:root`; U-Boot fa solo CRC. Non c'è verified boot.
- **Bootloader:** U-Boot 1.1.4, ambiente di default, `bootcmd` fisso su `0x9F010000`; `mtd:u-boot` è una partizione da 64 KiB scrivibile da root (salvo lock/RO da verificare). Riscriverlo è possibile in teoria, ma **sconsigliato**: UART TX-only, nessun recovery USB se il bootloader è rotto, servono JTAG/programmatore SPI.
- **Accesso fisico:** la HAL espone via USB file API i file virtuali `/tde/enable` (scrive `/etc/tdeenable`) e `/sys/dropbear` (crea `/usr/sbin/dropbear` da `/usr/sbin/dropbearmulti`). Se la file API USB li accetta senza restrizioni, un attaccante con accesso USB fisico può creare `/etc/tdeenable` e installare Dropbear senza la catena LAN. **Non testato** (richiede scrittura sul device); da verificare su un'unità di test, non sul hub di produzione.
- **Alternativa realistica:** root + servizio in user space (`harmony-hub-control`): kernel/HAL/driver stock, web UI/MQTT/IR locale in `/data`; in più il **copy-up** permette di patchare i file stock (`netservicestarter.lua`, listener, `/usr/sbin/dropbear`) senza riflashare. Già provato su 4.15.600, non tocca U-Boot/kernel/mfg. È la via a basso rischio per un "firmware open" funzionale.

### 10.2 Opzioni, rischio e prerequisiti
| Opzione | Cosa si sostituisce | Rischio | Prerequisiti |
|---|---|---|---|
| **A. User-space overlay** | solo `/data` + `/etc` (via root) | basso | root (catena §9.2); spazio in `mtd:data` (5 MiB) |
| **A2. Overlay patch dei file stock** | file del rootfs shadowati in `mtd:data` (copy-up): `/opt/luaworks/...`, `/usr/sbin/...`, `/etc/...` | basso/medio | root; spazio in `mtd:data`; attenzione a non rompere il servizio Lua; backup dei file originali |
| **B. Rootfs custom** | `mtd:root` (squashfs), kernel stock | medio | root; tool MTD erase/write; rootfs uClibc con libjansson/z/dbus/bluetooth/glib + HAL; backup di `mtd:root`; test di boot |
| **C. Kernel + initramfs custom** | `mtd:kernel` | alto | root; ricompilare/repack `uImage` (LZMA) + initramfs; U-Boot header CRC; backup in `kernel2`; piano di recovery |
| **D. Bootloader custom** | `mtd:u-boot` | molto alto | programmatore SPI/JTAG; dump e reverse di U-Boot; board init AR9331; accettare il brick |

### 10.3 Cosa serve per B/C
- **Root shell** (catena §9.2) e backup verificati di `mtd:u-boot`, `mtd:kernel`, `mtd:kernel2`, `mtd:mfg`, `/proc/mtd`, `/proc/cmdline`.
- **Kernel/rootfs compatibili:** il kernel è 2.6.31 AR9331 con patch Logitech (squashfs LZMA, unionfs 2.5.9.2, ramdisk squashfs, initramfs). Un kernel mainline richiederebbe driver per CC2544/IR/LED/BT e la board Pimento; il BSP AR9331 (Qualcomm/Atheros SDK) è la base realistica.
- **Driver:** `cc2544.ko` è GPL v2 (fonte richiedibile a Logitech); `ath_*` e `umac` sono dual BSD/GPL; la HAL (`/usr/bin/hal`) è **binaria proprietaria** ma dinamica e riutilizzabile in un rootfs custom con le stesse librerie. Per un firmware completamente open andrebbe reimplementata (IR/RF/BT/LED/OTA), lavoro molto maggiore.
- **Spazio:** root 4 MiB, data 5 MiB, cache 5 MiB, RAM 32 MiB. Un rootfs con HAL + Lua + BusyBox + Dropbear ci sta (stock: 3,75 MiB squashfs); niente comodità tipo Python/Node sul device.
- **Recovery:** UART TX-only; il recovery USB funziona solo se Linux/HAL è vivo. Per C/D serve un programmatore SPI (o JTAG) e un dump completo della flash.
- **mfg:** preservare `mtd:mfg` (cert/chiave per-unità) e non riscriverlo. Un firmware custom che perde il cert non può usare il cloud Logitech (per l'uso locale non serve, ma per il provisioning sì).

### 10.4 Checklist read-only per chiudere la fattibilità
Quando/sé si deciderà di toccare l'Hub (non fatto ora):
1. da root: `cat /proc/mtd`, `cat /proc/cmdline`, `dmesg`, `cat /sys/class/input/input0/tde`, `ls -l /dev/mtd*`;
2. dump verificati: `mtd:u-boot` (64 KiB), `mtd:kernel2` (960 KiB), `mtd:mfg` (64 KiB), `mtd:kernel` e `mtd:root` (già noti dall'immagine, ma utili per confronto);
3. `strings`/Ghidra su `mtd:u-boot`: versione, `bootcmd`, presenza di `bootm`/`tftpboot`/`usb`, verifica firma, env;
4. capire se `kernel2` è un fallback e se U-Boot lo usa (bootlog con `kernel2` corrotta);
5. verificare se `mtd:u-boot` è scrivibile da root (flag RO, lock CFI, `mtdinfo`);
6. solo dopo: piano di flash con backup, test su un secondo Hub o con programmatore SPI.

**Raccomandazione:** per l'uso personale, l'opzione **A/A2** (root + `harmony-hub-control` o servizio simile, con patch dei file stock via copy-up) dà quasi tutto il valore di un firmware open senza rischio di brick. L'opzione **B** è il passo successivo ragionevole (rootfs custom, kernel stock) se si vuole eliminare del tutto la dipendenza dal servizio Lua Logitech. **C/D** solo con recovery hardware.

---

## 11. Firmware custom: build locale e artefatti

> Costruito localmente il 2026-11-09. **Nessun artefatto è stato scritto sull'Hub.** Il target è un **rootfs sostitutivo per il kernel stock**: non è un firmware "from scratch", ma un'immagine avviabile con lo stesso kernel, HAL, servizio Lua, moduli e `mtd:mfg`, più SSH key-only e un flasher MTD separato.

### 11.1 Cosa è stato costruito
| Artefatto | Percorso (fuori dal repo) | Dimensione | Note / sha256 |
|---|---|---|---|
| Toolchain | `~/harmony-fw/build/toolchains/mips32--uclibc--stable/` | — | Bootlin 2017.05, gcc 5.4.0, uClibc |
| Dropbear server+keygen | `build/dropbear/dropbear-min/dropbearmulti` | 502.272 B | `a73ae9bd…cb61af5a` |
| Dropbear full multi (confronto) | `work/rootssh/dropbearmulti` (community) | 577.296 B | `e2ea632a…d5c6c8d` |
| Flasher MTD | `build/src/mtdwrite` | 108.444 B | `25fed527…c86bc2` |
| **Rootfs custom** | `build/harmony-image.custom.squashfs` | **3.977.216 B** | **`132856ae…cbfa12`** |
| Script di build | `build/build-custom-rootfs.sh` | — | — |

**Riproducibilità verificata:** due esecuzioni dello script hanno prodotto lo stesso sha256 `132856ae4fa518e4046e867755a488ba66825af2a72b921d6058e12fc2cbfa12` (grazie a `-mkfs-time`/`-inode-time` fissi). La build completa di Dropbear (con `dbclient`/`scp`, poi `strip`) riproduce **esattamente** il `dropbearmulti` del progetto community: stesso sha256 `e2ea632a…`, 577.296 B.

**Bundle pronto:** `~/harmony-fw/build/custom-fw-4.15.600/` contiene `harmony-image.custom.squashfs`, `mtdwrite` + `mtdwrite.c`, `flash-rootfs.sh`, `authorized_keys.test.pub`, `README.txt` e `SHA256SUMS` (verificato con `sha256sum -c`).

**Toolchain e build Dropbear:**
```bash
# toolchain
curl -L -o mips32.tar.bz2 \
  https://toolchains.bootlin.com/downloads/releases/toolchains/mips32/tarballs/mips32--uclibc--stable-2017.05-toolchains-1-1.tar.bz2
tar -xf mips32.tar.bz2
export PATH=$PWD/mips32--uclibc--stable/bin:$PATH

# dropbear 2025.89 (server + keygen, statico)
./configure --host=mips-buildroot-linux-uclibc --disable-zlib --disable-pam \
  --disable-lastlog --disable-utmp --disable-utmpx --disable-wtmp --disable-wtmpx \
  --disable-loginfunc --disable-pututline --disable-pututxline \
  CC=mips-buildroot-linux-uclibc-gcc CFLAGS="-Os -static" LDFLAGS="-static"
make -j"$(nproc)" MULTI=1 PROGRAMS="dropbear dropbearkey" dropbearmulti
mips-buildroot-linux-uclibc-strip dropbearmulti
```

**Pack riproducibile del rootfs:**
```bash
cp -a "$STOCK/." "$OUT/"                     # rootfs stock estratto
install -m 755 dropbearmulti "$OUT/usr/sbin/dropbearmulti"
ln -sf dropbearmulti "$OUT/usr/sbin/dropbear"
ln -sf dropbearmulti "$OUT/usr/sbin/dropbearkey"
sed -i 's#^    /usr/sbin/dropbear$#    /usr/sbin/dropbear -s -g -K 300#' "$OUT/etc/init.d/rcS"
rm -f "$OUT/etc/dropbear/dropbear_rsa_host_key"
printf '1\n' > "$OUT/etc/tdeenable"
printf 'custom-fw 4.15.600 base, built 2026-11-09\n' > "$OUT/etc/custom-fw"
mkdir -p "$OUT/home/root/.ssh" "$OUT/data"
install -m 600 your_key.pub "$OUT/home/root/.ssh/authorized_keys"
chmod 700 "$OUT/home/root/.ssh"
mksquashfs "$OUT" harmony-image.custom.squashfs \
  -comp lzma -b 131072 -noappend -all-root -no-xattrs \
  -mkfs-time 1762700000 -inode-time 1762700000
```
Lo script `~/harmony-fw/build/build-custom-rootfs.sh` fa esattamente questo, con `PUBKEY=` per la propria chiave.

### 11.2 Contenuto dell'immagine
Base: rootfs stock 4.15.600 estratto con `sasquatch`. Modifiche:
- `/usr/sbin/dropbearmulti` (Dropbear 2025.89 static, 502.272 B) + symlink `dropbear` e `dropbearkey`.
- `/etc/init.d/rcS`: la riga `/usr/sbin/dropbear` diventa `/usr/sbin/dropbear -s -g -K 300` (solo chiave, niente password, keepalive 300 s).
- `/etc/tdeenable` (sblocca anche `jsonfiletransfer` e il path SSH stock).
- `/etc/dropbear/dropbear_rsa_host_key` **rimossa**: `rcS` la rigenera al primo boot, quindi ogni unità ha una host key diversa (a differenza dell'immagine stock, che la condivide).
- `/home/root/.ssh/authorized_keys` con la chiave pubblica dell'utente (nel test è stata usata una chiave ed25519 locale, non inclusa).
- `/etc/custom-fw` = marker `custom-fw 4.15.600 base, built 2026-11-09`.
- `/data` creata vuota; nessun `mtdwrite` nell'immagine (è un tool separato, per non consumare spazio).

Superblock verificato: SquashFS 4.0, **compression id 2 (LZMA)**, block 131072, 569 inode, `bytes_used` 3.977.109. Stock: 3.751.936 B, 652 inode, stessa compressione. **Margine nella partizione root (4.194.304 B): 217.088 B.** L'immagine si estrae correttamente con `sasquatch`.

> **Attenzione:** l'immagine contiene una **chiave di test** e va considerata un artefatto di sviluppo. Per un uso reale, rigenerare la coppia e passare la `.pub` a `PUBKEY=... build-custom-rootfs.sh`; non usare la chiave privata di test su una rete non fidata.

### 11.3 Cosa è stato verificato (senza Hub)
- **Formato:** `mksquashfs -comp lzma` produce un'immagine con la stessa compression id (2) e lo stesso block size del rootfs stock; il kernel stock monta squashfs LZMA legacy. `sasquatch` estrae senza errori. Non è stato possibile montarla con il kernel reale (nessun accesso in scrittura all'Hub).
- **QEMU user-mode:** `qemu-mips-static` esegue `busybox`, `lua` (Lua 5.1.4) e `dropbearmulti -V` dal rootfs. `luaworks.so` va in **segfault** sotto QEMU user-mode (VM custom/HAL, dipendenze native): non è quindi possibile emulare il servizio completo con qemu-user; servirebbe una board o un emulatore di sistema con la macchina AR9331.
- **SSH end-to-end nel chroot (qemu-binfmt):** con `/dev` bind-montato, `dropbearkey` ha generato la host key, `dropbear -F -s -g -p 2222` ha accettato la chiave di test e ha eseguito `/bin/sh` come root: `CUSTOM-ROOTFS-OK`, `custom-fw 4.15.600 base…`, `uid=0(root)`. Questo valida binari, permessi, `authorized_keys` e shell; **non** valida il boot del kernel né `rcS`.
```bash
sudo mount --bind /dev rootfs-custom/dev
sudo chroot rootfs-custom /usr/sbin/dropbearkey -t ed25519 -f /etc/dropbear/test_host_key
sudo chroot rootfs-custom /usr/sbin/dropbear -F -E -p 2222 -r /etc/dropbear/test_host_key -s -g &
ssh -i <your-key> -p 2222 -T -o StrictHostKeyChecking=no root@127.0.0.1 \
    'echo CUSTOM-ROOTFS-OK; cat /etc/custom-fw; id'
# poi: kill %1; sudo umount rootfs-custom/dev
```
- **dropbearkey** in chroot fallisce senza `/dev/urandom` (il chroot non ha devtmpfs); sul device `/dev/urandom` c'è. La generazione della host key al primo boot è quindi attesa funzionante, ma **non testata su hardware**.
- **`mtdwrite`**: compilato static MIPS, usage verificato sotto QEMU; non eseguito su MTD reale.

### 11.4 Installazione (piano, NON eseguito)
> Questa è la parte rischiosa: scrivere `mtd:root` può rendere l'Hub non avviabile. Non eseguirla senza backup e senza un piano di recovery hardware (UART/JTAG/programmatore SPI). La UART è TX-only: se il rootfs non boota, Dropbear non parte e non c'è console interattiva.

Percorso previsto, da shell root già ottenuta (catena §9.2):
1. caricare su `/data` (o `/cache`) `harmony-image.custom.squashfs` e `mtdwrite`;
2. identificare la partizione root: `grep '"root"' /proc/mtd` → es. `mtd3`;
3. backup: `mtdwrite --backup /dev/mtd3 /cache/backup/root-stock.bin` (4 MiB). Attenzione: bundle (≈4,08 MB) e backup (4 MB) **non stanno entrambi** in `/data` (5 MiB) né in `/cache` (5 MiB): tenere il bundle in `/data` e il backup in `/cache`, o viceversa, oppure salvare il backup via SSH dal PC (`ssh root@hub 'cat /dev/mtd3' > root-stock.bin`);
4. scrittura: `mtdwrite --write /dev/mtd3 harmony-image.custom.squashfs --yes --verify --squashfs`;
5. `sync` e reboot;
6. verifica: SSH con la chiave di test, `cat /etc/custom-fw`, `dmesg`, controllo che il servizio Lua sia partito e che le attività funzionino;
7. sostituire subito `authorized_keys` con la propria chiave e rimuovere la chiave di test.

**Ripristino:** se il sistema boota ancora (rootfs vecchio o nuovo), `mtdwrite --write /dev/mtd3 /cache/backup/root-stock.bin --yes --verify`. Se non boota, serve recovery hardware; il backup su `/cache` non è raggiungibile senza boot.

**Alternativa più sicura (consigliata come primo passo):** non scrivere `mtd:root`; usare il **copy-up** dell'overlay per sostituire solo i file necessari (`/usr/sbin/dropbear`, `/etc/init.d/rcS`, `/opt/luaworks/...`) e tenere il rootfs stock. È reversibile cancellando i file dall'upper. Il rootfs custom serve per un'installazione pulita o per recuperare un'unità con rootfs corrotto.

### 11.5 Limiti e prossimi passi
- **Non è un firmware completamente open:** kernel 2.6.31 stock, HAL binaria, servizio LuaQ e moduli Logitech restano. Sostituisce solo il rootfs (utente, SSH, configurazione).
- **Nessuna immagine per `mtd:data`/`mtd:mfg`:** non vanno toccate; `/data` contiene configurazione e risorse, `mfg` contiene cert/chiave per-unità.
- **Spazio:** 217 KiB di margine nel rootfs; una web UI/servizio aggiuntivo va in `/data` (5 MiB) o richiede il taglio di altri file.
- **Per un firmware davvero open:** servono (a) rootfs Buildroot con la HAL stock e le librerie uClibc, oppure (b) kernel/initramfs custom con i driver AR9331/CC2544/IR/LED/BT. La via (b) richiede il BSP AR9331, il sorgente `cc2544.ko` (GPL v2, richiedibile) e un recovery hardware. La via (a) è realistica ma non elimina la HAL proprietaria.
- **Test mancanti:** boot reale, SSH, HAL/IR/RF/BT, aggiornamento OTA, factory reset, convivenza con `mtd:data` esistente. Da fare solo su un'unità di test o con programmatore SPI.

### 11.6 Verso un rootfs from-scratch (roadmap)
Un rootfs "nostro" al 100% è possibile ma richiede più lavoro; la via realistica è **BusyBox + HAL stock + driver stock**, senza cambiare kernel:
1. **BusyBox statico** con la toolchain Bootlin (`CROSS_COMPILE=mips-buildroot-linux-uclibc-`, `CONFIG_STATIC=y`), `/sbin/init` → BusyBox, `/etc/inittab` minimale che monta `/proc`, `/sys`, `/dev` (devtmpfs), avvia `rcS`/Dropbear.
2. **HAL stock** (`/usr/bin/hal`) + `libjansson`, `libz`, `libbluetooth`, `libdbus`, `libglib`, `libpthread`, `libm`, `libgcc_s`, `libc` uClibc; **moduli kernel** e firmware blob (`cc2544.bin`, `csr8811-*.psr`).
3. **Servizio custom** al posto (o accanto) a `luaworks`: può parlare direttamente con la HAL via LTCP `127.0.0.1:16716` (formato in §5.3) per IR/RF/BT/LED, oppure con il servizio Lua stock via WebSocket `127.0.0.1:8088`.
4. **/etc minimale**: `passwd` root, `hostname`, `fstab`, `init.d/rcS`, `dropbear`, `wpa_supplicant.conf`; `/data` vuota (upper unionfs).
5. Pack SquashFS LZMA ≤ 4 MiB, test su unità di test/recovery. La HAL resta binaria e proprietaria; i driver `cc2544.ko` sono GPL v2 (fonte richiedibile). Un kernel/initramfs custom è un passo ulteriore (rischio brick).

---

## 12. Strumenti e ambiente usati

- Estrazione: `7z` 26.06, `file`, `unzip`; `binwalk` assente; `squashfs-tools` 4.7.5 + **`sasquatch`** (AUR) per LZMA legacy.
- Firma: `openssl` 3.x (`rsa -pubin`, `pkeyutl -verifyrecover`, `cmp`).
- Kernel/initramfs: `unlzma`, `cpio`, `strings`; initramfs embedded estratta dal `uImage`.
- MIPS: **Ghidra 12.1.2** headless (`/opt/ghidra`), processore `MIPS:BE:32:default`. Analisi di `update`: 298 funzioni; `FUN_004002c0` = verifica SHA1 di un file (log `[update] sha1 verified` / `sha1 failed for %s`), `FUN_00400b78` = wrapper di install/log. Analisi di `/init`: `FUN_004006ac` = verifica firma (RSA public-decrypt + `strcmp`), `FUN_00406aa4` = public-decrypt, `FUN_0040fc90` = `strcmp`; la chiave DER embedded è a `0x42C0B0`. Analisi di `hal`: `libhal_tde_enable_write` (scrive `/etc/tdeenable`), `libhal_filesystem_close` (symlink `/usr/sbin/dropbear`), tabella file virtuali a `0x462E28`. Le chiamate sono spesso tramite tabelle di puntatori (`PTR_FUN_*`), quindi il call graph è opaco in alcuni punti.
- IDA Pro 9.3: non usato in questa passata (MIPS32 BE gestito da Ghidra; il binario è statico stripped).
- Rete: `curl` verso SUS; `./harmony.py find-hub`, `sysinfo`, `status`; test apertura porte TCP su 8088/5222 (read-only).
- Community: `Ripthulhu/harmony-hub-root` (catena di root, USB bridge, file toccati) e `Ripthulhu/harmony-hub-control` (servizio locale, sorgenti C per HBUS/LTCP, script di recovery). Fonti storiche: FireEye/Mandiant 2018, OpenWrt wiki Pimento, Tenable/CVE 2018.

---

## 13. File di lavoro (scratchpad, fuori dal repo)
```
harmony-fw/
  downloads/MyHarmony.zip                sha256 b41174af…c8f5c8009
  extract/AppFiles/                      app MyHarmony (CEF+Silverlight+plugin USB)
  work/UpdateLatestFirmwareTool.xap      sha256 a1415c03…d23e3fc
  work/src_updater/                      DLL decompilata (chiave SUS, template, verifica firma)
  work/kernel/                           kernel decompresso, initramfs estratta, init_key.der
  work/ghidra/                           progetto Ghidra su `update` + script Dump/Decomp
  work/control/                          sorgenti community HBUS/LTCP/rcS.local
  fw97/4.15.600.440906.hfw2             sha256 9eda076d…a0f8029d
  fw97/latest.json                       risposta SUS
  fw97/unz/ezhex/{update,uImage.bin,harmony-image.squashfs,sdigest,digest}
  fw97/unz/ezhex/rootfs/                 rootfs estratto (service Lua in opt/luaworks)
  build/toolchains/                      Bootlin mips32 uClibc 2017.05 (gcc 5.4.0)
  build/dropbear/                        Dropbear 2025.89 (full e server+keygen)
  build/src/mtdwrite.c, mtdwrite         flasher MTD statico (backup/write/verify)
  build/build-custom-rootfs.sh           build riproducibile del rootfs custom
  build/rootfs-custom/                   rootfs di lavoro (non l'immagine finale)
  build/harmony-image.custom.squashfs    rootfs custom 3.977.216 B, sha256 132856ae…
  build/custom-fw-4.15.600/              bundle: immagine + mtdwrite + flash script + SHA256SUMS
  build/keys/                            chiave di test (privata fuori dal repo)
```

## 14. Fonti
- FireEye/Mandiant, "Rooting a Logitech Harmony Hub" (2018) — U-Boot 1.1.4, UART TX-only, certificati ignorati, `/etc/tdeenable`, firmware 4.15.96.
- OpenWrt oldwiki, "Harmony Ultimate Hub Pimento" — AR9331, 32 MiB RAM, 16 MiB flash ST 25P64V6P, bootlog OEM, U-Boot default environment, CRC.
- Tenable / CVE-2018-15720/15721/15722/15723 — account XMPP hardcoded, auth bypass XMPP, command injection time/HTTP; fixed in 4.15.206.
- Wikidevi, "Logitech Harmony Ultimate Hub" — flash Macronix MX25L128, RAM, 6 LED IR, 2 jack mini-IR.
- Forum FHEM (thread Harmony Hub) — esempio `discoveryinfo` con `hubId=97` (skin) e `remoteId` separato; conferma della semantica del handshake.
- Decompilazione diretta MyHarmony / RRT / firmware 4.15.600 (2026-11-09); verifica firma OpenSSL; initramfs `/init`; Ghidra su `update`.
- `Ripthulhu/harmony-hub-root` (README, `harmony_xmpp_root_shell.py`, `harmony_usb_bridge.py`) e `Ripthulhu/harmony-hub-control` (README, docs/API.md, docs/SECURITY.md, docs/BUILD.md, `payload/source/codex_hbus.c`, `codex_hal_ltcp.c`, `payload/scripts/*`) — catena di root e servizio locale su 4.15.600.
