import numpy as np
# --- Code from previous message (HANTS_3D_strict and helpers) ---
from numpy.linalg import lstsq
from typing import Optional, Tuple

def _harmonic_design(ts: np.ndarray,
                     n_freq: int,
                     base_period_len: float,
                     include_intercept: bool = True) -> np.ndarray:
    ts = np.asarray(ts, dtype=float)
    omega = 2.0 * np.pi / base_period_len
    cols = []
    if include_intercept:
        cols.append(np.ones_like(ts))
    for k in range(1, n_freq + 1):
        cols.append(np.cos(k * omega * ts))
        cols.append(np.sin(k * omega * ts))
    X = np.vstack(cols).T
    return X

def _weighted_lstsq(X: np.ndarray, y: np.ndarray, w: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    w = np.asarray(w, dtype=float)
    w_sqrt = np.sqrt(w)
    Xw = X * w_sqrt[:, None]
    yw = y * w_sqrt
    coef, _, _, _ = lstsq(Xw, yw, rcond=None)
    fitted = X @ coef
    return coef, fitted

def _update_weights(residuals: np.ndarray,
                    valid_mask: np.ndarray,
                    scheme: str,
                    c: float) -> np.ndarray:
    r = np.abs(residuals)
    w = np.zeros_like(r, dtype=float)
    if scheme == "binary":
        w[valid_mask & (r <= c)] = 1.0
    elif scheme == "huber":
        w[valid_mask & (r <= c)] = 1.0
        idx = valid_mask & (r > c)
        w[idx] = (c / r[idx])
    elif scheme == "tukey":
        idx = valid_mask & (r < c)
        u = r[idx] / c
        w[idx] = (1 - u**2)**2
    else:
        raise ValueError("Unknown weight scheme. Use 'binary', 'huber', or 'tukey'.")
    return w

def HANTS_3D(
    inputs_3d: np.ndarray,
    ts: Optional[np.ndarray] = None,
    base_period_len: Optional[float] = None,
    n_freq: int = 3,
    low: float = -0.2,
    high: float = 1.0,
    fit_error_tolerance: float = 0.05,
    dod: int = 1,
    outliers_to_reject: str = "None",
    weight_scheme: str = "huber",
    max_iterations: int = 10,
    min_improvement: float = 1e-4,
) -> np.ndarray:
    if inputs_3d.ndim != 3:
        raise ValueError("inputs_3d must be (nx, ny, nt).")
    nx, ny, nt = inputs_3d.shape
    if ts is None:
        ts = np.arange(nt, dtype=float)
    else:
        ts = np.asarray(ts, dtype=float)
        if ts.shape[0] != nt:
            raise ValueError("ts length must match the time dimension of inputs_3d.")
    if base_period_len is None:
        base_period_len = float(nt)
    X = _harmonic_design(ts, n_freq=n_freq, base_period_len=base_period_len, include_intercept=True)
    min_points_required = (2 * n_freq + 1) + dod
    outputs = np.full_like(inputs_3d, np.nan, dtype=float)
    for i in range(nx):
        for j in range(ny):
            y = inputs_3d[i, j, :].astype(float)
            if np.isnan(y).all():
                continue
            valid = (~np.isnan(y)) & (y >= low) & (y <= high)
            if outliers_to_reject == "Hi":
                valid &= (y < high)
            elif outliers_to_reject == "Lo":
                valid &= (y > low)
            if valid.sum() < min_points_required:
                continue
            w = np.zeros(nt, dtype=float)
            w[valid] = 1.0
            prev_mae = np.inf
            fitted = np.full(nt, np.nan, dtype=float)
            for _ in range(max_iterations):
                if np.count_nonzero(w > 0) < min_points_required:
                    break
                try:
                    coef, fitted = _weighted_lstsq(X, y, w)
                except np.linalg.LinAlgError:
                    break
                residuals = y - fitted
                in_range = (~np.isnan(y)) & (y >= low) & (y <= high)
                w_new = _update_weights(residuals=residuals,
                                        valid_mask=in_range,
                                        scheme=weight_scheme,
                                        c=fit_error_tolerance)
                mae = np.nanmean(np.abs(residuals[w_new > 0])) if np.count_nonzero(w_new > 0) else np.inf
                if not np.isfinite(mae):
                    break
                if prev_mae - mae < min_improvement:
                    w = w_new
                    break
                w = w_new
                prev_mae = mae
            if np.count_nonzero(w > 0) >= min_points_required and np.isfinite(fitted).any():
                outputs[i, j, :] = fitted
    return outputs

