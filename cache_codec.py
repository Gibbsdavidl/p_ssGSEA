'''
This module handles caching and uncaching of data using pickle.

In the future, it might be prudent to use a less memory intensive object serialization method like hdf5.

Furthermore, caching (to minimize read-writes) is currently done through a lru policy with a size of 16. A size of 1
is more appropriate for most of the applications.
'''

import os
import pickle
import sqlite3
from data_models import *
from functools import lru_cache

class counter():
    '''
    This class is a simple counter which can increment and return a count, initially set to 0.
    This is used for keeping track of progress of the various tasks going on.
    '''

    def __init__(self):
        self.i = 0

    def count(self):
        self.i += 1
        return str(self.i)

    def __str__(self):
        return str(self.i)

#DEFINE NEW DATASET ABBREVIATIONS HERE
DATASETS = {"BC"}

#CHange this to change the directory will data dumps will be stored and read from
DATA_DIR = os.getcwd() + "/Data/AppCache"

'''
****************************Downloading expression data****************************
'''

EXPRESSION_PROFILES_DIR = lambda dataset: DATA_DIR + "/" + dataset + "/"
'''Returns the path of the directory where the Expression profile lives'''

EXPRESSION_PROFILES_FILE = lambda dataset: EXPRESSION_PROFILES_DIR(dataset) +  dataset + "_SampleProfiles.pkl"
'''Returns the path used to cache/uncache expression profiles for the given dataset'''

EXPRESSION_PROFILE_DB = lambda dataset: DATA_DIR + "/" + dataset + "/" + dataset + "Expression.db"
'''Returns the path to the database for the given dataset'''

EXPRESSION_PROFILE_DBTABLE = lambda dataset: dataset + "_GeneExpression"
'''Returns the given table containing expression data in the proper database for the given dataset'''

def dump_sample_profiles(dataset):
    '''
    Queries the database of the given dataset and dumps a pickled file containing gene expression data. The pickled
    file will contain a dictionary mapping patient id's to a data_models.sample (sample profile).

    NOTE: remember to create the proper corresponding database for the dataset!!!

    :param dataset: the name of the dataset downloading data from
    :type dataset: str
    '''
    if not os.path.exists(EXPRESSION_PROFILES_DIR(dataset)):
        os.makedirs(EXPRESSION_PROFILES_DIR(dataset))

    cursor = sqlite3.connect(EXPRESSION_PROFILE_DB(dataset)).cursor()
    table = EXPRESSION_PROFILE_DBTABLE(dataset)

    #first get a list of all the unique ids
    cursor.execute("Select Distinct Sample From " + table)
    rows = cursor.fetchall()
    sample_nums = [row[0] for row in rows]

    count = counter()

    samples = {}
    for num in sample_nums:
        #get all gene profiles from each profile
        cursor.execute("Select Sample, Gene, Intensity From " + table + " WHERE Sample='%s' AND Gene != ''" % num)
        sample_profiles = cursor.fetchall()

        profiles = {}
        for profile in sample_profiles:
            id, gene, intensity = profile
            other_fields = {}

            profiles[gene] = (expression_profile(id, gene, intensity, other_fields))

        samples[num] = sample(profiles, num)
        print("\t\tCompleted profile: " + str(count.count()) + " out of " + str(len(sample_nums)))

    pickle.dump(samples, open(EXPRESSION_PROFILES_FILE(dataset), 'wb'), protocol=-1)

@lru_cache(maxsize=16)
def load_sample_profiles(dataset):
    '''
    Returns expression data for the dataset, caching information along the way.

    :param dataset: the name of the dataset downloading data from
    :type dataset: str

    :returns: a dict mapping patient id's to their sample profiles
    '''
    if os.path.exists(EXPRESSION_PROFILES_FILE(dataset)):
        print("\tOpenning cached expression data!")
        return pickle.load(open(EXPRESSION_PROFILES_FILE(dataset), 'rb'))

    print("\tCalculating expression data!")
    dump_sample_profiles(dataset)
    print("\tSaved expression data!")
    return load_sample_profiles(dataset)

