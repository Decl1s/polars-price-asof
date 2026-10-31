"""Я проверяю реальные команды, пять опытов и воспроизводимый source-only ZIP."""
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from package_release import ROOT, package


def cli(*args, success=True):
    result=subprocess.run([sys.executable,'-m','price_asof',*map(str,args)],cwd=ROOT,capture_output=True,encoding='utf-8',timeout=30)
    if (result.returncode==0) != success:
        raise RuntimeError('Я получил неожиданный код CLI: '+result.stderr)
    return json.loads(result.stdout) if success else None


def main():
    versions={name:importlib.metadata.version(name) for name in ['polars','polars-runtime-32','tzdata']}
    if versions!={'polars':'2.1.0','polars-runtime-32':'2.1.0','tzdata':'2026.6'}:
        raise RuntimeError('Я ожидаю закреплённые runtime distributions')
    tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,encoding='utf-8',timeout=90)
    if tests.returncode or 'Ran 20 tests' not in tests.stderr:
        raise RuntimeError(tests.stderr)
    from price_asof.demo import data
    with tempfile.TemporaryDirectory(prefix='price-asof-') as tmp:
        base=Path(tmp);inputs=base/'input';out=base/'result'
        cli('generate','--out',inputs)
        def execute(target,*,age=7200,prices=None,success=True,fail=False):
            args=['run','--orders',inputs/'orders.jsonl','--prices',prices or inputs/'prices.jsonl','--out',base/target,'--max-age-seconds',age]
            if fail:args.append('--fail-before-publish')
            return cli(*args,success=success)
        baseline=execute('result')
        if baseline['counts']!=dict(orders=8,priced=5,missing_price=2,stale_price=1,amount_minor=9600):
            raise RuntimeError('Я не подтвердил контрольные числа demo')
        viewed=cli('inspect','--out',out)
        if len(viewed['preview'])!=8:raise RuntimeError('Я не показал все решения demo')
        again=execute('again')
        other=cli('inspect','--out',base/'again')
        if viewed['preview']!=other['preview'] or baseline['counts']!=again['counts']:
            raise RuntimeError('Я получил другой логический replay')
        before={p.name:p.read_bytes() for p in out.iterdir()}
        execute('result',success=False)
        if before!={p.name:p.read_bytes() for p in out.iterdir()}:raise RuntimeError('Я заменил существующий результат')
        execute('absent',success=False,fail=True)
        if (base/'absent').exists() or list(base.glob('.asof-stage-*')):raise RuntimeError('Я оставил частичный результат')
        # Я выполняю те же пять заданий, что описал в NOTES.
        if execute('age7201',age=7201)['counts']['amount_minor']!=11600:raise RuntimeError('Я не подтвердил границу возраста')
        zero=execute('age0',age=0)['counts']
        if (zero['priced'],zero['amount_minor'])!=(2,3600):raise RuntimeError('Я не подтвердил exact-only')
        _,prices=data()
        def write_prices(name,rows):
            p=base/name;p.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8');return p
        changed=[{**p,'unit_price_minor':1300} if p['price_id']=='A2' else p for p in prices]
        if execute('price1300',prices=write_prices('changed.jsonl',changed))['counts']['amount_minor']!=9900:raise RuntimeError('Я не подтвердил изменение действующей цены')
        future=[{**p,'unit_price_minor':99999} if p['price_id']=='A3' else p for p in prices]
        future_result=execute('future',prices=write_prices('future.jsonl',future))
        if future_result['counts']!=baseline['counts']:raise RuntimeError('Я допустил цену из будущего')
        ambiguous=[*prices,{**prices[0],'price_id':'DUPLICATE'}]
        execute('ambiguous',prices=write_prices('ambiguous.jsonl',ambiguous),success=False)
        if (base/'ambiguous').exists():raise RuntimeError('Я опубликовал неоднозначный join')
    archive=package()
    if package()!=archive:raise RuntimeError('Я получил разный ZIP')
    print(json.dumps({'python':sys.version.split()[0],'dependencies':versions,'tests':20,'demo':baseline['counts'],'exercises':5,'logical_replay':True,'no_partial_output':True,'archive':archive},ensure_ascii=False))


if __name__=='__main__':
    sys.path.insert(0,str(ROOT));main()
