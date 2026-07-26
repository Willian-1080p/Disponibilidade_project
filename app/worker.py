import os
import socket
import ssl
import subprocess
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from db import open_pool, pool

INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))


def check_http(target: str) -> dict:
    started = time.perf_counter()
    response = httpx.get(target, timeout=TIMEOUT, follow_redirects=True)
    latency = (time.perf_counter() - started) * 1000
    online = 200 <= response.status_code < 400
    return {
        "status": "online" if online else "offline",
        "latency_ms": latency,
        "status_code": response.status_code,
        "message": f"HTTP {response.status_code}",
    }


def check_tcp(host: str, port: int) -> dict:
    started = time.perf_counter()
    with socket.create_connection((host, port), timeout=TIMEOUT):
        latency = (time.perf_counter() - started) * 1000
    return {"status": "online", "latency_ms": latency, "message": "Porta acessível"}


def check_ping(host: str) -> dict:
    started = time.perf_counter()
    result = subprocess.run(
        ["ping", "-c", "1", "-W", str(max(1, int(TIMEOUT))), host],
        capture_output=True,
        text=True,
        timeout=TIMEOUT + 2,
        check=False,
    )
    latency = (time.perf_counter() - started) * 1000
    if result.returncode != 0:
        raise RuntimeError("Sem resposta ICMP")
    return {"status": "online", "latency_ms": latency, "message": "Ping respondido"}


def check_ssl(host: str, port: int) -> dict:
    started = time.perf_counter()
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=TIMEOUT) as raw:
        with context.wrap_socket(raw, server_hostname=host) as secure:
            certificate = secure.getpeercert()
    latency = (time.perf_counter() - started) * 1000
    expires = datetime.strptime(
        certificate["notAfter"], "%b %d %H:%M:%S %Y %Z"
    ).replace(tzinfo=timezone.utc)
    days = (expires - datetime.now(timezone.utc)).days
    return {
        "status": "warning" if days < 30 else "online",
        "latency_ms": latency,
        "message": f"Certificado válido por {days} dias",
        "certificate_expires_at": expires,
    }


def run_check(row: dict) -> dict:
    if row["check_type"] == "http":
        return check_http(row["target"])
    if row["check_type"] == "tcp":
        return check_tcp(row["target"], row["port"])
    if row["check_type"] == "ping":
        return check_ping(row["target"])
    if row["check_type"] == "ssl":
        host = urlparse(row["target"]).hostname or row["target"]
        return check_ssl(host, row["port"])
    raise ValueError("Tipo de verificação desconhecido")


def cycle() -> None:
    with pool.connection() as conn:
        cursor = conn.execute(
            "SELECT id, target, check_type, port FROM targets WHERE enabled = TRUE"
        )
        columns = [column.name for column in cursor.description]
        targets = [dict(zip(columns, row)) for row in cursor.fetchall()]

    for target in targets:
        try:
            result = run_check(target)
        except Exception as exc:
            result = {"status": "offline", "message": str(exc)[:500]}

        with pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO check_results
                    (target_id, status, latency_ms, status_code, message,
                     certificate_expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    target["id"],
                    result["status"],
                    result.get("latency_ms"),
                    result.get("status_code"),
                    result.get("message"),
                    result.get("certificate_expires_at"),
                ),
            )


if __name__ == "__main__":
    open_pool()
    print(f"Worker iniciado. Intervalo: {INTERVAL}s", flush=True)
    while True:
        cycle()
        time.sleep(INTERVAL)

