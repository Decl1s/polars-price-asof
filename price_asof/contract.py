"""Я проверяю контракт и ключи до вычислений, не скрывая ошибки за cast."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import polars as pl


class ContractError(ValueError):
    """Я отклоняю неоднозначный пакет целиком."""


ORDER_SCHEMA = {"order_id": pl.String, "sku": pl.String, "order_at": pl.Datetime("us", "UTC"), "quantity": pl.Int64}
PRICE_SCHEMA = {"price_id": pl.String, "sku": pl.String, "price_at": pl.Datetime("us", "UTC"), "unit_price_minor": pl.Int64}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("Я обнаружил повтор JSON-ключа")
        result[key] = value
    return result


def load(path, kind):
    if kind not in ("orders", "prices"):
        raise ContractError("Я ожидаю orders или prices")
    schema = ORDER_SCHEMA if kind == "orders" else PRICE_SCHEMA
    id_field = "order_id" if kind == "orders" else "price_id"
    time_field = "order_at" if kind == "orders" else "price_at"
    number = "quantity" if kind == "orders" else "unit_price_minor"
    low, high = (1, 1000) if kind == "orders" else (0, 100000000)
    rows, identifiers, price_keys = [], set(), set()
    digest = hashlib.sha256()
    byte_count = 0
    with Path(path).open("rb") as source:
        while raw := source.readline(8193):
            byte_count += len(raw)
            if len(raw) > 8192 or byte_count > 16 * 1024 * 1024 or len(rows) >= 50000:
                raise ContractError("Я ограничил строку 8 KiB, файл 16 MiB и 50000 строками")
            digest.update(raw)
            try:
                value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
                if not isinstance(value, dict) or set(value) != set(schema):
                    raise ValueError("fields")
                if not isinstance(value[id_field], str) or re.fullmatch(r"[A-Za-z0-9_-]{1,40}", value[id_field]) is None:
                    raise ValueError("id")
                if not isinstance(value["sku"], str) or re.fullmatch(r"P[0-9]{4}", value["sku"]) is None:
                    raise ValueError("sku")
                if type(value[number]) is not int or not low <= value[number] <= high:
                    raise ValueError("number")
                timestamp = value[time_field]
                if not isinstance(timestamp, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", timestamp) is None:
                    raise ValueError("timestamp")
                parsed = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if not 2020 <= parsed.year <= 2099:
                    raise ValueError("year")
                value[time_field] = parsed
            except (ValueError, UnicodeError, RecursionError, TypeError) as error:
                raise ContractError(f"Я отклонил строку {len(rows)+1} в {kind}: нарушен контракт") from error
            if value[id_field] in identifiers:
                raise ContractError(f"Я обнаружил повтор {id_field}")
            identifiers.add(value[id_field])
            if kind == "prices":
                key = (value["sku"], parsed)
                if key in price_keys:
                    raise ContractError("Я не выбираю случайную цену: пара (sku, price_at) должна быть уникальна")
                price_keys.add(key)
            rows.append(value)
    # Я задаю типы явно даже для пустого файла, чтобы NULL не превратил join key в Null dtype.
    return pl.DataFrame(rows, schema=schema, strict=True), digest.hexdigest()
