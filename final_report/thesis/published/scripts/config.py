import json
from pathlib import Path
import numpy as np

def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding='utf-8'))
    validate(cfg)
    return cfg

def validate(c):
    if c['system'] not in ('equation_3_2', 'appendix'):
        raise ValueError('Unknown ODE system')
    names = ['a','b','c','d','k','h','w'] if c['system'] == 'equation_3_2' else ['a','b','c','d','e']
    if any(c['parameters'].get(n) is None for n in names):
        raise ValueError('پارامترهای رابطه ۳-۲ در پایان‌نامه عدد ندارند؛ ابتدا همه را مستند و تعیین کنید. پروفایل پیوست روش متفاوتی است.')
    if not np.isfinite([c['parameters'][n] for n in names]).all():
        raise ValueError('Nonfinite ODE parameters')
    if c['dt'] <= 0 or c['transient'] < 0 or c['scale'] <= 0:
        raise ValueError('Invalid integrator settings')
    if c['dna_variant'] not in ('pseudocode_3_3','equation_3_3_feedback'):
        raise ValueError('Unknown DNA interpretation')
    if c['hash_mapping'] not in ('mod_1e8','appendix_fraction','equation_byte_mean'):
        raise ValueError('Unknown hash mapping')
    if not 0 < c['saliency_quantile'] <= 1:
        raise ValueError('Invalid saliency quantile')

def ode_parameters(c):
    validate(c)
    p=c['parameters']
    names=['a','b','c','d','k','h','w'] if c['system']=='equation_3_2' else ['a','b','c','d','e']
    return np.array([p[n] for n in names], dtype=np.float64)