'''
****************************Model fitting****************************
'''
from model_fit import get_trained_models
GENE_MODELS_DIR = lambda dataset: DATA_DIR + "/" + dataset + "/"
GENE_MODELS_FILE = lambda dataset: GENE_MODELS_DIR(dataset) + dataset + "_GMM_Models.pkl"
def dump_gene_models(dataset):
    '''
    Utilizing sample information, uses expression levels across samples for genes in order to train a GMM
    model for every gene. Ultimately dumps a dict of gene names to the GMM model for the gene. This will only
    train genes which appear in every gene_set!

    :param dataset: the name of the dataset downloading data from
    :type dataset: str
    '''

    if not os.path.exists(GENE_MODELS_DIR(dataset)):
        os.makedirs(GENE_MODELS_DIR(dataset))

    samples = load_sample_profiles(dataset)

    #map gene names -> list of expression intensities
    expressions = {}
    keys = [key for key in samples.keys()]
    genes = samples[keys[0]].profiles.keys()
    for gene in genes:
        expressions[gene] = []

    for id in samples.keys():
        sample = samples[id]
        for gene in sample.profiles.keys():
            if gene in genes:
                expressions[gene].append(sample.profiles[gene].intensity)

    models = get_trained_models(expressions)

    pickle.dump(models, open(GENE_MODELS_FILE(dataset), 'wb'), protocol=-1)

@lru_cache(maxsize=16)
def load_gene_models(dataset):
    '''
    Returns gene models of the dataset, caching information along the way.

    :param dataset: the name of the dataset downloading data from
    :type dataset: str

    :return: a dict mapping gene names to the trained model of the gene
    '''
    if os.path.exists(GENE_MODELS_FILE(dataset)):
        print("\tOpenning models!")
        return pickle.load(open(GENE_MODELS_FILE(dataset), 'rb'))

    print("\tCalculating GMM data!")
    dump_gene_models(dataset)
    print("\tSaving GMM data")
    return load_gene_models(dataset)

'''
****************************Gene popularity****************************
'''
GENE_SET_DB = DATA_DIR + "/GeneSets.db"
GENE_SET_GENE_TABLE = "GeneSet_Genes"
GENE_SET_URL_TABLE = "GeneSet_URL"

GENE_POPULARITY_DIR = lambda dataset: DATA_DIR + "/" + dataset + "/"
'''The directory where gene populairty file lives'''
GENE_POPULARITY_FILE = lambda dataset: GENE_POPULARITY_DIR(dataset) + dataset + "_GenePopularity.pkl"
'''Returns the path used to cache/uncache gene popularity for the given dataset'''

def dump_gene_popularity(dataset):
    '''
    Queries the database of the given dataset and dumps a pickled file containing gene popularity data. The pickled
    file will contain a dictionary mapping gene name to popularity score

    :param dataset: the name of the dataset downloading data from
    :type dataset: str
    '''

    if not os.path.exists(GENE_POPULARITY_DIR(dataset)):
        os.makedirs(GENE_POPULARITY_DIR(dataset))

    #get all genes in the dataset
    cursor = sqlite3.connect(EXPRESSION_PROFILE_DB(dataset)).cursor()
    table = EXPRESSION_PROFILE_DBTABLE(dataset)
    cursor.execute("Select Distinct Gene From " + table)
    rows = cursor.fetchall()
    cursor.close()

    gene_names = [row[0] for row in rows]

    #then query gene set db for popularity
    count = counter()
    cursor = sqlite3.connect(GENE_SET_DB).cursor()
    gene_pop = {}
    for names in gene_names:
        cursor.execute("Select GeneSet From " + GENE_SET_GENE_TABLE + " WHERE Gene='%s'" % names)
        gene_pop[names] = len(cursor.fetchall())
        print("\t\tCalcuated populairty for gene " + str(count.count()) + " out of " + str(len(gene_names)))

    cursor.close()
    pickle.dump(gene_pop, open(GENE_POPULARITY_FILE(dataset), 'wb'), protocol=-1)

@lru_cache(maxsize=16)
def load_gene_popularity(dataset):
    '''
    Returns gene popularity data for the dataset, caching information along the way.

    :param dataset: the name of the dataset downloading data from
    :type dataset: str

    :returns: a dict mapping gene name to their popularity score
    '''
    if os.path.exists(GENE_POPULARITY_FILE(dataset)):
        print("\tOpenning cached gene popularities!")
        return pickle.load(open(GENE_POPULARITY_FILE(dataset), 'rb'))

    print("\tCalculating gene popularities")
    dump_gene_popularity(dataset)
    print("\tSaving gene popularities")
    return load_gene_popularity(dataset)

