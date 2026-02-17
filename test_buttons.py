import time
from mta_app.buttons import Buttons

btn = Buttons(debug=True)

print("Press buttons (Ctrl+C to stop)...")
try:
    while True:
        ev = btn.pop_event()
        if ev:
            print(f"POP: {ev.kind} at {ev.t:.3f}")
        time.sleep(0.02)
except KeyboardInterrupt:
    pass
