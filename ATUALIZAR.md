# Atualização para a versão com agentes e dashboard híbrido

Esta versão preserva o banco, os alvos cadastrados e o histórico existente.

## 1. Antes de substituir os arquivos

Pare somente a execução dos serviços:

```powershell
docker compose stop
```

Guarde o seu arquivo `.env`. O pacote atualizado não contém esse arquivo e não
substitui suas senhas.

## 2. Substitua os arquivos

Extraia o conteúdo da nova versão sobre a pasta atual do projeto.

## 3. Reconstrua a aplicação

```powershell
docker compose up -d --build --force-recreate api worker
docker compose restart grafana
```

Não execute `docker compose down -v`, pois a opção `-v` apaga os volumes.

## 4. Valide

```powershell
docker ps
Invoke-RestMethod http://localhost:8620/health
```

Abra o novo painel administrativo:

```text
http://localhost:8620/
```

Abra o Grafana:

```text
http://localhost:3000/d/projeto-disponibilidade/central-de-disponibilidade-e-verificacao
```

O dashboard atualizado estará em:

```text
Dashboards > Disponibilidade > Central de Disponibilidade e Verificação
```

## 5. Crie um agente

Abra `http://localhost:8620/`, entre na aba **Agentes** e informe:

- nome e local;
- ID externo do cliente, se desejar;
- o IP/URL da API acessível pelo computador monitorado.

Clique em **Criar agente e baixar PS1**. O arquivo já será gerado com o
endereço e o token corretos, sem edição manual.
