"""
Résolution hostname -> IP puis collecte SNMP complète d'un équipement :
- santé générale (sysDescr, sysUpTime -> up/down)
- CPU (UCD-SNMP-MIB, dispo par défaut avec net-snmp)
- RAM (UCD-SNMP-MIB)
- température (NET-SNMP-EXTEND-MIB, optionnel, nécessite une extend "temperature")
- interfaces : statut, vitesse, trafic in/out (IF-MIB standard)
"""
import socket
import threading
import ipaddress
import time
from typing import Optional
from pysnmp.hlapi import (
    getCmd, nextCmd, SnmpEngine, CommunityData,
    UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
)
from .config import HOSTNAME_CACHE_TTL_SECONDS, SNMP_TIMEOUT, SNMP_RETRIES

# --- OIDs standards (IF-MIB / SNMPv2-MIB) ---
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
OID_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
OID_IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"
OID_IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
OID_IF_SPEED = "1.3.6.1.2.1.2.2.1.5"
OID_IF_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10"  # fallback 32 bits
OID_IF_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16"  # fallback 32 bits
OID_IF_HC_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"  # 64 bits
OID_IF_HC_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10"  # 64 bits
OID_IF_IN_UCAST_PKTS = "1.3.6.1.2.1.2.2.1.11"
OID_IF_HC_IN_UCAST_PKTS = "1.3.6.1.2.1.31.1.1.1.7"  # 64 bits
OID_IF_IN_DISCARDS = "1.3.6.1.2.1.2.2.1.13"
OID_IF_IN_ERRORS = "1.3.6.1.2.1.2.2.1.14"
OID_IF_OUT_UCAST_PKTS = "1.3.6.1.2.1.2.2.1.17"
OID_IF_HC_OUT_UCAST_PKTS = "1.3.6.1.2.1.31.1.1.1.11"  # 64 bits
OID_IF_OUT_DISCARDS = "1.3.6.1.2.1.2.2.1.19"
OID_IF_OUT_ERRORS = "1.3.6.1.2.1.2.2.1.20"

# --- BRIDGE-MIB (STP) ---
OID_DOT1D_BASE_PORT_IF_INDEX = "1.3.6.1.2.1.17.1.4.1.2"
OID_DOT1D_STP_PORT_STATE = "1.3.6.1.2.1.17.2.1.7"

# --- OIDs UCD-SNMP-MIB (CPU / RAM), dispo par défaut sur net-snmp Linux ---
OID_MEM_TOTAL = "1.3.6.1.4.1.2021.4.5.0"    # memTotalReal (kB)
OID_MEM_AVAIL = "1.3.6.1.4.1.2021.4.6.0"    # memAvailReal (kB)
OID_CPU_IDLE = "1.3.6.1.4.1.2021.11.11.0"   # ssCpuIdle (%)

# --- NET-SNMP-EXTEND-MIB (température simulée, optionnelle) ---
OID_EXTEND_OUTPUT = "1.3.6.1.4.1.8072.1.3.2.4.1.2"  # nsExtendOutputFull table

STATUS_MAP = {"1": "up", "2": "down", "3": "testing",
              "4": "unknown", "5": "dormant", "6": "notPresent",
              "7": "lowerLayerDown"}
STP_STATE_MAP = {"1": "disabled", "2": "blocking", "3": "listening",
                 "4": "learning", "5": "forwarding", "6": "broken"}

# Un seul moteur SNMP réutilisé pour toutes les requêtes (évite le coût de
# recréation à chaque appel, ~1s gagné par requête). Comme pysnmp.hlapi
# (synchrone) n'est pas thread-safe, un verrou garantit qu'un seul thread
# l'utilise à la fois : deux diagnostics lancés en même temps (ex: sw1 et
# sw2) restent tous les deux traités correctement, juste l'un après l'autre
# au niveau réseau plutôt que réellement en parallèle.
_snmp_engine = SnmpEngine()
_snmp_lock = threading.Lock()
_hostname_cache = {}
_hostname_cache_lock = threading.Lock()


class SNMPError(Exception):
    pass


