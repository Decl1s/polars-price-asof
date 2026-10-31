"""Я проверяю бизнес-правила и независимый простой oracle вместо копирования asof-кода."""
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
import polars as pl
from price_asof.contract import ContractError, load
from price_asof.demo import data, generate, order, price
from price_asof.pipeline import PipelineError, calculate, inspect, run


class AsOfTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.input=self.root/'input';generate(self.input)
        self.orders=self.input/'orders.jsonl';self.prices=self.input/'prices.jsonl'

    def tearDown(self):self.temp.cleanup()

    def write(self,name,rows):
        path=self.root/name;path.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8');return path

    def compute(self,orders=None,prices=None,age=7200):
        o,_=load(orders or self.orders,'orders');p,_=load(prices or self.prices,'prices')
        return calculate(o,p,age)

    def test_demo_counts_and_total(self):
        summary=run(self.orders,self.prices,self.root/'result')
        self.assertEqual(summary['counts'],dict(orders=8,priced=5,missing_price=2,stale_price=1,amount_minor=9600))
        _,df=inspect(self.root/'result');self.assertEqual(df.height,8)
        self.assertEqual(df.filter(pl.col('status')=='priced')['order_id'].to_list(),['O001','O002','O003','O004','O008'])

    def test_exact_timestamp_uses_new_price(self):
        row=self.compute().filter(pl.col('order_id')=='O002').row(0,named=True)
        self.assertEqual((row['price_id'],row['unit_price_minor'],row['age_seconds']),("A2",1200,0))

    def test_age_boundary_and_one_second_late(self):
        df=self.compute();rows={r['order_id']:r for r in df.to_dicts()}
        self.assertEqual((rows['O004']['status'],rows['O004']['age_seconds']),('priced',7200))
        self.assertEqual((rows['O005']['status'],rows['O005']['age_seconds']),('stale_price',7201))
        self.assertIsNone(rows['O005']['amount_minor'])

    def test_future_and_unknown_sku_are_missing(self):
        df=self.compute();rejected=df.filter(pl.col('status')=='missing_price')
        self.assertEqual(rejected['order_id'].to_list(),['O006','O007'])
        self.assertEqual(rejected['price_id'].null_count(),2)

    def test_before_first_price_has_no_future_match(self):
        orders=self.write('early.jsonl',[order('EARLY','P0001','08:59:59',1)])
        row=self.compute(orders=orders).row(0,named=True)
        self.assertEqual(row['status'],'missing_price');self.assertIsNone(row['price_id'])

    def test_zero_price_is_valid(self):
        row=self.compute().filter(pl.col('order_id')=='O008').row(0,named=True)
        self.assertEqual((row['status'],row['amount_minor'],row['price_id']),('priced',0,'E1'))

    def test_no_cross_sku_match(self):
        orders=self.write('sku.jsonl',[order('OTHER','P9999','12:00:00',1)])
        self.assertEqual(self.compute(orders=orders)['price_id'].null_count(),1)

    def test_unsorted_input_and_oracle(self):
        rng=random.Random(42);orders,prices=data();rng.shuffle(orders);rng.shuffle(prices)
        actual=self.compute(self.write('o.jsonl',orders),self.write('p.jsonl',prices)).to_dicts()
        expected={}
        # Я использую прямой поиск по маленькому списку; Polars join здесь не вызываю.
        from datetime import datetime
        for o in orders:
            candidates=[p for p in prices if p['sku']==o['sku'] and p['price_at']<=o['order_at']]
            match=max(candidates,key=lambda p:p['price_at']) if candidates else None
            age=int((datetime.fromisoformat(o['order_at'])-datetime.fromisoformat(match['price_at'])).total_seconds()) if match else None
            status='missing_price' if match is None else ('stale_price' if age>7200 else 'priced')
            expected[o['order_id']]=(match['price_id'] if match else None,status,match['unit_price_minor']*o['quantity'] if status=='priced' else None)
        for row in actual:self.assertEqual((row['price_id'],row['status'],row['amount_minor']),expected[row['order_id']])

    def test_duplicate_order_and_price_ids(self):
        orders,prices=data()
        for rows,kind in [(orders+[orders[0]],'orders'),(prices+[prices[0]],'prices')]:
            with self.subTest(kind=kind):
                with self.assertRaises(ContractError):load(self.write(kind+'.jsonl',rows),kind)

    def test_ambiguous_price_key_is_fatal(self):
        _,prices=data();prices.append({**prices[0],'price_id':'OTHER','unit_price_minor':99})
        out=self.root/'absent'
        with self.assertRaises(ContractError):run(self.orders,self.write('ambiguous.jsonl',prices),out)
        self.assertFalse(out.exists())

    def test_empty_typed_inputs(self):
        empty=self.write('empty.jsonl',[])
        for orders,prices,n in [(empty,self.prices,0),(self.orders,empty,8),(empty,empty,0)]:
            with self.subTest(n=n):
                df=self.compute(orders,prices)
                self.assertEqual(df.height,n);self.assertEqual(df.schema['amount_minor'],pl.Int64)
                self.assertEqual(df.schema['price_at'],pl.Datetime('us','UTC'))
                if n:self.assertEqual(df['status'].to_list(),['missing_price']*8)
        run(empty,empty,self.root/'empty-result');summary,df=inspect(self.root/'empty-result')
        self.assertEqual(summary['counts']['amount_minor'],0);self.assertTrue(df.is_empty())

    def test_invalid_contract_table(self):
        orders,_=data();valid=orders[0]
        cases=['[]','null','{}',json.dumps(valid)+' {}',json.dumps({**valid,'extra':1}),json.dumps(valid).replace('"quantity": 2','"quantity":2,"quantity":3')]
        for field,value in [('quantity',True),('quantity',0),('quantity',1.5),('quantity',1001),('order_at','2026-02-30T10:00:00Z'),('order_at','2026-10-31T10:00:00+00:00'),('order_at','2026-10-31T10:00:00.5Z'),('sku','BAD'),('order_id',None)]:
            cases.append(json.dumps({**valid,field:value}))
        cases.append('{"quantity":'+('9'*5000)+'}')
        for raw in cases:
            path=self.root/'bad';path.write_text(raw+'\n')
            with self.subTest(raw=raw[:50]):
                with self.assertRaises(ContractError):load(path,'orders')

    def test_input_resource_limits(self):
        path=self.root/'big';path.write_bytes(b'x'*8193)
        with self.assertRaises(ContractError):load(path,'orders')
        path.write_bytes(b'\xff\n')
        with self.assertRaises(ContractError):load(path,'orders')

    def test_invalid_max_age(self):
        for value in [-1,604801,True,1.5]:
            with self.subTest(value=value):
                with self.assertRaises(ContractError):self.compute(age=value)

    def test_failure_before_publish_leaves_no_result(self):
        with self.assertRaises(PipelineError):run(self.orders,self.prices,self.root/'absent',fail_before_publish=True)
        self.assertFalse((self.root/'absent').exists())
        self.assertEqual(list(self.root.glob('.asof-stage-*')),[])
        self.assertEqual(run(self.orders,self.prices,self.root/'absent')['counts']['amount_minor'],9600)

    def test_existing_output_is_unchanged(self):
        output=self.root/'result';run(self.orders,self.prices,output)
        before={p.name:p.read_bytes() for p in output.iterdir()}
        with self.assertRaises(PipelineError):run(self.orders,self.prices,output)
        self.assertEqual({p.name:p.read_bytes() for p in output.iterdir()},before)

    def test_parquet_roundtrip_and_logical_replay(self):
        run(self.orders,self.prices,self.root/'a');run(self.orders,self.prices,self.root/'b')
        summary,a=inspect(self.root/'a');other,b=inspect(self.root/'b')
        self.assertTrue(a.equals(b));self.assertEqual(summary['counts'],other['counts'])
        self.assertEqual(summary['inputs'],other['inputs'])
        self.assertEqual(a.schema,self.compute().schema)

    def test_corruption_is_detected(self):
        output=self.root/'result';run(self.orders,self.prices,output)
        with (output/'priced.parquet').open('ab') as f:f.write(b'changed')
        with self.assertRaises(PipelineError):inspect(output)

    def test_python_datetime_without_system_tz_database(self):
        # Я воспроизвожу отсутствие системной IANA базы, типичное для Windows.
        code = "from datetime import datetime,timezone; import polars as pl; f=pl.DataFrame({'at':[datetime(2026,10,31,tzinfo=timezone.utc)]},schema={'at':pl.Datetime('us','UTC')}); assert f.to_dicts()[0]['at'].isoformat()=='2026-10-31T00:00:00+00:00'"
        result=subprocess.run([sys.executable,'-c',code],env={**os.environ,'PYTHONTZPATH':''},capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_cli_generate_run_inspect(self):
        def cli(*args,success=True):
            result=subprocess.run([sys.executable,'-m','price_asof',*map(str,args)],capture_output=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode==0,success,result.stderr)
            return json.loads(result.stdout) if success else None
        output=self.root/'cli'
        cli('run','--orders',self.orders,'--prices',self.prices,'--out',output)
        got=cli('inspect','--out',output)
        self.assertEqual(got['summary']['counts']['amount_minor'],9600);self.assertEqual(len(got['preview']),8)
        cli('run','--orders',self.orders,'--prices',self.prices,'--out',output,success=False)
        cli('generate','--out',self.input,success=False)


if __name__=='__main__':unittest.main()