'''
****************************Gene Sets****************************
'''
GENE_SET_DIR = DATA_DIR
GENE_SET_FILE = GENE_SET_DIR + "/All_GeneSets.pkl"
def dump_all_gene_sets():
    '''
    Queries the main gene_set database and dumps ALL gene sets in the form of a dict mapping the name
    of the gene set to a gene_set object
    '''

    if not os.path.exists(GENE_SET_DIR):
        os.makedirs(GENE_SET_DIR)

    cursor = sqlite3.connect(GENE_SET_DB).cursor()
    cursor.execute("Select Distinct GeneSet From " + GENE_SET_GENE_TABLE)
    sets = [set[0] for set in cursor.fetchall()]

    gene_sets = {}
    count = counter()
    for set in sets:
        cursor.execute("Select Distinct Gene From " + GENE_SET_GENE_TABLE + " WHERE GeneSet='%s'" % set)
        genes = {x[0] for x in cursor.fetchall()}
        cursor.execute("Select Distinct URL From " + GENE_SET_URL_TABLE + " WHERE GeneSet='%s'" % set)
        url = cursor.fetchall()[0][0]
        gene_sets[set] = gene_set(set, url, genes)
        print("\t\tProcessed set " + str(count.count()) + " out of " + str(len(sets)))

    cursor.close()
    pickle.dump(gene_sets, open(GENE_SET_FILE, 'wb'), protocol=-1)

@lru_cache(maxsize=16)
def load_all_gene_sets():
    '''
    Returns all stored gene sets, caching information along the way.

    :returns: a dict mapping geneset names to their gene_set objects
    '''

    if os.path.exists(GENE_SET_FILE):
        print("\tOpenning cached gene sets!")
        return pickle.load(open(GENE_SET_FILE, 'rb'))

    print("\tCalculating gene sets!")
    dump_all_gene_sets()
    print("\tSaving gene sets!")
    return load_all_gene_sets()

FILTERED_GENE_SET_DIR = lambda dataset: DATA_DIR + "/" + dataset + "/"
FILTERED_GENE_SET_FILE = lambda dataset: FILTERED_GENE_SET_DIR(dataset) + dataset + "_FilteredGeneSets.pkl"
'''Returns the path used to cache/uncache expression profiles for the given dataset'''
def dump_filtered_gene_sets(dataset):
    '''
    Given the genes in a dataset, dumps gene_sets made from all the gene_sets filtered so only genes which appear in
    the dataset are present in the gene_sets. gene_sets with no genes left are removed. After this filtering process,
    removes all sets less than 5 genes or more than 100 genes.

    :param dataset: the name of the dataset downloading data from
    :type dataset: str
    '''

    if not os.path.exists(FILTERED_GENE_SET_DIR(dataset)):
        os.makedirs(FILTERED_GENE_SET_DIR(dataset))

    gene_sets = load_all_gene_sets()

    samples = load_sample_profiles(dataset)
    keys = [key for key in samples.keys()]
    valid_genes = samples[keys[0]].profiles.keys()

    filtered_sets = {}
    count = counter()
    for set_name in gene_sets:
        cur_set = gene_sets[set_name]
        new_genes = {gene for gene in cur_set.genes if gene in valid_genes}
        if len(new_genes) > 5 and len(new_genes) < 100:
            filtered_sets[set_name] = gene_set(set_name, cur_set.url, new_genes)
        print("\t\tProcessed set " + str(count.count()) + " out of " + str(len(gene_sets)))

    pickle.dump(filtered_sets, open(FILTERED_GENE_SET_FILE(dataset), 'wb'), protocol=-1)

@lru_cache(maxsize=16)
def load_filtered_gene_sets(dataset):
    '''
    Returns gene sets valid for the given dataset, caching information along the way.

    :returns: a dict mapping geneset names to their gene_set objects
    '''

    if os.path.exists(FILTERED_GENE_SET_FILE(dataset)):
        print("\tOpenning cached gene sets!")
        return pickle.load(open(FILTERED_GENE_SET_FILE(dataset), 'rb'))

    print("\tCalculating filtered gene sets!")
    dump_filtered_gene_sets(dataset)
    print("\tSaving filtered gene sets!")
    return load_filtered_gene_sets(dataset)

