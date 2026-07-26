from contextlib import asynccontextmanager
import hashlib
from pathlib import Path
import re
import secrets
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, HTTPException, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from db import close_pool, ensure_schema, open_pool, pool


class TargetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    target: str = Field(min_length=2, max_length=500)
    check_type: Literal["http", "tcp", "ping", "ssl"]
    port: int | None = Field(default=None, ge=1, le=65535)

    @model_validator(mode="after")
    def validate_port(self):
        if self.check_type in {"tcp", "ssl"} and self.port is None:
            raise ValueError("A porta é obrigatória para verificações TCP e SSL.")
        return self


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    client_external_id: str | None = Field(default=None, max_length=120)
    api_base_url: str = Field(min_length=8, max_length=500)

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        try:
            parsed = urlsplit(value)
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("Informe uma URL e porta válidas para a API.") from exc
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("A URL da API deve começar com http:// ou https://.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("A URL da API não pode conter credenciais, parâmetros ou fragmentos.")
        if parsed.path not in {"", "/"}:
            raise ValueError("Informe somente o endereço base, sem caminhos adicionais.")
        if any(character in value for character in {'"', "'", "`", "\r", "\n", "\t"}):
            raise ValueError("A URL da API contém caracteres inválidos.")
        return value


class Heartbeat(BaseModel):
    hostname: str = Field(min_length=1, max_length=255)
    local_ip: str | None = Field(default=None, max_length=64)
    operating_system: str | None = Field(default=None, max_length=255)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@asynccontextmanager
async def lifespan(_: FastAPI):
    open_pool()
    ensure_schema()
    yield
    close_pool()


app = FastAPI(
    title="Projeto Disponibilidade e Verificação",
    version="0.4.0",
    lifespan=lifespan,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
AGENT_TEMPLATE_PATH = (
    Path(__file__).resolve().parent
    / "agent_templates"
    / "Instalar-Agente-Disponibilidade.ps1"
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    with pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "service": "disponibilidade-api"}


@app.get("/api/targets")
def list_targets():
    query = """
        SELECT id, name, target, check_type, port, enabled, created_at
        FROM targets ORDER BY name
    """
    with pool.connection() as conn:
        cursor = conn.execute(query)
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


@app.post("/api/targets", status_code=status.HTTP_201_CREATED)
def create_target(payload: TargetCreate):
    query = """
        INSERT INTO targets (name, target, check_type, port)
        VALUES (%s, %s, %s, %s)
        RETURNING id, name, target, check_type, port, enabled, created_at
    """
    try:
        with pool.connection() as conn:
            cursor = conn.execute(
                query,
                (payload.name, payload.target, payload.check_type, payload.port),
            )
            row = cursor.fetchone()
            columns = [column.name for column in cursor.description]
            return dict(zip(columns, row))
    except Exception as exc:
        if "target_type_unique" in str(exc):
            raise HTTPException(409, "Este alvo já está cadastrado.") from exc
        raise


@app.get("/api/status")
def current_status():
    query = "SELECT * FROM latest_target_status ORDER BY name"
    with pool.connection() as conn:
        cursor = conn.execute(query)
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


@app.get("/api/targets/{target_id}/history")
def target_history(target_id: int, limit: int = 100):
    limit = min(max(limit, 1), 1000)
    query = """
        SELECT status, latency_ms, status_code, message,
               certificate_expires_at, checked_at
        FROM check_results
        WHERE target_id = %s
        ORDER BY checked_at DESC
        LIMIT %s
    """
    with pool.connection() as conn:
        cursor = conn.execute(query, (target_id, limit))
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


@app.delete("/api/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(target_id: int):
    with pool.connection() as conn:
        cursor = conn.execute("DELETE FROM targets WHERE id = %s", (target_id,))
        if cursor.rowcount == 0:
            raise HTTPException(404, "Alvo não encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/agents")
def list_agents():
    query = """
        SELECT id, name, location, client_external_id, hostname, local_ip,
               operating_system, last_seen_at, created_at, status
        FROM latest_agent_status
        ORDER BY name
    """
    with pool.connection() as conn:
        cursor = conn.execute(query)
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


@app.post("/api/agents", status_code=status.HTTP_201_CREATED)
def create_agent(payload: AgentCreate):
    token = secrets.token_urlsafe(32)
    try:
        template = AGENT_TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(500, "Modelo do agente PowerShell não encontrado.") from exc
    script_content = (
        template.replace("__API_BASE_URL__", payload.api_base_url)
        .replace("__AGENT_TOKEN__", token)
    )
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", payload.name).strip("_") or "computador"
    script_filename = f"Instalar-Agente-Disponibilidade-{safe_name}.ps1"
    query = """
        INSERT INTO agents (name, location, client_external_id, token_hash)
        VALUES (%s, %s, %s, %s)
        RETURNING id, name, location, client_external_id, created_at
    """
    with pool.connection() as conn:
        cursor = conn.execute(
            query,
            (
                payload.name,
                payload.location,
                payload.client_external_id,
                hash_token(token),
            ),
        )
        row = cursor.fetchone()
        columns = [column.name for column in cursor.description]
    agent = dict(zip(columns, row))
    agent["token"] = token
    agent["api_base_url"] = payload.api_base_url
    agent["script_filename"] = script_filename
    agent["script_content"] = script_content
    agent["warning"] = (
        "O token é exibido somente nesta resposta e já foi inserido no script."
    )
    return agent


@app.post("/api/heartbeat")
def receive_heartbeat(
    payload: Heartbeat,
    x_agent_token: str | None = Header(default=None),
):
    if not x_agent_token:
        raise HTTPException(401, "Cabeçalho X-Agent-Token ausente.")

    query = """
        UPDATE agents
        SET hostname = %s,
            local_ip = %s,
            operating_system = %s,
            last_seen_at = NOW()
        WHERE token_hash = %s AND enabled = TRUE
        RETURNING id, name, location, client_external_id, last_seen_at
    """
    with pool.connection() as conn:
        cursor = conn.execute(
            query,
            (
                payload.hostname,
                payload.local_ip,
                payload.operating_system,
                hash_token(x_agent_token),
            ),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(401, "Token de agente inválido ou desativado.")
        columns = [column.name for column in cursor.description]
        agent = dict(zip(columns, row))
    return {"status": "received", "agent": agent}


@app.delete("/api/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: int):
    with pool.connection() as conn:
        cursor = conn.execute("DELETE FROM agents WHERE id = %s", (agent_id,))
        if cursor.rowcount == 0:
            raise HTTPException(404, "Agente não encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
