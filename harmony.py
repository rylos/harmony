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
import time
from typing import Callable, Dict, List, Optional, Tuple

__version__ = "5.0"

CONFIG_MISSING_MSG = (
    "❌ Configuration file 'config.py' not found.\n"
    "   Run './harmony.py export-config' to find your Hub on the LAN and create it\n"
    "   (add '--ip <hub ip>' if automatic discovery doesn't find the Hub)."
)

# Comandi che funzionano anche senza config.py: l'Hub viene trovato via discovery
# UDP (o con --ip) e i comandi di discovery servono proprio a generare config.py
NO_CONFIG_COMMANDS = {"find-hub", "discover", "export-config", "show-hub", "show-activity",
                      "show-device", "status", "digest", "sysinfo", "ping", "events"}

try:
    import config
except ImportError:
    config = None

from retry_utils import async_retry
from device_helpers import find_audio_device


def network_retry(max_attempts: int = 3, base_delay: float = 0.5, max_delay: float = 5.0):
    """Retry decorator for FastHarmonyHub network operations (see retry_utils.async_retry)."""
    return async_retry(
        max_attempts, base_delay, max_delay,
        retry_exceptions=(aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, OSError),
        verbose_attr='_verbose_logging',
    )


# 🔧 CONFIGURATION (Loaded from config.py; vuota se manca, così 'find-hub' funziona senza)
HUB_IP = getattr(config, "HUB_IP", "")
REMOTE_ID = getattr(config, "REMOTE_ID", "")
ACTIVITIES = getattr(config, "ACTIVITIES", {})
DEVICES = getattr(config, "DEVICES", {})
AUDIO_COMMANDS = getattr(config, "AUDIO_COMMANDS", {})


def require_config():
    """Esce con messaggio chiaro se config.py manca."""
    if config is None:
        print(CONFIG_MISSING_MSG)
        sys.exit(1)

class HubError(Exception):
    """Errore restituito dall'Hub (code != 200)."""

    def __init__(self, code: str, msg: str, response: Optional[Dict] = None):
        super().__init__(f"Hub error {code}: {msg}")
        self.code = code
        self.msg = msg
        self.response = response or {}


# Codici risposta dell'Hub (da WebSocketLocalTransport.java dell'app ufficiale)
CODE_OK = "200"
CODE_CONTINUE = "100"
CODE_CHALLENGE_OK = "200.1"
CODE_ASYNC_ACCEPTED = "200.2"
CODE_HUB_INITIALISING = "510"
CODE_HUB_REQUEST_TIMEOUT = "5504"

# Tipi di evento push (senza "id") inviati dall'Hub. L'Hub usa maiuscole miste
# (es. "connect.stateDigest?notify") e l'app confronta con equalsIgnoreCase:
# qui normalizziamo tutto in minuscolo in _dispatch_event.
EVENT_STATE_DIGEST = "connect.statedigest?notify"
EVENT_ACTIVITY_FINISHED = "harmony.engine?startactivityfinished"
EVENT_AUTOMATION_STATE = "automation.state?notify"
EVENT_METADATA = "harmonyengine.metadata?notify"
# Eventi sintetici generati dal client
EVENT_CONNECTED = "client.connected"
EVENT_DISCONNECTED = "client.disconnected"

# activityStatus nello state digest
ACTIVITY_IDLE = 0        # nessuna attività / spento
ACTIVITY_STARTING = 1
ACTIVITY_STARTED = 2
ACTIVITY_STOPPING = 3

CMD_ENGINE = "vnd.logitech.harmony/vnd.logitech.harmony.engine"