'''
****************************Dataset specific clinical profiles****************************
'''
BC_CLINICAL_PROFILES_FILE = DATA_DIR + "/BC/BC_ClinicalProfiles.pkl"
BC_CLINICAL_DB = DATA_DIR + "/BC/BCClinical.db"
def dump_BC_clinical_profiles():
    '''
    Queries the BC database to download and dump a dict mapping patient id to clinical_profiles
    '''

    if not os.path.exists(BC_CLINICAL_PROFILES_FILE):
        os.makedirs(BC_CLINICAL_PROFILES_FILE)

    cursor = sqlite3.connect(BC_CLINICAL_DB).cursor()
    cursor.execute("Select * From BC_ClinicalData")
    rows = cursor.fetchall()

    count = counter()
    profiles = {}
    for row in rows:
        sample_num, first_series, posnodes, event_meta, \
        event_death, time_survival, time_recur, time_meta, esr1, nih, st_gallen, conserv, \
        c1_from_data, c1_cross_valid, c1_used = row

        other_fields = {}
        other_fields["first_series"] = first_series
        other_fields["posnodes"] = posnodes
        other_fields["event_meta"] = event_meta
        other_fields["event_death"] = event_death
        other_fields["time_survival"] = time_survival
        other_fields["time_recur"] = time_recur
        other_fields["time_meta"] = time_meta
        other_fields["esr1"] = esr1
        other_fields["nih"] = nih
        other_fields["st_gallen"] = st_gallen
        other_fields["conserv"] = conserv
        other_fields["c1_from_data"] = c1_from_data
        other_fields["c1_cross_valid"] = c1_cross_valid
        other_fields["c1_used"] = c1_used

        profiles[sample_num] = (clinical_data(sample_num, other_fields))
        print("\t\tProcessed patient " + count.count() + " out of " + str(len(rows)))

    pickle.dump(profiles, open(BC_CLINICAL_PROFILES_FILE, 'wb'), protocol=-1)

@lru_cache(maxsize=16)
def load_BC_clinical_profiles():
    '''
    Returns clinical profiles for the BC set, caching information along the way.

    :returns: a dict mapping patient id's to their clinical_profiles
    '''
    if os.path.exists(BC_CLINICAL_PROFILES_FILE):
        print("\tOpenning cached clinical profiles for BC set!")
        return pickle.load(open(BC_CLINICAL_PROFILES_FILE, 'rb'))

    print("\tCalculating BC clinical profiles!")
    dump_BC_clinical_profiles()
    print("\tSaving BC clinical profiles!")
    return load_BC_clinical_profiles()

'''
****************************Picking best models****************************
'''
BEST_MODELS_DIR = lambda dataset, bins, genes: DATA_DIR + "/" + dataset + "/"
BEST_MODELS_FILE = lambda dataset, bins, genes: BEST_MODELS_DIR(dataset, bins, genes) + dataset + "_BestModels_BINS_" \
                                                + str(bins) + "_GENES_" + str(genes) + ".pkl"
'''Returns the path used to cache/uncache gene popularity for the given dataset'''
import heapq
from master_selection import calculate_prior
from master_selection import calculate_bayes_error
def dump_best_models(dataset, num_bins, genes_per_bin):
    """
    Given a dataset, returns the best genes_per_bin which fall into num_bins evenly divided bayes error for the models

    ToDo: figure out a way to write this better
    """
    if not os.path.exists(BEST_MODELS_DIR(dataset, num_bins, genes_per_bin)):
        os.makedirs(BEST_MODELS_DIR(dataset, num_bins, genes_per_bin))

    gene_models = load_gene_models(dataset)
    popularity = load_gene_popularity(dataset)

    bin_bounds = [0.1] + [0.1 + x * (0.5 - 0.1) / num_bins for x in range(1, num_bins + 1)]
    find_bin = lambda prior: num_bins if prior == 0.5 \
                                else sum([i for i in range(0, len(bin_bounds) - 1)
                                  if (prior >= bin_bounds[i] and prior < bin_bounds[i + 1])])

    bins = [{} for x in range(0, num_bins)]

    #Here we check every gene fits the criteria and then add it to appropriate bin
    #bins are maps k : v where k = gene name v = bayes error
    count = counter()
    gene_names = gene_models.keys()
    for gene in gene_names:
        model = gene_models[gene]

        prior = calculate_prior(model)
        error = calculate_bayes_error(model)

        #pick and get all gene errors
        if popularity[gene] > 0 and prior >= 0.1:
            bin = find_bin(prior)
            bins[bin][gene] = error

        print("Examined gene " + str(count.count()) + " out of " + str(len(gene_names)))

    #then we go through each bin and take the 10 smallest bayes error
    #bestmodels is k: v where k = gene name and v = bayes error for that model
    best_models = {}
    for bin in bins:
        best_genes = heapq.nsmallest(genes_per_bin, bin, key=bin.get)
        for best_gene in best_genes:
            best_models[best_gene] = gene_models[best_gene]

    print(best_models)
    pickle.dump(best_models, open(BEST_MODELS_FILE(dataset, num_bins, genes_per_bin), 'wb'), protocol=-1)

