from sklearn import linear_model
from sklearn.metrics import mean_squared_error as mse
from concurrent.futures import ThreadPoolExecutor
from pomegranate import DiscreteDistribution, ConditionalProbabilityTable
from Utils.MathUtils import *
from gmr import GMM
from pandas import DataFrame


import itertools
import random


class BaseNode(object):
    """
    Base class for nodes.
    """
    def __init__(self, name):
        """
        :param name: name for node (taken from column name)
        type: node type
        disc_parents: list with discrete parents
        cont_parents: list with continuous parents
        children: node's children
        """
        self.name = name
        self.type = 'abstract'

        self.disc_parents = None
        self.cont_parents = None
        self.children = None

    def __repr__(self):
        return f"{self.name}"


class DiscreteNode(BaseNode):
    def __init__(self, name):
        super(DiscreteNode, self).__init__(name)
        self.type = 'Discrete'

    def fit_parameters(self, data: DataFrame) -> dict:
        """
        Method returns probas dict with following format {[<combinations>: value]}
        and vals, list of appeared values in combinations
        """
        def worker(node):
            parents = node.disc_parents + node.cont_parents
            if not parents:
                dist = DiscreteDistribution.from_samples(data[node.name].values)
                cprob = list(dict(sorted(dist.items())).values())
                vals = sorted([str(x) for x in list(dist.parameters[0].keys())])
            else:
                dist = DiscreteDistribution.from_samples(data[node.name].values)
                vals = sorted([str(x) for x in list(dist.parameters[0].keys())])
                dist = ConditionalProbabilityTable.from_samples(data[parents + [node.name]].values)
                params = dist.parameters[0]
                cprob = dict()
                for i in range(0, len(params), len(vals)):
                    probs = []
                    for j in range(i, (i + len(vals))):
                        probs.append(params[j][-1])
                    combination = [str(x) for x in params[i][0:len(parents)]]
                    cprob[str(combination)] = probs
            return {"cprob": cprob, 'vals': vals}

        pool = ThreadPoolExecutor(3)
        future = pool.submit(worker, self)
        return future.result()

    def choose(self, node_info: dict, pvals: list) -> str:
        """
        Return value from discrete node
        params:
        node_info: nodes info from distributions
        pvals: parent values
        """
        rindex = 0
        random.seed()
        vals = node_info['vals']
        if not pvals:
            dist = node_info['cprob']
        else:
            dist = node_info['cprob'][str(pvals)]
        lbound = 0
        ubound = 0
        rand = random.random()
        for interval in range(len(dist)):
            ubound += dist[interval]
            if lbound <= rand < ubound:
                rindex = interval
                break
            else:
                lbound = ubound

        return vals[rindex]


class GaussianNode(BaseNode):
    def __init__(self, name: str, model=linear_model.LinearRegression()):
        super(GaussianNode, self).__init__(name)
        self.model = model
        self.type = 'Gaussian'

    def fit_parameters(self, data: DataFrame) -> dict:
        """
        """
        parents = self.disc_parents + self.cont_parents
        if parents:
            # model = self.model
            predict = []
            if len(parents) == 1:
                self.model.fit(np.transpose([data[parents[0]].values]), data[self.name].values)
                predict = self.model.predict(np.transpose([data[parents[0]].values]))
            else:
                self.model.fit(data[parents].values, data[self.name].values)
                predict = self.model.predict(data[parents].values)
            variance = mse(data[self.name].values, predict)
            return {"mean": self.model.intercept_,
                    "coef": list(self.model.coef_),
                    "variance": variance}
        else:
            mean_base = np.mean(data[self.name].values)
            self.model.intercept_ = mean_base
            self.model.coef_ = np.array([])
            variance = np.var(data[self.name].values)
            return {"mean": mean_base,
                    "coef": [],
                    "variance": variance}

    def choose(self, node_info, pvals: list) -> float:
        """
        Return value from Gaussian node
        params:
        node: node
        pvals: parent values
        """
        # mean = node_info["mean"]
        mean = self.model.intercept_
        if pvals:
            for m in pvals:
                mean += m * self.model.coef_[0]
        variance = node_info['variance']
        # distribution = [mean, variance]
        return random.gauss(mean, math.sqrt(variance))


