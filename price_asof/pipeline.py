"""Я выбираю последнюю действовавшую цену, затем отдельно проверяю её возраст."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import polars as pl
from .contract import ContractError, load


class PipelineError(ValueError):
    """Я не публикую неполный или несогласованный расчёт."""


FILES = ("decisions.parquet", "priced.parquet", "rejected.parquet")


def calculate(orders, prices, max_age_seconds=7200):
    if type(max_age_seconds) is not int or not 0 <= max_age_seconds <= 604800:
        raise ContractError("Я ожидаю max-age-seconds от 0 до 604800")
    # Я реально сортирую обе таблицы по времени: это также сортирует время внутри SKU.
    # При by engine не доказывает sortedness; я не подменяю сортировку метаданными set_sorted.
    joined = orders.sort(["order_at", "order_id"]).join_asof(
        prices.sort(["price_at", "price_id"]), left_on="order_at", right_on="price_at",
        by="sku", strategy="backward", allow_exact_matches=True, coalesce=False,
        check_sortedness=False,
    )
    joined = joined.with_columns(((pl.col("order_at") - pl.col("price_at")).dt.total_microseconds() // 1000000).alias("age_seconds"))
    if joined.filter(pl.col("age_seconds") < 0).height:
        raise PipelineError("Я обнаружил цену из будущего")
    # Я не использую tolerance самого join: иначе потерял бы различие missing и stale.
    joined = joined.with_columns(
        pl.when(pl.col("price_id").is_null()).then(pl.lit("missing_price"))
        .when(pl.col("age_seconds") > max_age_seconds).then(pl.lit("stale_price"))
        .otherwise(pl.lit("priced")).alias("status")
    )
    return joined.with_columns(
        pl.when(pl.col("status") == "priced")
        .then(pl.col("quantity") * pl.col("unit_price_minor"))
        .otherwise(pl.lit(None, dtype=pl.Int64)).alias("amount_minor")
    ).sort("order_id")


def summary_for(decisions):
    priced = decisions.filter(pl.col("status") == "priced")
    return {"orders": decisions.height, "priced": priced.height,
            "missing_price": decisions.filter(pl.col("status") == "missing_price").height,
            "stale_price": decisions.filter(pl.col("status") == "stale_price").height,
            "amount_minor": int(priced["amount_minor"].sum())}


def run(orders_path, prices_path, out, *, max_age_seconds=7200, fail_before_publish=False):
    orders, order_hash = load(orders_path, "orders")
    prices, price_hash = load(prices_path, "prices")
    decisions = calculate(orders, prices, max_age_seconds)
    summary = {"schema_version": 1, "polars": pl.__version__, "max_age_seconds": max_age_seconds,
               "inputs": {"orders_sha256": order_hash, "prices_sha256": price_hash},
               "counts": summary_for(decisions)}
    target = Path(out)
    if target.exists() or target.is_symlink():
        raise PipelineError("Я ожидаю новое имя выходного каталога")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".asof-stage-", dir=target.parent))
    try:
        frames = [decisions, decisions.filter(pl.col("status") == "priced"), decisions.filter(pl.col("status") != "priced")]
        for name, frame in zip(FILES, frames, strict=True):
            frame.write_parquet(stage/name, compression="zstd", statistics=True)
        summary["files"] = {name: hashlib.sha256((stage/name).read_bytes()).hexdigest() for name in FILES}
        (stage/"summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2)+"\n",encoding="utf-8",newline="\n")
        inspect(stage)  # Я перечитываю Parquet до того, как каталог станет доступен по конечному имени.
        if fail_before_publish:
            raise PipelineError("Я вызвал учебный отказ до публикации")
        if target.exists() or target.is_symlink():
            raise PipelineError("Я обнаружил занятый выходной путь")
        os.rename(stage, target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return summary


def inspect(directory):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise PipelineError("Я ожидаю каталог результата")
    if {x.name for x in root.iterdir()} != {*FILES, "summary.json"}:
        raise PipelineError("Я не подтвердил состав выходного каталога")
    try:
        for name in [*FILES, "summary.json"]:
            if (root/name).is_symlink():
                raise PipelineError("Я не читаю symlink результата")
        summary = json.loads((root/"summary.json").read_text(encoding="utf-8"))
        if summary["schema_version"] != 1 or set(summary["files"]) != set(FILES):
            raise PipelineError("Я не знаю схему результата")
        for name in FILES:
            if hashlib.sha256((root/name).read_bytes()).hexdigest() != summary["files"][name]:
                raise PipelineError("Я обнаружил повреждение Parquet")
        decisions, priced, rejected = [pl.read_parquet(root/name) for name in FILES]
        if not priced.equals(decisions.filter(pl.col("status") == "priced")) or not rejected.equals(decisions.filter(pl.col("status") != "priced")):
            raise PipelineError("Я обнаружил несогласованные группы")
        if summary_for(decisions) != summary["counts"]:
            raise PipelineError("Я обнаружил несогласованную сводку")
        if decisions.height != priced.height + rejected.height:
            raise PipelineError("Я потерял строки при разделении")
        return summary, decisions
    except (KeyError, TypeError, json.JSONDecodeError, pl.exceptions.PolarsError) as error:
        raise PipelineError("Я не прочитал согласованный пакет результата") from error
