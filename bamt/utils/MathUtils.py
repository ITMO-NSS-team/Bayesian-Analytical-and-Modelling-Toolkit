import numpy as np
import math
from scipy import stats
from sklearn.mixture import GaussianMixture
from scipy.stats.distributions import chi2
from kneed import KneeLocator
from yellowbrick.cluster import KElbowVisualizer
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression


def lrts_comp(data):
    n = 1
    ps = []
    comps = []
    max_comp = 10
    if len(data) < max_comp:
        max_comp = len(data)
    for i in range(1, max_comp + 1, 1):
        gm1 = GaussianMixture(n_components=i, random_state=0)
        gm2 = GaussianMixture(n_components=i + 1, random_state=0)
        gm1.fit(data)
        ll1 = np.mean(gm1.score_samples(data))
        gm2.fit(data)
        ll2 = np.mean(gm2.score_samples(data))
        LR = -2 * (ll1 - ll2)
        p = chi2.sf(LR, 2)
        ps.append(p)
        comps.append(i)
    if len(comps) > 1:
        kn = KneeLocator(comps, ps, curve="concave", direction="increasing")
        n = kn.knee
        if not n:
            n = np.argmax(ps) + 1
    return n


def mix_norm_cdf(x, weights, means, covars):
    mcdf = 0.0
    for i in range(len(weights)):
        mcdf += weights[i] * stats.norm.cdf(x, loc=means[i][0], scale=covars[i][0][0])
    return mcdf


def theoretical_quantile(data, n_comp):
    model = GaussianMixture(n_components=n_comp, random_state=0)
    model.fit(data)
    q = []
    x = []
    # step =  ((np.max(model.sample(100000)[0])) - (np.min(model.sample(100000)[0])))/1000
    step = (np.max(data) - np.min(data)) / 1000
    d = np.arange(np.min(data), np.max(data), step)
    for i in d:
        x.append(i)
        q.append(mix_norm_cdf(i, model.weights_, model.means_, model.covariances_))
    return x, q


def quantile_mix(p, vals, q):
    ind = q.index(min(q, key=lambda x: abs(x - p)))
    return vals[ind]


def probability_mix(val, vals, q):
    ind = vals.index(min(vals, key=lambda x: abs(x - val)))
    return (q[ind])


def sum_dist(data, vals, q):
    percs = np.linspace(1, 100, 10)
    x = np.quantile(data, percs / 100)
    y = []
    for p in percs:
        y.append(quantile_mix(p / 100, vals, q))
    dist = 0
    for xi, yi in zip(x, y):
        dist = dist + (abs(-1 * xi + yi)) / math.sqrt(2)
    return dist


def component(data, columns, method):
    data = data[columns]
    n = 1
    max_comp = 10
    x = []
    if data.shape[0] < max_comp:
        max_comp = data.shape[0]
    if len(data.shape) == 1:
        x = np.transpose([data])
    else:
        x = data
    if method == 'aic':
        aics = []
        comps = []
        for i in range(1, max_comp + 1, 1):
            gm1 = GaussianMixture(n_components=i)
            try:
                gm1.fit(x)
            except:
                break
            aic1 = gm1.aic(x)
            aics.append(aic1)
            comps.append(i)
        if len(comps) > 1:
            kn = KneeLocator(comps, aics, curve='convex', direction='decreasing')
            n = kn.knee
            if not n:
                n = np.argmin(aics) + 1
            
    if method == 'bic':
        bics = []
        comps = []
        for i in range(1, max_comp + 1, 1):
            gm1 = GaussianMixture(n_components=i)
            try:
                gm1.fit(x)
            except:
                break
            bic1 = gm1.bic(x)
            bics.append(bic1)
            comps.append(i)
        if len(comps) > 1:
            kn = KneeLocator(comps, bics, curve='convex', direction='decreasing')
            n = kn.knee
            if not n:
                n = np.argmin(bics) + 1

    if method == 'LRTS':
        n = lrts_comp(x)
    if method == 'quantile':
        dists = []
        for i in range(1, max_comp, 1):
            vals, q = theoretical_quantile(x, i)
            dist = sum_dist(x, vals, q)
            dists.append(dist)
        kn1 = KneeLocator([i for i in range(1, max_comp, 1)], dists, curve='convex', direction='decreasing')
        n = kn1.knee
        if not n:
            n = np.argmin(dists) + 1
    return n

