from __future__ import annotations

import argparse
from pathlib import Path

from common import ASSETS_DIR, CONFIG_DIR, DATA_DIR, REPO_ROOT, ensure_dir


def upsert_line(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare local files for the YouTube automation pipeline.")
    parser.add_argument("--demo", action="store_true", help="Enable DEMO_MODE in the generated .env file.")
    args = parser.parse_args()

    env_example = REPO_ROOT / ".env.example"
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        env_path.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")

    ensure_dir(CONFIG_DIR)
    ensure_dir(ASSETS_DIR / "backgrounds")
    ensure_dir(ASSETS_DIR / "music")
    for relative_path in ["analytics", "audio", "scripts", "thumbnails", "videos"]:
        ensure_dir(DATA_DIR / relative_path)

    local_client_secret = CONFIG_DIR / "client_secret.json"
    local_token = CONFIG_DIR / "token.json"
    upsert_line(env_path, "YOUTUBE_CLIENT_SECRET_PATH", str(local_client_secret))
    upsert_line(env_path, "YOUTUBE_TOKEN_PATH", str(local_token))
    if args.demo:
        upsert_line(env_path, "DEMO_MODE", "true")

    print(f"Prepared local environment file: {env_path}")
    print(f"Place OAuth client file here: {local_client_secret}")
    print(f"Token will be stored here after first login: {local_token}")
    print(f"Background assets directory: {ASSETS_DIR / 'backgrounds'}")
    print(f"Music assets directory: {ASSETS_DIR / 'music'}")


if __name__ == "__main__":
    main()

