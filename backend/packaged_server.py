"""Entry point for the standalone Windows clinical server."""
import argparse
import multiprocessing
import os
import sys


REQUIRED_ENV = (
    "LUNGTIC_DB_URL",
    "LUNGTIC_DATA_DIR",
    "LUNGTIC_JWT_SECRET",
    "LUNGTIC_CAPTCHA_SECRET",
    "LUNGTIC_CORS_ORIGINS",
    "LUNGTIC_RECORD_ACTIVE_KEY_ID",
    "LUNGTIC_RECORD_KEYS_JSON",
)


def main() -> int:
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="LungTic 中心病例服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        parser.error("缺少服务配置：" + ", ".join(missing))
    if args.host not in ("127.0.0.1", "::1", "localhost") and os.getenv("LUNGTIC_ALLOW_NETWORK_BIND") != "1":
        parser.error("服务默认只监听本机；跨机器访问请先配置 HTTPS 反向代理")
    if not 1 <= args.port <= 65535:
        parser.error("端口必须在 1 到 65535 之间")

    from main import app
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, loop="asyncio", http="h11", ws="none", workers=1, reload=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