def number_of_components(data, columns):
    data = data[columns].values
    n = 1
    max_comp = 10
    if data.shape[0] < max_comp:
        max_comp = data.shape[0]
    bics = []
    aics = []
    comps = []
    for i in range(1, max_comp + 1, 1):
        gm1 = GaussianMixture(n_components=i, init_params='k-means++', reg_covar=0.001)
        try:
            gm1.fit(data)
        except:
            break
        bic1 = gm1.bic(data)
        aic1 = gm1.aic(data)
        bics.append(bic1)
        aics.append(aic1)
        comps.append(i)
    if len(comps) > 1:
        # kn1 = KneeLocator(comps, bics, curve='convex', direction='decreasing')
        # kn2 = KneeLocator(comps, aics, curve='convex', direction='decreasing')
        # if kn1.knee and kn2.knee:
        #     n = int((kn1.knee + kn2.knee) / 2)
        # else:
        n = int((np.argmin(bics) + 1 + np.argmin(aics) + 1) / 2)
    return n

def lrts_comp_old(data):
    n = 0
    biggets_p = -1 * np.infty
    comp_biggest = 0
    max_comp = 10
    if len(data) < max_comp:
        max_comp = len(data)
    for i in range(1, max_comp + 1, 1):
        gm1 = GaussianMixture(n_components=i, random_state=0)
        gm2 = GaussianMixture(n_components=i + 1, random_state=0)
        gm1.fit(data)
        ll1 = np.mean(gm1.score_samples(data))
        gm2.fit(data)
        ll2 = np.mean(gm2.score_samples(data))
        LR = 2 * (ll2 - ll1)
        p = chi2.sf(LR, 1)
        if p > biggets_p:
            biggets_p = p
            comp_biggest = i
        n = comp_biggest
    return n


def component_old(data, columns, method):
    n = 1
    max_comp = 10
    x = []
    if data.shape[0] < max_comp:
        max_comp = data.shape[0]
    if len(columns) == 1:
        x = np.transpose([data[columns[0]].values])
    else:
        x = data[columns].values
    if method == 'aic':
        lowest_aic = np.infty
        comp_lowest = 0
        for i in range(1, max_comp + 1, 1):
            gm1 = GaussianMixture(n_components=i, random_state=0)
            gm1.fit(x)
            aic1 = gm1.aic(x)
            if aic1 < lowest_aic:
                lowest_aic = aic1
                comp_lowest = i
            n = comp_lowest

    if method == 'bic':
        lowest_bic = np.infty
        comp_lowest = 0
        for i in range(1, max_comp + 1, 1):
            gm1 = GaussianMixture(n_components=i, random_state=0)
            gm1.fit(x)
            bic1 = gm1.bic(x)
            if bic1 < lowest_bic:
                lowest_bic = bic1
                comp_lowest = i
            n = comp_lowest

    if method == 'LRTS':
        n = lrts_comp_old(x)
    if method == 'quantile':
        biggest_p = -1 * np.infty
        comp_biggest = 0
        for i in range(1, max_comp, 1):
            vals, q = theoretical_quantile(x, i)
            dist = sum_dist(x, vals, q)
            p = probability_mix(dist, vals, q)
            if p > biggest_p:
                biggest_p = p
                comp_biggest = i
        n = comp_biggest
    return n


coef095 = [13.5, 43.5, 73.25, 101.25, 133.5, 161.75, 198.0, 217.25, 249.25, 275.25]
intercept095 = [-7.499999999999993,
 -29.66666666666662,
 -39.666666666666615,
 -56.49999999999994,
 -76.33333333333329,
 -78.33333333333329,
 -105.49999999999989,
 -94.99999999999994,
 -113.66666666666663,
 -92.49999999999977]

def func_for_ndim (n_dim):
    Zpred095 = []
    for j in range(10):
        Zpred095.append(n_dim*coef095[j] + intercept095[j])
    return Zpred095
def sample_n_comp (size, Z):
    m095 = LinearRegression().fit(np.transpose([Z]), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    return round(m095.predict([[size]])[0])