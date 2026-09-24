#!/usr/bin/env python3
"""
Discovery Harmony Hub sulla LAN senza conoscere l'IP.

Protocollo (ricavato dall'app Android ufficiale, WiFiDiscovery.java):
1. Il client apre un server TCP su una porta (default 5446).
2. Invia in broadcast UDP alla porta 5224 il testo
   ``_logitech-reverse-bonjour._tcp.local.\\n<porta>``.
3. L'Hub si connette LUI al server TCP del client e invia una stringa
   ``chiave:valore;chiave:valore;...`` con ip, remoteId, friendlyName, ecc.

Non dipende da config.py: serve proprio per generarla.
"""

import asyncio
import socket
from typing import Dict, List, Optional

DISCOVERY_PROBE_PORT = 5224      # porta UDP su cui ascolta l'Hub
DISCOVERY_LISTEN_PORT = 5446     # porta TCP su cui l'Hub risponde
PROBE_INTERVAL = 3.0             # l'app riinvia il probe ogni 3 s


def _parse_hub_response(raw: str) -> Dict[str, str]:
    """Converte ``a:1;b:x:y;c`` in {a: "1", b: "x:y", c: ""} (stessa logica dell'app)."""
    info: Dict[str, str] = {}
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        parts = item.split(":")
        if len(parts) < 2:
            info[parts[0]] = ""
        else:
            info[parts[0]] = ":".join(parts[1:])
    return info


def _broadcast_addresses() -> List[str]:
    """Indirizzi broadcast da usare: quello globale più quelli delle interfacce (se ricavabili)."""
    addrs = ["255.255.255.255"]
    try:
        import ipaddress
        import subprocess
        out = subprocess.run(["ip", "-4", "-o", "addr"], capture_output=True, text=True, timeout=2).stdout
        for line in out.splitlines():
            fields = line.split()
            if len(fields) > 3 and "/" in fields[3] and not fields[3].startswith("127."):
                net = ipaddress.ip_interface(fields[3]).network
                addrs.append(str(net.broadcast_address))
    except Exception:
        pass
    # dedup preservando l'ordine
    seen = set()
    return [a for a in addrs if not (a in seen or seen.add(a))]


async def discover_hubs(timeout: float = 6.0, listen_port: int = DISCOVERY_LISTEN_PORT,
                        first_only: bool = False, verbose: bool = False) -> List[Dict[str, str]]:
    """
    Cerca Hub Harmony sulla LAN.

    Args:
        timeout: durata massima della ricerca in secondi
        listen_port: porta TCP locale su cui l'Hub risponde
        first_only: termina appena trovato il primo Hub
        verbose: stampa i passi

    Returns:
        Lista di dict con le chiavi inviate dall'Hub (ip, remoteId, friendlyName,
        hubId, uuid, current_fw_version, email, accountId, discoveryServerUri, ...).
    """
    found: Dict[str, Dict[str, str]] = {}
    done = asyncio.Event()

    async def on_hub_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        try:
            raw = await asyncio.wait_for(reader.read(4096), timeout=3.0)
            info = _parse_hub_response(raw.decode("utf-8", errors="replace"))
            if info:
                info.setdefault("ip", peer[0] if peer else "")
                key = info.get("uuid") or info.get("remoteId") or info["ip"]
                if key not in found:
                    found[key] = info
                    if verbose:
                        print(f"   📡 Hub trovato: {info.get('friendlyName', '?')} @ {info.get('ip')}")
                    if first_only:
                        done.set()
        except Exception as e:
            if verbose:
                print(f"   ⚠️  Risposta Hub non leggibile da {peer}: {e}")
        finally:
            writer.close()

    try:
        server = await asyncio.start_server(on_hub_connect, host="0.0.0.0", port=listen_port)
    except OSError as e:
        raise OSError(f"Porta TCP {listen_port} non disponibile per la discovery: {e}") from e

    probe = f"_logitech-reverse-bonjour._tcp.local.\n{listen_port}".encode()
    targets = _broadcast_addresses()
    if verbose:
        print(f"🔍 Probe UDP → porta {DISCOVERY_PROBE_PORT} su {', '.join(targets)}; risposta attesa su TCP {listen_port}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)

    async def send_probes():
        loop = asyncio.get_running_loop()
        while not done.is_set():
            for addr in targets:
                try:
                    await loop.sock_sendto(sock, probe, (addr, DISCOVERY_PROBE_PORT))
                except (OSError, AttributeError):
                    try:
                        sock.sendto(probe, (addr, DISCOVERY_PROBE_PORT))
                    except OSError:
                        pass
            try:
                await asyncio.wait_for(done.wait(), timeout=PROBE_INTERVAL)
            except asyncio.TimeoutError:
                pass

    prober = asyncio.create_task(send_probes())
    try:
        async with server:
            try:
                await asyncio.wait_for(done.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass
    finally:
        done.set()
        prober.cancel()
        try:
            await prober
        except (asyncio.CancelledError, Exception):
            pass
        sock.close()

    return list(found.values())


def hub_summary(info: Dict[str, str]) -> str:
    """Riga descrittiva di un Hub trovato."""
    name = info.get("friendlyName") or info.get("host_name") or "Harmony Hub"
    return (f"{name}  ip={info.get('ip', '?')}  remoteId={info.get('remoteId', '?')}  "
            f"fw={info.get('current_fw_version', '?')}  email={info.get('email', '?')}")


if __name__ == "__main__":
    import sys

    async def _main():
        hubs = await discover_hubs(timeout=6.0, verbose=True)
        if not hubs:
            print("❌ Nessun Hub trovato")
            sys.exit(1)
        for h in hubs:
            print(hub_summary(h))

    asyncio.run(_main())
