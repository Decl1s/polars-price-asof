"""Я оставляю три команды без сервера: generate, run, inspect."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import polars as pl
from .contract import ContractError
from .demo import generate
from .pipeline import PipelineError, inspect, run


def json_value(value):
    if isinstance(value,datetime):
        return value.isoformat().replace("+00:00","Z")
    raise TypeError("Я не знаю тип JSON")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Я подбираю историческую цену заказа через Polars as-of")
    commands = parser.add_subparsers(dest="command",required=True)
    g = commands.add_parser("generate"); g.add_argument("--out",type=Path,required=True)
    r = commands.add_parser("run")
    r.add_argument("--orders",type=Path,required=True);r.add_argument("--prices",type=Path,required=True)
    r.add_argument("--out",type=Path,required=True)
    r.add_argument("--max-age-seconds",type=int,default=7200)
    r.add_argument("--fail-before-publish",action="store_true",help="Я вызываю учебный отказ до rename")
    i = commands.add_parser("inspect");i.add_argument("--out",type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            generate(args.out);result={"orders":8,"prices":7}
        elif args.command == "run":
            result=run(args.orders,args.prices,args.out,max_age_seconds=args.max_age_seconds,fail_before_publish=args.fail_before_publish)
        else:
            summary,frame=inspect(args.out)
            result={"summary":summary,"preview":frame.head(20).to_dicts()}
        print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,default=json_value))
        return 0
    except (ContractError,PipelineError) as error:
        print(str(error),file=sys.stderr);return 1
    except (OSError,pl.exceptions.PolarsError):
        print("Я не выполнил операцию: проверь файлы, доступ и типы данных",file=sys.stderr);return 1


if __name__ == "__main__":
    raise SystemExit(main())
