# YouTube Transcript MCP Server

MCP-сервер для получения транскриптов (субтитров) YouTube-видео. Работает без авторизации, поддерживает автоматические и ручные субтитры.

Транспорт: **Streamable HTTP** (stateless) — рекомендуемый для удалённых серверов.

## Запуск

```bash
docker compose up -d --build
```

Сервер будет доступен на `http://<host>:8000/mcp`

## Подключение к VS Code

Добавь в `.vscode/settings.json` (в проекте) или в глобальные настройки:

```json
{
  "mcp": {
    "servers": {
      "youtube-transcript": {
        "type": "http",
        "url": "http://<host>:8000/mcp"
      }
    }
  }
}
```

## Инструмент: `get_transcript`

| Параметр     | Тип    | По умолчанию | Описание                                      |
|-------------|--------|-------------|-----------------------------------------------|
| `video`     | string | —           | ID видео или полный URL                        |
| `languages` | string | `"en,ru"`   | Приоритет языков через запятую                  |
| `timestamps`| bool   | `true`      | Включать таймкоды                              |

### Примеры вызова

```
Получи транскрипт видео https://youtube.com/shorts/6MIdV-qFjIc

Покажи субтитры для dQw4w9WgXcQ на русском
```

## Проверка работоспособности

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"capabilities":{}}}'
```
