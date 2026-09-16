"""Finite-time Lyapunov spectrum: coupled variational RK4 with QR reorthogonalization."""
import numpy as np
from numba import njit
from .chaos import rhs_5d, step, initial_state
from .config import ode_parameters
from .artifacts import environment, write_json

@njit(cache=True)
def jacobian(s, p, variant):
    x, y, z, u, v = s
    a, b, c, d = p[:4]
    j = np.zeros((5, 5))
    j[0, 0] = -a; j[0, 1] = a; j[0, 3] = 1
    j[1, 0] = c-z; j[1, 1] = d; j[1, 2] = -x; j[1, 4] = 1
    j[2, 0] = y; j[2, 1] = x; j[2, 2] = -b
    if variant == 0:
        j[3, 0] = -p[4]; j[4, 1] = p[5]; j[4, 4] = -p[6]
    else:
        j[3, 1] = -z; j[3, 2] = -y; j[3, 3] = p[4]
        j[4, 0] = z; j[4, 2] = x; j[4, 4] = -p[4]
    return j

@njit(cache=True)
def variational_steps(s, q, count, dt, p, variant):
    for _ in range(count):
        a = rhs_5d(s, p, variant); A = jacobian(s, p, variant) @ q
        b = rhs_5d(s+dt*a/2, p, variant); B = jacobian(s+dt*a/2, p, variant) @ (q+dt*A/2)
        c = rhs_5d(s+dt*b/2, p, variant); C = jacobian(s+dt*b/2, p, variant) @ (q+dt*B/2)
        d = rhs_5d(s+dt*c, p, variant); D = jacobian(s+dt*c, p, variant) @ (q+dt*C)
        s = s+dt*(a+2*b+2*c+d)/6; q = q+dt*(A+2*B+2*C+D)/6
        if not np.isfinite(s).all() or not np.isfinite(q).all() or np.max(np.abs(s)) > 1e12:
            raise ValueError('Variational system diverged; no Lyapunov conclusion')
    return s, q

def lyapunov(digest, cfg, steps=100000, qr_interval=10, output=None):
    result = {'method': 'coupled_variational_RK4_QR_finite_time', 'config': cfg, 'digest': digest,
              'steps': steps, 'qr_interval': qr_interval, 'environment': environment(), 'proof_of_hyperchaos': False}
    try:
        if steps < 1 or qr_interval < 1: raise ValueError('Positive steps and QR interval required')
        p = ode_parameters(cfg); variant = 0 if cfg['system'] == 'equation_3_2' else 1
        s = initial_state(digest, cfg['hash_mapping']); dt = cfg['dt']
        for _ in range(cfg['transient']):
            s = step(s, dt, p, variant)
            if not np.isfinite(s).all() or np.max(np.abs(s)) > 1e12: raise ValueError('Transient diverged')
        q = np.eye(5); sums = np.zeros(5); history = []; phase = []; amplitude = 0.
        completed = 0
        while completed < steps:
            count = min(qr_interval, steps-completed)
            s, q = variational_steps(s, q, count, dt, p, variant)
            q, r = np.linalg.qr(q); diagonal = np.abs(np.diag(r))
            if (diagonal <= 0).any(): raise ValueError('Singular tangent flow')
            sums += np.log(diagonal); completed += count; amplitude = max(amplitude, float(np.abs(s).max()))
            if len(phase) < 5000: phase.append(s.tolist())
            if completed == steps or completed % (qr_interval*100) == 0:
                history.append({'time': completed*dt, 'spectrum': (sums/(completed*dt)).tolist()})
        spectrum = sums/(steps*dt)
        result.update({'status': 'ok', 'spectrum': spectrum.tolist(), 'positive_count_finite_time': int((spectrum > 0).sum()),
                       'convergence': history, 'phase': phase, 'max_abs_state': amplitude,
                       'discretization_exceeds_float64_exact_integer_range': amplitude*cfg['scale'] > 2**53,
                       'sum_spectrum': float(spectrum.sum()), 'analytic_divergence': float(np.trace(jacobian(s, p, variant)))})
    except Exception as exc: result.update({'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'})
    if output: write_json(output, result)
    return result