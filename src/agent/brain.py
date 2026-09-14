def clamp(x): return round(max(0,min(100,x)),1)
def market_context_score(asset_market,benchmarks):
    name='IPC México' if asset_market=='MEX' else 'S&P 500'
    b=next((x for x in benchmarks if x['name']==name),None)
    if not b:return 50.0
    r1m=b.get('ret_1m') or 0; r3=b.get('ret_3m') or 0; ytd=b.get('ret_ytd') or 0
    return clamp(50+0.6*r1m+0.25*r3+0.15*ytd)
def validation_score(validated,strategy=None,dynamic_score=None):
    if dynamic_score is not None:return clamp(dynamic_score)
    if not validated:return 0.0
    if not strategy:return 70.0
    rb=float(strategy.get('robustness_score',0));pf=float(strategy.get('profit_factor',1));exp=float(strategy.get('expectancy_r',0))
    return clamp(0.55*rb+min(pf,3)/3*25+min(max(exp,0),0.5)/0.5*20)
def composite(technical,viability,vulnerability,market_context,validation):
    if validation>0: raw=.28*technical+.23*viability+.17*(100-vulnerability)+.12*market_context+.20*validation
    else: raw=min(.35*technical+.28*viability+.22*(100-vulnerability)+.15*market_context,79)
    return clamp(raw)
def explanation(x):
    r=[]
    r.append('fuerza técnica alta' if x['score']>=70 else 'fuerza técnica intermedia' if x['score']>=55 else 'fuerza técnica baja')
    if x['viability_score']>=60:r.append('histórico favorable')
    elif x['viability_score']<35:r.append('histórico débil')
    if x['vulnerability_score']>=70:r.append('riesgo histórico elevado')
    elif x['vulnerability_score']<=45:r.append('riesgo histórico moderado')
    if x['market_context_score']>=60:r.append('contexto favorable')
    elif x['market_context_score']<40:r.append('contexto débil')
    if x.get('validated_match'):r.append('setup actual coincide con su estrategia validada')
    elif x.get('validation_score',0)>0:r.append('activo con validación histórica propia, pero el setup actual no coincide')
    else:r.append('sin validación histórica propia todavía')
    return '; '.join(r).capitalize()+'.'