def resolve_ip(hostname: str) -> str:
    """Résout un hostname (ex: switch1.local ou une IP directe) en IPv4."""
    hostname = hostname.strip()
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        if "." not in hostname:
            hostname = f"{hostname}.local"
    try:
        ipaddress.ip_address(hostname)
        return hostname
    except ValueError:
        pass

    now = time.monotonic()
    with _hostname_cache_lock:
        cached = _hostname_cache.get(hostname.lower())
        if cached and now - cached[1] < HOSTNAME_CACHE_TTL_SECONDS:
            return cached[0]
    try:
        address = socket.gethostbyname(hostname)
        with _hostname_cache_lock:
            _hostname_cache[hostname.lower()] = (address, now)
        return address
    except socket.gaierror as e:
        if cached:
            return cached[0]
        raise SNMPError(f"Résolution impossible pour '{hostname}': {e}")


def _snmp_get(ip: str, community: str, oid: str) -> Optional[str]:
    with _snmp_lock:
        iterator = getCmd(
            _snmp_engine,
            CommunityData(community, mpModel=1),
            UdpTransportTarget((ip, 161), timeout=SNMP_TIMEOUT, retries=SNMP_RETRIES),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
    if errorIndication or errorStatus:
        return None
    for varBind in varBinds:
        value = str(varBind[1])
        if value in ("No Such Object currently exists at this OID",
                     "No Such Instance currently exists at this OID"):
            return None
        return value
    return None


def _snmp_walk(ip: str, community: str, oid: str) -> list:
    results = []
    with _snmp_lock:
        iterator = nextCmd(
            _snmp_engine,
            CommunityData(community, mpModel=1),
            UdpTransportTarget((ip, 161), timeout=SNMP_TIMEOUT, retries=SNMP_RETRIES),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False
        )
        for errorIndication, errorStatus, errorIndex, varBinds in iterator:
            if errorIndication or errorStatus:
                break
            for varBind in varBinds:
                oid_str = str(varBind[0])
                value = str(varBind[1])
                results.append((oid_str, value))
    return results


def _walk_to_dict(ip: str, community: str, base_oid: str) -> dict:
    """Retourne {index: valeur} à partir d'un walk IF-MIB (dernier segment de l'OID = index)."""
    out = {}
    for oid_str, value in _snmp_walk(ip, community, base_oid):
        idx = oid_str.split(".")[-1]
        out[idx] = value
    return out


def collect_diagnostics(hostname: str, community: str = "public") -> dict:
    """
    Résout le hostname puis interroge l'équipement en SNMP.
    Retourne un dict prêt à être stocké en base (voir schemas.DiagnosticOut).
    Ne lève pas d'exception si le switch ne répond pas : is_up=False + error_message.
    """
    result = {
        "resolved_ip": None,
        "is_up": False,
        "sys_descr": None,
        "sys_uptime": None,
        "cpu_usage": None,
        "ram_total_kb": None,
        "ram_used_kb": None,
        "temperature_c": None,
        "error_message": None,
        "interfaces": [],
    }

    try:
        ip = resolve_ip(hostname)
    except SNMPError as e:
        result["error_message"] = str(e)
        return result

    result["resolved_ip"] = ip

    sys_descr = _snmp_get(ip, community, OID_SYS_DESCR)
    if sys_descr is None:
        result["error_message"] = "Pas de réponse SNMP (switch injoignable ou communauté invalide)"
        return result

    result["is_up"] = True
    result["sys_descr"] = sys_descr

    uptime = _snmp_get(ip, community, OID_SYS_UPTIME)
    if uptime:
        try:
            # sysUpTime is TimeTicks: hundredths of a second.
            uptime_ticks = uptime.split("(")[1].split(")")[0] if "(" in uptime else uptime
            result["sys_uptime"] = int(uptime_ticks.strip())
        except (IndexError, ValueError):
            result["sys_uptime"] = None

    # --- CPU ---
    cpu_idle = _snmp_get(ip, community, OID_CPU_IDLE)
    if cpu_idle is not None:
        try:
            result["cpu_usage"] = round(100.0 - float(cpu_idle), 2)
        except ValueError:
            pass

    # --- RAM ---
    mem_total = _snmp_get(ip, community, OID_MEM_TOTAL)
    mem_avail = _snmp_get(ip, community, OID_MEM_AVAIL)
    if mem_total is not None:
        try:
            result["ram_total_kb"] = int(mem_total)
            if mem_avail is not None:
                result["ram_used_kb"] = int(mem_total) - int(mem_avail)
        except ValueError:
            pass

    # --- Température (optionnelle, via extend "temperature") ---
    try:
        extend_values = _snmp_walk(ip, community, OID_EXTEND_OUTPUT)
        for oid_str, value in extend_values:
            try:
                result["temperature_c"] = float(value.strip())
                break
            except ValueError:
                continue
    except Exception:
        pass

    # --- Interfaces ---
    descr = _walk_to_dict(ip, community, OID_IF_DESCR)
    admin = _walk_to_dict(ip, community, OID_IF_ADMIN_STATUS)
    oper = _walk_to_dict(ip, community, OID_IF_OPER_STATUS)
    speed = _walk_to_dict(ip, community, OID_IF_SPEED)
    in_octets = _walk_to_dict(ip, community, OID_IF_HC_IN_OCTETS)
    out_octets = _walk_to_dict(ip, community, OID_IF_HC_OUT_OCTETS)
    in_packets = _walk_to_dict(ip, community, OID_IF_HC_IN_UCAST_PKTS)
    out_packets = _walk_to_dict(ip, community, OID_IF_HC_OUT_UCAST_PKTS)

    # Prefer 64-bit HC counters and retain compatibility with older devices.
    for counters, fallback_oid in (
        (in_octets, OID_IF_IN_OCTETS),
        (out_octets, OID_IF_OUT_OCTETS),
        (in_packets, OID_IF_IN_UCAST_PKTS),
        (out_packets, OID_IF_OUT_UCAST_PKTS),
    ):
        for idx, value in _walk_to_dict(ip, community, fallback_oid).items():
            counters.setdefault(idx, value)
    in_errors = _walk_to_dict(ip, community, OID_IF_IN_ERRORS)
    out_errors = _walk_to_dict(ip, community, OID_IF_OUT_ERRORS)
    in_discards = _walk_to_dict(ip, community, OID_IF_IN_DISCARDS)
    out_discards = _walk_to_dict(ip, community, OID_IF_OUT_DISCARDS)

    bridge_port_if = _walk_to_dict(ip, community, OID_DOT1D_BASE_PORT_IF_INDEX)
    stp_state_by_port = _walk_to_dict(ip, community, OID_DOT1D_STP_PORT_STATE)
    stp_state_by_if = {
        bridge_port_if[port]: STP_STATE_MAP.get(state, state)
        for port, state in stp_state_by_port.items()
        if port in bridge_port_if
    }

    for idx in descr:
        result["interfaces"].append({
            "if_index": int(idx),
            "if_descr": descr.get(idx),
            "admin_status": STATUS_MAP.get(admin.get(idx), admin.get(idx)),
            "oper_status": STATUS_MAP.get(oper.get(idx), oper.get(idx)),
            "speed_bps": int(speed[idx]) if idx in speed and speed[idx].isdigit() else None,
            "in_octets": int(in_octets[idx]) if idx in in_octets and in_octets[idx].isdigit() else None,
            "out_octets": int(out_octets[idx]) if idx in out_octets and out_octets[idx].isdigit() else None,
            "in_packets": int(in_packets[idx]) if idx in in_packets and in_packets[idx].isdigit() else None,
            "out_packets": int(out_packets[idx]) if idx in out_packets and out_packets[idx].isdigit() else None,
            "in_errors": int(in_errors[idx]) if idx in in_errors and in_errors[idx].isdigit() else None,
            "out_errors": int(out_errors[idx]) if idx in out_errors and out_errors[idx].isdigit() else None,
            "in_discards": int(in_discards[idx]) if idx in in_discards and in_discards[idx].isdigit() else None,
            "out_discards": int(out_discards[idx]) if idx in out_discards and out_discards[idx].isdigit() else None,
            "stp_state": stp_state_by_if.get(idx),
        })

    return result