@lru_cache(maxsize=16)
def load_best_models(dataset, num_bins, genes_per_bin):
    '''
    Returns the best genes for the given dataset, caching information along the way.

    :param dataset: the name of the dataset downloading data from
    :type dataset: str

    :param num_bins: the number of bins dividing up bayes error range
    :type num_bins: int

    :param genes_per_bin: the number of best models to choose for each bin
    :type genes_per_bin: int

    :returns: a dict mapping gene names to their models, the best ones!
    '''

    if os.path.exists(BEST_MODELS_FILE(dataset, num_bins, genes_per_bin)):
        print("\tOpenning cached best models!")
        return pickle.load(open(BEST_MODELS_FILE(dataset, num_bins, genes_per_bin), 'rb'))

    print("\tCalculating best models!")
    dump_best_models(dataset, num_bins, genes_per_bin)
    print("\tSaving best models!")
    return load_best_models(dataset, num_bins, genes_per_bin)

'''
****************************Simulating Phenotypes****************************
'''
PHENOTYPE_SIMS_DIR  = lambda dataset, n, master_gene: DATA_DIR + "/" + dataset + "/SimPhenotypes/" + master_gene + "/"

PHENOTYPE_SIMS_FILE = lambda dataset, n, master_gene: PHENOTYPE_SIMS_DIR(dataset, n, master_gene) + \
                        dataset + "_SimPheno_" + "Gene_" + str(master_gene) + "_N_" + str(n) + ".pkl"
'''Returns the path used to cache/uncache gene popularity for the given dataset'''
from simulation import simulate_data
def dump_sim_phenotypes(dataset, n, master_gene):
    '''
    From the gene expressions and samples of the given dataset, simulates n tables of phenotypes for each sample with
    the given master_gene.

    Dumps a file of lists of dicts mapping id's to class (0 or 1)

    In general class 0 has lower gene expression levels of the master gene than class 1.

    :param dataset: the dataset from which to reference data from
    :type dataset: str

    :param n: the number of simulations to run
    :type n: int

    :param master_gene: the master gene used to simulate data
    :type master_gene: str
    '''

    if not os.path.exists(PHENOTYPE_SIMS_DIR(dataset, n, master_gene)):
        os.makedirs(PHENOTYPE_SIMS_DIR(dataset, n, master_gene))

    models = load_gene_models(dataset)
    samples = load_sample_profiles(dataset)

    data_sets = []
    count = counter()
    for i in range(0, n):
        labels = simulate_data(models, master_gene, [samples[key] for key in samples.keys()], len(samples))
        data_sets.append(labels)
        print("\t\tSimulation " + str(count.count()) + " complete out of " + str(n))

    pickle.dump(data_sets, open(PHENOTYPE_SIMS_FILE(dataset, n, master_gene), 'wb'))

@lru_cache(maxsize=16)
def load_sim_phenotypes(dataset, n, master_gene):
    '''
    Returns the a set of n simulated phenotypes using the given mastergene, caching data along the way

    :param dataset: the dataset from which to reference data from
    :type dataset: str

    :param n: the number of simulations to run
    :type n: int

    :param master_gene: the master gene used to simulate data
    :type master_gene: str
    '''
    if os.path.exists(PHENOTYPE_SIMS_FILE(dataset, n, master_gene)):
        print("\tOpenning cached simulated phenotype data!")
        return pickle.load(open(PHENOTYPE_SIMS_FILE(dataset, n, master_gene), 'rb'))

    print("\tCalculating simulated phenotype data!")
    dump_sim_phenotypes(dataset, n, master_gene)
    print("\tSaving simulated phenotype data!")
    return load_sim_phenotypes(dataset, n, master_gene)

