---
name: Design System
description: Применяет дизайн-систему ЧайHouse при создании или редизайне страниц, компонентов, форм и модалок (Tailwind, Alpine, тёмная тема, Mobile-First)
---

# Дизайн-система ЧайHouse

Перед созданием или стилизацией любого UI прочитайте `docs/DESIGN.md` — это
обязательный стандарт проекта. Краткая выжимка:

## Стек (подключён в templates/base.html)
- **Tailwind CSS** (Play CDN) — утилиты, `darkMode: 'class'`, палитра бренда:
  `teal-500/600` (акцент/CTA), `charcoal-*` (текст), `sand-*` (тёплый фон),
  `brass-*` (золотые бейджи), `terra-*` (ошибки, деструктив).
- **Inter** — текст, **Manrope** — заголовки (`font-display`).
- **Alpine.js** — интерактив (меню, дропдауны, табы, модалки).
- **HTMX** — динамические фрагменты без перезагрузки.
- **Lucide** — иконки `<i data-lucide="...">`.
- **Toastify** — flash-сообщения Flask → тосты (никаких alert()).

## Обязательные правила
1. Карточки/панели: `rounded-2xl border border-gray-100 shadow-sm hover:shadow-md
   transition-all duration-200`, фон `bg-white` / `dark:bg-gray-900`.
2. Кнопки/поля: `rounded-xl`; focus: `focus-visible:ring-2 ring-teal-500`.
3. Воздух: `p-6` внутри, `gap-6` в сетках.
4. Все кликабельные элементы: `transition-all duration-200`, hover-состояния,
   active: `active:scale-[0.98]`.
5. Mobile-First: базовые стили для смартфона, расширение `sm: md: lg:`.
6. Тёмная тема: каждый компонент получает `dark:`-варианты
   (`dark:bg-gray-900`, `dark:border-gray-800`, `dark:text-gray-100`).
   Никаких «голых» `bg-white`/`text-charcoal-900`.
7. Переиспользуй макросы: `{% from "components/buttons.html" import btn_primary %}`
   (и cards.html / fields.html). Не дублируй готовое.
8. Новый код — только Tailwind-утилиты; не добавляй стили в legacy `app.css`.
9. Inline-скрипты — только с nonce `{{ script_nonce }}` (CSP).
10. Проверяй результат в браузере (скриншот + консоль) и на ширине 360px.

## Процесс
1. Прочитай `docs/DESIGN.md`.
2. Используй существующие компоненты из `templates/components/`.
3. После изменений: живая проверка страницы в браузере, включая тёмную тему и
   мобильную ширину.
4. Обнови CHANGELOG.md, если изменение заметное.
