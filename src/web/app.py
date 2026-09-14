from flask import Flask,jsonify,render_template,request
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone, timedelta
import json,atexit,math,threading,os
from src.config.loader import load_settings,project_root
from src.agent.engine import NexusAgent
from src.agent.portfolio import PaperPortfolio
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
            st,_=agent.scan_once()
            write_runtime(scan_running=False,last_scan_finished_utc=datetime.now(timezone.utc).isoformat(),last_scan_ok=True,last_scan_error=None)
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

    return app
