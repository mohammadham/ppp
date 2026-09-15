import numpy as np
from scipy.stats import chisquare, binom, norm
from skimage.metrics import structural_similarity

def entropy(image):
    counts=np.bincount(image.ravel(),minlength=256)
    p=counts[counts>0]/image.size
    return float(-np.sum(p*np.log2(p)))

def correlations(image,n=10000,seed=2026):
    rng=np.random.default_rng(seed); result={}
    for name,dr,dc in [('horizontal',0,1),('vertical',1,0),('diagonal',1,1)]:
        if image.shape[0]<=dr or image.shape[1]<=dc: result[name]=None; continue
        r=rng.integers(0,image.shape[0]-dr,n); c=rng.integers(0,image.shape[1]-dc,n)
        x=image[r,c].astype(float); y=image[r+dr,c+dc].astype(float)
        result[name]=float(np.corrcoef(x,y)[0,1]) if x.std()>0 and y.std()>0 else None
    return result

def security(image,n=10000,seed=2026):
    stat,p=chisquare(np.bincount(image.ravel(),minlength=256))
    return {'entropy':entropy(image),'chi_square':float(stat),'chi_square_p':float(p),
            'chi_square_expected_count':image.size/256,'chi_square_approximation_valid':image.size/256>=5,
            **{'correlation_'+k:v for k,v in correlations(image,n,seed).items()}}

def psnr(a,b):
    if not a.size:return None
    mse=float(np.mean((a.astype(float)-b.astype(float))**2))
    return float('inf') if mse==0 else float(10*np.log10(255**2/mse))

def quality(a,b,roi=None):
    if a.shape!=b.shape:raise ValueError('Metric shape mismatch')
    mse=float(np.mean((a.astype(float)-b.astype(float))**2))
    window=min(7,min(a.shape)); window-=1-window%2
    if window<3: ssim,ssim_map=None,None
    else: ssim,ssim_map=structural_similarity(a,b,data_range=255,win_size=window,full=True)
    result={'mse':mse,'psnr':psnr(a,b),'ssim':float(ssim) if ssim is not None else None,
            'bit_exact':bool(np.array_equal(a,b))}
    if roi is not None:
        result['roi_psnr']=psnr(a[roi],b[roi])
        result['roi_mse']=float(np.mean((a[roi].astype(float)-b[roi].astype(float))**2)) if roi.any() else None
        result['roi_ssim_local_mean']=float(ssim_map[roi].mean()) if roi.any() and ssim_map is not None else None
    return result

def differential(a,b,alpha=.05):
    if a.shape!=b.shape:raise ValueError('Differential shape mismatch')
    count=int(np.count_nonzero(a!=b)); n=a.size
    diff=np.abs(a.astype(float)-b.astype(float))/255
    # Ideal independent uniform 8-bit images; exact binomial lower-tail and CLT UACI interval.
    vals=np.arange(256); probs=np.where(vals==0,256,2*(256-vals))/256**2
    mean=float(np.sum(probs*vals/255)); var=float(np.sum(probs*(vals/255-mean)**2))
    radius=float(norm.ppf(1-alpha/2)*np.sqrt(var/n))
    p=float(binom.cdf(count,n,255/256))
    return {'npcr':100*count/n,'uaci':100*float(diff.mean()),'npcr_lower_tail_p':p,
            'npcr_not_below_ideal_at_alpha':p>=alpha,'uaci_ideal_interval_pct':[100*(mean-radius),100*(mean+radius)],
            'uaci_in_ideal_interval':mean-radius<=float(diff.mean())<=mean+radius,'alpha':alpha}