"""Bounded request bodies and best-effort single-process production abuse limits."""
from collections import OrderedDict, deque
import threading
import time

from starlette.responses import JSONResponse
from app.config import settings


class RequestLimits:
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def allow(self, key, limit):
        now = time.monotonic()
        with self.lock:
            stamps = self.entries.pop(key, deque())
            while stamps and now - stamps[0] >= 60:
                stamps.popleft()
            self.entries[key] = stamps
            while len(self.entries) > 4096:
                self.entries.popitem(last=False)
            if len(stamps) >= limit:
                return False
            stamps.append(now)
            return True


limits = RequestLimits()


class RequestSecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        if settings.app_env.lower() == "production":
            path = scope["path"]
            group, limit = "api", 240
            if path.startswith("/api/auth/") and scope["method"] == "POST": group, limit = "auth", 30
            elif path == "/api/ai/chat": group, limit = "ai", 20
            elif path.startswith(("/api/simulate/", "/api/v1/")) and scope["method"] == "POST": group, limit = "simulation", 60
            elif scope["method"] == "POST" and ("what-if" in path or "affordability" in path): group, limit = "planning", 30
            client = (scope.get("client") or ("unknown",))[0]
            if not limits.allow((client, group), limit):
                return await JSONResponse({"detail": "Too many requests. Try again shortly."}, status_code=429,
                                          headers={"Retry-After": "60", "Cache-Control": "no-store"})(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > settings.max_request_bytes:
                return await JSONResponse({"detail": "Request body is too large."}, status_code=413,
                                          headers={"Cache-Control": "no-store"})(scope, receive, send)
            if not message.get("more_body", False):
                break
        replayed = False
        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)
