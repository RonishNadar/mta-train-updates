from mta_app.config import load_settings
from mta_app.runner import run_monitor


def main() -> int:
    settings = load_settings("settings.json")
    run_monitor(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
