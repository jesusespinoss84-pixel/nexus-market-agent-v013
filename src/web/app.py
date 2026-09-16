from flask import Flask,jsonify,render_template,request
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone, timedelta
import json,atexit,math,threading,os,urllib.request,urllib.parse
from src.config.loader import load_settings,project_root
from src.agent.engine import NexusAgent
from src.agent.portfolio import PaperPortfolio
from src.agent.autonomy import AutonomousPaperAgent
from src.agent.learning import PaperLearningAgent
from src.agent.risk_governor import RiskGovernor
from src.agent.validator import SymbolValidator
from src.data.yfinance_provider import YFinanceProvider

scheduler=None
_job_lock=threading.Lock()

def readj(p,d):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except:return d

def create_app():
    global scheduler
    app=Flask(__name__,template_folder='templates',static_folder='static')
    s=load_settings();root=project_root()
    agent=NexusAgent()
    provider=YFinanceProvider(s,root)
    validator=SymbolValidator(s,provider)
    portfolio=PaperPortfolio(s)
    autonomy=AutonomousPaperAgent(s)
    learner=PaperLearningAgent(s)
    riskgov=RiskGovernor(s)

    def send_telegram(text):
        token=os.getenv('NEXUS_TELEGRAM_BOT_TOKEN','').strip()
        chat=os.getenv('NEXUS_TELEGRAM_CHAT_ID','').strip()
        if not token or not chat:return {'ok':False,'configured':False,'error':'TELEGRAM_NOT_CONFIGURED'}
        try:
            data=urllib.parse.urlencode({'chat_id':chat,'text':text}).encode()
            req=urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage',data=data,method='POST')
            with urllib.request.urlopen(req,timeout=12) as r:
                return {'ok':200<=r.status<300,'configured':True,'status':r.status}
        except Exception as e:return {'ok':False,'configured':True,'error':str(e)}

    def write_runtime(**kw):
        p=root/s['storage'].get('runtime','storage/runtime.json')
        old=readj(p,{})
        old.update(kw)
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(old,indent=2,ensure_ascii=False),encoding='utf-8')

    def scan_job():
        if not _job_lock.acquire(blocking=False):return
        try:
            write_runtime(scan_running=True,last_scan_started_utc=datetime.now(timezone.utc).isoformat())
            before=len(autonomy.alerts(1000))
            st,_=agent.scan_once()
            fresh=autonomy.alerts(1000)[before:]
            if s.get('alerts',{}).get('telegram_enabled',False):
                for a in fresh[-10:]: send_telegram(f"NEXUS {a.get('title')} · {a.get('body')}")
            write_runtime(scan_running=False,last_scan_finished_utc=datetime.now(timezone.utc).isoformat(),last_scan_ok=True,last_scan_error=None,last_alerts_generated=len(fresh))
            return st
        except Exception as e:
            print('AGENT ERROR',e,flush=True)
            write_runtime(scan_running=False,last_scan_finished_utc=datetime.now(timezone.utc).isoformat(),last_scan_ok=False,last_scan_error=str(e))
        finally:_job_lock.release()

    def live_job():
        if not s.get('paper_portfolio',{}).get('live_enabled',True):return
        # Do not interrupt a full scanner job.
        if not _job_lock.acquire(blocking=False):return
        try:
            fx=provider.get_usdmxn()
            portfolio.live_update(provider,s['assets'],fx)
            write_runtime(last_live_update_utc=datetime.now(timezone.utc).isoformat(),last_live_ok=True,last_live_error=None)
        except Exception as e:
            print('LIVE PAPER ERROR',e,flush=True)
            write_runtime(last_live_update_utc=datetime.now(timezone.utc).isoformat(),last_live_ok=False,last_live_error=str(e))
        finally:_job_lock.release()

    if s['agent']['enabled']:
        scheduler=BackgroundScheduler(daemon=True,timezone='UTC')
        scheduler.add_job(scan_job,'interval',minutes=int(s['agent']['scan_minutes']),id='scan',max_instances=1,coalesce=True,
                          next_run_time=datetime.now(timezone.utc)+timedelta(seconds=2))
        scheduler.add_job(live_job,'interval',minutes=int(s['paper_portfolio'].get('live_update_minutes',2)),id='livepaper',
                          max_instances=1,coalesce=True,next_run_time=datetime.now(timezone.utc)+timedelta(seconds=20))
        scheduler.start()
        atexit.register(lambda:scheduler.shutdown(wait=False) if scheduler and scheduler.running else None)

    @app.after_request
    def no_cache(resp):
        if request.path.startswith('/api/') or request.path=='/':
            resp.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
            resp.headers['Pragma']='no-cache';resp.headers['Expires']='0'
        return resp

    @app.get('/')
    def home():return render_template('index.html')

    @app.get('/healthz')
    def healthz():
        return jsonify({'ok':True,'version':s['app']['version'],'mode':s['app']['mode'],'utc':datetime.now(timezone.utc).isoformat()})

    @app.get('/api/status')
    def status():
        st=readj(root/s['storage']['state'],{})
        rt=readj(root/s['storage'].get('runtime','storage/runtime.json'),{})
        st['runtime']=rt
        st['version']=s['app']['version']
        st['live_paper']=bool(s.get('paper_portfolio',{}).get('live_enabled',True))
        st['scan_minutes']=int(s['agent']['scan_minutes'])
        st['live_update_minutes']=int(s['paper_portfolio'].get('live_update_minutes',2))
        return jsonify(st)

    @app.get('/api/watchlist')
    def watch():return jsonify(readj(root/s['storage']['snapshot'],[]))

    @app.get('/api/benchmarks')
    def bench():return jsonify(readj(root/s['storage']['benchmarks'],[]))

    @app.get('/api/portfolio')
    def portfolio_api():return jsonify(portfolio.summary())

    @app.get('/api/trades')
    def trades():
        p=portfolio.summary()
        ev=portfolio.events()
        return jsonify({'positions':p.get('positions',[]),'closed':p.get('closed',[])[-100:],'events':ev[-100:]})

    @app.get('/api/equity')
    def equity():return jsonify(readj(root/s['storage']['equity_curve'],[]))

    @app.post('/api/live-now')
    def live_now():
        live_job()
        return jsonify({'ok':True,'portfolio':portfolio.summary()})

    @app.get('/api/intelligence/<symbol>')
    def intelligence(symbol):
        rows=readj(root/s['storage']['snapshot'],[])
        x=next((r for r in rows if r.get('symbol')==symbol),None)
        if not x:return jsonify({'status':'NOT_FOUND','symbol':symbol}),404
        keys=['symbol','name','sector','industry','comparison_benchmark','relative_strength_3m_pct','relative_strength_score',
              'abnormal_volume_ratio','volume_context_score','volatility_30d_live','volatility_context_score',
              'earnings_days','earnings_context_score','news_sentiment_score','news_headlines','market_intelligence_score','updated_at']
        return jsonify({k:x.get(k) for k in keys})

    @app.get('/api/validation/<symbol>')
    def validation(symbol):
        a=next((x for x in s['assets'] if x['symbol']==symbol),None)
        if not a:return jsonify({'status':'UNKNOWN_SYMBOL','symbol':symbol,'top10':[]}),404
        d=validator.load(symbol)
        return jsonify(d or {'status':'NOT_RUN','symbol':symbol,'validation_score':0,'top10':[]})

    @app.post('/api/validate/<symbol>')
    def validate(symbol):
        a=next((x for x in s['assets'] if x['symbol']==symbol),None)
        if not a:return jsonify({'status':'UNKNOWN_SYMBOL','symbol':symbol}),404
        mode=(request.args.get('mode') or 'full').lower()
        if mode not in ('quick','full'):mode='full'
        try:
            d=validator.validate(a,mode=mode,force=True)
            scan_job()
            return jsonify(d)
        except Exception as e:return jsonify({'status':'ERROR','symbol':symbol,'error':str(e)}),500

    @app.get('/api/sensitivity')
    def sensitivity_summary():
        symbol=request.args.get('symbol')
        if symbol:
            d=validator.load(symbol)
            return jsonify(d or {'status':'NOT_RUN','symbol':symbol,'top10':[]})
        return jsonify(readj(root/s['storage']['sensitivity_summary'],{'status':'EMPTY','symbol':s['sensitivity']['symbol'],'top10':[]}))

    @app.get('/api/chart/<symbol>/<period>')
    def chart(symbol,period):
        a=next((x for x in s['assets'] if x['symbol']==symbol),None)
        mp={'1m':('1mo','1d'),'3m':('3mo','1d'),'1y':('1y','1d'),'5d':('5d','5m')}
        if not a or period not in mp:return jsonify({'points':[]}),404
        per,intv=mp[period]
        df,resolved,_=provider.get_bars(symbol,per,intv,a.get('fallback_symbols',[]))
        if df is None or df.empty or 'close' not in df.columns:return jsonify({'points':[],'resolved_symbol':resolved})
        points=[]
        for i,r in df.tail(500).iterrows():
            try:
                v=float(r['close'])
                if math.isfinite(v):points.append({'t':str(i),'close':round(v,4)})
            except Exception:pass
        vals=[p['close'] for p in points];meta={}
        if vals:
            first,last=vals[0],vals[-1]
            meta={'first':round(first,4),'last':round(last,4),'change_pct':round((last/first-1)*100,2) if first else None,
                  'high':round(max(vals),4),'low':round(min(vals),4),'resolved_symbol':resolved}
        return jsonify({'points':points,'meta':meta})

    @app.post('/api/run-now')
    def run_now():
        st=scan_job()
        return jsonify({'ok':True,'state':st or readj(root/s['storage']['state'],{})})

    @app.post('/api/paper/order')
    def paper_order():
        body=request.get_json(silent=True) or {}
        symbol=str(body.get('symbol') or '').strip()
        side=str(body.get('side') or '').upper().strip()
        asset=next((x for x in s['assets'] if x['symbol']==symbol),None)
        if not asset:return jsonify({'ok':False,'error':'UNKNOWN_SYMBOL'}),404
        q=provider.get_live_price(symbol,asset.get('fallback_symbols',[]))
        if not q:return jsonify({'ok':False,'error':'NO_LIVE_QUOTE'}),503
        fx=provider.get_usdmxn()
        rows=readj(root/s['storage']['snapshot'],[])
        row=next((x for x in rows if x.get('symbol')==symbol),None) or {**asset,'price':q['price'],'validation_score':0,'composite_score':0}
        row['price']=q['price']
        if side=='BUY':
            out=portfolio.manual_open(row,fx,body.get('budget_mxn'),body.get('stop_pct'),body.get('target_pct'))
        elif side=='SELL':
            out=portfolio.manual_close(symbol,q['price'],fx,'MANUAL')
        else:return jsonify({'ok':False,'error':'SIDE_MUST_BE_BUY_OR_SELL'}),400
        if out.get('ok'):
            send_telegram(f"NEXUS PAPER {side} {symbol} · Simulación confirmada")
        return jsonify(out),200 if out.get('ok') else 400

    @app.get('/api/agent/decisions')
    def agent_decisions():
        limit=max(1,min(int(request.args.get('limit',100)),500))
        return jsonify(list(reversed(autonomy.decisions(limit))))

    @app.get('/api/alerts/feed')
    def alerts_feed():
        limit=max(1,min(int(request.args.get('limit',50)),200))
        return jsonify(list(reversed(autonomy.alerts(limit))))

    @app.get('/api/autonomy/status')
    def autonomy_status():
        c=s.get('autonomous_agent',{})
        return jsonify({'enabled':bool(c.get('enabled',True)),'paper_only':True,'auto_open':bool(c.get('auto_open',True)),'auto_close_on_pause':bool(c.get('auto_close_on_pause',True)),'real_execution':False,'thresholds':{k:c.get(k) for k in ['min_validation_score','min_composite_score','min_ai_strength','max_vulnerability_for_entry','pause_vulnerability','pause_market_context']}})


    @app.get('/api/learning/status')
    def learning_status():
        d=learner.summary(); d['enabled']=bool(s.get('learning_agent',{}).get('enabled',True)); d['paper_only']=True
        d['fractional_us_enabled']=bool(s.get('paper_portfolio',{}).get('allow_fractional_us',True))
        return jsonify(d)

    @app.get('/api/learning/samples')
    def learning_samples():
        limit=max(1,min(int(request.args.get('limit',50)),500))
        return jsonify(list(reversed(learner.samples(limit))))

    @app.get('/api/learning/audit')
    def learning_audit():
        return jsonify(learner.audit())

    @app.get('/api/learning/counterfactual')
    def learning_counterfactual():
        return jsonify(learner.counterfactual())

    @app.get('/api/learning/calibration')
    def learning_calibration():
        return jsonify(learner.calibration())

    @app.get('/api/risk-governor/status')
    def risk_governor_status():
        return jsonify(riskgov.evaluate(portfolio.summary(),readj(root/s['storage']['snapshot'],[])))

    @app.get('/api/risk-governor/stress')
    def risk_governor_stress():
        return jsonify(riskgov.stress_test(portfolio.summary(),readj(root/s['storage']['snapshot'],[])))

    @app.get('/api/real-trading/status')
    def real_trading_status():
        cfg=s.get('real_trading',{})
        return jsonify({
            'enabled':bool(cfg.get('enabled',False)),
            'execution_mode':cfg.get('execution_mode','manual_confirmation_only'),
            'broker':cfg.get('broker'),
            'autonomous_execution':False,
            'note':cfg.get('note'),
            'requirements':[
                'Cuenta propia con intermediario autorizado y contrato vigente',
                'API oficial del intermediario y credenciales protegidas',
                'Confirmación manual de cada orden real',
                'Bitácora auditable de señales, confirmaciones y ejecuciones',
                'Revisión fiscal y regulatoria aplicable antes de operar'
            ]
        })

    @app.get('/api/alerts/status')
    def alerts_status():
        return jsonify({
            'browser':True,
            'feed_enabled':True,
            'telegram_configured':bool(os.getenv('NEXUS_TELEGRAM_BOT_TOKEN') and os.getenv('NEXUS_TELEGRAM_CHAT_ID')),
            'telegram_bot_token_env':'NEXUS_TELEGRAM_BOT_TOKEN',
            'telegram_chat_id_env':'NEXUS_TELEGRAM_CHAT_ID'
        })

    @app.post('/api/alerts/test')
    def alerts_test():
        return jsonify(send_telegram('NEXUS Market Agent V0.16.5 · Alerta de prueba correcta.'))

    @app.get('/api/platform')
    def platform():
        return jsonify({
            'render':{
                'current_plan':'free',
                'pricing_url':'https://render.com/pricing',
                'billing_url':'https://dashboard.render.com/billing',
                'service_url':'https://dashboard.render.com/web/srv-dak1sdmk1f9s73amjk9g'
            },
            'legal':{
                'cnbv_brokers':'https://www.cnbv.gob.mx/SECTORES-SUPERVISADOS/BURS%C3%81TIL/Descripci%C3%B3n/Paginas/Casas-de-Bolsa.aspx',
                'cnbv_advisers':'https://www.gob.mx/cnbv/acciones-y-programas/asesores-en-inversiones',
                'cnbv_rules':'https://www.gob.mx/cnbv/acciones-y-programas/disposiciones-legales-casas-de-bolsa'
            }
        })

    return app
