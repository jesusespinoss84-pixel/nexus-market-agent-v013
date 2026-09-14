import argparse
from src.config.loader import load_settings
from src.agent.validator import SymbolValidator

p=argparse.ArgumentParser();p.add_argument('symbol');p.add_argument('--mode',choices=['quick','full'],default='full');args=p.parse_args()
s=load_settings();a=next((x for x in s['assets'] if x['symbol'].upper()==args.symbol.upper()),None)
if not a:raise SystemExit(f'Símbolo no configurado: {args.symbol}')
v=SymbolValidator(s)
def progress(n,total):
    if n==1 or n%100==0 or n==total:print(f'[{n}/{total}] {n/total*100:.1f}%')
r=v.validate(a,mode=args.mode,force=True,progress=progress)
print('\nVALIDACIÓN TERMINADA')
print('Símbolo:',r['symbol']);print('Score:',r.get('validation_score'));print('Robustez:',r.get('robustness_score'));print('Walk-forward:',(r.get('walk_forward') or {}).get('label'));print('Validada:',r.get('validated'))
