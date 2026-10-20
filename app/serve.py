"""Portable single-worker entry point. Hosting supplies PORT; migrations are separate."""
import uvicorn
from app.config import settings


def main():
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, workers=1,
                reload=False, access_log=settings.app_env.lower() != "production")


if __name__ == "__main__":
    main()
