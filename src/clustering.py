import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score
from analysis_common import FEATURES, load_analysis, save_csv

def run():
    frame = load_analysis()
    x = StandardScaler().fit_transform(frame[FEATURES])
    diagnostics = []
    for k in range(2, min(9, len(frame))):
        model = KMeans(n_clusters=k, n_init=30, random_state=42).fit(x)
        diagnostics.append({'k': k, 'silhouette': silhouette_score(x, model.labels_),
                            'inertia': model.inertia_, 'calinski_harabasz': calinski_harabasz_score(x, model.labels_),
                            'davies_bouldin': davies_bouldin_score(x, model.labels_),
                            'minimum_cluster_size': np.bincount(model.labels_).min()})
    diag = pd.DataFrame(diagnostics)
    # Exclude singleton profiles from the baseline choice, retaining their diagnostics.
    valid = diag[diag.minimum_cluster_size >= 3]
    if valid.empty:
        raise ValueError('No defensible cluster solution with at least three members per cluster.')
    k = int(valid.sort_values(['silhouette', 'k'], ascending=[False, True]).iloc[0].k)
    baseline = KMeans(n_clusters=k, n_init=30, random_state=42).fit(x)
    out = frame[['geo_code', 'geo_name', 'year'] + FEATURES].copy()
    out['cluster'] = ['Profile ' + chr(65 + int(i)) for i in baseline.labels_]
    profiles = out.groupby('cluster')[FEATURES].agg(['mean', 'std', 'min', 'max'])
    profiles.columns = ['_'.join(c) for c in profiles.columns]
    profiles['n'] = out.groupby('cluster').size()
    save_csv(profiles.reset_index(), 'results/cluster_profiles.csv')
    save_csv(out, 'results/kmeans_results.csv')
    save_csv(diag, 'results/kmeans_diagnostics.csv')
    stability = []
    for seed in range(30):
        labels = KMeans(n_clusters=k, n_init=30, random_state=seed).fit_predict(x)
        stability.append({'experiment': 'initialization', 'seed': seed, 'k': k,
                          'adjusted_rand_index': adjusted_rand_score(baseline.labels_, labels)})
        rng = np.random.default_rng(seed)
        indices = rng.choice(len(x), size=len(x), replace=True)
        fitted = KMeans(n_clusters=k, n_init=30, random_state=seed).fit(x[indices])
        stability.append({'experiment': 'bootstrap_neighborhoods', 'seed': seed, 'k': k,
                          'adjusted_rand_index': adjusted_rand_score(baseline.labels_, fitted.predict(x))})
    save_csv(pd.DataFrame(stability), 'results/cluster_stability.csv')
    return out

if __name__ == '__main__':
    print(run().groupby('cluster').size())
