# Projeto Disponibilidade e Verificação

Plataforma pessoal e independente para verificar disponibilidade, registrar
histórico e exibir gráficos. Esta primeira versão não usa Zabbix.

## Componentes

- API FastAPI para cadastrar alvos e consultar resultados;
- worker para verificações HTTP/HTTPS, TCP, ping e certificado SSL;
- agentes PowerShell com nome e token exclusivos para computadores externos;
- PostgreSQL para alvos e histórico;
- Grafana com datasource e dashboard provisionados;
- Docker Compose para executar toda a stack.

## Portas

| Serviço | Endereço |
|---|---|
| Painel administrativo | `http://localhost:8620/` |
| API e documentação | `http://localhost:8620/docs` |
| Saúde da API | `http://localhost:8620/health` |
| Grafana | `http://localhost:3000/d/projeto-disponibilidade/central-de-disponibilidade-e-verificacao` |

## Como iniciar

1. Copie `.env.example` para `.env`.
2. Troque as duas senhas no `.env`.
3. Execute:

```powershell
docker compose up -d --build
docker compose ps
```

Abra o Grafana e acesse a pasta **Disponibilidade**. Dois alvos internos de
teste já são cadastrados automaticamente: API e PostgreSQL.

## Painel administrativo web

Abra `http://localhost:8620/` para:

- visualizar todos os alvos e agentes;
- acompanhar o status atual;
- cadastrar ping, HTTP/HTTPS, TCP e SSL;
- criar agentes com token individual e baixar o PowerShell pronto;
- informar o IP/URL da API que será colocado automaticamente no agente;
- copiar o token exibido somente na criação;
- excluir alvos ou agentes com confirmação;
- abrir rapidamente o Grafana ou o Swagger.

O painel atualiza os dados automaticamente a cada minuto.

## Cadastrar um alvo

Abra `http://localhost:8620/docs` e use `POST /api/targets`.

Exemplo HTTP:

```json
{
  "name": "Site pessoal",
  "target": "https://example.com",
  "check_type": "http",
  "port": null
}
```

Exemplo TCP:

```json
{
  "name": "Servidor RDP",
  "target": "192.168.1.10",
  "check_type": "tcp",
  "port": 3389
}
```

Exemplo ping:

```json
{
  "name": "Gateway",
  "target": "192.168.1.1",
  "check_type": "ping",
  "port": null
}
```

Exemplo SSL:

```json
{
  "name": "Certificado do site",
  "target": "example.com",
  "check_type": "ssl",
  "port": 443
}
```

## Endpoints

- `GET /health`
- `GET /api/targets`
- `POST /api/targets`
- `DELETE /api/targets/{id}`
- `GET /api/status`
- `GET /api/targets/{id}/history`
- `GET /api/agents`
- `POST /api/agents`
- `DELETE /api/agents/{id}`
- `POST /api/heartbeat`

## Agente para computadores externos

A forma recomendada é abrir a aba **Agentes** do painel:

1. informe o nome e o local do computador;
2. em **Endereço da API**, informe um endereço acessível pelo computador;
3. clique em **Criar agente e baixar PS1**;
4. execute o arquivo baixado pelo PowerShell como administrador.

Se o computador estiver na mesma rede, use por exemplo:

```text
http://192.168.1.10:8620
```

Se estiver fora da rede, use a URL pública HTTPS do projeto. Não use
`localhost`, pois nesse caso o agente tentaria acessar o próprio computador.

Também é possível criar pelo `POST /api/agents`:

```json
{
  "name": "PC Wellington",
  "location": "Casa",
  "client_external_id": null,
  "api_base_url": "http://192.168.1.10:8620"
}
```

A resposta contém o token, o nome do arquivo e o conteúdo do instalador
PowerShell. Pela interface web, o download começa automaticamente.

Se o Windows bloquear a execução, abra o PowerShell como administrador e use:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Instalar-Agente-Disponibilidade-PC_Wellington.ps1
```

O mesmo arquivo instala a tarefa agendada, envia o primeiro heartbeat e depois
executa automaticamente a cada minuto.

O campo `client_external_id` já está reservado para o futuro ID único do
cliente no Wave Manutenção.

## Próximas fases

1. Interface web própria em tema escuro;
2. alertas por e-mail ou Telegram;
3. janela de manutenção;
4. cálculo de SLA em 24 horas, 7 dias e 30 dias;
5. autenticação;
6. integração opcional com o Wave Manutenção por API.

## Dashboard híbrido

O dashboard **Central de Disponibilidade e Verificação** combina:

- indicadores de monitorados, online, offline e disponibilidade;
- filtro de agentes por local;
- gráfico de latência por origem;
- volume de verificações online e com falha;
- linha do tempo de status dos alvos;
- blocos de estado dos computadores com agente;
- inventário rápido de agentes;
- disponibilidade por alvo nas últimas 24 horas.

Para atualizar uma instalação existente, consulte `ATUALIZAR.md`.
