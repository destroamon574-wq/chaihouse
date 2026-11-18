# 🌍 Деплой ЧайHouse в интернет

Приложение готово к хостингу: production-сервер **waitress** в зависимостях, `ProxyFix` для HTTPS
за прокси, health-check `/healthz`, конфигурация только через переменные окружения, файлы
`Procfile` и `render.yaml` в репозитории.

Ниже — три варианта. Для портфолио рекомендую **Render** (бесплатно, HTTPS, деплой из GitHub).

---

## Вариант 1. Render — бесплатно, 10 минут (рекомендую)

1. Зарегистрируйтесь на <https://render.com> через GitHub (доступ к репозиторию `chaihouse`).
2. **New → Web Service** → выберите репозиторий `destroamon574-wq/chaihouse`.
3. Render сам прочитает `render.yaml`; если создаёте вручную, укажите:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `waitress-serve --port=$PORT --call app:create_app`
   - **Health Check Path**: `/healthz`
4. Переменные окружения (Environment):
   | Ключ | Значение |
   |---|---|
   | `FLASK_ENV` | `production` |
   | `SECRET_KEY` | нажмите «Generate» (или длинная случайная строка) |
   | `SITE_URL` | `https://chaihouse.onrender.com` (ваш адрес после первого деплоя) |
   | `DEMO_MODE` | `1` (демо-подсказки на странице входа) |
5. **Create Web Service** → подождите 2–3 минуты → сайт откроется по адресу вида
   `https://chaihouse.onrender.com`.

> ⚠️ Бесплатный план Render: сервис засыпает после ~15 минут без трафика (первый запрос
> просыпается 30–60 секунд) и **диск эфемерный** — SQLite-база сбрасывается при рестарте.
> Для портфолио это плюс (демо всегда в исходном виде). Для сохранности данных нужен
> платный **Persistent Disk** (монтируется в `/var/data`) и переменные:
> `DATABASE_PATH=/var/data/chaihouse.db`, `UPLOAD_DIR=/var/data/uploads`.

## Вариант 2. Railway — быстрый деплой из GitHub

1. <https://railway.app> → **New Project → Deploy from GitHub repo** → `chaihouse`.
2. Railway определит Python по репозиторию; если нет — Start Command:
   `waitress-serve --port=$PORT --call app:create_app`.
3. Добавьте `FLASK_ENV=production`, `SECRET_KEY`, `SITE_URL` (домен Railway).
4. HTTPS выдаётся автоматически.

## Вариант 3. Свой VPS (полный контроль)

```bash
# на сервере (Ubuntu 22.04+)
sudo apt update && sudo apt install -y python3-venv nginx
git clone https://github.com/destroamon574-wq/chaihouse.git && cd chaihouse
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполните SECRET_KEY, FLASK_ENV=production, SITE_URL=https://ваш-домен
```

Сервис systemd (`/etc/systemd/system/chaihouse.service`):

```ini
[Unit]
Description=ChaiHouse
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/chaihouse
EnvironmentFile=/opt/chaihouse/.env
ExecStart=/opt/chaihouse/.venv/bin/waitress-serve --port=8000 --call app:create_app
Restart=always

[Install]
WantedBy=multi-user.target
```

Nginx: проксирование на `127.0.0.1:8000`, HTTPS через `certbot --nginx`.
Обязательно пробросьте заголовок `X-Forwarded-Proto $scheme` (ProxyFix уже включён в production).

---

## Чек-лист перед публикацией

- [ ] `SECRET_KEY` — длинная случайная строка (не `dev-only-change-me-chaihouse`)
- [ ] `FLASK_ENV=production` (включает `Secure`-cookie, HSTS, ProxyFix)
- [ ] `SITE_URL` — реальный публичный адрес (влияет на canonical, Open Graph, sitemap)
- [ ] Демо-пароли админа/владельца изменены, если сайт не должен быть «песочницей»
      (по умолчанию `DEMO_MODE=1` показывает подсказки на странице входа)
- [ ] `DEBUG` выключен (production-режим его не включает)
- [ ] HTTPS работает (Render/Railway — автоматически; VPS — certbot)
- [ ] Для сохранности SQLite — persistent disk (`DATABASE_PATH`, `UPLOAD_DIR`) или Postgres
- [ ] Резервные копии: `python scripts/backup_db.py` (в проекте есть сервис бэкапов)
- [ ] Обновлён `SITE_URL` в README и описании репозитория ссылкой на живой сайт

## Проверка после деплоя

```bash
curl -I https://ваш-домен/healthz      # 200 OK
curl -I https://ваш-домен/             # 200, заголовки CSP, HSTS
```

Затем прогоните Lighthouse на публичном URL — целевые показатели: Accessibility / Best Practices / SEO — 100.
