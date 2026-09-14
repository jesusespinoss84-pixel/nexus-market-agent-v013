from pathlib import Path
import os
import yaml

ROOT=Path(__file__).resolve().parents[2]

def load_settings():
    with (ROOT/'config'/'settings.yaml').open('r',encoding='utf-8') as f:
        s=yaml.safe_load(f)

    # Cloud/Render overrides.
    if os.getenv('PORT'):
        try:s['app']['port']=int(os.getenv('PORT'))
        except:pass
    if os.getenv('NEXUS_SCAN_MINUTES'):
        try:s['agent']['scan_minutes']=max(1,int(os.getenv('NEXUS_SCAN_MINUTES')))
        except:pass
    if os.getenv('NEXUS_LIVE_MINUTES'):
        try:s['paper_portfolio']['live_update_minutes']=max(1,int(os.getenv('NEXUS_LIVE_MINUTES')))
        except:pass

    # Persist JSON/CSV/cache outside the ephemeral application directory.
    data_dir=os.getenv('NEXUS_DATA_DIR')
    if data_dir:
        base=Path(data_dir)
        base.mkdir(parents=True,exist_ok=True)
        for key,val in list(s.get('storage',{}).items()):
            if not isinstance(val,str):continue
            p=Path(val)
            parts=list(p.parts)
            if parts and parts[0].lower()=='storage':
                p=Path(*parts[1:]) if len(parts)>1 else Path(key)
            s['storage'][key]=str((base/p).resolve())
    return s

def project_root():
    return ROOT
