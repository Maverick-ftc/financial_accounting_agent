import os
from .core import ROOT

def load_env():
    path=ROOT/'.env'
    if not path.exists():
        return
    allowed={'DEEPSEEK_API_KEY','DEEPSEEK_MODEL'}
    for number,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError(f'Invalid .env line {number}')
        key,value=line.split('=',1);key=key.strip();value=value.strip()
        if key not in allowed:
            raise ValueError(f'Unsupported .env setting on line {number}')
        if len(value)>1 and value[0]==value[-1] and value[0] in ('"',"'"):
            value=value[1:-1]
        if not os.environ.get(key):
            os.environ[key]=value
