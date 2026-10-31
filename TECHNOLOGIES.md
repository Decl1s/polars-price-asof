# Мой фактический стек

31.10.2026 · версия0.1.0. Я сверил текущий PyPI: стабильная Polars2.1.0.
Сигнатуру join_asof дополнительно проверил у установленного runtime, поведение — тестами.

| Компонент | Версия / фиксация | Для чего я использую и почему | Официальный источник |
| --- | --- | --- | --- |
| CPython | Рекомендую/CI3.14.10; локально3.14.4; минимум3.11 | Я создаю CLI, строгий контракт, локальные файлы и тесты | [Release](https://www.python.org/downloads/release/python-31410/), [stdlib](https://docs.python.org/3.14/library/) |
| Polars | 2.1.0, прямая dependency | Я использую DataFrame, join_asof, expressions, UTC datetime, Int64, Parquet | [PyPI](https://pypi.org/project/polars/2.1.0/), [join_asof](https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.join_asof.html) |
| tzdata | 2026.6, прямая dependency | Я предоставляю IANA базу для ZoneInfo при Polars → Python на Windows; проверяю и без системного TZPATH | [tzdata](https://pypi.org/project/tzdata/2026.6/), [zoneinfo](https://docs.python.org/3.14/library/zoneinfo.html) |
| polars-runtime-32 | 2.1.0, единственная транзитивная dependency | Я получаю готовый native runtime без установки Rust toolchain | [Runtime](https://pypi.org/project/polars-runtime-32/2.1.0/) |
| Parquet / Zstandard | Writer/reader и native compression внутри закреплённого Polars2.1.0 | Я сохраняю UTC/nullable Int64 и типизированные пустые наборы без PyArrow | [Polars Parquet](https://docs.pola.rs/user-guide/io/parquet/), [Parquet](https://parquet.apache.org/docs/) |
| Python standard library | Вместе с выбранным CPython | Я использую argparse, datetime, hashlib, importlib.metadata, json, os/pathlib, re, shutil/tempfile, subprocess/sys, unittest, random и zipfile/urllib для выпуска | [json](https://docs.python.org/3.14/library/json.html), [unittest](https://docs.python.org/3.14/library/unittest.html) |
| uv | 0.13.1 локально | Я скомпилировал полный hash lock и установил его в venv | [Compile/sync](https://docs.astral.sh/uv/pip/compile/) |
| venv / pip | venv из Python; pip нужен только для README/CI установки, его версия видна в логе | Я изолирую приложение и устанавливаю по --require-hashes; локально uv не требует pip в venv | [venv](https://docs.python.org/3.14/library/venv.html), [Hash checking](https://pip.pypa.io/en/stable/topics/secure-installs/) |
| Git | Локально2.53.0; runner управляет своей версией | Я проверяю отдельный корень и публикую явный список | [Git](https://git-scm.com/docs) |
| GitHub Actions | ubuntu-24.04 / windows-2025 | Я выполняю gate на двух ОС и зависимый release; образы не считаю immutable lock | [Actions](https://docs.github.com/en/actions) |
| actions/checkout | 7.0.1, SHA в DEPENDENCIES | Я читаю код без persist-credentials | [checkout](https://github.com/actions/checkout) |
| actions/setup-python | 7.1.0, SHA в DEPENDENCIES | Я закрепляю Python3.14.10 в CI | [setup-python](https://github.com/actions/setup-python) |
| JSONL / Markdown / ZIP STORE / SHA-256 | Контракт и manifest1, source archive0.1.0 | Я храню входы, русский разбор и повторяемую source-поставку | [JSON](https://www.rfc-editor.org/rfc/rfc8259), [zipfile](https://docs.python.org/3.14/library/zipfile.html) |
| VS Code tasks | Схема2.0.0, необязательно | Я даю четыре запуска без обязательных расширений | [Tasks](https://code.visualstudio.com/docs/debugtest/tasks) |

Полное runtime-дерево содержит ровно3 distributions. Я перечислил их в
DEPENDENCIES.json и закрепил версии/доступные platform hashes в requirements.lock.
Дополнительные extras, pandas, numpy и PyArrow я не устанавливал. Наличие macOS
wheel в lock не означает проверку macOS. Native зависимости writer/compression
входят в готовый runtime wheel, который я фиксирую хешем; отдельно их не собираю.
Полную бинарную среду runner, ОС и pip я не выдаю за независимо закреплённую сборку.
