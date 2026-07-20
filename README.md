### Hexlet tests and linter status:

[![Actions Status](https://github.com/autobol4ik/devops-engineer-from-scratch-project-313/actions/workflows/hexlet-check.yml/badge.svg)](https://github.com/autobol4ik/devops-engineer-from-scratch-project-313/actions)
[![CI](https://github.com/autobol4ik/devops-engineer-from-scratch-project-313/actions/workflows/ci.yml/badge.svg)](https://github.com/autobol4ik/devops-engineer-from-scratch-project-313/actions/workflows/ci.yml)

# Деплой приложения на PaaS

Развернутое приложение: [hexlet-project-313.onrender.com](https://hexlet-project-313.onrender.com)

## Запуск

Установите зависимости:

```bash
uv sync
```

Запустите приложение:

```bash
make run
```

После запуска приложение доступно по адресу `http://localhost:8080`. Проверить маршрут можно командой:

```bash
curl http://localhost:8080/ping
```

В ответ приложение возвращает `pong`.
