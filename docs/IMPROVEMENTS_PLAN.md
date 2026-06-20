# План реализации доработок Telemelya (SMP-169) + покрытие тестами

> **Статус: реализовано** (issue #3, ветка `feat/interactive-e2e-issue-3`, версия `0.2.0`).
> Все 6 критериев приёмки покрыты: 116 pytest + 7 BDD-сценариев e2e зелёные на живом
> стеке. Дополнительно по ходу исправлены: резолв сессии для `getFile`/`answerCallbackQuery`
> (нет chat_id) через глобальные мапы, Telegram-формат URL скачивания `/file/bot{token}/...`,
> устойчивость `responses/wait` к таймауту Redis.



Источник постановки: `fedot_gardener/doc/TELEMELYA_IMPROVEMENTS.md`.
Решения по объёму: **только план** (без изменений кода); эмуляция inline-выбора —
**оба механизма** (прямая эмуляция `sendMessage` + доставка `chosen_inline_result`);
тесты — **на живом стеке** (`docker-compose.local.yml` + `examples/echo_bot`), как
существующий сьют.

## 1. Анализ текущего состояния (gap-анализ)

| # | Проблема | Факт в коде | Разрыв |
|---|----------|-------------|--------|
| 1 | edit-методы | `editMessageText` есть и пишется в ленту (`bot_api.py:258`). | Нет `editMessageReplyMarkup`, `editMessageCaption` → aiogram бьёт в 404 → `Failed to deserialize object`. Нет хранимого сообщения; правка не применяется, в `result` нет `reply_markup`. |
| 2 | answerCallbackQuery | Пишется в ленту (`bot_api.py:244`), но только поле `raw`. | Нет полей `callback_query_id`/`text`/`show_alert` верхнего уровня; нет ассерт-хелпера. |
| 3 | inline-режим | Отсутствует полностью. | Нет моделей `InlineQuery`/`ChosenInlineResult`, нет `answerInlineQuery`, нет клиентских `send_inline_query`/`choose_inline_result`. |
| 4 | байты фото | `client.send_photo` (`client.py:78`) шлёт случайный `file_id` без байтов. | `getFile`/download у бота не отдают содержимое → vision-пайплайн не работает. |
| 5 | message_id в ленте | Есть в `result`, но в записи `get_responses()` — только у `deleteMessage`. | Нет `message_id` у `sendMessage`/`sendPhoto`/edit; нечем адресовать правки. |

Тестовый стек: интеграционные тесты на httpx → `127.0.0.1:8080` (Redis+MinIO живые),
fixtures в `telemelya/tests/conftest.py`, BDD в `telemelya/tests/features` + шаги,
живой пример `examples/echo_bot/bot.py`.

## 2. План реализации по этапам

### Этап 0 — Хранилище сообщений и детерминированный message_id (фундамент #1, #5)
- `server/state.py`: `next_message_id(session)` (Redis INCR `msgseq:{session}`) вместо
  `int(time.time()*1000)%1e6`; `store_message`/`get_message`/`update_message`
  (Redis hash `messages:{session}` → JSON по `message_id`); TTL как у `responses`.
- `server/bot_api.py`: `sendMessage`/`sendPhoto` берут `message_id` из `next_message_id`,
  сохраняют сообщение в стор и кладут `message_id` в `response_record`.
- `reset_session` чистит `messages:*` и `msgseq:*`.

### Этап 1 — Edit-методы (Проблема 1)
- Эндпоинты `editMessageReplyMarkup`, `editMessageCaption`; доработать `editMessageText`.
- Логика: найти хранимое сообщение по `message_id` → применить (text/caption/reply_markup)
  → вернуть полный `Message` в `result` → записать `method/chat_id/message_id/новое содержимое`.
- **КРИТИЧНО: `result` обязан содержать НОВЫЙ `reply_markup`.** Текущий `editMessageText`
  (`bot_api.py:274-280`) кладёт `message_id/from/chat/date/text`, но НЕ `reply_markup` —
  из-за этого aiogram/тест не видит изменённую клавиатуру. Для `editMessageReplyMarkup`
  и доработанного `editMessageText` явно добавить новый `reply_markup` в `result`
  (а для `editMessageCaption` — новый `caption`). Именно это устраняет
  `Failed to deserialize object`. Вынести как явный ассерт в `TestEditMessageReplyMarkup`.
- **Мягкий фолбэк на неизвестный `message_id` — с warning.** Если id нет в сторе:
  вернуть схема-валидный синтетический `Message` (чтобы старые сценарии с «чужими» id
  не падали) **И залогировать `logger.warning`**. Предусмотреть opt-in strict-режим
  (env-флаг, напр. `TELEMELYA_STRICT_EDIT=1`) → отдавать `ok:false` вместо синтетики.
  Иначе тест с неверным id «молча зелёный» и маскирует баг.
- `DEFAULT_BOT_INFO.supports_inline_queries = True` (нужно для #3).

### Этап 2 — answerCallbackQuery (Проблема 2)
- Поднять `callback_query_id`, `text`, `show_alert` в запись (верхний уровень).
- `client/collector.py`: `assert_callback_answered(text=None, show_alert=None)`.

### Этап 3 — Inline-режим (Проблема 3, оба механизма)
- `models.py`: `InlineQuery`, `ChosenInlineResult`, `InputTextMessageContent`,
  `InlineQueryResultArticle`; расширить `Update` (`inline_query`, `chosen_inline_result`).
- `server/bot_api.py`: `answerInlineQuery` → запись результатов
  (`id`, `title`, `input_message_content`, `reply_markup`) + сохранить набор результатов
  во временный стор `inline_results:{session}:{inline_query_id}`.
- `server/control_api.py` + `client/client.py`:
  - `send_inline_query(query, from_user)` → доставляет боту `inline_query` update.
  - `choose_inline_result(query|inline_query_id, result_id|index, *, deliver_update=False)`:
    - **Механизм A (по умолчанию):** берёт `input_message_content` записанного результата
      и постит его как `sendMessage`-запись «от имени бота» в ленту.
    - **Механизм B (`deliver_update=True`):** доставляет боту настоящий
      `chosen_inline_result` update, чтобы бот сам решил, что постить.
- **Петля замыкается на реальную кнопку.** В тесте `choose_inline_result` берёт `query`
  не хардкодом, а из `switch_inline_query` записанной кнопки бота (из `get_responses()`).
  Это доказывает полную связку «кнопка `switch_inline_query` → inline-запрос →
  `answerInlineQuery` → выбор → сообщение от бота» — ровно контракт SMP-169 «via @Федот».

### Этап 4 — Реальные байты фото (Проблема 4)
- `server/control_api.py`: `POST /api/v1/test/upload_media` (multipart) → заливает байты
  в MinIO под `session/file_id`, пушит `media_meta`, возвращает `file_id`.
- `client/client.py: send_photo`: читает файл → заливает байты → шлёт update с этим
  `file_id`. Тогда `getFile`→`file/{path}` у бота отдают реальное содержимое.
- Альтернатива без нового эндпоинта: `send_update` принимает multipart-файл — но
  отдельный `upload_media` чище и переиспользуем.

### Этап 5 — Адресация по message_id (Проблема 5)
- `models.BotResponse`: добавить `message_id`, `callback_query_id`, `show_alert`,
  `inline_query_id`, `results`.
- `client/collector.py`: property `last_message_id` — **как удобство, НЕ как основа
  ассертов.** В реальном flow бот шлёт несколько сообщений (статус + ответ + бар оценки),
  поэтому «последнее» неоднозначно. Тесты должны находить нужную запись в `get_responses()`
  (по тексту/кнопке), брать её `message_id` и слать callback/правку именно на него.
  Добавить хелпер вроде `find_response(method=..., contains=...) → message_id`.
- README + `docs/connectingTelemelya.md`: новые эндпоинты/методы/шаги.

## 3. Затрагиваемые файлы

| Файл | Этапы |
|------|-------|
| `telemelya/server/state.py` | 0, 3 |
| `telemelya/server/bot_api.py` | 0, 1, 2, 3 |
| `telemelya/server/control_api.py` | 3, 4 |
| `telemelya/server/media.py` | 4 (переиспользование) |
| `telemelya/models.py` | 0, 2, 3, 5 |
| `telemelya/client/client.py` | 3, 4, 5 |
| `telemelya/client/collector.py` | 2, 5 |
| `examples/echo_bot/bot.py` | e2e-хендлеры для #1–#4 |
| `README.md`, `docs/*` | документация |

## 4. Покрытие тестами (маппинг на критерии приёмки)

Стиль — существующие httpx-интеграционные тесты на живом стеке + BDD.

| Критерий приёмки | Тесты | Файл |
|------------------|-------|------|
| 1. edit-in-place виден, нет deserialize-ошибки | `TestEditMessageReplyMarkup` — **явный ассерт `result["reply_markup"]` == новая клавиатура** (не только что записалось); правка применена к стору; запись несёт `message_id`. `TestEditMessageCaption` (новый `caption` в `result`), доработка `TestEditMessageText` (новый `reply_markup` в `result`). `test_edit_unknown_message_id_warns` — фолбэк валиден + warning; strict-режим → `ok:false`. | `tests/test_bot_api.py` |
| 2. answerCallbackQuery / answerInlineQuery в ленте | `test_answer_callback_records_fields` (text/show_alert), `TestAnswerInlineQuery` | `test_bot_api.py`, `test_inline.py` |
| 3. send_inline_query + выбор результата | `test_send_inline_query_delivered`, `test_choose_inline_result_emulated` (механизм A), `test_choose_inline_result_delivers_update` (механизм B). **`test_switch_inline_button_roundtrip`** — `query` берётся из `switch_inline_query` кнопки бота (не хардкод): кнопка → inline → сообщение от бота. На живом echo-боте с inline-хендлером. | `test_inline.py` |
| 4. send_photo доставляет байты | `test_send_photo_uploads_real_bytes` — **round-trip через самого бота:** `getFile` отдаёт `file_path`, бот `bot.download_file(file_path)` резолвит его против file-эндпоинта Telemelya (с токеном), скачанные байты == исходным. Дополнительно — round-trip через клиентский `get_media`. | `test_media.py` (+ e2e на echo_bot) |
| 5. message_id в исходящих + адресация | `test_sendmessage_record_has_message_id`, `test_sendphoto_record_has_message_id`, `test_callback_targets_specific_record_id` — **из нескольких записей выбрать нужную по тексту/кнопке и слать callback на её `message_id`** (не на `last_message_id`). | `test_bot_api.py` |
| 6. Существующие BDD/тесты зелёные | Регресс: полный прогон `tests/` + `features/` | весь сьют |

**Негативные/граничные кейсы:**
- edit несуществующего `message_id` → мягкий фолбэк, не падает.
- `choose_inline_result` без предшествующего `answerInlineQuery` → понятная ошибка.
- `getFile` для не-залитого фото → `ok:false` (как сейчас).
- `upload_media` без файла / неверный content-type → 422.
- детерминизм `message_id`: два `sendMessage` подряд → разные возрастающие id.

**BDD-фичи (новые):**
- `edit_keyboard.feature` — тап по кнопке → правка той же inline-клавиатуры.
- `callback_toast.feature` — callback → `answer(show_alert)` виден в ленте.
- `inline.feature` — `switch_inline_query` → выбор результата → сообщение «от бота».
Новые шаги в `tests/steps/` (inline_steps.py, edit_steps.py) на русском, в стиле
существующих `messaging_steps.py`.

**Расширение `examples/echo_bot/bot.py`** (живой бот для e2e):
- inline-хендлер: `answerInlineQuery` с article + `input_message_content`;
- callback-хендлер: `edit_reply_markup` + `answer(text=..., show_alert=True)`;
- photo-хендлер: `get_file` + download → подтверждение размера/контента.

## 5. Порядок выполнения и риски
1. Этап 0 (фундамент) → 1 → 5 (дешёвые, разблокируют адресацию).
2. Этап 2 (мелкая доработка).
3. Этап 4 (байты — изолирован).
4. Этап 3 (inline — крупнейший, оба механизма) последним.

Риски:
- **Детерминизм id** в параллельных сессиях — решается INCR на session-ключе.
- **`Failed to deserialize`** воспроизводится только через живой aiogram — обязателен
  e2e на echo-боте, не только прямые эндпоинт-тесты.
- **TTL/cleanup** новых ключей (`messages:*`, `msgseq:*`, `inline_results:*`) — добавить
  в `reset_session`, иначе протечки между сценариями.
- Версия пакета: бамп `0.1.4 → 0.2.0` (новые публичные методы клиента/эндпоинты).

## 6. Definition of Done
- Все 6 критериев приёмки покрыты зелёными тестами на живом стеке.
- e2e на echo-боте подтверждает отсутствие `Failed to deserialize object`.
- README/docs обновлены под новые методы/эндпоинты/шаги.
- Существующие QA/share BDD остаются зелёными (регресс).
