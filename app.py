import time

from mta_app.config import load_settings
from mta_app.lcd_ui import LCDUI, PageData
from mta_app.buttons import Buttons
from mta_app.monitor import Monitor


def main() -> int:
    settings = load_settings("settings.json")

    # LCD config (optional in settings.json)
    lcd_cfg = getattr(settings, "lcd", None)  # if you didn’t add schema support, just hardcode below

    # If you added lcd to settings.json but didn’t add it to models/config parsing,
    # you can hardcode here instead:
    i2c_port = 1
    i2c_address = 0x27

    lcd = LCDUI(i2c_port=i2c_port, i2c_address=i2c_address)
    buttons = Buttons(left_gpio=16, right_gpio=20, select_gpio=21)

    mon = Monitor(settings)
    mon.start()

    # Page indices:
    # 0 = Home, 1..N = stations, N+1 = Settings
    station_count = len(settings.stations)
    last_page = station_count + 1
    page = 0

    try:
        while True:
            # Handle buttons
            ev = buttons.pop_event()
            if ev:
                if ev.kind == "LEFT":
                    page = max(0, page - 1)
                elif ev.kind == "RIGHT":
                    page = min(last_page, page + 1)
                elif ev.kind == "SELECT":
                    if page == last_page:
                        # Settings page: reload settings.json
                        settings = load_settings("settings.json")
                        mon.stop()
                        mon = Monitor(settings)
                        mon.start()
                        station_count = len(settings.stations)
                        last_page = station_count + 1
                        page = min(page, last_page)
                    else:
                        # Any other page: force refresh now
                        mon.force_refresh()

            # Render current page
            if page == 0:
                lcd.render_home(page_idx=page, page_total=last_page)
            elif page == last_page:
                lcd.render_settings(page_idx=page, page_total=last_page)
            else:
                st = settings.stations[page - 1]
                snap = mon.get_snapshot(page - 1)

                data = PageData(
                    stop_name=st.stop_name,
                    direction=st.direction,
                    direction_label=st.direction_label,
                    arrivals=snap.arrivals,
                )
                lcd.render_station(data, page_idx=page, page_total=last_page)

            # UI refresh rate (also drives marquee)
            time.sleep(0.12)

    except KeyboardInterrupt:
        return 0
    finally:
        mon.stop()
        lcd.close()


if __name__ == "__main__":
    raise SystemExit(main())
