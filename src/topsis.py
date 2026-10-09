import numpy as np
from analysis_common import FEATURES, DIRECTIONS, load_analysis, matrix, weights_for, result_frame, save_csv

def components(frame, features=FEATURES, weights=None):
    x = matrix(frame, features)
    norms = np.linalg.norm(x, axis=0)
    if (norms == 0).any():
        raise ValueError('Zero vector norm.')
    weighted = x / norms * weights_for(features, weights)
    high = np.array([DIRECTIONS[f] > 0 for f in features])
    ideal = np.where(high, weighted.max(axis=0), weighted.min(axis=0))
    anti = np.where(high, weighted.min(axis=0), weighted.max(axis=0))
    distance_ideal = np.linalg.norm(weighted - ideal, axis=1)
    distance_anti = np.linalg.norm(weighted - anti, axis=1)
    return weighted, ideal, anti, distance_ideal, distance_anti

def calculate(frame, features=FEATURES, weights=None):
    _, _, _, di, da = components(frame, features, weights)
    return da / (di + da)

def run():
    frame = load_analysis()
    out = result_frame(frame, calculate(frame), 'topsis_score')
    _, _, _, di, da = components(frame)
    distances = dict(zip(frame.geo_code, zip(di, da)))
    out['distance_to_disadvantage_ideal'] = out.geo_code.map(lambda c: distances[c][0])
    out['distance_to_advantage_ideal'] = out.geo_code.map(lambda c: distances[c][1])
    save_csv(out, 'results/topsis_results.csv')
    weighted, ideal, anti, _, _ = components(frame)
    trace = frame[['geo_code', 'geo_name']].copy()
    trace[FEATURES] = weighted
    save_csv(trace, 'results/topsis_weighted_matrix.csv')
    import pandas as pd
    save_csv(pd.DataFrame({'indicator': FEATURES, 'weight': 1 / len(FEATURES),
                          'ideal_disadvantage': ideal, 'anti_ideal': anti}), 'results/topsis_ideals.csv')
    return out

if __name__ == '__main__':
    print(run().head().to_string(index=False))
