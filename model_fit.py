'''
Contains methods to fit gene expression to mixed gaussian model as per the paper
'''

import timeit
import numpy as np

import matplotlib.pyplot as plt
from scipy.stats import norm
from db_setup import read_dumped_data
from sklearn.mixture import GMM

import gaussian_sampling
import pickle

#for pickle formatting
from process_BC_data import sample
from process_BC_data import expression_profile
from process_BC_data import clinical_data

'''
x should data points of the intensity of the gene in question
y should be the corresponding class of each sample, supports only binary 1 and 0 for now

plot = boolean value whether to plot the resulting classifier's frequency curve
title = title of graph to plot

no test/train split since this is a clustering model

returns the trained model
'''
def fit_test_model(x):
    gauss_model = GMM(n_components=2, n_init=5, n_iter=1000)
    gauss_model.fit(x)

    return gauss_model

'''
Given a gauss mix model, prints parameters for each seperate peak
'''
def print_model_params(gauss_model):
    coeffs = gauss_model.weights_
    mus = [x[0] for x in gauss_model.means_]
    sigmas = [x[0] for x in gauss_model.covars_]

    string = ("Gaussian model: " + str(gauss_model)) + '\n'
    string += ("Coeff:\t" + str(coeffs)) + '\n'
    string += ("Mus:\t" + str(mus)) + '\n'
    string += ("Sigmas:\t" + str(sigmas)) + '\n'

    print(string)

'''
prints out information how the given model clusters and classified real data
Assuems 1D features
'''
def print_test_model(x, Y, gauss_model):
    Y_h = gauss_model.predict(x)

    tp = 0
    fp = 0
    tn = 0
    fn = 0
    for i in range(0, len(Y)):
        if Y[i] == 1 and Y_h[i] == 1:
            tp += 1
        elif Y[i] == 1 and Y_h[i] == 0:
            fn += 1
        elif Y[i] == 0 and Y_h[i] == 0:
            tn += 1
        elif Y[i] == 0 and Y_h[i] == 1:
            fp += 1

    tab = "\t\t\t\t"
    print(tab + tab + "Actual")
    print(tab + tab + "Positive" + tab + "Negative")
    print("Predicted Positive" + tab + str(tp) + tab + str(fp))
    print("Predicted Negative" + tab + str(fn) + tab + str(tn))

'''
Dumps dictionary key : value where key = gene name, value = bayesian mixed model with 2 peaks
'''
def dump_trained_models(file):
    print("Training model for every gene...")
    genes = []
    for gene_sample in read_dumped_data("BC_gene_profiles.pkl"):
        genes.append(gene_sample)

    i = 0
    models = {}
    for i in range(0, len(genes)):
        gene = genes[i]
        intensities = [[x] for x in gene.intensities]
        model = fit_test_model(intensities)

        models[gene.name] = model
        i += 1
        if i % 100 == 0:
            print("Finished model #" + str(i))

    pickle.dump(models, open(file, 'wb'))

if __name__ == "__main__":
    dict = pickle.load(open("BC_trained_models.pkl", 'rb'))

    gauss_model = dict["ERBB2"]
    coeffs = gauss_model.weights_
    mus = [x[0] for x in gauss_model.means_]
    sigmas = [x[0] for x in gauss_model.covars_]

    num_samples = [10000, 10000]
    gaussian_sampling.plot_multidist(num_samples, mus, sigmas, coeffs, "Combined.png")

    #def plot_multidist(num_samples, mus, sigmas, coeffs, title, values):