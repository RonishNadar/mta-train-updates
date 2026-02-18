# app.py
import socket
import time
import threading
import json
from pathlib import Path

from mta_app.buttons import Buttons
from mta_app.config import load_settings
from mta_app.lcd_ui import LCDUI, PageData
from mta_app.monitor import Monitor
from mta_app.web_config import WebConfigServer
from mta_app.wifi_manager import has_nmcli, get_active_ssid, scan_ssids, connect_wifi
from mta_app.weather import WeatherWorker, c_to_f


def save_app_fields_to_settings(path: str, *, favorite_station_index, leave_buffer_min, temp_unit) -> None:
    """
    Persist runtime UI config into settings.json (no dataclass mutation required).
    """
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw.setdefault("app", {})
    raw["app"]["favorite_station_index"] = favorite_station_index
    raw["app"]["leave_buffer_min"] = int(leave_buffer_min)
    raw["app"]["temp_unit"] = str(temp_unit).upper()
    p.write_text(json.dumps(raw, indent=2), encoding="utf-8")


def get_local_ip() -> str:
    """
    Best-effort LAN IP detection without extra dependencies.
    Returns something like 192.168.x.x, or "-" if not available.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't need to be reachable; no packets sent in practice.
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "-"


# UI states
STATE_MAIN = "MAIN"                 # home/station/settings-landing via left/right
STATE_SETTINGS_ROOT = "SETTINGS"    # settings menu list
STATE_IP = "IP"
STATE_WIFI_LIST = "WIFI_LIST"
STATE_WIFI_PASS = "WIFI_PASS"
STATE_WEB = "WEB"
STATE_BUFFER = "BUFFER"
STATE_ABOUT = "ABOUT"


def main() -> int:
    settings_path = "settings.json"
    settings = load_settings(settings_path)

    # ---- Runtime (mutable) copies for frozen dataclasses ----
    favorite_station_index = settings.app.favorite_station_index
    leave_buffer_min = settings.app.leave_buffer_min
    temp_unit = settings.app.temp_unit

    # LCD config
    i2c_port = 1
    i2c_address = 0x27
    lcd = LCDUI(i2c_port=i2c_port, i2c_address=i2c_address)

    # Buttons: BCM numbering
    buttons = Buttons(left_gpio=16, right_gpio=20, select_gpio=21, up_gpio=19, down_gpio=26)

    # MTA background monitor
    mon = Monitor(settings)
    mon.start()

    # Web config server for editing settings.json
    websrv = WebConfigServer(port=8088)
    websrv.start()

    # Weather background worker (Open-Meteo, no API key)
    weather = WeatherWorker(lat=40.6782, lon=-73.9442, refresh_s=600)
    weather.start()

    # Pages:
    # 0 = Home
    # 1..N = stations
    # N+1 = Settings landing
    station_count = len(settings.stations)
    last_page = station_count + 1
    page = 0

    # Per-station scroll offset for arrivals list (0 = show top 2)
    station_scroll: dict[int, int] = {}   # key: station_index (0-based), val: offset
    last_page_seen: int | None = None

    # Settings menu selection index: 0..4
    # ["IP address", "Wi Fi", "Select stations", "Leave buffer", "About"]
    state = STATE_MAIN
    settings_sel = 0

    # Wi-Fi support + UI vars
    wifi_supported = has_nmcli()
    wifi_ssids: list[str] = []
    wifi_sel = 0
    wifi_active = ""
    wifi_target = ""
    wifi_pass = " " * 16
    wifi_cursor = 0

    charset = list(" abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{}.,:?/")
    charset_idx = 0

    # Background Wi-Fi scanning state to avoid UI freeze
    wifi_scanning = False
    wifi_scan_status = ""
    wifi_scan_thread: threading.Thread | None = None

    def start_wifi_scan() -> None:
        nonlocal wifi_scanning, wifi_scan_status, wifi_ssids, wifi_active, wifi_sel, wifi_scan_thread
        if wifi_scanning or not wifi_supported:
            return
        wifi_scanning = True
        wifi_scan_status = "Scanning..."

        def worker():
            nonlocal wifi_scanning, wifi_scan_status, wifi_ssids, wifi_active, wifi_sel
            try:
                wifi_active = get_active_ssid()
                wifi_ssids = scan_ssids(limit=20)
                wifi_sel = 0
                wifi_scan_status = "" if wifi_ssids else "No networks"
            except Exception:
                wifi_scan_status = "Scan failed"
            finally:
                wifi_scanning = False

        wifi_scan_thread = threading.Thread(target=worker, daemon=True)
        wifi_scan_thread.start()

    # Cache IP and refresh it occasionally
    ip = "-"
    last_ip_refresh = 0.0

    # Render scheduler state
    last_render_t = 0.0

    def render_now(now_t: float) -> None:
        nonlocal last_render_t
        # ---------- RENDER ----------
        if state == STATE_MAIN:
            if page == 0:
                # Home: leave-in line based on favorite
                if favorite_station_index is None:
                    leave_line = "Fav: (hold Select)"
                else:
                    snap = mon.get_snapshot(favorite_station_index)
                    etas = sorted([eta for (_route, eta) in snap.arrivals if eta is not None])

                    if not etas:
                        leave_line = "Fav: no ETA"
                    else:
                        # Pick the first ETA that is >= leave_buffer_min.
                        # If the first ETA is too soon, use the next one.
                        chosen_eta = None
                        for eta in etas:
                            if eta >= leave_buffer_min:
                                chosen_eta = eta
                                break

                        # If *all* ETAs are < buffer, fall back to the soonest one
                        if chosen_eta is None:
                            chosen_eta = etas[0]

                        leave_in = chosen_eta - leave_buffer_min
                        if leave_in <= 0:
                            leave_line = "Leave now"
                        else:
                            leave_line = f"Leave in {leave_in:02d} min"


                ws = weather.get_snapshot()

                unit = (temp_unit or "C").upper()
                if unit == "F":
                    temp_val = c_to_f(ws.temp_c)
                    feels_val = c_to_f(ws.feels_like_c)
                else:
                    temp_val = ws.temp_c
                    feels_val = ws.feels_like_c

                lcd.render_home(
                    page_idx=page,
                    weather_kind=ws.condition_kind,
                    weather_text=ws.condition_text,
                    pop_pct=ws.pop_pct,
                    temp_val=temp_val,
                    feels_val=feels_val,
                    temp_unit=unit,
                    leave_line=leave_line,
                )

            elif page == last_page:
                lcd.render_settings_landing(page_idx=page)

            else:
                st = settings.stations[page - 1]
                snap = mon.get_snapshot(page - 1)

                st_idx = page - 1
                off = station_scroll.get(st_idx, 0)
                arr = snap.arrivals or []

                # Clamp offset to valid range (so 2-line window stays valid)
                max_off = max(0, len(arr) - 2)
                if off > max_off:
                    off = max_off
                    station_scroll[st_idx] = off

                data = PageData(
                    stop_name=st.stop_name,
                    direction=st.direction,
                    direction_label=st.direction_label,
                    arrivals=arr[off : off + 2],  # show window of 2
                )
                is_fav = (favorite_station_index is not None) and ((page - 1) == favorite_station_index)
                lcd.render_station(data, page_idx=page, is_favorite=is_fav)

        elif state == STATE_SETTINGS_ROOT:
            lcd.render_settings_menu(selected_idx=settings_sel, page_idx=page)

        elif state == STATE_IP:
            lcd.render_ip_page(ip_address=ip)

        elif state == STATE_WIFI_LIST:
            status = wifi_scan_status if (wifi_scanning or wifi_scan_status) else ""
            lcd.render_wifi_list_page(wifi_ssids, wifi_active, wifi_sel, status=status)

        elif state == STATE_WIFI_PASS:
            lcd.render_wifi_password_page(wifi_target, wifi_pass, wifi_cursor)

        elif state == STATE_WEB:
            url = f"{ip}:8088"
            lcd.render_web_config_page(url=url)

        elif state == STATE_BUFFER:
            lcd.render_leave_buffer_page(leave_buffer_min)

        elif state == STATE_ABOUT:
            lcd.render_about_page()

        last_render_t = now_t

    try:
        while True:
            now_t = time.time()

            # Refresh IP every 5 seconds (cheap)
            if now_t - last_ip_refresh > 5.0:
                ip = get_local_ip()
                last_ip_refresh = now_t

            ev = buttons.pop_event()

            # Reset scroll when you land on a station page (fresh view shows top 2)
            if last_page_seen != page:
                if 1 <= page <= station_count:
                    station_scroll[page - 1] = 0
                last_page_seen = page
            
            state_changed = False

            if ev:
                k = ev.kind

                # ---------- MAIN NAV ----------
                if state == STATE_MAIN:
                    if k == "LEFT":
                        page = last_page if page == 0 else (page - 1)
                        state_changed = True

                    elif k == "RIGHT":
                        page = 0 if page == last_page else (page + 1)
                        state_changed = True

                    elif k == "SELECT":
                        if page == last_page:
                            state = STATE_SETTINGS_ROOT
                            state_changed = True
                        else:
                            mon.force_refresh()
                    
                    elif k == "UP":
                        if 1 <= page <= station_count:
                            st_idx = page - 1
                            off = station_scroll.get(st_idx, 0)
                            station_scroll[st_idx] = max(0, off - 1)
                            state_changed = True

                    elif k == "DOWN":
                        if 1 <= page <= station_count:
                            st_idx = page - 1
                            snap = mon.get_snapshot(st_idx)
                            arr = snap.arrivals or []
                            max_off = max(0, len(arr) - 2)
                            off = station_scroll.get(st_idx, 0)
                            station_scroll[st_idx] = min(max_off, off + 1)
                            state_changed = True


                    elif k == "SELECT_LONG":
                        # only when on a station page
                        if 1 <= page <= station_count:
                            fav_idx = page - 1
                            favorite_station_index = fav_idx
                            save_app_fields_to_settings(
                                settings_path,
                                favorite_station_index=favorite_station_index,
                                leave_buffer_min=leave_buffer_min,
                                temp_unit=temp_unit,
                            )
                            print(f"[Fav] Set favorite station index = {fav_idx} ({settings.stations[fav_idx].stop_name})")
                            state_changed = True

                # ---------- SETTINGS ROOT ----------
                elif state == STATE_SETTINGS_ROOT:
                    if k == "UP":
                        settings_sel = (settings_sel - 1) % 5
                        state_changed = True
                    elif k == "DOWN":
                        settings_sel = (settings_sel + 1) % 5
                        state_changed = True
                    elif k == "LEFT":
                        state = STATE_MAIN
                        state_changed = True
                    elif k == "SELECT":
                        if settings_sel == 0:
                            state = STATE_IP
                        elif settings_sel == 1:
                            state = STATE_WIFI_LIST
                            wifi_sel = 0
                            wifi_ssids = []
                            wifi_active = ""
                            wifi_scan_status = "nmcli missing" if not wifi_supported else "Scanning..."
                            if wifi_supported:
                                start_wifi_scan()
                        elif settings_sel == 2:
                            state = STATE_WEB
                        elif settings_sel == 3:
                            state = STATE_BUFFER
                        elif settings_sel == 4:
                            state = STATE_ABOUT
                        state_changed = True

                # ---------- IP PAGE ----------
                elif state == STATE_IP:
                    if k == "LEFT":
                        state = STATE_SETTINGS_ROOT
                        state_changed = True

                # ---------- LEAVE BUFFER PAGE ----------
                elif state == STATE_BUFFER:
                    if k == "UP":
                        leave_buffer_min = min(60, leave_buffer_min + 1)
                        state_changed = True
                    elif k == "DOWN":
                        leave_buffer_min = max(0, leave_buffer_min - 1)
                        state_changed = True
                    elif k == "LEFT":
                        state = STATE_SETTINGS_ROOT
                        state_changed = True
                    elif k == "SELECT":
                        save_app_fields_to_settings(
                            settings_path,
                            favorite_station_index=favorite_station_index,
                            leave_buffer_min=leave_buffer_min,
                            temp_unit=temp_unit,
                        )
                        state = STATE_SETTINGS_ROOT
                        state_changed = True

                # ---------- ABOUT PAGE ----------
                elif state == STATE_ABOUT:
                    if k == "LEFT":
                        state = STATE_SETTINGS_ROOT
                        state_changed = True

                # ---------- WEB PAGE ----------
                elif state == STATE_WEB:
                    if k == "LEFT":
                        state = STATE_SETTINGS_ROOT
                        state_changed = True
                    elif k == "SELECT":
                        # Reload settings.json without rebooting
                        settings = load_settings(settings_path)

                        # Refresh runtime values
                        favorite_station_index = settings.app.favorite_station_index
                        leave_buffer_min = settings.app.leave_buffer_min
                        temp_unit = settings.app.temp_unit

                        # Restart monitor with new station list
                        mon.stop()
                        mon = Monitor(settings)
                        mon.start()

                        station_count = len(settings.stations)
                        last_page = station_count + 1
                        page = min(page, last_page)

                        state_changed = True

                # ---------- WIFI LIST PAGE ----------
                elif state == STATE_WIFI_LIST:
                    if k == "LEFT":
                        state = STATE_SETTINGS_ROOT
                        state_changed = True
                    elif k == "UP":
                        if wifi_ssids:
                            wifi_sel = max(0, wifi_sel - 1)
                            state_changed = True
                    elif k == "DOWN":
                        if wifi_ssids:
                            wifi_sel = min(len(wifi_ssids) - 1, wifi_sel + 1)
                            state_changed = True
                    elif k == "SELECT":
                        if not wifi_supported:
                            state = STATE_SETTINGS_ROOT
                            state_changed = True
                        elif wifi_scanning:
                            pass
                        elif not wifi_ssids:
                            start_wifi_scan()
                            state_changed = True
                        else:
                            wifi_target = wifi_ssids[wifi_sel]
                            wifi_pass = " " * 16
                            wifi_cursor = 0
                            charset_idx = 0
                            state = STATE_WIFI_PASS
                            state_changed = True

                # ---------- WIFI PASSWORD PAGE ----------
                elif state == STATE_WIFI_PASS:
                    if k == "LEFT":
                        state = STATE_WIFI_LIST
                        state_changed = True
                    elif k == "RIGHT":
                        wifi_cursor = min(15, wifi_cursor + 1)
                        charset_idx = 0
                        state_changed = True
                    elif k == "UP" or k == "DOWN":
                        if k == "UP":
                            charset_idx = (charset_idx + 1) % len(charset)
                        else:
                            charset_idx = (charset_idx - 1) % len(charset)
                        pw_list = list(wifi_pass)
                        pw_list[wifi_cursor] = charset[charset_idx]
                        wifi_pass = "".join(pw_list)
                        state_changed = True
                    elif k == "SELECT":
                        pw = wifi_pass.strip()
                        ok, _msg = connect_wifi(wifi_target, pw)

                        # Show result briefly on list page
                        state = STATE_WIFI_LIST
                        wifi_scan_status = "Connected" if ok else "Failed"
                        start_wifi_scan()
                        state_changed = True

            # ---------- RENDER SCHEDULER ----------
            if state == STATE_MAIN and (0 < page < last_page):
                min_render_period = 0.12  # station page: marquee + ETA refresh
            else:
                min_render_period = 0.5   # mostly static pages

            periodic_due = (now_t - last_render_t) >= min_render_period

            if state == STATE_WIFI_LIST and wifi_scanning:
                periodic_due = True

            if state_changed or periodic_due:
                render_now(now_t)

            time.sleep(0.02)

    except KeyboardInterrupt:
        return 0
    finally:
        try:
            websrv.stop()
            weather.stop()
        except Exception:
            pass
        mon.stop()
        lcd.close()


if __name__ == "__main__":
    raise SystemExit(main())
