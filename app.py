import socket
import time

from mta_app.buttons import Buttons
from mta_app.config import load_settings
from mta_app.lcd_ui import LCDUI, PageData
from mta_app.monitor import Monitor
from mta_app.web_config import WebConfigServer
from mta_app.wifi_manager import has_nmcli, get_active_ssid, scan_ssids, connect_wifi


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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

    i2c_port = 1
    i2c_address = 0x27

    lcd = LCDUI(i2c_port=i2c_port, i2c_address=i2c_address)
    buttons = Buttons(left_gpio=16, right_gpio=20, select_gpio=21, up_gpio=19, down_gpio=26)

    mon = Monitor(settings)
    mon.start()

    websrv = WebConfigServer(port=8088)
    websrv.start()

    station_count = len(settings.stations)
    last_page = station_count + 1  # last page is settings hub
    page = 0

    state = STATE_MAIN
    settings_sel = 0

    # wifi UI vars
    wifi_supported = has_nmcli()
    wifi_ssids = []
    wifi_sel = 0
    wifi_active = ""
    wifi_target = ""
    wifi_pass = " " * 16
    wifi_cursor = 0
    charset = list(" abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{}.,:?/")
    charset_idx = 0

    ip = "-"
    last_ip_refresh = 0.0

    try:
        while True:
            # refresh IP periodically
            now_t = time.time()
            if now_t - last_ip_refresh > 5.0:
                ip = get_local_ip()
                last_ip_refresh = now_t

            ev = buttons.pop_event()

            if ev:
                print(f"[APP] got {ev.kind} at {ev.t:.3f} state={state} page={page}")
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
                            wifi_active = get_active_ssid()
                            wifi_ssids = scan_ssids(limit=20)
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
                        # reload settings.json quickly
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
                        wifi_sel = max(0, wifi_sel - 1)
                    elif k == "DOWN":
                        wifi_sel = min(max(0, len(wifi_ssids) - 1), wifi_sel + 1)
                    elif k == "SELECT":
                        if not wifi_supported:
                            # if nmcli not available, just go back
                            state = STATE_SETTINGS_ROOT
                        elif wifi_ssids:
                            wifi_target = wifi_ssids[wifi_sel]
                            wifi_pass = " " * 16
                            wifi_cursor = 0
                            charset_idx = 0
                            state = STATE_WIFI_PASS

                # ---------- WIFI PASSWORD PAGE ----------
                elif state == STATE_WIFI_PASS:
                    if k == "LEFT":
                        state = STATE_WIFI_LIST
                    elif k == "RIGHT":
                        wifi_cursor = min(15, wifi_cursor + 1)
                        charset_idx = 0
                    elif k == "LEFT":
                        wifi_cursor = max(0, wifi_cursor - 1)
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
                        pw = wifi_pass.strip()
                        ok, msg = connect_wifi(wifi_target, pw)
                        # After connect attempt, refresh list and return
                        wifi_active = get_active_ssid()
                        wifi_ssids = scan_ssids(limit=20)
                        state = STATE_WIFI_LIST
                        wifi_sel = 0

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
                if not wifi_supported:
                    lcd.render_ip_page(ip_address="nmcli missing")
                else:
                    lcd.render_wifi_list_page(wifi_ssids, wifi_active, wifi_sel)

            elif state == STATE_WIFI_PASS:
                lcd.render_wifi_password_page(wifi_target, wifi_pass, wifi_cursor)

            elif state == STATE_WEB:
                url = f"{ip}:8088"
                lcd.render_web_config_page(url=url)

            elif state == STATE_ABOUT:
                lcd.render_about_page()

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
