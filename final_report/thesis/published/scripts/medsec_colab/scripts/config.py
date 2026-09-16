import json
from pathlib import Path
import numpy as np

def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding='utf-8'))
    validate(cfg)
    return cfg

def validate(c):
    if c['system'] not in ('equation_3_2', 'appendix', 'subathra_2025'):
        raise ValueError('Unknown ODE system')
    if c['system'] == 'equation_3_2':
        names = ['a','b','c','d','k','h','w']
        missing = [n for n in names if c['parameters'].get(n) is None]
        if missing:
            raise ValueError('پارامترهای رابطه ۳-۲ تعیین‌نشده‌اند: ' + ', '.join(missing) +
                             ' — یا عددها را در پروفایل مستند خودتان تعیین کنید یا PROFILE را صریحاً به '
                             'scripts/appendix_experiment.json (اعداد مستند پیوست پایان‌نامه) تغییر دهید.')
    elif c['system'] == 'appendix':
        names = ['a','b','c','d','e']
        missing = [n for n in names if c['parameters'].get(n) is None]
        if missing:
            raise ValueError('پارامترهای تعیین‌نشدهٔ سیستم پیوست: ' + ', '.join(missing))
    elif c['system'] == 'subathra_2025':
        # سیستم ۵بعدی ابرآشوبی سوباترا & Thanikaiselvan (Nature Sci Rep, 2025)
        # پارامترهای تعریف‌شده: gamma, beta, partial, epsilon, vartheta, rho, kappa
        # در config armazenished as a,b,c,d,e برای سازگاری عقب، اما از validate شده
        names = ['a','b','c','d','e']
        missing = [n for n in names if c['parameters'].get(n) is None]
        if missing:
            raise ValueError('پارامترهای سیستم سوباترا ۲۰۲۵ تعیین‌نشده‌اند: ' + ', '.join(missing))
    if not np.isfinite([c['parameters'][n] for n in names]).all():
        raise ValueError('Nonfinite ODE parameters')
    if not np.isfinite([c['dt'], c['scale']]).all() or c['dt'] <= 0 or c['transient'] < 0 or c['scale'] <= 0:
        raise ValueError('Invalid integrator settings')
    if not isinstance(c['transient'], int): raise ValueError('Transient must be an integer')
    if c['dna_variant'] not in ('pseudocode_3_3','equation_3_3_feedback'):
        raise ValueError('Unknown DNA interpretation')
    if c['hash_mapping'] not in ('mod_1e8','appendix_fraction','equation_byte_mean'):
        raise ValueError('Unknown hash mapping')
    if not 0 < c['saliency_quantile'] <= 1:
        raise ValueError('Invalid saliency quantile')
    if c['roi_coordinates'] not in ('original', 'permuted_union_original'): raise ValueError('Invalid ROI convention')
    if not isinstance(c['saliency_filter'], int) or c['saliency_filter'] < 1: raise ValueError('Invalid saliency filter')
    if not np.isfinite(c['saliency_sigma']) or c['saliency_sigma'] <= 0: raise ValueError('Invalid saliency sigma')
    if not isinstance(c['compression_level'], int) or not 0 <= c['compression_level'] <= 9: raise ValueError('Invalid zlib level')
    for name in ('correlation_pairs', 'differential_trials'):
        if not isinstance(c[name], int) or c[name] < 1: raise ValueError(f'Invalid {name}')

def ode_parameters(c):
    validate(c)
    p=c['parameters']
    names=['a','b','c','d','k','h','w'] if c['system']=='equation_3_2' else ['a','b','c','d','e']
    return np.array([p[n] for n in names], dtype=np.float64)