def load_sim_phenotype_keyed(dataset, n, master_gene):
    '''
    As above, but returns as entry in dict with key as given master_gene. This is for parallelization
    '''

    return {master_gene: load_sim_phenotypes(dataset, n, master_gene)}
'''
****************************ssGSEA Phenotypes****************************
'''
ssGSEA_SCORES_DIR = lambda dataset: DATA_DIR + "/" + dataset + "/"

ssGSEA_SCORES_FILES = lambda dataset, tag: ssGSEA_SCORES_DIR(dataset) + tag + dataset + "_ssGSEAScores.pkl"
'''Returns the path used to cache/uncache gene enrichment scores per id'''
from ssGSEA import calculate_enrichment_score
def dump_ssGSEA_scores(dataset, tag):
    """
    For every id and good gene set of the given dataset, dumps enrichment score information. Specifically dumps
    a dictionary mapping gene set names to a dictionary mapping id's to enrichment scores for that set. Does not
    normalize scores, and sets weight value on ranking terms to 0.25

    :param dataset: the dataset from which to reference data from
    :type dataset: str
    """
    if not os.path.exists(ssGSEA_SCORES_DIR(dataset)):
        os.makedirs(ssGSEA_SCORES_DIR(dataset))

    gene_sets = load_filtered_gene_sets(dataset)
    samples = load_sample_profiles(dataset)

    if tag == 'null':
        print("Simulating null hypothesis...")
        scramble_sample(samples)

    paths = {}
    #for each gene set
    count = counter()
    for set in gene_sets.keys():
        gene_set = gene_sets[set].genes

        #go through all the samples and calculate the ES
        scores = {}
        for id in samples.keys():
            profile = samples[id].profiles
            expressions = {}

            for gene in profile.keys():
                expressions[gene] = profile[gene].intensity

            score = calculate_enrichment_score(gene_set, expressions, 0.25)

            scores[id] = sum(score)

        paths[set] = scores

        print("\t\tScores for set " + str(count.count()) + " done out of " + str(len(gene_sets.keys())))

    pickle.dump(paths, open(ssGSEA_SCORES_FILES(dataset, tag), 'wb'))

@lru_cache(maxsize=16)
def load_ssGSEA_scores(dataset, tag=''):
    '''
    Returns a dictionary mapping gene set names to a dictionary mapping id's to enrichment scores for that set

    :param dataset: the dataset from which to reference data from
    :type dataset: str

    :returns: a dictionary mapping gene set names to a dictionary mapping id's to enrichment scores
    '''

    if os.path.exists(ssGSEA_SCORES_FILES(dataset, tag)):
        print("\tOpenning cached enrichment sets!")
        return pickle.load(open(ssGSEA_SCORES_FILES(dataset, tag), 'rb'))

    print("\tCalculating enrichment data!")
    dump_ssGSEA_scores(dataset, tag)
    print("\tSaving enrichment data!")
    return load_ssGSEA_scores(dataset, tag)

