"""This module estimates supervised model to predict sentiment."""

import os      # change folder
import pickle

import pandas as pd
import numpy as np

from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer

from sklearn.model_selection import KFold
from sklearn.model_selection import cross_val_score

# svm
from sklearn.linear_model import SGDClassifier

# grid search
from sklearn.model_selection import GridSearchCV
from pprint import pprint
from time import time

# set directory
direct = "/"

# functions


def tokenize(txt):
    """Tokenize by whitespace."""
    return txt.split()


def scores(row):
    """Map textual sentiment categories to numbers in pandas df."""
    if row["cla"] == "neutral":
        val = 0
    elif row["cla"] == "positive":
        val = 1
    else:
        val = -1

    return val


def accuracy(pred, actual):
    """Calculate accuracy of predictions."""
    return sum(pred == actual) / len(pred)


# Note: Modified to allow for upsampling, keep original data give indices.
# stackoverflow.com/questions/23455728/scikit-learn-balanced-subsampling

def balanced_subsample(x, y, subsample_size = 1.0, set_seed = None):
    """Create a balanced subsample with upsampling."""
    x = np.asarray(x)
    y = np.asarray(y)
    if set_seed is None:
        np.random.seed()
    else:
        np.random.seed(set_seed)

    class_xs = []
    max_elems = None
    ix = np.asarray(list(range(0, len(x))))
    for yi in np.unique(y):
        indx = ix[(y == yi)]
        elems = x[(y == yi)]
        class_xs.append((yi, elems, indx))
        if max_elems is None or elems.shape[0] > max_elems:
            max_elems = elems.shape[0]

    use_elems = max_elems
    if subsample_size < 1:
        use_elems = int(max_elems * subsample_size)

    xs = []
    ys = []
    xx = []

    for ci, this_xs, ix in class_xs:
        n_xs = len(this_xs)
        ix2 = list(range(0, n_xs))
        if n_xs < use_elems:
            diff = use_elems - n_xs
            extr = np.random.choice(ix2, size = diff, replace = True)
            ix = np.append(ix, [ix[i] for i in extr])
            ix2 = np.append(ix2, extr)
            this_xs = [this_xs[i] for i in ix2]

        x_ = this_xs[:use_elems]
        y_ = np.empty(use_elems)
        y_.fill(ci)

        xs.append(x_)
        ys.append(y_)
        xx.append(ix)

    xs = np.concatenate(xs)
    ys = np.concatenate(ys)
    xx = np.concatenate(xx)

    xs = list(xs)
    ys = list(ys)
    xx = list(xx)

    ys = [int(i) for i in ys]

    return xs, ys, xx


def indexer(index1, index2):
    """Return indexed elements of variable."""
    return [index1[i] for i in index2]


def cver(y, x, splits, seed):
    """Stratified k-fold crossvalidation with upsampling."""
        kf = KFold(n_splits = splits, shuffle = True, 
               random_state = seed)

    ind = np.array(list(range(0, len(x))))

    ind_train, ind_test = [], []
    x_train, x_test = [], []
    y_train, y_test = [], []

    for train_set, test_set in kf.split(x):
        x_train.append(x[train_set])
        x_test.append(x[test_set])
        y_train.append(y[train_set])
        y_test.append(y[test_set])
        ind_train.append(ind[train_set])
        ind_test.append(ind[test_set])

    ind_train_tmp, ind_test_tmp = [], []

    # Upsample
    for i in range(0, len(x_train)):
        bal_res = balanced_subsample(x_train[i], y_train[i], set_seed = seed)
        x_train[i] = bal_res[0]
        y_train[i] = bal_res[1]
        ind_train_tmp.append(bal_res[2])

    for i in range(0, len(x_test)):
        bal_res = balanced_subsample(x_test[i], y_test[i], set_seed = seed)
        x_test[i] = bal_res[0]
        y_test[i] = bal_res[1]
        ind_test_tmp.append(bal_res[2])

    # Indices
    custom_cv = []
    for i in range(0, len(ind_train)):
        train_indices = np.array(indexer(list(ind_train[i]), ind_train_tmp[i]))
        test_indices = np.array(indexer(list(ind_test[i]), ind_test_tmp[i]))
        custom_cv.append((train_indices, test_indices))

    return custom_cv


