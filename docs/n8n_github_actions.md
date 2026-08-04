# n8n -> GitHub Actions

El flujo recomendado es que n8n invoque el workflow `MIRA ETL` usando `workflow_dispatch`.

Endpoint:

```text
POST https://api.github.com/repos/{owner}/{repo}/actions/workflows/etl.yml/dispatches
```

Body:

```json
{
  "ref": "main",
  "inputs": {
    "source": "costa_rica_sicop",
    "period": "202001"
  }
}
```

Headers:

```text
Accept: application/vnd.github+json
Authorization: Bearer {GITHUB_TOKEN}
X-GitHub-Api-Version: 2022-11-28
```

El token debe tener permisos para ejecutar Actions en el repositorio.
