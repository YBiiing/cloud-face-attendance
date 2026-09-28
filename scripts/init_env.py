"""Create a local .env without overwriting existing credentials."""
from pathlib import Path
import secrets


def main() -> None:
    target = Path(__file__).resolve().parent.parent / ".env"
    try:
        with target.open("x", encoding="utf-8") as output:
            for key in ("MYSQL_PASSWORD", "MYSQL_ROOT_PASSWORD", "APP_SECRET"):
                output.write(f"{key}={secrets.token_hex(32)}\n")
    except FileExistsError:
        print("Existing .env preserved.")
    else:
        print("Local .env created; secret values are not displayed.")


if __name__ == "__main__":
    main()