class FastHarmonyHub:
    """
    Client WebSocket per Harmony Hub (porta 8088).

    Modellato sul trasporto locale dell'app Android ufficiale:
    - un unico reader task smista risposte (messaggi con "id") ed eventi push (senza "id")
    - press/release fire-and-forget con lo stesso id e timestamp relativo alla connessione
    - stato via connect.statedigest?get + eventi connect.statedigest?notify
    - keepalive con frame PING ogni 45 s (heartbeat aiohttp)
    """

    DEFAULT_TIMEOUT = 3.0       # timeout richieste (come l'app)
    ACTIVITY_TIMEOUT = 60.0     # timeout avvio attività (come l'app)
    PING_INTERVAL = 45.0        # PING_INTERVAL dell'app

    def __init__(self, verbose_logging: bool = False, event_callback: Optional[Callable[[str, Dict], None]] = None,
                 hub_ip: Optional[str] = None, remote_id: Optional[str] = None):
        # IP e remoteId espliciti (discovery senza config.py) o da config.py
        self.hub_ip = hub_ip or HUB_IP
        self.remote_id = str(remote_id or REMOTE_ID)
        self.base_url = f"http://{self.hub_ip}:8088"
        self.ws_url = f"{self.base_url}/?domain=svcs.myharmony.com&hubId={self.remote_id}"
        self.session: Optional[aiohttp.ClientSession] = None
        self._connected = False
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._verbose_logging = verbose_logging
        self._msg_counter = 0
        self._connect_time = 0.0
        self._reader_task: Optional[asyncio.Task] = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._event_callback = event_callback
        self._event_waiters: List[Tuple[Callable[[str, Dict], bool], asyncio.Future]] = []
        self.last_digest: Optional[Dict] = None
        self._closing = False
        # Serializza le send: hold_command può girare in parallelo alle altre richieste
        self._send_lock = asyncio.Lock()

    # ------------------------------------------------------------------ connessione

    @network_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def connect(self):
        """Connessione persistente con retry automatico; avvia il reader task."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=None, connect=3, sock_connect=3)
            self.session = aiohttp.ClientSession(timeout=timeout)

        if self._connected and self._ws is not None and not self._ws.closed:
            return

        try:
            # heartbeat: aiohttp invia PING e chiude se manca il PONG (come l'app, 45 s)
            ws_timeout = aiohttp.ClientWSTimeout(ws_close=10) if hasattr(aiohttp, "ClientWSTimeout") else 10
            self._ws = await self.session.ws_connect(self.ws_url, heartbeat=self.PING_INTERVAL,
                                                     timeout=ws_timeout, autoping=True)
        except Exception:
            self._connected = False
            raise

        self._connected = True
        self._connect_time = time.monotonic()
        if self._reader_task is None or self._reader_task.done():
            self._reader_task = asyncio.create_task(self._reader_loop(self._ws))
        self._emit_event(EVENT_CONNECTED, {"ip": self.hub_ip})

    async def close(self):
        self._connected = False
        self._closing = True
        task = self._reader_task
        self._reader_task = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._fail_pending(ConnectionError("WebSocket connection closed"))
        if self.session is not None:
            try:
                await self.session.close()
            except Exception:
                pass
        # Azzera i riferimenti così connect() può ricreare sessione e websocket
        self._ws = None
        self.session = None
        self._closing = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    @property
    def connected(self) -> bool:
        return self._connected and self._ws is not None and not self._ws.closed

    # ------------------------------------------------------------------ reader / eventi

    async def _reader_loop(self, ws: aiohttp.ClientWebSocketResponse):
        """Unico consumatore del WebSocket: risposte → future, eventi → callback."""
        reason = "closed"
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except ValueError:
                        continue
                    if not isinstance(data, dict):
                        continue
                    if "id" in data:
                        self._resolve_response(data)
                    else:
                        self._dispatch_event(str(data.get("type", "")), data.get("data") or {})
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    reason = f"error: {ws.exception()}"
                    break
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                    break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            reason = f"error: {e}"
        finally:
            if self._ws is ws:
                self._connected = False
            self._fail_pending(ConnectionError(f"WebSocket connection {reason}"))
            if not self._closing:
                self._emit_event(EVENT_DISCONNECTED, {"reason": reason})

    def _resolve_response(self, data: Dict):
        msg_id = str(data.get("id"))
        fut = self._pending.get(msg_id)
        if fut is None or fut.done():
            return
        code = str(data.get("code", CODE_OK))
        if code == CODE_CONTINUE:
            # progress: la risposta finale arriva dopo con lo stesso id
            return
        self._pending.pop(msg_id, None)
        fut.set_result(data)

    def _fail_pending(self, exc: Exception):
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()
        for _, fut in self._event_waiters:
            if not fut.done():
                fut.set_exception(exc)
        self._event_waiters.clear()

    def _dispatch_event(self, event_type: str, data: Dict):
        event_type = event_type.lower()
        if event_type == EVENT_STATE_DIGEST:
            self.last_digest = data
        self._emit_event(event_type, data)

    def _emit_event(self, event_type: str, data: Dict):
        for waiter in list(self._event_waiters):
            predicate, fut = waiter
            if fut.done():
                self._event_waiters.remove(waiter)
                continue
            try:
                if predicate(event_type, data):
                    self._event_waiters.remove(waiter)
                    fut.set_result((event_type, data))
            except Exception:
                pass
        if self._event_callback is not None:
            try:
                self._event_callback(event_type, data)
            except Exception as e:
                if self._verbose_logging:
                    print(f"⚠️  event_callback error: {e}")

    async def wait_for_event(self, predicate: Callable[[str, Dict], bool], timeout: float) -> Tuple[str, Dict]:
        """Attende il primo evento per cui predicate(type, data) è True."""
        fut = asyncio.get_running_loop().create_future()
        self._event_waiters.append((predicate, fut))
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            if (predicate, fut) in self._event_waiters:
                self._event_waiters.remove((predicate, fut))

    # ------------------------------------------------------------------ invio richieste

    def _next_id(self) -> str:
        self._msg_counter += 1
        return str(self._msg_counter)

    def _timestamp(self) -> int:
        """ms trascorsi dalla connessione (BaseHub.getTimestamp dell'app)."""
        return int((time.monotonic() - self._connect_time) * 1000)

    def _build(self, cmd: str, params: Optional[Dict] = None, full: Optional[Dict] = None,
               msg_id: Optional[str] = None, timeout: Optional[int] = None) -> Tuple[str, Dict]:
        """Costruisce il messaggio come Request.getJsonRequest dell'app."""
        msg_id = msg_id or self._next_id()
        hbus: Dict = {"id": msg_id, "cmd": cmd}
        if full is not None:
            hbus.update(full)          # JSON diretto in hbus (setFullJSONData)
        else:
            hbus["params"] = params if params is not None else {}
        message: Dict = {"hbus": hbus}
        if timeout:
            message["timeout"] = int(timeout)
        return msg_id, message

    async def _ensure_connected(self):
        if not self.connected:
            await self.connect()

    async def _send_raw(self, message: Dict):
        await self._ensure_connected()
        async with self._send_lock:
            await self._ws.send_str(json.dumps(message))

    async def _send_nowait(self, cmd: str, params: Optional[Dict] = None, msg_id: Optional[str] = None) -> str:
        """Invio fire-and-forget (expectNoResult nell'app). Restituisce l'id usato."""
        msg_id, message = self._build(cmd, params, msg_id=msg_id)
        await self._send_raw(message)
        return msg_id

    async def _request(self, cmd: str, params: Optional[Dict] = None, full: Optional[Dict] = None,
                       timeout: float = DEFAULT_TIMEOUT, hub_timeout: Optional[int] = None,
                       raise_on_error: bool = True, _retry: int = 1) -> Dict:
        """
        Invia una richiesta e attende la risposta con lo stesso id.
        Restituisce il dict grezzo {id, code, msg, data}. Se code non è 200/200.1/200.2
        solleva HubError (o restituisce la risposta se raise_on_error=False).
        """
        await self._ensure_connected()
        msg_id, message = self._build(cmd, params, full, timeout=hub_timeout)
        fut = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut
        try:
            async with self._send_lock:
                await self._ws.send_str(json.dumps(message))
            data = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise asyncio.TimeoutError(f"Nessuna risposta dall'Hub a {cmd} entro {timeout}s")
        except Exception:
            self._pending.pop(msg_id, None)
            raise

        code = str(data.get("code", CODE_OK))
        if code in (CODE_OK, CODE_CHALLENGE_OK, CODE_ASYNC_ACCEPTED):
            return data
        if code == CODE_HUB_INITIALISING and _retry > 0:
            if self._verbose_logging:
                print("⏳ Hub in inizializzazione, riprovo tra 1s…")
            await asyncio.sleep(1.0)
            return await self._request(cmd, params, full, timeout, hub_timeout, raise_on_error, _retry - 1)
        if code == CODE_HUB_REQUEST_TIMEOUT:
            raise asyncio.TimeoutError(f"Timeout lato Hub (5504) per {cmd}")
        if raise_on_error:
            raise HubError(code, str(data.get("msg", "ERROR")), data)
        return data

    # ------------------------------------------------------------------ comandi dispositivo

    def _action_json(self, device_id: str, command: str) -> str:
        return json.dumps({"command": command, "type": "IRCommand", "deviceId": str(device_id)})

    async def _hold_action(self, action: str, status: str, msg_id: Optional[str] = None) -> str:
        return await self._send_nowait(
            f"{CMD_ENGINE}?holdAction",
            {"action": action, "status": status, "timestamp": str(self._timestamp())},
            msg_id=msg_id,
        )

    async def send_device_fast(self, device_id: str, command: str, use_press_release: bool = True,
                               ack_timeout: float = 0.1, hold_ms: int = 20) -> Dict:
        """
        Comando dispositivo come l'app ufficiale: press e release fire-and-forget,
        stesso id, timestamp relativo. Attende al massimo ack_timeout l'eventuale
        risposta d'errore dell'Hub al press (0 = non aspettare affatto).
        """
        action = self._action_json(device_id, command)
        await self._ensure_connected()

        # Registra un future sull'id del press per intercettare eventuali errori
        msg_id = self._next_id()
        fut = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut

        try:
            if use_press_release:
                await self._hold_action(action, "press", msg_id)
                await asyncio.sleep(max(hold_ms, 0) / 1000)
                try:
                    await self._hold_action(action, "release", msg_id)
                except (aiohttp.ClientError, ConnectionError, OSError):
                    # Il release è fire-and-forget: se il websocket cade segnala solo la disconnessione
                    self._connected = False
            else:
                await self._hold_action(action, "pressrelease", msg_id)

            if ack_timeout <= 0:
                return {"status": "sent", "id": msg_id}
            try:
                data = await asyncio.wait_for(fut, ack_timeout)
            except asyncio.TimeoutError:
                return {"status": "sent", "id": msg_id}
            code = str(data.get("code", CODE_OK))
            if code in (CODE_OK, CODE_CONTINUE, CODE_ASYNC_ACCEPTED):
                return data
            return {"error": f"{data.get('msg', 'ERROR')} (code {code})", "code": code, "id": msg_id}
        finally:
            self._pending.pop(msg_id, None)

    async def hold_command(self, device_id: str, command: str, stop: asyncio.Event,
                           repeat_interval: float = 0.25, max_duration: float = 30.0) -> Dict:
        """
        Tasto tenuto premuto fino a stop.set(): press, poi 'hold' ripetuto ogni
        repeat_interval, infine release (stesso id). max_duration è una sicurezza
        contro release persi (es. finestra chiusa col tasto premuto).
        """
        action = self._action_json(device_id, command)
        await self._ensure_connected()
        msg_id = await self._hold_action(action, "press")
        t0 = time.monotonic()
        try:
            while not stop.is_set() and time.monotonic() - t0 < max_duration:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=repeat_interval)
                    break
                except asyncio.TimeoutError:
                    pass
                await self._hold_action(action, "hold", msg_id)
        finally:
            try:
                await self._hold_action(action, "release", msg_id)
            except (aiohttp.ClientError, ConnectionError, OSError):
                self._connected = False
        return {"status": "sent", "id": msg_id, "duration": time.monotonic() - t0}

    async def send_device_hold(self, device_id: str, command: str, duration: float,
                               repeat_interval: float = 0.25) -> Dict:
        """Tasto tenuto premuto per `duration` secondi (vedi hold_command)."""
        stop = asyncio.Event()
        asyncio.get_running_loop().call_later(max(duration, 0), stop.set)
        return await self.hold_command(device_id, command, stop, repeat_interval, max_duration=duration + 1)

    async def fire_sequence(self, sequence_id: str) -> Dict:
        """Esegue una sequenza Harmony (BaseHub.doFireSequence)."""
        return await self._request(f"{CMD_ENGINE}?holdAction", {
            "action": json.dumps({"sequenceId": str(sequence_id)}),
            "status": "press",
            "timestamp": str(self._timestamp()),
        })

    # ------------------------------------------------------------------ attività

    async def start_activity_fast(self, activity_id: str, wait: bool = True,
                                  timeout: float = ACTIVITY_TIMEOUT,
                                  progress: Optional[Callable[[str], None]] = None) -> Dict:
        """
        Avvia un'attività (-1 = spegni tutto). Con wait=True attende l'evento
        startActivityFinished (o lo state digest coerente) invece di un timeout cieco.
        """
        activity_id = str(activity_id)
        params = {
            "async": "true",
            "timestamp": str(self._timestamp()),
            "args": {"rule": "start"},
            "activityId": activity_id,
        }
        await self._ensure_connected()

        def _finished(event_type: str, data: Dict) -> bool:
            if event_type == EVENT_ACTIVITY_FINISHED:
                return str(data.get("activityId", "")) == activity_id
            if event_type == EVENT_STATE_DIGEST:
                status = _to_int(data.get("activityStatus"), -1)
                if activity_id == "-1":
                    return status == ACTIVITY_IDLE and str(data.get("activityId", "-1")) == "-1"
                return status == ACTIVITY_STARTED and str(data.get("activityId")) == activity_id
            return False

        def _progress(event_type: str, data: Dict) -> bool:
            if progress and event_type == EVENT_STATE_DIGEST:
                progress(describe_digest(data))
            return False

        waiter = asyncio.create_task(self.wait_for_event(_finished, timeout)) if wait else None
        prog_waiter = asyncio.create_task(self.wait_for_event(_progress, timeout)) if (wait and progress) else None
        try:
            ack = await self._request(f"{CMD_ENGINE}?startactivity", params,
                                      timeout=self.DEFAULT_TIMEOUT, hub_timeout=int(timeout))
        except Exception:
            for t in (waiter, prog_waiter):
                if t:
                    t.cancel()
            raise
        if not wait:
            return ack
        try:
            event_type, data = await waiter
            return {"id": ack.get("id"), "code": CODE_OK, "msg": "OK", "event": event_type, "data": data}
        except asyncio.TimeoutError:
            return {"id": ack.get("id"), "code": ack.get("code"), "status": "sent",
                    "warning": f"nessuna conferma dall'Hub entro {timeout:.0f}s"}
        finally:
            if prog_waiter:
                prog_waiter.cancel()

    async def run_activity_rule(self, activity_id: str, rule: str = "start") -> Dict:
        """API activityengine dell'app (harmony.activityengine?runactivity), rule = start|end."""
        return await self._request("harmony.activityengine?runactivity", full={
            "activityId": str(activity_id),
            "timestamp": str(self._timestamp()),
            "async": True,
            "args": {"rule": rule},
        }, hub_timeout=int(self.ACTIVITY_TIMEOUT))

    # ------------------------------------------------------------------ stato

    async def get_state_digest(self, timeout: float = DEFAULT_TIMEOUT) -> Dict:
        """Stato completo (connect.statedigest?get) — è quello che usa l'app, non getCurrentActivity."""
        result = await self._request("connect.statedigest?get", {"format": "json"}, timeout=timeout)
        digest = result.get("data") or {}
        self.last_digest = digest
        return digest

    async def get_status(self) -> Dict:
        """Stato sintetico: {activity_id, status, running, transitioning, digest}."""
        return parse_digest(await self.get_state_digest())

    async def get_current_fast(self) -> Dict:
        """Stato corrente via getCurrentActivity (compatibilità: {data: {result: id}})."""
        return await self._request(f"{CMD_ENGINE}?getCurrentActivity", {"verb": "get"}, timeout=2)

    async def get_config_fast(self) -> Dict:
        """Recupera configurazione completa del Hub"""
        return await self._request(f"{CMD_ENGINE}?config", {"verb": "get"}, timeout=10, hub_timeout=30)

    async def get_system_info(self) -> Dict:
        return await self._request(f"vnd.logitech.harmony/vnd.logitech.harmony.system?systeminfo")

    async def get_discovery_info(self) -> Dict:
        return await self._request("connect.discoveryinfo?get")

    async def get_hub_info_fast(self) -> Dict:
        """Info Hub: ip, remote id, attività corrente, versione firmware e system info."""
        digest = {}
        sysinfo = {}
        try:
            digest = await self.get_state_digest()
        except Exception as e:
            if self._verbose_logging:
                print(f"⚠️  statedigest non disponibile: {e}")
        try:
            sysinfo = (await self.get_system_info()).get("data") or {}
        except Exception as e:
            if self._verbose_logging:
                print(f"⚠️  systeminfo non disponibile: {e}")
        discovery = {}
        try:
            discovery = (await self.get_discovery_info()).get("data") or {}
        except Exception as e:
            if self._verbose_logging:
                print(f"⚠️  discoveryinfo non disponibile: {e}")
        activity_id = str(digest.get("activityId", "-1")) if digest else None
        hub_info = {
            "ip": self.hub_ip,
            "remote_id": self.remote_id,
            "current_activity": {"data": {"result": activity_id}} if activity_id is not None else {},
            "name": discovery.get("friendlyName", ""),
            "firmware_version": digest.get("hubSwVersion", "") or discovery.get("current_fw_version", ""),
            "model": discovery.get("productId", ""),
            "serial_number": sysinfo.get("unit_id", ""),
            "digest": digest,
            "system_info": sysinfo,
            "discovery_info": discovery,
        }
        return {"data": hub_info, "cmd": "hub_info"}

    async def get_provision_info_fast(self) -> Dict:
        return await self._request("setup.account?getProvisionInfo", {})

    async def ping_http(self, timeout: float = 3.0) -> bool:
        """
        connect.ping via HTTP POST su :8088 (HarmonyWebServices.ping dell'app).
        Il firmware 4.15 risponde HTTP 417 {"code":"417"} a connect.ping ma risponde:
        consideriamo raggiungibile l'Hub se restituisce una risposta JSON qualsiasi.
        """
        headers = {
            "Origin": "http://localhost.nebula.myharmony.com",
            "Referer": "http://localhost.nebula.myharmony.com/mobile-fat.html",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        own_session = self.session is None or self.session.closed
        session = aiohttp.ClientSession() if own_session else self.session
        try:
            async with session.post(self.base_url, json={"id": "124", "cmd": "connect.ping"},
                                    headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    return True
                try:
                    body = await resp.json(content_type=None)
                except Exception:
                    return False
                return isinstance(body, dict) and "code" in body
        except Exception:
            return False
        finally:
            if own_session:
                await session.close()

    # ------------------------------------------------------------------ extra

    async def set_sleep_timer(self, interval_s: int) -> Dict:
        """
        Sleep timer (harmony.engine?setsleeptimer). interval in SECONDI (l'app manda minuti*60);
        -1 annulla il timer. ATTENZIONE: 0 spegne tutto immediatamente. Risposta: {timerId}.
        """
        interval_s = int(interval_s)
        if interval_s == 0:
            interval_s = -1
        return await self._request("harmony.engine?setsleeptimer", {"interval": interval_s})

    async def get_sleep_timer(self) -> Dict:
        return await self._request("harmony.engine?gettimerinterval")

    async def change_channel(self, channel: str) -> Dict:
        """Cambia canale nell'attività corrente (favoriti)."""
        return await self._request("harmony.engine?changeChannel", {"channel": str(channel)},
                                   hub_timeout=int(self.ACTIVITY_TIMEOUT))

    async def help_sync(self, fix_type: str, value: str) -> Dict:
        """Fix-it dell'app: fix_type 'power' o 'input'."""
        return await self._request(f"{CMD_ENGINE}?helpSync", {"type": fix_type, "value": value})


def _to_int(value, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_digest(digest: Dict) -> Dict:
    """Riduce lo state digest ai campi utili."""
    status = _to_int(digest.get("activityStatus"), -1)
    running_raw = str(digest.get("runningActivityList", "") or "")
    running = [a for a in running_raw.split(",") if a and a != "-1"]
    activity_id = str(digest.get("activityId", "-1"))
    if activity_id == "-1" and running:
        activity_id = running[0]
    return {
        "activity_id": activity_id,
        "status": status,
        "running": running,
        "transitioning": status in (ACTIVITY_STARTING, ACTIVITY_STOPPING),
        "sync_status": _to_int(digest.get("syncStatus"), -1),
        "state_version": _to_int(digest.get("stateVersion"), -1),
        "config_version": _to_int(digest.get("configVersion", digest.get("hubConfigVersion")), -1),
        "sleep_timer_id": _to_int(digest.get("sleepTimerId"), -1),
        "firmware": str(digest.get("hubSwVersion", "")),
        "digest": digest,
    }


def activity_name(activity_id: str) -> Optional[str]:
    for info in ACTIVITIES.values():
        if str(info.get("id")) == str(activity_id):
            return info.get("name")
    return None


def describe_digest(digest: Dict) -> str:
    """Testo di stato leggibile da uno state digest."""
    st = parse_digest(digest)
    return describe_status(st)


def describe_status(st: Dict) -> str:
    aid = st["activity_id"]
    name = activity_name(aid) or (f"ID: {aid}" if aid != "-1" else "OFF")
    if st["status"] == ACTIVITY_STARTING:
        return f"⏳ Avvio: {name}"
    if st["status"] == ACTIVITY_STOPPING:
        return f"⏳ Spegnimento: {name}"
    if aid == "-1" or st["status"] == ACTIVITY_IDLE and not st["running"]:
        return "⚫ OFF"
    if activity_name(aid):
        return f"🟢 {name}"
    return f"🟡 {name}"

async def fetch_remote_id(hub_ip: str, timeout: float = 5.0) -> Optional[str]:
    """remoteId dell'Hub via HTTP POST setup.account?getProvisionInfo (activeRemoteId)."""
    headers = {
        "Origin": "http://localhost.nebula.myharmony.com",
        "Referer": "http://localhost.nebula.myharmony.com/mobile-fat.html",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"http://{hub_ip}:8088/",
                                    json={"id": "124", "cmd": "setup.account?getProvisionInfo"},
                                    headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                body = await resp.json(content_type=None)
        remote_id = (body.get("data") or {}).get("activeRemoteId")
        return str(remote_id) if remote_id else None
    except Exception:
        return None


async def resolve_hub(args) -> Tuple[Optional[str], Optional[str]]:
    """
    IP e remoteId quando config.py manca (o con --ip):
    --ip → remoteId via HTTP; altrimenti discovery UDP sulla LAN.
    """
    if args.ip:
        remote_id = await fetch_remote_id(args.ip)
        if not remote_id:
            print(f"❌ No Harmony Hub answering at {args.ip}:8088")
            return None, None
        if args.verbose:
            print(f"🔗 Hub {args.ip} (remoteId {remote_id})")
        return args.ip, remote_id

    from hub_discovery import discover_hubs, hub_summary
    print(f"🔍 config.py not found: searching the LAN for a Harmony Hub ({args.timeout:.0f}s)…")
    try:
        hubs = await discover_hubs(timeout=args.timeout, first_only=True, verbose=args.verbose)
    except OSError as e:
        print(f"❌ {e}")
        hubs = []
    if not hubs:
        print("❌ No Hub found automatically.")
        print("   This PC must be on the same LAN as the Hub, and the firewall must allow UDP")
        print("   broadcast to port 5224 and incoming TCP connections on port 5446.")
        print("   Alternatively pass the Hub IP (see your router's DHCP list):")
        print(f"   ./harmony.py {args.command} --ip 192.168.1.X")
        return None, None
    hub = hubs[0]
    print(f"✅ {hub_summary(hub)}")
    remote_id = hub.get("remoteId") or await fetch_remote_id(hub.get("ip", ""))
    return hub.get("ip"), remote_id


async def _run_activity(hub: FastHarmonyHub, activity_id: str, name: str, args) -> Dict:
    """Avvia un'attività dalla CLI, attendendo (salvo --no-wait) la conferma via evento."""
    if args.verbose:
        print(f"🚀 Avvio attività: {name} (ID: {activity_id})")
    t0 = time.perf_counter()
    progress = (lambda text: print(f"   {text}")) if args.verbose else None
    try:
        result = await hub.start_activity_fast(activity_id, wait=not args.no_wait, progress=progress)
    except HubError as e:
        print(f"❌ {e.msg} (code {e.code})")
        return {"error": str(e)}
    elapsed = time.perf_counter() - t0
    if "warning" in result:
        print(f"⚠️  {name}: inviato, {result['warning']}")
    elif args.no_wait:
        print(f"✅ {name} (inviato)")
    else:
        print(f"✅ {name} ({elapsed:.1f}s)")
    if args.verbose:
        print(f"📊 Risultato: {result}")
    return result


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

🔍 INFORMAZIONI E STATO:
  harmony.py status      📊 Stato attuale    (state digest, anche transizioni)
  harmony.py digest      📊 State digest grezzo (JSON)
  harmony.py sysinfo     🏠 Info sistema/discovery/provision
  harmony.py ping        🏓 Verifica raggiungibilità (HTTP connect.ping)
  harmony.py events      👂 Mostra gli eventi push dell'Hub (--timeout SEC)
  harmony.py list        📋 Lista completa   (Tutti i comandi)
  harmony.py help        ❓ Questo help      (Guida dettagliata)

🧰 EXTRA:
  harmony.py find-hub    🔍 Trova l'Hub sulla LAN (non serve config.py)
  harmony.py sleep 30    😴 Sleep timer 30 min (sleep off per annullare, sleep per leggere)
  harmony.py channel 5   📺 Cambia canale nell'attività corrente

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
  harmony.py onkyo VolumeUp --hold 2  # Tieni premuto 2 secondi
  harmony.py tv --no-wait             # Non attendere la conferma dell'Hub
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
    
    parser.add_argument('--version', action='version', version=f'Harmony Hub Controller {__version__}')
    parser.add_argument('command', nargs='?', help='Comando da eseguire (usa "help" per guida completa)')
    parser.add_argument('action', nargs='?', help='Azione per dispositivo (es: PowerOn) o ID per discovery commands (es: activity/device ID)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Output dettagliato con metriche performance')
    parser.add_argument('--no-press-release', action='store_true', help='Disabilita Press/Release (modalità tradizionale)')
    parser.add_argument('--no-wait', action='store_true', help='Attività: non attendere la conferma dell\'Hub (ritorna subito)')
    parser.add_argument('--hold', type=float, metavar='SEC', help='Dispositivi: tieni premuto il tasto per SEC secondi')
    parser.add_argument('--timeout', type=float, default=6.0, help='find-hub/events: durata in secondi (default 6)')
    parser.add_argument('--ip', help='IP dell\'Hub (salta la discovery automatica quando config.py manca)')
    
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
    if cmd == "find-hub":
        from hub_discovery import discover_hubs, hub_summary
        print(f"🔍 Cerco Hub Harmony sulla LAN ({args.timeout:.0f}s)…")
        try:
            hubs = await discover_hubs(timeout=args.timeout, verbose=args.verbose)
        except OSError as e:
            print(f"❌ {e}")
            return
        if not hubs:
            print("❌ Nessun Hub trovato (stessa LAN? broadcast UDP permesso dal firewall?)")
            return
        for h in hubs:
            print(f"✅ {hub_summary(h)}")
            if args.verbose:
                for k, v in sorted(h.items()):
                    print(f"     {k}: {v}")
        if config is None:
            print("\n💡 Create config.py with: ./harmony.py export-config")
        else:
            print("\n💡 In config.py: HUB_IP = \"%s\", REMOTE_ID = \"%s\"" % (hubs[0].get("ip", "?"), hubs[0].get("remoteId", "?")))
        return

    # Senza config.py i comandi di discovery/diagnostica trovano l'Hub da soli
    hub_ip, remote_id = None, None
    if config is None or args.ip:
        if cmd not in NO_CONFIG_COMMANDS:
            require_config()
        hub_ip, remote_id = await resolve_hub(args)
        if not hub_ip:
            return

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
        print("  📊 status    → Stato attuale (anche transizioni)")
        print("  📊 digest    → State digest grezzo")
        print("  🏠 sysinfo   → Info sistema Hub")
        print("  🏓 ping      → Verifica raggiungibilità")
        print("  👂 events    → Eventi push live")
        print("  📋 list      → Questa lista")
        print("  ❓ help      → Guida completa")

        print("\n🧰 EXTRA:")
        print("  🔍 find-hub      → Trova l'Hub sulla LAN")
        print("  😴 sleep <min>   → Sleep timer (off per annullare)")
        print("  📺 channel <n>   → Cambia canale")
        
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
    async with FastHarmonyHub(verbose_logging=args.verbose, hub_ip=hub_ip, remote_id=remote_id) as hub:
        cmd = args.command.lower()
        use_pr = not args.no_press_release  # Press/Release abilitato di default
        
        try:
            # 🔍 DISCOVERY COMMANDS (New functionality with performance monitoring)
            if cmd in ["discover", "show-activity", "show-device", "show-hub", "export-config"]:
                try:
                    from discovery_handlers import handle_discovery_command
                    success = await handle_discovery_command(
                        hub, cmd, args.action, args.verbose, hub.hub_ip, hub.remote_id
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
                await asyncio.sleep(0.5)  # le risposte senza future vengono scartate dal reader

                # 2. Status round-trip via statedigest (10x)
                times = []
                for _ in range(10):
                    t0 = _t.perf_counter()
                    await hub.get_state_digest()
                    times.append((_t.perf_counter() - t0) * 1000)
                print(f"📊 Status round-trip statedigest (10x):")
                print(f"   {' / '.join(f'{t:.0f}ms' for t in times)}")
                print(f"   {_stats(times)}")
                print()

                # 2b. Status round-trip via getCurrentActivity (10x)
                times = []
                for _ in range(10):
                    t0 = _t.perf_counter()
                    await hub.get_current_fast()
                    times.append((_t.perf_counter() - t0) * 1000)
                print(f"📊 Status round-trip getCurrentActivity (10x):")
                print(f"   {' / '.join(f'{t:.0f}ms' for t in times)}")
                print(f"   {_stats(times)}")
                print()
                
                # 3. Device command via send_device_fast (10x Mute toggle)
                if audio_device:
                    times = []
                    for _ in range(10):
                        t0 = _t.perf_counter()
                        await hub.send_device_fast(audio_device["id"], "Mute")
                        times.append((_t.perf_counter() - t0) * 1000)
                        await asyncio.sleep(0.3)
                        await hub.send_device_fast(audio_device["id"], "Mute")
                        await asyncio.sleep(0.3)
                    print(f"📊 Device send_device_fast (10x Mute):")
                    print(f"   {' / '.join(f'{t:.0f}ms' for t in times)}")
                    print(f"   {_stats(times)}")
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
                
                # 5. Activity start (off → off, safe no-op, 3x, senza attendere l'evento)
                times = []
                for _ in range(3):
                    t0 = _t.perf_counter()
                    await hub.start_activity_fast("-1", wait=False)
                    times.append((_t.perf_counter() - t0) * 1000)
                print(f"📊 Activity start (PowerOff no-op, 3x):")
                print(f"   {' / '.join(f'{t:.0f}ms' for t in times)}")
                print(f"   {_stats(times)}")
                print()
                
                print("✅ Benchmark completato")

            # 🎯 ATTIVITÀ (Priorità su tutto: se scrivo 'off' voglio spegnere il sistema)
            elif cmd in ACTIVITIES:
                activity = ACTIVITIES[cmd]
                await _run_activity(hub, activity["id"], activity["name"], args)

            # 📱 DISPOSITIVI (Specific action overrides generic audio commands but not activities without action)
            elif cmd in DEVICES and args.action:
                device = DEVICES[cmd]

                if args.hold:
                    result = await hub.send_device_hold(device["id"], args.action, args.hold)
                else:
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
                st = await hub.get_status()
                print(describe_status(st))
                if st["running"] and len(st["running"]) > 1:
                    names = [activity_name(a) or a for a in st["running"]]
                    print(f"   attività in esecuzione: {', '.join(names)}")
                if args.verbose:
                    print(f"📊 Digest: {json.dumps(st['digest'], indent=2)}")

            # 📊 STATE DIGEST grezzo
            elif cmd == "digest":
                print(json.dumps(await hub.get_state_digest(), indent=2))

            # 🏠 SYSTEM INFO
            elif cmd == "sysinfo":
                for label, coro in (("systeminfo", hub.get_system_info()),
                                    ("discoveryinfo", hub.get_discovery_info()),
                                    ("provisioninfo", hub.get_provision_info_fast())):
                    try:
                        print(f"── {label}")
                        print(json.dumps((await coro).get("data", {}), indent=2))
                    except Exception as e:
                        print(f"   ❌ {e}")

            # 🏓 PING HTTP
            elif cmd == "ping":
                t0 = time.perf_counter()
                ok = await hub.ping_http()
                print(f"{'✅ Hub raggiungibile' if ok else '❌ Hub non risponde'} ({(time.perf_counter() - t0) * 1000:.0f}ms)")

            # 😴 SLEEP TIMER
            elif cmd == "sleep":
                if not args.action:
                    result = await hub.get_sleep_timer()
                    print(f"😴 Sleep timer: {result.get('data')}")
                else:
                    minutes = 0 if args.action.lower() in ("off", "0", "cancel") else float(args.action)
                    result = await hub.set_sleep_timer(int(minutes * 60) if minutes > 0 else -1)
                    if minutes:
                        print(f"😴 Sleep timer impostato: {minutes:g} min (timerId {result.get('data', {}).get('timerId')})")
                    else:
                        print("😴 Sleep timer annullato")

            # 📺 CANALE / FAVORITO
            elif cmd == "channel":
                if not args.action:
                    print("❌ Specifica il canale: harmony.py channel <numero>")
                else:
                    await hub.change_channel(args.action)
                    print(f"📺 Canale → {args.action}")

            # 👂 EVENTI LIVE (debug)
            elif cmd == "events":
                print(f"👂 Ascolto eventi dall'Hub per {args.timeout:.0f}s (Ctrl+C per uscire)…")
                hub._event_callback = lambda t, d: print(f"[{time.strftime('%H:%M:%S')}] {t}\n{json.dumps(d, indent=2)}")
                try:
                    await asyncio.sleep(args.timeout)
                except (KeyboardInterrupt, asyncio.CancelledError):
                    pass

            # ⚫ FALLBACK per 'off' se non definito in ACTIVITIES ma richiesto esplicitamente come attività di sistema
            elif cmd == "off":
                await _run_activity(hub, "-1", "SPEGNI TUTTO", args)

            else:
                print(f"❌ Comando '{cmd}' non riconosciuto. Usa 'list' per vedere i comandi.")
        
        except Exception as e:
            print(f"❌ {e}")

if __name__ == "__main__":
    asyncio.run(main())
