# Дизайн-система ЧайHouse — правила UI/UX

> Этот документ — обязательный стандарт для **всех новых страниц и модулей**
> проекта (Flask + Jinja2). Стек: Tailwind CSS, Alpine.js, HTMX, Lucide, Toastify.

## 1. Стек

| Инструмент | Назначение | Подключение |
|---|---|---|
| Tailwind CSS | Стилизация (утилиты, тёмная тема, кастомные цвета бренда) | CDN `cdn.tailwindcss.com` + inline-конфиг (nonce) в `base.html` |
| Inter | Основной текст сайта | Google Fonts, грузится в `base.html` |
| Manrope | Заголовки (утилита `font-display`, все `h1–h6` автоматически) | Google Fonts, грузится в `base.html` |
| Alpine.js | Интерактив: модальные окна, дропдауны, табы, мобильное меню | CDN jsDelivr (`defer`) |
| HTMX | Динамическое обновление фрагментов страницы без перезагрузки | CDN jsDelivr (`defer`) |
| Lucide | Векторные иконки (`<i data-lucide="icon-name">`) | CDN jsDelivr; инициализация в `static/js/ui-init.js` |
| Toastify-js | Всплывающие уведомления вместо `alert()` | CDN jsDelivr; конвертация Flask flash в `static/js/ui-init.js` |

CSP-примечание: inline-скрипты разрешены **только с nonce** (`script_nonce`
генерируется в `app.py` на каждый запрос). `unsafe-inline` в `script-src` запрещён.
`'unsafe-eval'` в `script-src` разрешён — он требуется стандартной CDN-сборке
Alpine.js для вычисления выражений (`x-data`, `@click` и т.п.). Альтернатива —
CSP-сборка `@alpinejs/csp`, но она не поддерживает inline-выражения и потребует
переписать все компоненты на JS-функции (можно сделать при усилении безопасности).
`unsafe-inline` в `style-src` нужен для Tailwind Play CDN — компилирует CSS в рантайме.

## 2. Визуальный стиль — современный минимализм

- **Карточки и панели**: `rounded-2xl`, `border border-gray-100`, `shadow-sm` → `hover:shadow-md`, фон `bg-white` / `dark:bg-gray-900`.
- **Кнопки и поля ввода**: `rounded-xl`.
- **Воздух**: внутренние отступы `p-6`, сетки — `gap-6`, секции — `py-12`–`py-20`.
- **Тени**: только `shadow-sm`/`shadow-md`/`shadow-lg` (дропдауны/модалки). Никаких резких теней.
- **Типографика**: заголовки — Manrope (`font-display`, `tracking-tight`), текст — Inter. Палитра текста: `charcoal-900` (светлая) / `gray-100` (тёмная), вторичный — `gray-500`.
- **Цвета бренда** (Tailwind-конфиг в `base.html`):
  - `teal-500/600` — основной акцент (CTA, ссылки, focus-состояния);
  - `charcoal-*` — текст и тёмные поверхности;
  - `sand-*` — тёплый фон секций;
  - `brass-*` — золотые акценты (бейджи, оценки);
  - `terra-*` — ошибки и разрушающие действия.

## 3. Микро-взаимодействия

- Все кликабельные элементы: `transition-all duration-200`.
- Hover: смена цвета фона, `hover:shadow-md`, для карточек-ссылок — `hover:-translate-y-0.5`.
- Active: `active:scale-[0.98]` на кнопках.
- Focus: всегда `focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2` — доступность обязательна.
- Состояние загрузки: кнопки отправки форм — макрос `btn_submit_loading()` (спиннер + «Отправляем…»), логика в `ui-init.js`.
- Появление/скрытие Alpine-элементов: `x-transition` с `duration-200`.

## 4. Адаптивность — Mobile-First

- Базовые стили пишутся для смартфона; расширение только префиксами `sm:` → `md:` → `lg:` → `xl:`.
- Навигация: десктоп-меню `hidden lg:block`, мобильное — Alpine-панель с `lg:hidden`.
- Сетки: `grid-cols-1` → `sm:grid-cols-2` → `lg:grid-cols-3` / `grid-cols-4`.
- Таблицы — внутри `overflow-x-auto` обёртки (не ломают мобильную ширину).
- Точки останова Tailwind по умолчанию: `sm 640px`, `md 768px`, `lg 1024px`, `xl 1280px`.
- Проверять страницы на ширинах: 360, 496, 768, 1024, 1440 px.

## 5. Тёмная тема

- Режим: `darkMode: 'class'` (класс `dark` на `<html>`).
- Переключатель — в навбаре (`components/navbar.html`), выбор хранится в `localStorage`, системная тема — значение по умолчанию (`static/js/theme.js` подключён в `<head>` без `defer`, чтобы не было мигания).
- Для **каждого** компонента писать `dark:`-варианты: фон `dark:bg-gray-900/950`, границы `dark:border-gray-800`, текст `dark:text-gray-100`.
- Нельзя оставлять «жёсткие» `bg-white`/`text-charcoal-900` без парного `dark:`-класса.

## 6. Уведомления

- Серверные flash-сообщения Flask остаются источником правды (категории: `success`, `danger`, `warning`, `info`).
- `ui-init.js` конвертирует их в Toastify-тосты (справа сверху, 4.5 с, кнопка закрытия) и удаляет fallback-блок.
- Fallback: без JS блоки `.flash-stack` рендерятся как раньше — доступность не теряется.
- В JS-коде запрещено использовать `alert()`/`confirm()` для уведомлений об операциях.

## 7. Компоненты (templates/components/)

| Файл | Содержимое |
|---|---|
| `navbar.html` | Шапка: логотип, меню, тема, колокольчик, дропдаун аккаунта, мобильное меню (Alpine) |
| `footer.html` | Футер: 4 колонки (mobile-first), контакты, дисклеймер |
| `buttons.html` | Макросы: `btn_primary`, `btn_secondary`, `btn_ghost`, `btn_danger`, `btn_submit_loading` |
| `cards.html` | Макросы: `card`, `stat_card`, `link_card`, `section_head` |
| `fields.html` | Макросы форм: `field_input`, `field_textarea`, `field_select`, `field_checkbox` |
| `ui.html` | Legacy-макросы старой системы (иконки, карточки меню) — используются до полной миграции |

Подключение макросов: `{% from "components/buttons.html" import btn_primary %}`.

## 8. Правила миграции

- Существующие страницы используют legacy CSS (`static/css/app.css`) — это нормально.
- Preflight у Tailwind **отключён** (`corePlugins: { preflight: false }`), чтобы не ломать legacy-страницы. После миграции всех страниц — включить.
- Новые/переделываемые страницы: только Tailwind-утилиты + макросы из `components/`, без новых стилей в `app.css`.
- HTMX-фрагменты: partial-шаблон без наследования `base.html`, контейнер с `hx-`-атрибутами; ответы отдаются только во фрагмент.
- Иконки в новом коде: `<i data-lucide="...">` + `lucide.createIcons()` (уже в `ui-init.js`).

## 9. Запрещено

- Inline-скрипты без nonce (CSP).
- Новые цвета вне палитры Tailwind/бренда.
- Фиксированные высоты/ширины без `max-w-*`.
- Отрицательные отступы «вручную» вместо gap.
- Использование `!important` — только в `[x-cloak]`.
