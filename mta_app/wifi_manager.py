from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List, Tuple


def _run(cmd: List[str]) -> str:
    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    return out.strip()


def has_nmcli() -> bool:
    try:
        _run(["nmcli", "-v"])
        return True
    except Exception:
        return False


def get_active_ssid() -> str:
    """
    Returns currently connected SSID or "".
    """
    try:
        # nmcli -t -f ACTIVE,SSID dev wifi
        out = _run(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"])
        for line in out.splitlines():
            # format: yes:MySSID
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0] == "yes":
                return parts[1]
        return ""
    except Exception:
        return ""


def scan_ssids(limit: int = 20) -> List[str]:
    """
    Returns a list of nearby SSIDs (unique, non-empty).
    """
    try:
        # Force rescan
        _run(["nmcli", "dev", "wifi", "rescan"])
    except Exception:
        pass

    try:
        out = _run(["nmcli", "-t", "-f", "SSID", "dev", "wifi", "list"])
        ssids: List[str] = []
        seen = set()
        for line in out.splitlines():
            ssid = line.strip()
            if not ssid:
                continue
            if ssid in seen:
                continue
            seen.add(ssid)
            ssids.append(ssid)
            if len(ssids) >= limit:
                break
        return ssids
    except Exception:
        return []


def connect_wifi(ssid: str, password: str) -> Tuple[bool, str]:
    """
    Connect using nmcli. Returns (ok, message).
    """
    try:
        # This will create/update a connection profile
        _run(["nmcli", "dev", "wifi", "connect", ssid, "password", password])
        return True, "Connected"
    except subprocess.CalledProcessError as e:
        msg = e.output.strip() if e.output else "Connect failed"
        return False, msg
    except Exception as e:
        return False, str(e)