def cv_pred(x, y, custom_cv, piper, unique_y = True):
    """Predict value of model fitted by using cver fct."""
    sub_y = []
    sub_preds = []
    sub_score = []

    for i in range(0, len(custom_cv)):
        train_ind = custom_cv[i][0]
        test_ind = custom_cv[i][1]

        if unique_y is True:
            test_ind = list(set(test_ind))

        x_train_sub = [x[i] for i in train_ind]
        y_train_sub = [y[i] for i in train_ind]

        x_test_sub = [x[i] for i in test_ind]
        y_test_sub = [y[i] for i in test_ind]

        results_sub = piper.fit(x_train_sub, y_train_sub)

        sub_y.extend(y_test_sub)
        sub_preds.extend(results_sub.predict(x_test_sub))
        sub_score.append(results_sub.score(x_test_sub, y_test_sub))

    return sub_score, sub_y, sub_preds


# data

# change directory
os.chdir(direct + "data/financial_phrase_bank")

# load phrasebank
phrasebank = pickle.load(open("lem_Sentences_66Agree.p", "rb"))

sentences = pd.Series(phrasebank[0])
classif = pd.Series(phrasebank[1])
ident = pd.Series(range(0, len(classif)))

df = pd.DataFrame({"lemma": sentences,
                   "cla": classif,
                   "ident": ident,
                   })

df["sentiment"] = df.apply(scores, axis = 1)


# setup
seed = 123
splits = 5

# CountVectorizer
stop_words = (None, 'english')
max_df = (0.85, 0.90, 0.95, 1.0)
min_df = (0.00, 0.01, 0.05, 0.1)
ngram_range = ((1, 1), (1, 2))
sublinear_tf = (True, False)

# TfidfTransformer
use_idf = (True, False)
norm = ('l1', 'l2')

# SGDClassifier
alpha = (0.005, 0.001, 0.0005, 0.0001, 0.00005, 0.00001, 0.000005, 0.000001)
loss = ('hinge', 'log', 'squared_hinge', 'perceptron')
penalty = (None, 'l1', 'l2', 'elasticnet')

# obtain cross validation set
lem = df["lemma"]
sco = df["sentiment"]

custom_cv = cver(sco, lem, splits, seed)

piper = Pipeline([("vect", CountVectorizer(tokenizer = tokenize)),
                  ("tfidf", TfidfTransformer()),
                  ("clf", SGDClassifier(shuffle = True,
                                        max_iter = 80,
                                        random_state = seed)),
                  ])


parameters = {'vect__ngram_range': ngram_range,
              'vect__stop_words': stop_words,
              'vect__max_df': max_df,
              'vect__min_df': min_df,
              'tfidf__sublinear_tf': sublinear_tf,
              'tfidf__use_idf': use_idf,
              'tfidf__norm': norm,
              'clf__alpha': alpha,
              'clf__penalty': penalty,
              'clf__loss': loss,
              }

grid_search = GridSearchCV(piper, parameters, n_jobs= 7, verbose = 1,
                           refit = True, cv = custom_cv)

print("Performing grid search...")
print("pipeline:", [name for name, _ in piper.steps])
print("parameters:")
pprint(parameters)
t0 = time()
grid_search.fit(lem, sco)
print("done in %0.3fs" % (time() - t0))
print()

print("Best score: %0.3f" % grid_search.best_score_)
print("Best parameters set:")
best_parameters = grid_search.best_estimator_.get_params()
for param_name in sorted(parameters.keys()):
    print("\t%s: %r" % (param_name, best_parameters[param_name]))


# set pipeline to best model from grid search
piper = grid_search.best_estimator_

# save best parameters
os.chdir(direct + "output/model")
pickle.dump(piper, open("best_parameter_grid.p", "wb"))

# crossvalidation
results = cross_val_score(piper, lem, sco, cv = custom_cv)
print(results)
print("Accuracy: " + str(results.mean()))


# Re-estimate winning model
print("Unique observations")
sub_score, sub_y, sub_preds = cv_pred(lem, sco, custom_cv, piper,
                                      unique_y = False)
print("Accuracy: " + str(sum(sub_score) / len(sub_score)))


print(pd.crosstab(pd.Series(sub_y), pd.Series(sub_preds), rownames = ["True"],
                  colnames = ["Predicted"], margins = True))

print("\n \n")
# Re-estimate winning model on same cv sample and predict
sub_score, sub_y, sub_preds = cv_pred(lem, sco, custom_cv, piper,
                                      unique_y = True)
print("Upsampled observations")
print("Accuracy: " + str(sum(sub_score) / len(sub_score)))


print(pd.crosstab(pd.Series(sub_y), pd.Series(sub_preds), rownames = ["True"],
                  colnames = ["Predicted"], margins = True))