class ConditionalGaussianNode(BaseNode):
    def __init__(self, name):
        super(ConditionalGaussianNode, self).__init__(name)
        self.type = 'ConditionalGaussian'

    def fit_parameters(self, data: DataFrame) -> dict:
        hycprob = dict()
        values = []
        combinations = []
        for d_p in self.disc_parents:
            values.append(np.unique(data[d_p].values))
        for xs in itertools.product(*values):
            combinations.append(list(xs))
        for comb in combinations:
            mask = np.full(len(data), True)
            for col, val in zip(self.disc_parents, comb):
                mask = (mask) & (data[col] == val)
            new_data = data[mask]
            mean_base = np.nan
            variance = np.nan
            key_comb = [str(x) for x in comb]
            if new_data.shape[0] != 0:
                if self.cont_parents:
                    model = linear_model.LinearRegression()
                    if len(self.cont_parents) == 1:
                        model.fit(np.transpose([new_data[self.cont_parents[0]].values]), new_data[self.name].values)
                        predict = model.predict(np.transpose([new_data[self.cont_parents[0]].values]))
                    else:
                        model.fit(new_data[self.cont_parents].values, new_data[self.name].values)
                        predict = model.predict(new_data[self.cont_parents].values)
                    mean_base = model.intercept_
                    variance = mse(new_data[self.name].values, predict)
                    hycprob[str(key_comb)] = {'variance': variance, 'mean': mean_base,
                                              'coef': list(model.coef_)}
                else:
                    mean_base = np.mean(new_data[self.name].values)
                    variance = np.var(new_data[self.name].values)
                    hycprob[str(key_comb)] = {'variance': variance, 'mean': mean_base, 'coef': []}
            else:
                if self.cont_parents:
                    scal = list(np.full(len(self.cont_parents), np.nan))
                    hycprob[str(key_comb)] = {'variance': variance, 'mean': mean_base, 'coef': scal}
                else:
                    # mean_base = np.nan
                    # variance = np.nan
                    hycprob[str(key_comb)] = {'variance': variance, 'mean': mean_base, 'coef': []}
        return {"hybcprob": hycprob}

    def choose(self, node_info: dict, pvals: list) -> float:
        """
        Return value from ConditionalGaussian node
        params:
        node_info: nodes info from distributions
        pvals: parent values
        """
        dispvals = []
        lgpvals = []
        for pval in pvals:
            if ((isinstance(pval, str)) | ((isinstance(pval, int)))):
                dispvals.append(pval)
            else:
                lgpvals.append(pval)
        lgdistribution = node_info["hybcprob"][str(dispvals)]
        mean = lgdistribution["mean"]
        if lgpvals:
            for x in range(len(lgpvals)):
                mean += lgpvals[x] * lgdistribution["coef"][x]
        variance = lgdistribution["variance"]
        return random.gauss(mean, math.sqrt(variance))


class MixtureGaussianNode(BaseNode):
    def __init__(self, name):
        super(MixtureGaussianNode, self).__init__(name)
        self.type = 'MixtureGaussian'

    def fit_parameters(self, data: DataFrame) -> dict:
        parents = self.disc_parents + self.cont_parents
        if not parents:
            n_comp = int((component(data, [self.name], 'aic') + component(data, [self.name],
                                                                          'bic')) / 2)  # component(data, [node], 'LRTS')#
            # n_comp = 3
            gmm = GMM(n_components=n_comp)
            gmm.from_samples(np.transpose([data[self.name].values]))
            means = gmm.means.tolist()
            cov = gmm.covariances.tolist()
            # weigts = np.transpose(gmm.to_responsibilities(np.transpose([data[node].values])))
            w = gmm.priors.tolist()  # []
            # for row in weigts:
            #     w.append(np.mean(row))
            return {"mean": means, "coef": w, "covars": cov}
        if parents:
            if not self.disc_parents and self.cont_parents:
                nodes = [self.name] + self.cont_parents
                new_data = data[nodes]
                new_data.reset_index(inplace=True, drop=True)
                n_comp = int((component(new_data, nodes, 'aic') + component(new_data, nodes,
                                                                            'bic')) / 2)  # component(new_data, nodes, 'LRTS')#
                # n_comp = 3
                gmm = GMM(n_components=n_comp)
                gmm.from_samples(new_data[nodes].values)
                means = gmm.means.tolist()
                cov = gmm.covariances.tolist()
                # weigts = np.transpose(gmm.to_responsibilities(new_data[nodes].values))
                w = gmm.priors.tolist()  # []
                # for row in weigts:
                #     w.append(np.mean(row))
                return {"mean": means,
                        "coef": w,
                        "covars": cov}

    def choose(self, node_info: dict, pvals: list):
        """
        Return value from MixtureGaussian node
        params:
        node_info: nodes info from distributions
        pvals: parent values
        """
        mean = node_info["mean"]
        covariance = node_info["covars"]
        w = node_info["coef"]
        n_comp = len(node_info['coef'])
        if n_comp != 0:
            if pvals:
                indexes = [i for i in range(1, len(pvals) + 1)]
                if not np.isnan(np.array(pvals)).all():
                    gmm = GMM(n_components=n_comp, priors=w, means=mean, covariances=covariance)
                    sample = gmm.predict(indexes, [pvals])[0][0]
                else:
                    sample = np.nan
            else:
                gmm = GMM(n_components=n_comp, priors=w, means=mean, covariances=covariance)
                sample = gmm.sample(1)[0][0]
        else:
            sample = np.nan
        return sample


