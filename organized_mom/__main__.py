import os
from pathlib import Path

import uvicorn


def main():
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except ImportError:
        pass
    from .app import create_app

    # Public hosting needs an authentication layer; keep this release on loopback.
    uvicorn.run(create_app(), host="127.0.0.1", port=int(os.getenv("MOM_PORT", "8000")))


if __name__ == "__main__":
    main()
