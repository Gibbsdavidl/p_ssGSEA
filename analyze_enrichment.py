'''
This file contains methods for analyzing phenotype and enrichment scores across certain gene_sets
'''

import scipy.stats as stats

def analyze_phenotype_score_dist(enrichment_scores, phenotype, gene_set):
    '''
    :param enrichment_scores: a mapping of gene_set names to a dictionary mapping id's to their enrichment scores
    for the gene_set
    :type enrichment_scores: dict

    :param phenotype: a mapping of sample id's to the sample's phenotype, either 0 or 1
    :type phenotype: dict

    :param gene_set: the name of the geneset to check enrichment score distribution
    :type gene_set: str

    :returns: a tuple in the form (c0. c1) where c0/1 is a list of enrichment scores for class0/class1 respectively
    '''

    set_scores = enrichment_scores[gene_set]

    #enrichment scores for class 0/1
    class0 = []
    class1 = []

    for id in set_scores.keys():
        if phenotype[id] == 0:
            class0.append(set_scores[id])
        else:
            class1.append(set_scores[id])

    return (class0, class1)

def rank_by_t_test(enrichment_scores, phenotypes):
    '''
    Given a map of gene_sets to a dictionary of id's to enrichment scores for a gene set, and a list of dictionaries
    mapping id's to phenotype class 0 or 1, each element of the list representing a trial of simulated phenotype,
    returns a list, one element for every trial of simulated phenotype, where each element is a map of gene_set names
    to a tuple in the form (a, b) where a is the t-score found by comparing the distributions of enrichment scores
    found between samples with different phenotype classes and b is the p-value

    :param enrichment_scores: a mapping of gene_set names to a dictionary mapping id's to their enrichment scores
    for the gene_set
    :type enrichment_scores: dict

    :param phenotypes: a list of maps, each map a mapping of sample id's to the sample's phenotype, either 0 or 1. Each
    map represents a series of simulated phenotypes
    :type phenotypes: dict

    :returns: a list of maps, mapping gene_sets to a tuple of representing t-score and p-value
    '''
    gene_sets = enrichmentScores.keys()

    rankings = []
    for trial in range(0, len(phenotypes)):
        phenotype = phenotypes[trial]
        scores = {}
        for gene_set in gene_sets:
            class0, class1 = analyze_phenotype_score_dist(enrichment_scores, phenotype, gene_set)
            tstat, pvalue = stats.ttest_ind(class0, class1)
            scores[gene_set] = (abs(tstat), pvalue)
        rankings.append(scores)

    return rankings

def evaluate_rankings(rankings, gene_sets, master_gene):
    '''
    Given a list of dicts mapping gene_set to a tuple describing t-statistic and p-value, returns the ranking's
    ability at including the master_gene in the top sets

    **ToDo:**refine ranking

    :rankings: a list mapping of gene_sets to tuples containg the tstatistic and pvalue of the gene set in seperating the two classes
    :type rankings: list

    :param gene_sets: a mapping of gene_set names to gene_sets
    :type gene_sets: dict

    :param master_gene: the master_gene to which we expect to show up in the top k-rankings
    :type master_gene: str

    :returns: a list, with each element being the "score" calculated on the ranking of the master_gene in the given
    rankings
    '''

    def linear_method(ranking):
        # parse gene_sets in order from high tstat to low
        sorted_sets = sorted(ranking, key=ranking.get, reverse=True)
        # for scores for every gene ranking
        running_scores = {}
        # number of times gene appears in list of sets
        set_count = {}

        i = 0
        for set in sorted_sets:
            i += 1

            # go through every set and update scores
            set_genes = gene_sets[set].genes
            for gene in set_genes:
                if gene not in running_scores.keys():
                    running_scores[gene] = 0
                    set_count[gene] = 0
                running_scores[gene] += i
                set_count[gene] += 1

        # calculate final scores
        final_scores = {}
        for gene in running_scores:
            final_scores[gene] = running_scores[gene] / set_count[gene]
        return final_scores

    master_gene_ranks = []
    for ranking in rankings:
        scores = linear_method(ranking)
        print(scores)
        #scores = squared_method(ranking)

        sorted_genes = sorted(scores, key=scores.get)
        i = 0
        for gene in sorted_genes:
            i += 1
            if gene == master_gene:
                master_gene_ranks.append(i)

    return master_gene_ranks

if __name__ == "__main__":
    import cache_codec

    MASTER_GENE = "ERBB2"
    DATASET = "BC"

    enrichmentScores = cache_codec.load_ssGSEA_scores(DATASET)
    gene_set_names = enrichmentScores.keys()
    phenotypes = cache_codec.load_sim_phenotypes(DATASET, 10, MASTER_GENE)
    print(phenotypes)

    rankings = rank_by_t_test(enrichmentScores, phenotypes)

    gene_sets = cache_codec.load_filtered_gene_sets(DATASET)
    evaluate_rankings(rankings, gene_sets, MASTER_GENE)




