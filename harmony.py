#!/usr/bin/env python3
"""
🚀 Harmony Hub FAST CLI Controller
CLI ottimizzato per velocità massima con Press/Release precision
"""

import asyncio
import aiohttp
import json
import argparse
import sys
import random
import functools
from typing import Dict, Callable, Any

try:
    import config
except ImportError:
    print("❌ Configuration file 'config.py' not found.")
    print("   Please copy 'config.sample.py' to 'config.py' and configure your Hub details.")
    sys.exit(1)

# Network retry mechanism with exponential backoff
def network_retry(max_attempts: int = 3, base_delay: float = 0.5, max_delay: float = 5.0):
    """
    Decorator for network operations with exponential backoff retry logic.
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 0.5)
        max_delay: Maximum delay in seconds between retries (default: 5.0)
    
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, OSError) as e:
                    last_exception = e
                    
                    # Don't retry on the last attempt
                    if attempt == max_attempts - 1:
                        break
                    
                    # Calculate exponential backoff delay
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    
                    # Add some jitter to prevent thundering herd
                    jitter = random.uniform(0, 0.1 * delay)
                    total_delay = delay + jitter
                    
                    # Log retry attempt (if verbose logging is available)
                    if args and hasattr(args[0], '_verbose_logging') and args[0]._verbose_logging:
                        print(f"🔄 Network error on attempt {attempt + 1}/{max_attempts}, retrying in {total_delay:.2f}s: {e}")
                    
                    await asyncio.sleep(total_delay)
                except Exception as e:
                    # For non-network errors, don't retry
                    raise e
            
            # If we get here, all retry attempts failed
            raise last_exception
        
        return wrapper
    return decorator

from device_helpers import find_device_by_type, find_audio_device, find_tv_device, find_shield_device


# 🔧 CONFIGURATION (Loaded from config.py)
HUB_IP = config.HUB_IP
REMOTE_ID = config.REMOTE_ID
ACTIVITIES = config.ACTIVITIES
DEVICES = config.DEVICES
AUDIO_COMMANDS = config.AUDIO_COMMANDS

class FastHarmonyHub:
    def __init__(self, verbose_logging: bool = False):
        self.base_url = f"http://{HUB_IP}:8088"
        self.ws_url = f"{self.base_url}/?domain=svcs.myharmony.com&hubId={REMOTE_ID}"
        self.session = None
        self._connected = False
        self._ws = None
        self._verbose_logging = verbose_logging
        self._msg_counter = 0

    @network_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def connect(self):
        """Connessione persistente con retry automatico"""
        if self.session is None:
             # Timeout ottimizzato per velocità
            timeout = aiohttp.ClientTimeout(total=3, connect=1)
            self.session = aiohttp.ClientSession(timeout=timeout)
        
        if not self._connected or self._ws is None or self._ws.closed:
            try:
                self._ws = await self.session.ws_connect(self.ws_url)
                self._connected = True
            except Exception as e:
                self._connected = False
                raise e

    async def close(self):
        if self._ws:
            await self._ws.close()
        if self.session:
            await self.session.close()
        self._connected = False

    async def __aenter__(self):
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _send_ws_fast(self, command: Dict, timeout: float = 10) -> Dict:
        """Invio WebSocket ultra-veloce con filtro ID"""
        try:
            # Assicura connessione
            if not self._connected or self._ws is None or self._ws.closed:
                await self.connect()

            # Assicura ID univoco se non presente
            if "id" not in command or command["id"] == "0":
                self._msg_counter += 1
                msg_id = str(self._msg_counter)
                command["id"] = msg_id
                if "hbus" in command:
                    command["hbus"]["id"] = msg_id
            else:
                msg_id = command["id"]

            await self._ws.send_str(json.dumps(command))
            
            try:
                async with asyncio.timeout(timeout):
                    async for msg in self._ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            # Filtra per ID per evitare race condition con notifiche
                            if str(data.get("id")) == str(msg_id):
                                return data
                            # Se è un errore o altro, continua ad ascoltare
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            raise aiohttp.ClientError("WebSocket error")
                        elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                            self._connected = False
                            raise ConnectionError("WebSocket connection closed")
            except asyncio.TimeoutError:
                # Se timeout, assumiamo inviato ma nessuna risposta (fire and forget o slow)
                return {"status": "sent", "warning": "timeout waiting response"}
                    
        except Exception as e:
            self._connected = False
            # Re-raise the exception to let the retry decorator handle it
            raise e
    
    async def start_activity_fast(self, activity_id: str) -> Dict:
        """Avvio attività ultra-veloce"""
        command = {
            "hubId": REMOTE_ID,
            "timeout": 30,
            "hbus": {
                "cmd": "vnd.logitech.harmony/vnd.logitech.harmony.engine?startactivity",
                "id": "0",
                "params": {
                    "async": "true",
                    "timestamp": 0,
                    "args": {"rule": "start"},
                    "activityId": activity_id
                }
            }
        }
        return await self._send_ws_fast(command, timeout=3)
    
    async def send_device_fast(self, device_id: str, command: str, use_press_release: bool = True) -> Dict:
        """Comando dispositivo con Press/Release per massima precisione"""
        action_json = json.dumps({"command": command, "type": "IRCommand", "deviceId": device_id})
        
        params = {
            "status": "press",
            "timestamp": "0",
            "verb": "render",
            "action": action_json,
        }
        cmd_press = {
            "hubId": REMOTE_ID, "timeout": 10,
            "hbus": {
                "cmd": "vnd.logitech.harmony/vnd.logitech.harmony.engine?holdAction",
                "id": "0", "params": params,
            },
        }
        
        if use_press_release:
            # Press — await response
            result = await self._send_ws_fast(cmd_press, timeout=0.2)
            
            # Minimal pause to simulate real button press
            await asyncio.sleep(0.02)
            
            # Release — fire-and-forget (Hub never responds to release)
            self._msg_counter += 1
            release_params = dict(params, status="release")
            cmd_release = {
                "hubId": REMOTE_ID, "timeout": 10, "id": str(self._msg_counter),
                "hbus": {
                    "cmd": "vnd.logitech.harmony/vnd.logitech.harmony.engine?holdAction",
                    "id": str(self._msg_counter), "params": release_params,
                },
            }
            if self._ws and not self._ws.closed:
                await self._ws.send_str(json.dumps(cmd_release))
            
            return result
        else:
            return await self._send_ws_fast(cmd_press, timeout=1)
    
    async def get_current_fast(self) -> Dict:
        """Stato corrente ultra-veloce"""
        command = {
            "hubId": REMOTE_ID,
            "timeout": 10,
            "hbus": {
                "cmd": "vnd.logitech.harmony/vnd.logitech.harmony.engine?getCurrentActivity",
                "id": "0",
                "params": {"verb": "get"}
            }
        }
        return await self._send_ws_fast(command, timeout=2)

    async def get_config_fast(self) -> Dict:
        """Recupera configurazione completa del Hub ultra-veloce"""
        command = {
            "hubId": REMOTE_ID,
            "timeout": 30,
            "hbus": {
                "cmd": "vnd.logitech.harmony/vnd.logitech.harmony.engine?config",
                "id": "0",
                "params": {"verb": "get"}
            }
        }
        return await self._send_ws_fast(command, timeout=3)

    async def get_hub_info_fast(self) -> Dict:
        """Recupera informazioni del Hub ultra-veloce"""
        command = {
            "hubId": REMOTE_ID,
            "timeout": 10,
            "hbus": {
                "cmd": "vnd.logitech.harmony/vnd.logitech.harmony.engine?getCurrentActivity",
                "id": "0",
                "params": {"verb": "get"}
            }
        }
        # Get current activity first, then we can extend this with more hub info
        current_result = await self._send_ws_fast(command, timeout=2)
        
        # Add hub connection info to the result
        hub_info = {
            "ip": HUB_IP,
            "remote_id": REMOTE_ID,
            "current_activity": current_result
        }
        
        return {"data": hub_info, "cmd": "hub_info"}

    async def get_provision_info_fast(self) -> Dict:
        """Recupera informazioni di provisioning del Hub ultra-veloce"""
        command = {
            "hubId": REMOTE_ID,
            "timeout": 10,
            "hbus": {
                "cmd": "setup.account?getProvisionInfo",
                "id": "0",
                "params": {}
            }
        }
        return await self._send_ws_fast(command, timeout=3)

async def main():
    parser = argparse.ArgumentParser(
        description="🚀 Harmony Hub FAST CLI Controller - Controllo ultra-veloce del tuo sistema multimediale",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
╭─────────────────────────────────────────────────────────────────╮
│                    🎮 HARMONY HUB FAST CLI                     │
│                   Controllo Ultra-Veloce                       │
╰─────────────────────────────────────────────────────────────────╯

🎯 ATTIVITÀ PRINCIPALI (0.4s - 1.0s):
  harmony.py tv          🔴 Guarda TV        (Samsung + Onkyo)
  harmony.py music       🎵 Ascolta musica   (Solo Onkyo)
  harmony.py shield      🎮 NVIDIA Shield    (Shield + TV + Audio)
  harmony.py clima       ❄️  Condizionatore   (Controllo clima)
  harmony.py off         ⚫ Spegni tutto     (PowerOff globale)

🎵 CONTROLLI AUDIO ONKYO (0.3s):
  harmony.py vol+        🔊 Volume su        (VolumeUp)
  harmony.py vol-        🔉 Volume giù       (VolumeDown)
  harmony.py mute        🔇 Muto/Unmute      (Toggle mute)
  harmony.py audio-on    🎵 Accendi Onkyo    (PowerOn audio)
  harmony.py audio-off   🎵 Spegni Onkyo     (PowerOff audio)

📱 CONTROLLI DISPOSITIVI DIRETTI:
  harmony.py samsung <cmd>    📺 TV Samsung      (es: PowerOn, PowerOff)
  harmony.py onkyo <cmd>      🎵 Onkyo Receiver  (es: VolumeUp, Mute)
  harmony.py shield <cmd>     🎮 NVIDIA Shield   (es: PowerOn, Home)
  harmony.py xbox <cmd>       🎮 Xbox 360        (es: PowerOn, Guide)
  harmony.py ps3 <cmd>        🎮 PlayStation 3   (es: PowerOn, PS)
  harmony.py clima <cmd>      ❄️  Climatizzatore  (es: PowerOn, PowerOff)

🔍 INFORMAZIONI E STATO (0.18s):
  harmony.py status      📊 Stato attuale    (Attività in corso)
  harmony.py list        📋 Lista completa   (Tutti i comandi)
  harmony.py help        ❓ Questo help      (Guida dettagliata)

🔍 DISCOVERY E CONFIGURAZIONE (0.5s - 2.0s):
  harmony.py discover           🔍 Scopri configurazione Hub completa
  harmony.py show-activity <id> 🎯 Dettagli attività specifica
  harmony.py show-device <id>   📱 Dettagli dispositivo specifico
  harmony.py show-hub           🏠 Informazioni Hub e performance
  harmony.py export-config      💾 Esporta config.py aggiornato

⚡ PERFORMANCE:
  • Attività:     0.4s - 1.0s  (75% più veloce del CLI standard)
  • Audio:        0.3s         (Press/Release precision)
  • Stato:        0.18s        (18% più veloce)
  • Dispositivi:  0.3s - 0.5s  (Press/Release precision)
  • Discovery:    0.5s - 2.0s  (Dipende dalla configurazione Hub)

🔧 CONFIGURAZIONE:
  • Hub IP:       {HUB_IP}
  • Remote ID:    {REMOTE_ID}
  • Timeout:      100ms (ottimizzato per velocità)
  • Press/Release: Abilitato (simula telecomando reale)
  • Cache:        Configurazione hardcoded (no query)

💡 ESEMPI D'USO:
  harmony.py tv                    # Avvia "Guarda TV"
  harmony.py vol+ && harmony.py vol+ # Alza volume 2 volte
  harmony.py samsung PowerOff      # Spegni solo la TV
  harmony.py status               # Controlla cosa è attivo
  harmony.py off                  # Spegni tutto rapidamente
  
  # Discovery e configurazione:
  harmony.py discover             # Scopri configurazione Hub
  harmony.py show-activity 32923208 # Dettagli attività specifica
  harmony.py show-device 43664815  # Dettagli dispositivo specifico
  harmony.py show-hub             # Info Hub e test performance
  harmony.py export-config        # Genera config.py aggiornato
  
  # Opzioni avanzate:
  harmony.py vol+ --no-press-release  # Modalità tradizionale
  harmony.py discover --verbose       # Output dettagliato

📝 NOTE:
  • I comandi sono case-insensitive
  • Press/Release simula pressione tasto reale (massima precisione)
  • Usa --no-press-release per modalità tradizionale se necessario
  • Timeout ottimizzati per velocità massima
  • Supporta tutti i dispositivi del tuo Hub Harmony
  • Discovery commands richiedono connessione Hub attiva
  • Usa --verbose per informazioni dettagliate su performance
        """
    )
    
    parser.add_argument('command', nargs='?', help='Comando da eseguire (usa "help" per guida completa)')
    parser.add_argument('action', nargs='?', help='Azione per dispositivo (es: PowerOn) o ID per discovery commands (es: activity/device ID)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Output dettagliato con metriche performance')
    parser.add_argument('--no-press-release', action='store_true', help='Disabilita Press/Release (modalità tradizionale)')
    
    args = parser.parse_args()
    
    # Gestione help esplicito
    if not args.command or args.command.lower() in ['help', 'h', '--help']:
        parser.print_help()
        return
    
    # Pre-validate commands that require parameters before connecting
    cmd = args.command.lower()
    if cmd == "show-activity" and not args.action:
        print("❌ Specifica l'ID dell'attività: harmony.py show-activity <activity_id>")
        return
    elif cmd == "show-device" and not args.action:
        print("❌ Specifica l'ID del dispositivo: harmony.py show-device <device_id>")
        return
    
    # Handle commands that don't require hub connection
    if cmd == "list":
        print("╭─────────────────────────────────────────────────────────╮")
        print("│                🎮 HARMONY FAST CLI                     │")
        print("│                  Comandi Disponibili                   │")
        print("╰─────────────────────────────────────────────────────────╯")
        print()
        print("🎯 ATTIVITÀ PRINCIPALI:")
        for name, info in ACTIVITIES.items():
            icon = {"tv": "📺", "music": "🎵", "shield": "🎮", "clima": "❄️", "off": "⚫"}.get(name, "🎯")
            print(f"  {icon} {name:8} → {info['name']}")
        
        print("\n🎵 CONTROLLI AUDIO:")
        audio_icons = {"vol+": "🔊", "vol-": "🔉", "mute": "🔇", "on": "🎵", "off": "🎵"}
        for name, cmd_name in AUDIO_COMMANDS.items():
            icon = audio_icons.get(name, "🎵")
            print(f"  {icon} {name:8} → {cmd_name}")
        print("  🎵 audio-on  → PowerOn Onkyo")
        print("  🎵 audio-off → PowerOff Onkyo")
        
        print("\n📱 DISPOSITIVI:")
        device_icons = {"onkyo": "🎵", "samsung": "📺", "shield": "🎮", "clima": "❄️", "xbox": "🎮", "ps3": "🎮"}
        for name, info in DEVICES.items():
            icon = device_icons.get(name, "📱")
            print(f"  {icon} {name:8} → {info['name']}")
        
        print("\n🔍 INFORMAZIONI:")
        print("  📊 status    → Stato attuale")
        print("  📋 list      → Questa lista")
        print("  ❓ help      → Guida completa")
        
        print("\n🔍 DISCOVERY E CONFIGURAZIONE:")
        print("  🔍 discover           → Scopri configurazione Hub completa")
        print("  🎯 show-activity <id> → Dettagli attività specifica")
        print("  📱 show-device <id>   → Dettagli dispositivo specifico")
        print("  🏠 show-hub           → Informazioni Hub e performance")
        print("  💾 export-config      → Esporta config.py aggiornato")
        
        print("\n💡 ESEMPI PRATICI:")
        print("  ./harmony.py tv                 # Avvia Guarda TV")
        print("  ./harmony.py vol+ && ./harmony.py vol+  # Volume +2")
        print("  ./harmony.py samsung PowerOff   # Spegni solo TV")
        print("  ./harmony.py status            # Controlla stato")
        print("  ./harmony.py discover          # Scopri configurazione")
        print("  ./harmony.py show-activity 32923208  # Dettagli attività")
        print("  ./harmony.py show-device 43664815    # Dettagli dispositivo")
        print("  ./harmony.py show-hub          # Info Hub e performance")
        print("  ./harmony.py export-config     # Genera config.py")
        
        print("\n⚡ PERFORMANCE:")
        print("  • Attività:     0.4s - 1.0s")
        print("  • Audio:        0.3s") 
        print("  • Stato:        0.18s")
        print("  • Dispositivi:  0.3s - 0.5s")
        print("  • Discovery:    0.5s - 2.0s")
        
        print("\n🔧 OPZIONI:")
        print("  --verbose             → Output dettagliato con metriche")
        print("  --no-press-release    → Modalità tradizionale (no Press/Release)")
        return
    
    # 🚀 COMANDI ULTRA-VELOCI
    async with FastHarmonyHub(verbose_logging=args.verbose) as hub:
        cmd = args.command.lower()
        use_pr = not args.no_press_release  # Press/Release abilitato di default
        
        try:
            # 🔍 DISCOVERY COMMANDS (New functionality with performance monitoring)
            if cmd in ["discover", "show-activity", "show-device", "show-hub", "export-config"]:
                try:
                    from discovery_handlers import handle_discovery_command
                    success = await handle_discovery_command(
                        hub, cmd, args.action, args.verbose, HUB_IP, REMOTE_ID
                    )
                    if not success:
                        return  # Error already printed by handler
                except ImportError:
                    print("❌ Discovery handlers non disponibili")
                    return

            # 📊 BENCHMARK
            elif cmd == "benchmark":
                import time as _t
                audio_alias, audio_device = find_audio_device(DEVICES)
                
                print("╭─────────────────────────────────────────╮")
                print("│        ⚡ HARMONY HUB BENCHMARK         │")
                print("╰─────────────────────────────────────────╯")
                print()
                
                def _stats(times):
                    avg = sum(times) / len(times)
                    mn, mx = min(times), max(times)
                    p50 = sorted(times)[len(times) // 2]
                    return f"avg: {avg:.0f}ms  p50: {p50:.0f}ms  min: {mn:.0f}ms  max: {mx:.0f}ms"
                
                # 1. Raw send_str latency (10x)
                times = []
                for _ in range(10):
                    hub._msg_counter += 1
                    msg = json.dumps({"hubId": REMOTE_ID, "timeout": 1, "id": str(hub._msg_counter),
                        "hbus": {"cmd": "vnd.logitech.harmony/vnd.logitech.harmony.engine?getCurrentActivity",
                                 "id": str(hub._msg_counter), "params": {"verb": "get"}}})
                    t0 = _t.perf_counter()
                    await hub._ws.send_str(msg)
                    times.append((_t.perf_counter() - t0) * 1000)
                print(f"📊 Raw WebSocket send_str (10x):")
                print(f"   {' / '.join(f'{t:.1f}ms' for t in times)}")
                print(f"   {_stats(times)}")
                print()
                # drain
                try:
                    async with asyncio.timeout(0.5):
                        async for msg in hub._ws:
                            if msg.type != aiohttp.WSMsgType.TEXT:
                                break
                except asyncio.TimeoutError:
                    pass
                
                # 2. Status round-trip (10x)
                times = []
                for _ in range(10):
                    t0 = _t.perf_counter()
                    await hub.get_current_fast()
                    times.append((_t.perf_counter() - t0) * 1000)
                print(f"📊 Status round-trip (10x):")
                print(f"   {' / '.join(f'{t:.0f}ms' for t in times)}")
                print(f"   {_stats(times)}")
                print()
                
                # 3. Device press+release breakdown (5x Mute toggle)
                if audio_device:
                    t_press, t_sleep, t_release, t_total = [], [], [], []
                    for _ in range(5):
                        action = {"command": "Mute", "type": "IRCommand", "deviceId": audio_device["id"]}
                        action_json = json.dumps(action)
                        
                        t0 = _t.perf_counter()
                        # Press
                        tp0 = _t.perf_counter()
                        cmd_press = {"hubId": REMOTE_ID, "timeout": 10, "hbus": {
                            "cmd": "vnd.logitech.harmony/vnd.logitech.harmony.engine?holdAction",
                            "id": "0", "params": {"status": "press", "timestamp": "0",
                                                  "verb": "render", "action": action_json}}}
                        await hub._send_ws_fast(cmd_press, timeout=0.2)
                        tp1 = _t.perf_counter()
                        t_press.append((tp1 - tp0) * 1000)
                        
                        # Sleep
                        ts0 = _t.perf_counter()
                        await asyncio.sleep(0.05)
                        ts1 = _t.perf_counter()
                        t_sleep.append((ts1 - ts0) * 1000)
                        
                        # Release
                        import copy
                        cmd_release = copy.deepcopy(cmd_press)
                        cmd_release["hbus"]["params"]["status"] = "release"
                        tr0 = _t.perf_counter()
                        await hub._send_ws_fast(cmd_release, timeout=0.2)
                        tr1 = _t.perf_counter()
                        t_release.append((tr1 - tr0) * 1000)
                        
                        t_total.append((_t.perf_counter() - t0) * 1000)
                        
                        # Unmute
                        await asyncio.sleep(0.3)
                        await hub.send_device_fast(audio_device["id"], "Mute")
                        await asyncio.sleep(0.3)
                    
                    print(f"📊 Device command breakdown (5x Mute):")
                    print(f"   Press:   {' / '.join(f'{t:.0f}ms' for t in t_press)}  → {_stats(t_press)}")
                    print(f"   Sleep:   {' / '.join(f'{t:.0f}ms' for t in t_sleep)}  → {_stats(t_sleep)}")
                    print(f"   Release: {' / '.join(f'{t:.0f}ms' for t in t_release)}  → {_stats(t_release)}")
                    print(f"   Total:   {' / '.join(f'{t:.0f}ms' for t in t_total)}  → {_stats(t_total)}")
                    print()
                
                # 4. Config retrieval (3x)
                times = []
                for _ in range(3):
                    t0 = _t.perf_counter()
                    await hub.get_config_fast()
                    times.append((_t.perf_counter() - t0) * 1000)
                print(f"📊 Config retrieval (3x):")
                print(f"   {' / '.join(f'{t:.0f}ms' for t in times)}")
                print(f"   {_stats(times)}")
                print()
                
                # 5. Activity start (off → off, safe no-op, 3x)
                times = []
                for _ in range(3):
                    t0 = _t.perf_counter()
                    await hub.start_activity_fast("-1")
                    times.append((_t.perf_counter() - t0) * 1000)
                print(f"📊 Activity start (PowerOff no-op, 3x):")
                print(f"   {' / '.join(f'{t:.0f}ms' for t in times)}")
                print(f"   {_stats(times)}")
                print()
                
                print("✅ Benchmark completato")

            # 🎯 ATTIVITÀ (Priorità su tutto: se scrivo 'off' voglio spegnere il sistema)
            elif cmd in ACTIVITIES:
                activity = ACTIVITIES[cmd]
                if args.verbose:
                    print(f"🚀 Avvio attività: {activity['name']} (ID: {activity['id']})")
                result = await hub.start_activity_fast(activity["id"])
                if "error" not in result:
                    print(f"✅ {activity['name']}")
                    if args.verbose:
                        print(f"📊 Risultato: {result}")
                else:
                    print(f"❌ {result['error']}")

            # 📱 DISPOSITIVI (Specific action overrides generic audio commands but not activities without action)
            elif cmd in DEVICES and args.action:
                device = DEVICES[cmd]
                
                result = await hub.send_device_fast(device["id"], args.action, use_press_release=use_pr)
                
                if "error" not in result:
                    print(f"📱 {device['name']} → {args.action}")
                    if args.verbose:
                        print(f"📊 Risultato: {result}")
                else:
                    print(f"❌ {result['error']}")

            # 🎵 AUDIO COMMANDS
            elif cmd in AUDIO_COMMANDS:
                audio_alias, audio_device = find_audio_device(DEVICES)
                if audio_device:
                    if args.verbose:
                        print(f"🎵 Invio comando audio: {AUDIO_COMMANDS[cmd]} → {audio_device['name']} (ID: {audio_device['id']})")
                    
                    result = await hub.send_device_fast(audio_device["id"], AUDIO_COMMANDS[cmd], use_press_release=use_pr)
                    
                    if "error" not in result:
                        print(f"🎵 {AUDIO_COMMANDS[cmd]}")
                        if args.verbose:
                            print(f"📊 Risultato: {result}")
                    else:
                        print(f"❌ {result['error']}")
                else:
                    print("❌ Nessun dispositivo audio trovato")
            
            # 🎵 AUDIO SPECIALI
            elif cmd == "audio-on":
                audio_alias, audio_device = find_audio_device(DEVICES)
                if audio_device:
                    result = await hub.send_device_fast(audio_device["id"], "PowerOn", use_press_release=use_pr)
                    print(f"🎵 {audio_device['name']} ON" if "error" not in result else f"❌ {result['error']}")
                else:
                    print("❌ Nessun dispositivo audio trovato")
            
            elif cmd == "audio-off":
                audio_alias, audio_device = find_audio_device(DEVICES)
                if audio_device:
                    result = await hub.send_device_fast(audio_device["id"], "PowerOff", use_press_release=use_pr) 
                    print(f"🎵 {audio_device['name']} OFF" if "error" not in result else f"❌ {result['error']}")
                else:
                    print("❌ Nessun dispositivo audio trovato")
            
            # 🔍 STATUS
            elif cmd == "status":
                result = await hub.get_current_fast()
                if "data" in result and "result" in result["data"]:
                    activity_id = result["data"]["result"]
                    if activity_id == "-1":
                        print("⚫ OFF")
                    else:
                        # Trova nome attività
                        for name, info in ACTIVITIES.items():
                            if info["id"] == activity_id:
                                print(f"🟢 {info['name']}")
                                break
                        else:
                            print(f"🟡 ID: {activity_id}")
                else:
                    print(f"❌ {result}")
            
            # ⚫ FALLBACK per 'off' se non definito in ACTIVITIES ma richiesto esplicitamente come attività di sistema
            elif cmd == "off":
                if args.verbose:
                    print(f"🚀 Spegnimento sistema: PowerOff (ID: -1)")
                result = await hub.start_activity_fast("-1")
                if "error" not in result:
                    print("⚫ SPEGNI TUTTO")
                    if args.verbose:
                        print(f"📊 Risultato: {result}")
                else:
                    print(f"❌ {result['error']}")
            
            else:
                print(f"❌ Comando '{cmd}' non riconosciuto. Usa 'list' per vedere i comandi.")
        
        except Exception as e:
            print(f"❌ {e}")

if __name__ == "__main__":
    asyncio.run(main())
