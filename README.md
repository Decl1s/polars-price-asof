# Моя лаборатория исторических цен на Polars

[![Я проверяю проект](https://github.com/Decl1s/polars-price-asof/actions/workflows/check.yml/badge.svg)](https://github.com/Decl1s/polars-price-asof/actions/workflows/check.yml)

Я подбираю каждому заказу последнюю цену того же SKU, действовавшую **на время
заказа**. Через backward `join_asof` я исключаю будущие цены, отдельно отмечаю
устаревшую цену и отсутствие истории. Я сохраняю объяснимое решение для каждой
строки, два поднабора Parquet и согласованную сводку. Это учебный проект на
синтетических данных для демонстрации за 5–10 минут.

[Карта кода](START_HERE.md) · [Подробный конспект и 5 заданий](NOTES.md) ·
[Мои решения](CONCEPT.md) · [Стек](TECHNOLOGIES.md) · [Фактические проверки](VALIDATION.md)

## Как я запускаю

Я рекомендую Python3.14.10; минимально нужен3.11. Локально я проверил3.14.4,
а в CI закрепил3.14.10. Polars2.1.0 и единственный транзитивный runtime2.1.0
закреплены с хешами. Я устанавливаю их в venv, без глобальных компонентов.

```text
python -m venv .venv
```

На Linux я активирую окружение через `source .venv/bin/activate`. В PowerShell
я вызываю `.venv\Scripts\python.exe` вместо `python` ниже; execution policy менять
не нужно. Затем выполняю:

```text
python -m pip install --require-hashes -r requirements.lock
python -m price_asof generate --out artifacts/input
python -m price_asof run --orders artifacts/input/orders.jsonl --prices artifacts/input/prices.jsonl --out artifacts/result
python -m price_asof inspect --out artifacts/result
```

Я ожидаю8 заказов и7 цен: **5 priced, 2 missing_price, 1 stale_price**,
сумму принятых строк **9600 копеек**. Inspect показывает первые20 решений;
в demo я вижу все8.

| Заказ | Найденная цена | Возраст, секунды | Мой исход | Сумма, копейки |
| --- | --- | ---: | --- | ---: |
| O001 | A1 | 3540 | priced | 2000 |
| O002 | A2 | 0 | priced | 3600 |
| O003 | B1 | 2700 | priced | 2000 |
| O004 | C1 | 7200 | priced | 2000 |
| O005 | C1 | 7201 | stale_price | null |
| O006 | null | null | missing_price | null |
| O007 | null | null | missing_price | null |
| O008 | E1 | 0 | priced | 0 |

Я принимаю цену на точной границе её вступления в силу и на границе возраста7200.
Для O006 существует только будущая цена, поэтому я её не подставляю. Нулевая E1
валидна: я проверяю наличие price_id, а не ненулевую сумму.

## Что я получаю в каталоге результата

- В `decisions.parquet` я сохраняю каждый заказ, price_id/price_at, возраст, статус и сумму.
- В `priced.parquet` я оставляю только priced, в `rejected.parquet` — missing/stale.
- В `summary.json` я фиксирую counts, лимит возраста, версию Polars, SHA256 входов
  и трёх Parquet. Локальные пути в manifest я не записываю.

Я читаю и проверяю три Parquet перед публикацией каталога. Inspect сверяет состав,
хеши и согласованность поднаборов/сводки. Хеши помогают обнаружить случайное
повреждение, но не аутентифицируют автора файла.

## Мои входные контракты

Заказ:

```json
{"order_id":"O001","sku":"P0001","order_at":"2026-10-31T09:59:00Z","quantity":2}
```

Цена:

```json
{"price_id":"A1","sku":"P0001","price_at":"2026-10-31T09:00:00Z","unit_price_minor":1000}
```

Я требую ровно четыре поля каждого типа. ID — 1–40 латинских букв, цифр, `_`, `-`;
SKU — `P` и четыре цифры. Время — существующая дата2020–2099, UTC до секунды с `Z`,
без смещения и долей. Quantity — целое1–1000, цена — целое0–100000000 копеек одной
условной валюты. Bool, null, дроби, повторные JSON-ключи и лишние поля я отклоняю.

Order_id и price_id уникальны. Пара `(sku, price_at)` тоже уникальна: даже две
одинаковые по сумме цены в один момент я не выбираю случайно. Неправильный вход
останавливает весь пакет. Отсутствующая/старая история — другой случай: сам заказ
валиден, поэтому я сохраняю решение с причиной. Я допускаю пустые файлы; Parquet
с нулём строк сохраняет явную типизированную схему.

## Как я меняю политику и проверяю результат

```text
python -m price_asof run --orders artifacts/input/orders.jsonl --prices artifacts/input/prices.jsonl --out artifacts/age7201 --max-age-seconds 7201
python -m price_asof run --orders artifacts/input/orders.jsonl --prices artifacts/input/prices.jsonl --out artifacts/exact --max-age-seconds 0
python -m unittest discover -s tests -v
python scripts/ci.py
```

Для age7201 я ожидаю6 priced и11600; для0 —2 priced и3600. Каждый опыт получает
новое имя выхода. Существующий каталог я сохраняю. Повтор исходного входа даёт те
же логические строки и суммы; побайтовое равенство Parquet между платформами я
не обещаю. Для fail/retry я запускаю run с новым выходом и `--fail-before-publish`:
команда возвращает1, окончательного каталога нет, повтор без флага проходит.

CLI возвращает0 при успехе,1 при ошибке данных/файлов и2 при неверных аргументах.
Один файл ограничен16 MiB/50000 строк, строка —8 KiB. `--max-age-seconds` принимает
целые0–604800. Я сортирую DataFrames в памяти; потоковую обработку больших данных
здесь не заявляю.

Для полного gate и упаковки я работаю из Git clone: проверяю Git root и совпадение
tracked файлов с `PUBLIC_FILES.txt`. Сам CLI работает и из распакованного source ZIP.
Архив я собираю командой `python scripts/package_release.py`; в `dist/` получаю
source ZIP и SHA256SUMS. CI Linux/Windows запускает gate, затем отдельный release job.

## Мои ограничения

Я моделирую effective time цены. Я **не доказываю**, что запись уже была известна
системе в момент заказа: published_at/ingested_at в этой модели нет. Для такой
задачи нужна дополнительная временная ось. Я не делаю оплату, скидки, возвраты,
валютный курс, инкрементальный state и промышленную нагрузку. Публикация каталога
не является проверкой power loss или защиты от враждебной гонки файловой системы.
Все данные синтетические; сервисов и платных облаков нет.

[Каталог моих учебных проектов](https://github.com/Decl1s/Decl1s/blob/main/PROJECTS.md)
