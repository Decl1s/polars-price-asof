"""Я генерирую фиксированный пример: границы времени, старая, будущая и нулевая цена."""
import json
from pathlib import Path


def price(identifier, sku, moment, amount):
    return {"price_id": identifier, "sku": sku, "price_at": f"2026-10-31T{moment}Z", "unit_price_minor": amount}


def order(identifier, sku, moment, quantity):
    return {"order_id": identifier, "sku": sku, "order_at": f"2026-10-31T{moment}Z", "quantity": quantity}


def data():
    prices = [price("A1","P0001","09:00:00",1000),price("A2","P0001","10:00:00",1200),
              price("A3","P0001","12:00:00",1500),price("B1","P0002","09:30:00",500),
              price("C1","P0003","08:00:00",2000),price("D1","P0004","10:30:00",700),
              price("E1","P0005","10:00:00",0)]
    orders = [order("O001","P0001","09:59:00",2),order("O002","P0001","10:00:00",3),
              order("O003","P0002","10:15:00",4),order("O004","P0003","10:00:00",1),
              order("O005","P0003","10:00:01",1),order("O006","P0004","10:00:00",1),
              order("O007","P9999","10:00:00",1),order("O008","P0005","10:00:00",5)]
    return orders, prices


def generate(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    orders, prices = data()
    for name, rows in [("orders.jsonl",orders),("prices.jsonl",prices)]:
        (root/name).write_text("".join(json.dumps(row,sort_keys=True)+"\n" for row in rows),encoding="utf-8",newline="\n")
