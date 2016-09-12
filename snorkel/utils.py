import re
import sys
import numpy as np
import scipy.sparse as sparse
import random
from .models import Corpus



class ProgressBar(object):
    def __init__(self, N, length=40):
        self.N      = N
        self.nf     = float(N)
        self.length = length

    def bar(self, i):
        """Assumes i ranges through [0, N-1]"""
        b = np.ceil(((i+1) / self.nf) * self.length)
        sys.stdout.write("\r[%s%s] %d%%" % ("="*b, " "*(self.length-b), 100*((i+1) / self.nf)))
        sys.stdout.flush()

    def close(self):
        sys.stdout.write("\n\n")
        sys.stdout.flush()


def get_ORM_instance(ORM_class, session, instance):
    """
    Given an ORM class and *either an instance of this class, or the name attribute of an instance
    of this class*, return the instance
    """
    if isinstance(instance, str):
        return session.query(ORM_class).filter(ORM_class.name == instance).one()
    else:
        return instance


def camel_to_under(name):
    """
    Converts camel-case string to lowercase string separated by underscores.

    Written by epost
    (http://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-snake-case).

    :param name: String to be converted
    :return: new String with camel-case converted to lowercase, underscored
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def sparse_abs(X):
    """Element-wise absolute value of sparse matrix- avoids casting to dense matrix!"""
    X_abs = X.copy()
    if not sparse.issparse(X):
        return abs(X_abs)
    if sparse.isspmatrix_csr(X) or sparse.isspmatrix_csc(X):
        X_abs.data = np.abs(X_abs.data)
    elif sparse.isspmatrix_lil(X):
        X_abs.data = np.array([np.abs(L) for L in X_abs.data])
    else:
        raise ValueError("Only supports CSR/CSC and LIL matrices")
    return X_abs


def matrix_coverage(L):
    """
    Given an N x M matrix where L_{i,j} is the label given by the jth LF to the ith candidate:
    Return the **fraction of candidates that each LF labels.**
    """
    return np.ravel(sparse_abs(L).sum(axis=0) / float(L.shape[0]))


def matrix_overlaps(L):
    """
    Given an N x M matrix where L_{i,j} is the label given by the jth LF to the ith candidate:
    Return the **fraction of candidates that each LF _overlaps with other LFs on_.**
    """
    L_abs = sparse_abs(L)
    return np.ravel(np.where(L_abs.sum(axis=1) > 1, 1, 0).T * L_abs / float(L.shape[0]))


def matrix_conflicts(L):
    """
    Given an N x M matrix where L_{i,j} is the label given by the jth LF to the ith candidate:
    Return the **fraction of candidates that each LF _conflicts with other LFs on_.**
    """
    L_abs = sparse_abs(L)
    return np.ravel(np.where(L_abs.sum(axis=1) != sparse_abs(L.sum(axis=1)), 1, 0).T * L_abs / float(L.shape[0]))


def get_as_dict(x):
    """Return an object as a dictionary of its attributes"""
    if isinstance(x, dict):
        return x
    else:
        try:
            return x._asdict()
        except AttributeError:
            return x.__dict__


def sort_X_on_Y(X, Y):
    return [x for (y,x) in sorted(zip(Y,X), key=lambda t : t[0])]


def corenlp_cleaner(words):
  d = {'-RRB-': ')', '-LRB-': '(', '-RCB-': '}', '-LCB-': '{',
       '-RSB-': ']', '-LSB-': '['}
  return map(lambda w: d[w] if w in d else w, words)


def split_corpus(session, corpus, train=0.8, development=0.1, test=0.1, seed=None):
    if train + development + test != 1:
        raise ValueError("Values for train + development + test must sum to 1")
   
    random.seed(seed)
    docs = [doc for doc in corpus.documents]
    docs.sort(key=lambda d: d.name)
    random.shuffle(docs)        

    n = len(docs)
    num_train = int(train * n)
    num_development = int(development * n)

    train_corpus = Corpus(name=corpus.name + ' Training')
    for doc in docs[:num_train]:
        train_corpus.append(doc)
    session.add(train_corpus)
    print "%d Documents added to corpus %s" % (len(train_corpus), train_corpus.name)

    development_corpus = Corpus(name=corpus.name + ' Development')
    for doc in docs[num_train:num_train + num_development]:
        development_corpus.append(doc)
    session.add(development_corpus)
    print "%d Documents added to corpus %s" % (len(development_corpus), development_corpus.name)

    test_corpus = Corpus(name=corpus.name + ' Test')
    for doc in docs[num_train + num_development:]:
        test_corpus.append(doc)
    session.add(test_corpus)
    print "%d Documents added to corpus %s" % (len(test_corpus), test_corpus.name)

    session.commit()


def tokens_to_ngrams(tokens, n_max=3, delim=' '):
    N = len(tokens)
    for root in range(N):
        for n in range(min(n_max, N - root)):
            yield delim.join(tokens[root:root+n+1])