class ConditionalMixtureGaussianNode(BaseNode):
    def __init__(self, name):
        super(ConditionalMixtureGaussianNode, self).__init__(name)
        self.type = 'ConditionalMixtureGaussian'

    def fit_parameters(self, data: DataFrame) -> dict:
        hycprob = dict()
        values = []
        combinations = []
        for d_p in self.disc_parents:
            values.append(np.unique(data[d_p].values))
        for xs in itertools.product(*values):
            combinations.append(list(xs))
        for comb in combinations:
            mask = np.full(len(data), True)
            for col, val in zip(self.disc_parents, comb):
                mask = (mask) & (data[col] == val)
            new_data = data[mask]
            new_data.reset_index(inplace=True, drop=True)
            key_comb = [str(x) for x in comb]
            nodes = [self.name] + self.cont_parents
            if new_data.shape[0] > 5:
                if self.cont_parents:
                    n_comp = int((component(new_data, nodes, 'aic') + component(new_data, nodes,
                                                                                'bic')) / 2)  # component(new_data, nodes, 'LRTS')#int((component(new_data, nodes, 'aic') + component(new_data, nodes, 'bic')) / 2)
                    # n_comp = 3
                    gmm = GMM(n_components=n_comp)
                    gmm.from_samples(new_data[nodes].values)
                else:
                    n_comp = int((component(new_data, [self.name], 'aic') + component(new_data, [self.name],
                                                                                      'bic')) / 2)  # component(new_data, [node], 'LRTS')#int((component(new_data, [node], 'aic') + component(new_data, [node], 'bic')) / 2)
                    # n_comp = 3
                    gmm = GMM(n_components=n_comp)
                    gmm.from_samples(np.transpose([new_data[self.name].values]))
                means = gmm.means.tolist()
                cov = gmm.covariances.tolist()
                # weigts = np.transpose(gmm.to_responsibilities(np.transpose([new_data[node].values])))
                w = gmm.priors.tolist()  # []
                # for row in weigts:
                #     w.append(np.mean(row))
                hycprob[str(key_comb)] = {'covars': cov, 'mean': means, 'coef': w}
            elif new_data.shape[0] != 0:
                n_comp = 1
                gmm = GMM(n_components=n_comp)
                if self.cont_parents:
                    gmm.from_samples(new_data[nodes].values)
                else:
                    gmm.from_samples(np.transpose([new_data[self.name].values]))
                means = gmm.means.tolist()
                cov = gmm.covariances.tolist()
                # weigts = np.transpose(gmm.to_responsibilities(np.transpose([new_data[node].values])))
                w = gmm.priors.tolist()  # []
                # for row in weigts:
                #     w.append(np.mean(row))
                hycprob[str(key_comb)] = {'covars': cov, 'mean': means, 'coef': w}
            else:
                if self.cont_parents:
                    hycprob[str(key_comb)] = {'covars': np.nan, 'mean': np.nan, 'coef': []}
                else:
                    hycprob[str(key_comb)] = {'covars': np.nan, 'mean': np.nan, 'coef': []}
        return {"hybcprob": hycprob}

    def choose(self, node_info: dict, pvals: list) -> float:
        """
        Return value from ConditionalMixtureGaussian node
        params:
        node_info: nodes info from distributions
        pvals: parent values
        """
        dispvals = []
        lgpvals = []
        for pval in pvals:
            if ((isinstance(pval, str)) | ((isinstance(pval, int)))):
                dispvals.append(pval)
            else:
                lgpvals.append(pval)
        lgdistribution = node_info["hybcprob"][str(dispvals)]
        mean = lgdistribution["mean"]
        covariance = lgdistribution["covars"]
        w = lgdistribution["coef"]
        if len(w) != 0:
            if len(lgpvals) != 0:
                indexes = [i for i in range(1, (len(lgpvals) + 1), 1)]
                if not np.isnan(np.array(lgpvals)).all():
                    n_comp = len(w)
                    gmm = GMM(n_components=n_comp, priors=w, means=mean, covariances=covariance)
                    sample = gmm.predict(indexes, [lgpvals])[0][0]
                else:
                    sample = np.nan
            else:
                n_comp = len(w)
                gmm = GMM(n_components=n_comp, priors=w, means=mean, covariances=covariance)
                sample = gmm.sample(1)[0][0]
        else:
            sample = np.nan
        return sample


