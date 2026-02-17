# app.py
import socket
import time
import threading

from mta_app.buttons import Buttons
from mta_app.config import load_settings
from mta_app.lcd_ui import LCDUI, PageData
from mta_app.monitor import Monitor
from mta_app.web_config import WebConfigServer
from mta_app.wifi_manager import has_nmcli, get_active_ssid, scan_ssids, connect_wifi


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
STATE_MAIN = "MAIN"                 # home/station/settings-root via left/right
STATE_SETTINGS_ROOT = "SETTINGS"    # menu list
STATE_IP = "IP"
STATE_WIFI_LIST = "WIFI_LIST"
STATE_WIFI_PASS = "WIFI_PASS"
STATE_WEB = "WEB"
STATE_ABOUT = "ABOUT"


def main() -> int:
    settings = load_settings("settings.json")

    # LCD config (hardcoded; you can parse from settings.json if you want)
    i2c_port = 1
    i2c_address = 0x27

    lcd = LCDUI(i2c_port=i2c_port, i2c_address=i2c_address)
    buttons = Buttons(left_gpio=16, right_gpio=20, select_gpio=21, up_gpio=19, down_gpio=26)

    mon = Monitor(settings)
    mon.start()

    websrv = WebConfigServer(port=8088)
    websrv.start()

    # Pages:
    # 0 = Home
    # 1..N = stations
    # N+1 = Settings hub
    station_count = len(settings.stations)
    last_page = station_count + 1
    page = 0

    # Settings menu selection index: 0..3
    state = STATE_MAIN
    settings_sel = 0

    # Wi-Fi support + UI vars
    wifi_supported = has_nmcli()
    wifi_ssids = []
    wifi_sel = 0
    wifi_active = ""
    wifi_target = ""
    wifi_pass = " " * 16
    wifi_cursor = 0

    # Character set for password entry
    charset = list(" abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{}.,:?/")
    charset_idx = 0

    # Background Wi-Fi scanning state to avoid UI freeze
    wifi_scanning = False
    wifi_scan_status = ""
    wifi_scan_thread = None

    def start_wifi_scan() -> None:
        nonlocal wifi_scanning, wifi_scan_status, wifi_ssids, wifi_active, wifi_sel, wifi_scan_thread
        if wifi_scanning:
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

    # Cache IP and refresh it occasionally (Wi-Fi can change)
    ip = "-"
    last_ip_refresh = 0.0

    try:
        while True:
            # Refresh IP every 5 seconds
            now_t = time.time()
            if now_t - last_ip_refresh > 5.0:
                ip = get_local_ip()
                last_ip_refresh = now_t

            # Handle buttons
            ev = buttons.pop_event()
            if ev:
                k = ev.kind

                # ---------- MAIN NAV ----------
                if state == STATE_MAIN:
                    if k == "LEFT":
                        page = max(0, page - 1)
                    elif k == "RIGHT":
                        page = min(last_page, page + 1)
                    elif k == "SELECT":
                        if page == last_page:
                            state = STATE_SETTINGS_ROOT
                        else:
                            mon.force_refresh()

                # ---------- SETTINGS ROOT ----------
                elif state == STATE_SETTINGS_ROOT:
                    if k == "UP":
                        settings_sel = max(0, settings_sel - 1)
                    elif k == "DOWN":
                        settings_sel = min(3, settings_sel + 1)
                    elif k == "LEFT":
                        state = STATE_MAIN
                    elif k == "SELECT":
                        if settings_sel == 0:
                            state = STATE_IP
                        elif settings_sel == 1:
                            state = STATE_WIFI_LIST
                            wifi_sel = 0
                            wifi_ssids = []
                            wifi_active = ""
                            if not wifi_supported:
                                wifi_scan_status = "nmcli missing"
                                wifi_scanning = False
                            else:
                                start_wifi_scan()
                        elif settings_sel == 2:
                            state = STATE_WEB
                        elif settings_sel == 3:
                            state = STATE_ABOUT

                # ---------- IP PAGE ----------
                elif state == STATE_IP:
                    if k == "LEFT":
                        state = STATE_SETTINGS_ROOT

                # ---------- ABOUT PAGE ----------
                elif state == STATE_ABOUT:
                    if k == "LEFT":
                        state = STATE_SETTINGS_ROOT

                # ---------- WEB PAGE ----------
                elif state == STATE_WEB:
                    if k == "LEFT":
                        state = STATE_SETTINGS_ROOT
                    elif k == "SELECT":
                        # reload settings.json without rebooting
                        settings = load_settings("settings.json")
                        mon.stop()
                        mon = Monitor(settings)
                        mon.start()
                        station_count = len(settings.stations)
                        last_page = station_count + 1
                        page = min(page, last_page)

                # ---------- WIFI LIST PAGE ----------
                elif state == STATE_WIFI_LIST:
                    if k == "LEFT":
                        state = STATE_SETTINGS_ROOT
                    elif k == "UP":
                        if wifi_ssids:
                            wifi_sel = max(0, wifi_sel - 1)
                    elif k == "DOWN":
                        if wifi_ssids:
                            wifi_sel = min(len(wifi_ssids) - 1, wifi_sel + 1)
                    elif k == "SELECT":
                        # If still scanning, treat SELECT as "refresh scan"
                        if wifi_supported and wifi_scanning:
                            # ignore or allow refresh:
                            pass
                        elif wifi_supported and not wifi_scanning:
                            if not wifi_ssids:
                                # allow rescan on SELECT when empty
                                start_wifi_scan()
                            else:
                                wifi_target = wifi_ssids[wifi_sel]
                                wifi_pass = " " * 16
                                wifi_cursor = 0
                                charset_idx = 0
                                state = STATE_WIFI_PASS

                # ---------- WIFI PASSWORD PAGE ----------
                elif state == STATE_WIFI_PASS:
                    if k == "LEFT":
                        # go back to list without connecting
                        state = STATE_WIFI_LIST
                    elif k == "RIGHT":
                        wifi_cursor = min(15, wifi_cursor + 1)
                        charset_idx = 0
                    elif k == "UP" or k == "DOWN":
                        # change character at cursor
                        if k == "UP":
                            charset_idx = (charset_idx + 1) % len(charset)
                        else:
                            charset_idx = (charset_idx - 1) % len(charset)

                        pw_list = list(wifi_pass)
                        pw_list[wifi_cursor] = charset[charset_idx]
                        wifi_pass = "".join(pw_list)
                    elif k == "SELECT":
                        # Attempt connection
                        pw = wifi_pass.strip()
                        ok, msg = connect_wifi(wifi_target, pw)

                        # After connect attempt, go back and refresh list in background
                        state = STATE_WIFI_LIST
                        wifi_scan_status = ("Connected" if ok else "Failed")
                        start_wifi_scan()

            # ---------- RENDER ----------
            if state == STATE_MAIN:
                if page == 0:
                    lcd.render_home(page_idx=page)
                elif page == last_page:
                    lcd.render_settings_menu(selected_idx=settings_sel, page_idx=page)
                else:
                    st = settings.stations[page - 1]
                    snap = mon.get_snapshot(page - 1)
                    data = PageData(
                        stop_name=st.stop_name,
                        direction=st.direction,
                        direction_label=st.direction_label,
                        arrivals=snap.arrivals,
                    )
                    lcd.render_station(data, page_idx=page)

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

            elif state == STATE_ABOUT:
                lcd.render_about_page()

            # UI refresh rate (also drives marquee)
            time.sleep(0.12)

    except KeyboardInterrupt:
        return 0
    finally:
        try:
            websrv.stop()
        except Exception:
            pass
        mon.stop()
        lcd.close()


if __name__ == "__main__":
    raise SystemExit(main())
