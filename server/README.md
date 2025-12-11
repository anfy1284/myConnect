# MyConnect Server

Серверная часть проекта MyConnect. Отвечает за аутентификацию клиентов и маршрутизацию пакетов между ними через WebSocket.

## Требования

*   Python 3.8+
*   Открытый порт (по умолчанию 8765)

## Установка

1.  Перейдите в директорию сервера:
    ```bash
    cd server
    ```
2.  Установите зависимости:
    ```bash
    pip install -r requirements.txt
    ```

## Конфигурация

Файл настройки: `config.json`

```json
{
    "host": "0.0.0.0",          // Интерфейс для прослушивания
    "port": 8765,               // Порт
    "clients": {                // Список разрешенных клиентов
        "client1_token": "client1",  // "Токен": "Имя клиента"
        "deutschland_token": "deutschland"
    },
    "request_timeout": 30,      // Таймаут запросов (сек)
    "log_retention_days": 7,    // Срок хранения логов
    "enable_logging": true,     // Включить логирование в файл
    "log_file": "server.log",   // Имя файла лога
    "use_tls": false,           // Включить SSL/TLS (рекомендуется для продакшена)
    "cert_file": "cert.pem",    // Путь к сертификату (если use_tls: true)
    "key_file": "key.pem"       // Путь к ключу (если use_tls: true)
}
```

### Настройка TLS (WSS)

Для безопасного соединения рекомендуется включить TLS.
1.  Получите сертификаты (например, через Let's Encrypt) или сгенерируйте самоподписанные.
2.  Установите `"use_tls": true` в конфиге.
3.  Укажите пути к `cert_file` и `key_file`.

## Запуск

```bash
python main.py
```

Сервер начнет слушать входящие соединения. Логи будут писаться в `server.log` (если включено).

## Развертывание (Пример для Systemd)

Создайте файл `/etc/systemd/system/myconnect.service`:

```ini
[Unit]
Description=MyConnect Server
After=network.target

[Service]
User=root
WorkingDirectory=/path/to/myConnect/server
ExecStart=/usr/bin/python3 /path/to/myConnect/server/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl enable myconnect
sudo systemctl start myconnect
```
