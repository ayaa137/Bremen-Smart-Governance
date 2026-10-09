from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
YEAR = 2024
FEATURES = ['unemployment', 'employment', 'benefit_receipt']
LABELS = {'unemployment': 'Unemployment quotient (%)', 'employment': 'Social-insurance employment (%)',
          'benefit_receipt': 'SGB II receipt, under 65 (%)', 'child_benefits': 'SGB II receipt, under 15 (%)',
          'income_median': 'Median income per taxpayer (1000 EUR)', 'single_parents': 'Single-parent households (%)'}
DIRECTIONS = {'unemployment': 1, 'employment': -1, 'benefit_receipt': 1, 'child_benefits': 1, 'income_median': -1}
SOURCE = 'Source: Statistisches Landesamt Bremen, supplied Datentabelle.xls'

def save_csv(frame, relative):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding='utf-8-sig')

def write_doc(relative, text):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + '\n', encoding='utf-8')

def load_analysis(eligible=True):
    frame = pd.read_csv(ROOT / 'data/processed/ortsteil_analysis_ready.csv', dtype={'geo_code': str})
    return frame[frame.scoring_eligible].copy() if eligible else frame

def weights_for(features, weights=None):
    w = np.ones(len(features)) if weights is None else np.asarray(weights, dtype=float)
    if len(w) != len(features) or not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise ValueError('Weights must be finite, nonnegative and have positive sum.')
    return w / w.sum()

def matrix(frame, features):
    x = frame[features].to_numpy(dtype=float)
    if not np.isfinite(x).all() or (np.ptp(x, axis=0) == 0).any():
        raise ValueError('Scoring requires finite, nonconstant indicators.')
    return x

def result_frame(frame, score, name):
    out = frame[['geo_code', 'geo_name', 'year']].copy()
    out[name] = score
    out['rank'] = pd.Series(score).rank(ascending=False, method='min').to_numpy().astype(int)
    return out.sort_values(['rank', 'geo_code'])
