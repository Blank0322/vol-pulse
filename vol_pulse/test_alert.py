import os

from .alert_system import AlertMessage, AlertSystem


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def main() -> None:
    load_dotenv()
    print("PUSH_USER_KEY:", "set" if os.getenv("PUSH_USER_KEY") else "missing")
    print("PUSH_API_TOKEN:", "set" if os.getenv("PUSH_API_TOKEN") else "missing")
    alert = AlertSystem()
    alert.send(
        AlertMessage(
            title="IV Hunter Test Alert",
            body="This is a test notification from IV options monitor.",
        )
    )


if __name__ == "__main__":
    main()
