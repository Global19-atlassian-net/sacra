from __future__ import print_function
import os, csv, sys, json, re
import logging
from pdb import set_trace
from Bio import Entrez
from Bio import SeqIO

def query_genbank(accessions, parsers, email=None, retmax=10, n_entrez=10, gbdb="nuccore", **kwargs):
    # https://www.biostars.org/p/66921/
    logger = logging.getLogger(__name__)
    if not email:
        email = os.environ['NCBI_EMAIL']
    Entrez.email = email
    logger.debug("Genbank email: {}".format(email))

    # prepare queries for download in chunks no greater than n_entrez
    queries = []
    for i in sorted(xrange(0, len(accessions), n_entrez)):
        queries.append(set(accessions[i:i+n_entrez]))

    def esearch(accs):
        if len(accs) == 0:
            logger.debug("No accessions left to search")
            return
        logger.debug("esearch with {}".format(accs))
        list_accs = list(accs)
        res = Entrez.read(Entrez.esearch(db=gbdb, term=" ".join(list_accs), retmax=retmax))
        if "ErrorList" in res:
            not_found = res["ErrorList"]["PhraseNotFound"][0]
            logger.debug("esearch failed - accession {} doesn't exist. Retrying".format(not_found))
            accs.remove(not_found)
            esearch(accs)
        else: # success :)
            for i, x in enumerate(list_accs):
                acc_gi_map[x] = res["IdList"][i]

    # populate Accession -> GI number via entrez esearch
    acc_gi_map = {x:None for x in accessions}
    for qq in queries:
        esearch(qq)
    gi_numbers = [x for x in acc_gi_map.values() if x != None]

    # get entrez data vie efetch
    logger.debug("Getting epost results for {}".format(gi_numbers))
    try:
        search_handle = Entrez.epost(db=gbdb, id=",".join(gi_numbers))
        search_results = Entrez.read(search_handle)
        webenv, query_key = search_results["WebEnv"], search_results["QueryKey"]
    except:
        logger.critical("ERROR: Couldn't connect with entrez, please run again")
        sys.exit(2)
    for start in range(0, len(gi_numbers), retmax):
        #fetch entries in batch
        try:
            handle = Entrez.efetch(db=gbdb, rettype="gb", retstart=start, retmax=retmax, webenv=webenv, query_key=query_key)
        except IOError:
            logger.critical("ERROR: Couldn't connect with entrez, please run again")
        else:
            SeqIO_records = SeqIO.parse(handle, "genbank")
            for record in SeqIO_records:
                for parser in parsers:
                    parser(record, **kwargs)