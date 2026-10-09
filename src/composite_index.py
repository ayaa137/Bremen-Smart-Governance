import numpy as np
from analysis_common import FEATURES, DIRECTIONS, load_analysis, matrix, weights_for, result_frame, save_csv

def normalize(frame, features=FEATURES):
    x = matrix(frame, features)
    z = (x - x.min(axis=0)) / np.ptp(x, axis=0)
    for j, feature in enumerate(features):
        if DIRECTIONS[feature] < 0:
            z[:, j] = 1 - z[:, j]
    return z

def calculate(frame, features=FEATURES, weights=None):
    return normalize(frame, features) @ weights_for(features, weights)

def run():
    frame = load_analysis()
    out = result_frame(frame, calculate(frame), 'composite_score')
    save_csv(out, 'results/composite_index_results.csv')
    z = frame[['geo_code', 'geo_name', 'year']].copy()
    z[FEATURES] = normalize(frame)
    save_csv(z, 'results/composite_normalized_indicators.csv')
    return out

if __name__ == '__main__':
    print(run().head().to_string(index=False))