class LogitNode(DiscreteNode):
    def __init__(self, name, classifier=None):
        super(LogitNode, self).__init__(name)
        if classifier is None:
            classifier = linear_model.LogisticRegression(multi_class='multinomial', solver='newton-cg', max_iter=100)
        self.classifier = classifier
        self.type = 'Logit' + f" ({type(self.classifier).__name__})"

    def fit_parameters(self, data: DataFrame) -> dict:
        parents = self.disc_parents + self.cont_parents
        model = self.classifier.fit(data[parents].values, data[self.name].values)

        return {'classes': list(model.classes_),
                'classifier_ojb': None,
                'classifier': type(self.classifier).__name__}

    def choose(self, node_info: dict, pvals: list) -> str:
        """
        Return value from Logit node
        params:
        node_info: nodes info from distributions
        pvals: parent values
        """
        pvals = [str(p) for p in pvals]

        model = self.classifier

        if len(node_info["classes"]) > 1:
            distribution = model.predict_proba(np.array(pvals).reshape(1, -1))[0]

            # choose
            rand = random.random()
            lbound = 0
            ubound = 0
            for interval in range(len(node_info["classes"])):
                ubound += distribution[interval]
                if (lbound <= rand and rand < ubound):
                    rindex = interval
                    break
                else:
                    lbound = ubound

            return str(node_info["classes"][rindex])

        else:
            return str(node_info["classes"][0])


class ConditionalLogitNode(DiscreteNode):
    def __init__(self, name, classifier=None):
        super(ConditionalLogitNode, self).__init__(name)
        if classifier is None:
            classifier = linear_model.LogisticRegression(multi_class='multinomial', solver='newton-cg', max_iter=100)
        self.classifier = classifier
        self.type = 'ConditionalLogit' + f" ({type(self.classifier).__name__})"

    def fit_parameters(self, data: DataFrame) -> dict:
        hycprob = dict()
        values = []
        combinations = []
        for d_p in self.disc_parents:
            values.append(np.unique(data[d_p].values))
        for xs in itertools.product(*values):
            combinations.append(list(xs))
        for comb in combinations:
            mask = np.full(len(data), True)
            for col, val in zip(self.disc_parents, comb):
                mask = (mask) & (data[col] == val)
            new_data = data[mask]
            mean_base = [np.nan]
            classes = []
            key_comb = [str(x) for x in comb]
            if new_data.shape[0] != 0:
                model = self.classifier
                values = set(new_data[self.name])
                if len(values) > 1:
                    model.fit(new_data[self.cont_parents].values, new_data[self.name].values)
                    classes = model.classes_
                else:
                    classes = list(values)
                hycprob[str(key_comb)] = {'classes': list(classes)}
            else:
                scal = list(np.full(len(self.cont_parents), np.nan))
                hycprob[str(key_comb)] = {'classes': list(classes)}
        return {"hybcprob": hycprob}

    def choose(self, node_info: dict, pvals: list) -> str:
        """
        Return value from ConditionalLogit node
        params:
        node_info: nodes info from distributions
        pvals: parent values
        """
        dispvals = []
        lgpvals = []
        for pval in pvals:
            if (isinstance(pval, str)):
                dispvals.append(pval)
            else:
                lgpvals.append(pval)
        lgdistribution = node_info["hybcprob"][str(dispvals)]

        model = self.classifier

        if len(lgdistribution["classes"]) > 1:
            distribution = model.predict_proba(np.array(lgpvals).reshape(1, -1))[0]

            rand = random.random()
            rindex=0
            lbound = 0
            ubound = 0
            for interval in range(len(lgdistribution["classes"])):
                ubound += distribution[interval]
                if (lbound <= rand and rand < ubound):
                    rindex = interval
                    break
                else:
                    lbound = ubound
            return str(lgdistribution["classes"][rindex])

        else:
            return str(lgdistribution["classes"][0])