'''
****************************Bayes Phenotypes****************************
'''
BAYES_SCORES_DIR = lambda dataset: DATA_DIR + "/" + dataset + "/"
BAYES_SCORES_FILE = lambda dataset, mode, tag: BAYES_SCORES_DIR(dataset) + tag + dataset + "_" + str(mode) + "_BayesHighScores.pkl"
'''Returns the path used to cache/uncache gene enrichment scores per id'''
from p_model import pmodel
def dump_bayes_scores(dataset, mode, tag):
    """
    For every id and good gene set of the given dataset, dumps enrichment score information. Specifically dumps
    a dictionary mapping gene set names to a dictionary mapping id's to enrichment scores for that set.

    :param dataset: the dataset from which to reference data from
    :type dataset: str
    """
    if not os.path.exists(BAYES_SCORES_DIR(dataset)):
        os.makedirs(BAYES_SCORES_DIR(dataset))

    gene_sets = load_filtered_gene_sets(dataset)
    samples = load_sample_profiles(dataset)

    if tag == 'null':
        print("Simulating null hypothesis...")
        scramble_sample(samples)

    max_expression = {}
    min_negative_expression = {}
    #first normalize gene expression value
    for id in samples:
        sample = samples[id]
        for gene in sample.profiles.keys():
            exp = sample.profiles[gene].intensity

            if gene not in max_expression.keys():
                max_expression[gene] = exp
            if exp > max_expression[gene]:
                max_expression[gene] = exp

            if gene not in min_negative_expression.keys():
                min_negative_expression[gene] = 0
            if exp < min_negative_expression[gene]:
                min_negative_expression[gene] = exp
                
    paths = {}
    #for each gene set
    count = counter()
    for set in gene_sets.keys():
        gene_set = gene_sets[set].genes

        #go through all the samples and calculate the ES
        scores = {}
        for id in samples.keys():
            profile = samples[id].profiles
            expressions = []

            for gene in profile.keys():
                if gene in gene_set:
                    #transform expression data into values between 0 and 1
                    #-.0001 because rounding to 1 = nan values
                    expressions.append((profile[gene].intensity - min_negative_expression[gene]) / (max_expression[gene] - min_negative_expression[gene]))

            score = pmodel(expressions, [1/3 , 1/3, 1/3], mode)
            if str(score) == 'nan':
                print(expressions)
            scores[id] = score

        paths[set] = scores

        print("\t\tScores for set " + str(count.count()) + " done out of " + str(len(gene_sets.keys())))

    pickle.dump(paths, open(BAYES_SCORES_FILE(dataset, mode, tag), 'wb'))

@lru_cache(maxsize=16)
def load_bayes_scores(dataset, mode, tag=''):
    '''
    Returns a dictionary mapping gene set names to a dictionary mapping id's to enrichment scores for that set

    :param dataset: the dataset from which to reference data from
    :type dataset: str

    :returns: a dictionary mapping gene set names to a dictionary mapping id's to enrichment scores
    '''

    if os.path.exists(BAYES_SCORES_FILE(dataset, mode, tag)):
        print("\tOpenning cached enrichment sets!")
        return pickle.load(open(BAYES_SCORES_FILE(dataset, mode, tag), 'rb'))

    print("\tCalculating enrichment data!")
    dump_bayes_scores(dataset, mode, tag)
    print("\tSaving enrichment data!")
    return load_bayes_scores(dataset, mode, tag)

'''
Null enrichment
'''
NULL_SCORES_DIR = lambda dataset: DATA_DIR + "/" + dataset + "/"
NULL_SCORES_FILE = lambda dataset, tag: NULL_SCORES_DIR(dataset) + tag + dataset + "_"  + "_NullHighScores.pkl"
def dump_null_scores(dataset, tag):
    '''
    Dumps a dictionary mapping gene set to a dicitonary mapping id's to enrichment scores for that set (random scorse)
    '''
    if not os.path.exists(NULL_SCORES_DIR(dataset)):
        os.makedirs(NULL_SCORES_DIR(dataset))

    gene_sets = load_filtered_gene_sets(dataset)
    samples = load_sample_profiles(dataset)

    if tag == 'null':
        print("Simulating null hypothesis")
        scramble_sample(samples)

    random_scores = {}
    for set in gene_sets.keys():
        local_scores = {}
        for id in samples.keys():
            import random
            local_scores[id] = random.random() * 5000

        random_scores[set] = local_scores

    pickle.dump(random_scores, open(NULL_SCORES_FILE(dataset, tag), 'wb'))

@lru_cache(maxsize=16)
def load_null_scores(dataset, tag=''):
    if os.path.exists(NULL_SCORES_FILE(dataset, tag)):
        print("\tOpenning cached enrichment sets!")
        return pickle.load(open(NULL_SCORES_FILE(dataset, tag), 'rb'))

    print("\tCalculating enrichment data!")
    dump_null_scores(dataset, tag)
    print("\tSaving enrichment data!")
    return load_null_scores(dataset, tag)

'''
For null tests given a map of ids to sample_profile objects, will scramble the gene labels for expression levels
'''
def scramble_sample(samples):
    import random
    for id in samples:
        print("\tScrambling sample id", id)
        sample = samples[id]
        profiles = sample.profiles

        profile_scores = [profiles[gene].intensity for gene in profiles]
        random.shuffle(profile_scores)

        for gene in profiles:
            profiles[gene].intensity = profile_scores.pop()

if __name__ == "__main__":
    g = load_sample_profiles("BC")
    print(g[4].profiles.keys())

