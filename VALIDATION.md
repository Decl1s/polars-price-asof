# Что я проверил

31.10.2026 · Polars Price AsOf0.1.0.

Я прошёл20 unittest на Linux x86_64, Python3.14.4, Polars2.1.0 и runtime-32 2.1.0 и tzdata2026.6
в отдельном venv. Я установил полное дерево с --require-hashes и сверил фактическую
сигнатуру join_asof. Первый локальный запуск прошёл. Первый Windows CI выявил
ZoneInfoNotFoundError UTC при преобразовании Polars → Python: системной IANA базы
не было. Я добавил tzdata2026.6 и отдельную проверку с PYTHONTZPATH=""; формулу
расчёта сохранил. Повторный CI подтверждаю отдельным результатом, первый failure
не скрываю.

Я проверил8/7 demo,5 priced/2 missing/1 stale и9600 копеек; точное время смены
цены; возраст7200/7201; будущее и неизвестный SKU; ранний заказ до первой версии;
цену0; запрет cross-SKU; перемешанный вход против независимого простого oracle.
Я проверил уникальные ID/price keys, неправильные типы, resource limits, UTC,
пустые typed inputs, Parquet roundtrip, логический replay, сохранность занятого
выхода, cleanup staging при отказе и обнаружение повреждённого Parquet.

Я прошёл полный gate `python scripts/ci.py`: он дополнительно вызвал CLI отдельными процессами,
выполняет пять заданий (11600/3600/9900, неизменность от будущей цены, отказ при
ambiguous key), проверил новый выход и два одинаковых source ZIP. Все этапы прошли.
Финальный checksum исходников я записываю в локальном журнале серии.

Я подготовил workflow Linux/Windows на Python3.14.10 с hash install и pip check.
Фактические результаты [CI](https://github.com/Decl1s/polars-price-asof/actions)
и release job я не подменяю локальным успехом. Я отдельно сверяю публичность,
remote tree/blob SHA, tag, скачанный source ZIP и вклад в календаре профиля.

Я не проверял macOS, большие объёмы, cold-cache timings, published_at/bitemporal
semantics, отключение питания, враждебные filesystem races и GUI IDE. Я проверяю
логическое равенство Parquet, а byte-reproducibility обещаю только source ZIP.
Реальных входов, окружения и контактов в исходном архиве нет.
