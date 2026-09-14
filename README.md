# Tarot Academy Bot

Простий Telegram-бот для навчального курсу з індивідуальним графіком уроків. Усі дані зберігаються в одній Google Spreadsheet, без окремої бази даних і без додаткового scheduler.

## Структура проєкту

- `app/main.py` — запуск бота і фонового worker
- `app/config.py` — змінні середовища
- `app/google_sheets.py` — робота з Google Sheets
- `app/liqpay.py` — формування LiqPay checkout-запиту
- `app/payments.py` — логіка оплат і відкриття доступу після оплати
- `app/payment_web.py` — HTTP endpoints для LiqPay checkout/callback
- `app/lessons.py` — відправка уроків і логіка завершення курсу
- `app/worker.py` — перевірка `next_lesson_at`
- `app/keyboards.py` — меню
- `app/handlers/start.py` — `/start` і допомога
- `app/handlers/course.py` — `📚 Мій курс`, `📊 Мій прогрес`
- `app/handlers/admin.py` — `/broadcast`
- `scripts/setup_google_sheets.py` — створення листків і заголовків

## `.env`

- `BOT_TOKEN`
- `ADMIN_IDS` — список Telegram ID через кому
- `SUPPORT_USERNAME` — Telegram username підтримки без `@`, для кнопки в розділі допомоги
- `MANUAL_PAYMENT_ENABLED` — `true`, якщо доступ відкривається вручну після скріншота оплати
- `MANUAL_PAYMENT_REVIEW_CHAT_ID` — ID групи, куди бот надсилає скріншоти оплат для перевірки
- `MANUAL_PAYMENT_DETAILS` — реквізити/інструкція для ручної оплати, яку бот покаже користувачу
- `GOOGLE_SPREADSHEET_ID`
- `GOOGLE_CREDENTIALS_FILE`
- `TIMEZONE`
- `LESSON_CHECK_INTERVAL`
- `LIQPAY_ENABLED` — `true`, якщо потрібно вмикати оплату перед доступом до курсу
- `LIQPAY_SANDBOX` — `true` для тестового режиму LiqPay
- `LIQPAY_PUBLIC_KEY`
- `LIQPAY_PRIVATE_KEY`
- `LIQPAY_AMOUNT`
- `LIQPAY_CURRENCY` — зазвичай `UAH`
- `LIQPAY_DESCRIPTION`
- `PUBLIC_BASE_URL` — публічний HTTPS URL сервера, наприклад `https://example.com`
- `LIQPAY_RESULT_URL` — URL повернення після оплати, якщо порожній, буде `PUBLIC_BASE_URL/payment-result`
- `PAYMENT_WEB_HOST`
- `PAYMENT_WEB_PORT`

Є шаблон: `.env.example`.

## Google Sheets

Одна таблиця містить 4 листки:

### `Lessons`

- `lesson_number`
- `title`
- `text`
- `video_file_id`
- `document_file_id`
- `delay_hours`
- `active`

Тут адміністратор керує уроками: редагує текст, назву, `file_id`, затримку і може вимикати уроки через `active=FALSE`.

### `Users`

- `telegram_id`
- `username`
- `first_name`
- `registered_at`
- `current_lesson`
- `last_lesson_sent_at`
- `next_lesson_at`
- `status`

`current_lesson` — останній успішно надісланий урок.
`next_lesson_at` — дата і час наступної відправки.
`status` — `active`, `completed`, `blocked`.

### `Statistics`

- `metric`
- `value`

Мінімум: `total_users`, `active_users`, `completed_users`, `blocked_users`. Також бот може писати `lesson_N` для кількості користувачів на конкретному уроці.

### `Payments`

- `order_id`
- `telegram_id`
- `username`
- `first_name`
- `amount`
- `currency`
- `status`
- `created_at`
- `paid_at`
- `liqpay_payment_id`
- `raw_status`

Тут бот зберігає створені оплати і статуси callback від LiqPay.

## LiqPay

Коли `LIQPAY_ENABLED=false`, бот працює без оплати: `/start` одразу реєструє користувача і надсилає перший урок.

