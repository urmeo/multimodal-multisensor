"""Finite complete-case ICC and explicitly scoped multiple-comparison statistics."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .hrv import _real_series

_NAN_ICC = {
    "icc": float("nan"),
    "ci95": (float("nan"), float("nan")),
    "F": float("nan"),
}


def icc1(data) -> dict:
    """ICC(1,1), participants by ratings, with a 95% CI and finite complete rows."""
    raw = np.asarray(data, dtype=object)
    if raw.ndim != 2 or raw.shape[1] < 2:
        return {**_NAN_ICC, "n": 0, "k": 0}
    ratings = _real_series(raw.ravel(), "data").to_numpy(float).reshape(raw.shape)
    ratings = ratings[np.isfinite(ratings).all(axis=1)]
    n, k = ratings.shape
    if n < 2:
        return {**_NAN_ICC, "n": int(n), "k": int(k)}
    scale = float(np.max(np.abs(ratings)))
    if not scale:
        return {**_NAN_ICC, "n": int(n), "k": int(k)}
    ratings = ratings / scale
    deviations = ratings - ratings[:, :1]
    mean_deviation = deviations.mean(axis=1, keepdims=True)
    mean_rows = ratings[:, :1] + mean_deviation
    centered_rows = mean_rows[:, 0] - mean_rows[:, 0].mean()
    ms_between = k * (centered_rows**2).sum() / (n - 1)
    ms_within = ((deviations - mean_deviation) ** 2).sum() / (n * (k - 1))
    denominator = ms_between + (k - 1) * ms_within
    if not denominator:
        return {**_NAN_ICC, "n": int(n), "k": int(k)}
    icc = (ms_between - ms_within) / denominator
    if ms_within == 0:
        return {
            "icc": float(icc),
            "ci95": (float("nan"), float("nan")),
            "n": int(n),
            "k": int(k),
            "F": float("inf"),
        }
    f_statistic = ms_between / ms_within
    f_lower = f_statistic / stats.f.ppf(0.975, n - 1, n * (k - 1))
    f_upper = f_statistic * stats.f.ppf(0.975, n * (k - 1), n - 1)
    lower = (f_lower - 1) / (f_lower + (k - 1))
    upper = (f_upper - 1) / (f_upper + (k - 1)) if np.isfinite(f_upper) else 1.0
    return {
        "icc": float(icc),
        "ci95": (float(lower), float(upper)),
        "n": int(n),
        "k": int(k),
        "F": float(f_statistic),
    }


def _pvalues(pvals) -> np.ndarray:
    raw = np.asarray(pvals, dtype=object)
    if raw.ndim != 1:
        raise ValueError("p-values must be a one-dimensional vector")
    values = _real_series(raw, "p-values").to_numpy(float)
    if ((values < 0) | (values > 1)).any():
        raise ValueError("p-values must be in [0, 1], with NaN for unrun tests")
    return values


def _adjust(pvals, method: str) -> np.ndarray:
    pvalues = _pvalues(pvals)
    out = np.full(pvalues.shape, np.nan)
    valid = ~np.isnan(pvalues)
    values = pvalues[valid]
    count = len(values)
    if not count:
        return out
    order = np.argsort(values, kind="stable")
    if method == "holm":
        adjusted = np.maximum.accumulate(values[order] * np.arange(count, 0, -1))
    else:
        adjusted = values[order] * count / np.arange(1, count + 1)
        adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    original_order = np.empty(count)
    original_order[order] = np.clip(adjusted, 0, 1)
    out[valid] = original_order
    return out


def holm(pvals) -> np.ndarray:
    """Holm family-wise adjusted p-values in input order; unrun NaNs excluded."""
    return _adjust(pvals, "holm")


def benjamini_hochberg(pvals) -> np.ndarray:
    """BH FDR adjusted p-values in input order; unrun NaNs excluded."""
    return _adjust(pvals, "bh")


def corr_matrix_fdr(df: pd.DataFrame, method: str = "pearson") -> dict:
    """Pairwise finite Pearson or Spearman correlations with one BH test family.

    Constant or fewer-than-three complete pairs are undefined, including their
    p-values. Diagonal correlations are descriptive and never counted as tests.
    """
    if method not in {"pearson", "spearman"}:
        raise ValueError("method must be 'pearson' or 'spearman'")
    if not df.columns.is_unique:
        raise ValueError("correlation columns must have unique names")
    columns = list(df.columns)
    values = [
        _real_series(df[column], str(column)).to_numpy(float) for column in columns
    ]
    size = len(columns)
    r, p_raw, p_fdr = (np.full((size, size), np.nan) for _ in range(3))
    counts = np.zeros((size, size), dtype=int)
    pairs = []
    correlate = stats.pearsonr if method == "pearson" else stats.spearmanr
    for i, column in enumerate(values):
        finite = column[np.isfinite(column)]
        counts[i, i] = len(finite)
        if len(finite) >= 3 and np.any(finite != finite[0]):
            r[i, i] = 1.0
        for j in range(i + 1, size):
            other = values[j]
            mask = np.isfinite(column) & np.isfinite(other)
            counts[i, j] = counts[j, i] = int(mask.sum())
            first, second = column[mask], other[mask]
            if (
                len(first) >= 3
                and np.any(first != first[0])
                and np.any(second != second[0])
            ):
                if method == "pearson":
                    first = first / float(np.max(np.abs(first)))
                    second = second / float(np.max(np.abs(second)))
                    first = first - first.mean()
                    second = second - second.mean()
                correlation, pvalue = correlate(first, second)
                r[i, j] = r[j, i] = float(correlation)
                p_raw[i, j] = p_raw[j, i] = float(pvalue)
            pairs.append((i, j, p_raw[i, j]))
    adjusted = benjamini_hochberg([pvalue for _, _, pvalue in pairs])
    for (i, j, _), value in zip(pairs, adjusted):
        p_fdr[i, j] = p_fdr[j, i] = value

    def frame(matrix):
        return pd.DataFrame(matrix, index=columns, columns=columns)

    return {
        "r": frame(r),
        "p_raw": frame(p_raw),
        "p_fdr": frame(p_fdr),
        "n_pairs": frame(counts),
        "n_tests": int(np.isfinite(adjusted).sum()),
        "method": method,
        "adjustment": "Benjamini-Hochberg",
        "family": "all valid off-diagonal column pairs",
    }