Коли `LIQPAY_ENABLED=true`, новий користувач після `/start` отримує кнопку `Оплатити курс`. Кнопка веде на сторінку бота `/pay/{order_id}`, яка автоматично відправляє POST-form на LiqPay checkout. Якщо `LIQPAY_SANDBOX=true`, бот передає в checkout sandbox-режим для тестових ключів. Після успішної оплати LiqPay надсилає server-to-server callback на:

```text
PUBLIC_BASE_URL/liqpay/callback
```

Після підтвердження callback бот створює користувача в `Users`, відмічає платіж у `Payments` і надсилає перший урок.

Для роботи оплати сервер має бути доступний з інтернету по HTTPS, а `PUBLIC_BASE_URL` має вказувати саме на цей публічний URL.

## Ручна перевірка оплат

Якщо потрібно приймати оплату за реквізитами і вручну перевіряти скріншоти, увімкніть:

```env
MANUAL_PAYMENT_ENABLED=true
MANUAL_PAYMENT_REVIEW_CHAT_ID=-1001234567890
MANUAL_PAYMENT_DETAILS=Карта: 0000 0000 0000 0000\nОтримувач: ...
LIQPAY_ENABLED=false
```

Після `/start` новий користувач отримає опис курсу з кнопкою `Реквізити для оплати`. Після натискання кнопки бот надсилає реквізити та прохання надіслати скріншот квитанції. Коли користувач надсилає фото, бот відправляє його в групу `MANUAL_PAYMENT_REVIEW_CHAT_ID` з кнопками `Підтвердити` і `Відхилити`.

Якщо `MANUAL_PAYMENT_ENABLED=true`, ручна оплата має пріоритет над LiqPay: бот не створює LiqPay checkout і не запускає LiqPay web-сервер.

Після підтвердження бот створює користувача в `Users`, надсилає повідомлення про підтвердження оплати і відкриває перший урок. Після відхилення користувач отримує повідомлення, що оплату відхилено.

## Допомога і підтримка

У меню є кнопка `ℹ️ Допомога`, також працює команда `/help`. Вона показує коротку інструкцію по кнопках курсу, оплаті та доступу.

Кнопка `🏢 Про компанію` показує дані продавця, вид діяльності та контактний email.

Кнопка `💬 Підтримка` надсилає inline-кнопку `Зв'язатися з підтримкою`, яка відкриває Telegram-чат з username із `SUPPORT_USERNAME`.

## Як працюють Lessons

- Новий користувач після `/start` одразу отримує перший активний урок.
- Після кожної успішної відправки бот записує `current_lesson`, `last_lesson_sent_at` і `next_lesson_at`.
- Наступний урок планується через `delay_hours` наступного уроку.
- Якщо активних уроків більше немає, користувач отримує повідомлення про завершення, а статус стає `completed`.

## Як працюють Users

- Користувач шукається за `telegram_id`.
- Повторний `/start` не створює дублікати і не перезапускає курс.
- Якщо користувач блокує бота, статус змінюється на `blocked`.

## Для чого `setup_google_sheets.py`

Скрипт перевіряє наявність листків `Lessons`, `Users`, `Statistics` і додає заголовки, якщо листок порожній. Існуючі дані не видаляються.

## Як додати урок

Додайте рядок у `Lessons` і заповніть:

- номер уроку в `lesson_number`
- назву в `title`
- текст у `text`
- `video_file_id` і/або `document_file_id`, якщо вони є
- `delay_hours`, якщо потрібно значення відмінне від `24h`. Можна писати `3m`, `1h`, `2d`, `30s`; старий числовий формат теж працює, наприклад `0.05` для 3 хвилин
- `active=TRUE`, щоб урок брав участь у курсі

## `/broadcast`

Команда доступна тільки для ID з `ADMIN_IDS`.

Логіка:

1. адміністратор запускає `/broadcast`
2. бот просить текст
3. бот просить підтвердження
4. після підтвердження надсилає повідомлення користувачам
5. показує кількість успішних відправок і помилок

Якщо під час розсилки користувач уже заблокував бота, його статус змінюється на `blocked`.

## Захист контенту

Матеріали уроків надсилаються з `protect_content=True`. Це застосовується до тексту, відео і документів уроку.
