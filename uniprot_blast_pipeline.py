# UniProt BLAST Automation Pipeline


#Workflow:
#1. Retrieve protein sequences from UniProt
#2. Submit BLAST searches to the EBI NCBI BLAST REST API
#3. Restrict searches to target species using taxonomy IDs
#4. Parse XML results
#5. Identify the best homologous hit based on E-value

import json
import requests
import subprocess
import time
import logging
import xml.etree.ElementTree as ET

#API Configuration
# Endpoints and parameters used to interact with UniProt and the EBI BLAST REST service.

# API Endpoint Configurations
UNIPROT_FASTA_URL = "https://www.uniprot.org/uniprot/{}.fasta"
EBI_BLAST_RUN_URL = "https://www.ebi.ac.uk/Tools/services/rest/ncbiblast/run"
EBI_BLAST_STATUS_URL = "https://www.ebi.ac.uk/Tools/services/rest/ncbiblast/status/{}"
EBI_BLAST_RESULT_URL = "https://www.ebi.ac.uk/Tools/services/rest/ncbiblast/result/{}/xml"

MAX_RETRIES = 2
RETRY_DELAY = 5

#input

input_file = "blast_inputs.json"

# Load the inputs
with open(input_file, "r") as f:
    inputs = json.load(f)

uniprots = inputs["uniprots"]
taxonomy_ids = inputs["taxonomy_ids"]
species_names = inputs["species_names"]
e_value = inputs["e_value"]
reviewed_only = inputs["reviewed_only"]

logging.basicConfig(
    filename="uniprot_blast.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def fetch_sequence(uniprot_id, retries=MAX_RETRIES, delay=RETRY_DELAY):
    """
    Retrieves the FASTA sequence for a given UniProt ID.
    Implements a retry mechanism to handle transient network issues.
    """
    uniprot_id = uniprot_id.strip()
    base_url = UNIPROT_FASTA_URL.format(uniprot_id)

    logging.info("Fetching sequence for UniProt ID: %s", uniprot_id)

    for attempt in range(retries):
        try:
            response = requests.get(base_url)
            response.raise_for_status()

            if response.status_code == 200:
                logging.info("Sequence retrieved for UniProt ID: %s", uniprot_id)
                return response.text

        except requests.RequestException as e:
            logging.error("Sequence fetch failed for %s: %s", uniprot_id, str(e))

        #delay before retrying
        logging.info("Retrying in %d seconds...", delay)
        time.sleep(delay)

    logging.error("Failed to fetch sequence for UniProt ID: %s after %d attempts", uniprot_id, retries)
    return None


def submit_blast_job(uniprot_id, sequence, taxonomy_id, email="research@xyz.org"):
    """
    Submits a protein sequence to EBI NCBI BLAST via curl.
    Targeting specific taxonomy IDs to refine homology search.
    """
    logging.info("Submitting BLAST job for %s against taxonomy %s", uniprot_id, taxonomy_id)

    command = [
        "curl",
        "--form", "email=%s" % email,
        "--form", "program=blastp",
        "--form", "matrix=BLOSUM80",
        "--form", "alignments=50",
        "--form", "scores=50",
        "--form", "exp=1e-5",
        "--form", "filter=F",
        "--form", "gapalign=true",
        "--form", "compstats=F",
        "--form", "align=0",
        "--form", "stype=protein",
        "--form", "sequence=%s" % sequence,
        "--form", "database=uniprotkb",
        "--form", "taxids=%s" % taxonomy_id,
        EBI_BLAST_RUN_URL
    ]

    #execute system call and capture the job ID from stdout
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode == 0:
        logging.info("BLAST job submitted successfully for %s", uniprot_id)
        return stdout.strip()

    logging.error("BLAST submission failed for %s", uniprot_id)
    logging.error(stderr)

    return None

def check_job_status(job_id):
    """
    Polls the EBI server to check the completion status of a submitted job.
    Uses a blocking sleep loop until the job reaches a terminal state.
    """
    logging.info("Checking status for job %s", job_id)

    status_url = EBI_BLAST_STATUS_URL.format(job_id)

    while True:
        response = requests.get(status_url)
        status = response.text

        logging.info("Job %s status: %s", job_id, status)

        if status == "FINISHED":
            return True
        elif status in ["RUNNING", "PENDING", "QUEUED"]:
            time.sleep(10) # Wait period before re-polling to respect API rate limits
        else:
            # Handles FAILED or ERROR states
            return False


def retrieve_result(job_id):
    """
    Downloads the XML result file from EBI once a job is finished.
    """
    logging.info("Retrieving result for job %s", job_id)

    result_url = EBI_BLAST_RESULT_URL.format(job_id)
    response = requests.get(result_url)

    if response.status_code == 200:
        logging.info("Result retrieved for job %s", job_id)
        return response.text

    logging.error("Failed to retrieve result for job %s", job_id)
    return None


def query_uniprot_blast(uniprots, taxonomy_ids, species_names, e_value, reviewed_only):
    """
    Main orchestration logic:
    Iterates through UniProt IDs, runs BLAST against target species, 
    and parses XML results to identify the 'Best Hit' based on E-Value.
    """
    species_names_str = "_".join(name.replace(" ", "_") for name in species_names)

    for uniprot_id in uniprots:

        #skip unknown ids
        if uniprot_id == "Unknown":
            logging.info("Skipping unknown UniProt ID")
            continue

        sequence = fetch_sequence(uniprot_id)

        if not sequence:
            logging.info("Skipping %s due to sequence retrieval failure", uniprot_id)
            continue

        for taxonomy_id in taxonomy_ids:

            job_id = submit_blast_job(uniprot_id, sequence, taxonomy_id)

            if not job_id:
                continue

            # Wait for EBI processing to complete
            if check_job_status(job_id):

                xml_result = retrieve_result(job_id)

                if xml_result:
                    #parse the XML response using the EBI schema namespace
                    root = ET.fromstring(xml_result)
                    namespace = "http://www.ebi.ac.uk/schema"

                    hits = root.findall(".//{%s}hit" % namespace)

                    min_expectation = float("inf")
                    best_hit = None

                    #output header 
                    print("***************************************************")
                    print("#Query: %s, Species: %s" % (uniprot_id, species_names_str))
                    print("#Uniprot_ID    Species      Evalue")
                    print("***************************************************")

                    # find the hit with the lowest E-Value (highest significance)
                    for hit in hits:
                        ac = hit.get("ac")
                        description = hit.get("description")
                        alignment = hit.find(".//{%s}alignment" % namespace)

                        if alignment is not None:
                            expectation_element = alignment.find("{%s}expectation" % namespace)

                            if expectation_element is not None:
                                try:
                                    expectation = float(expectation_element.text)
                                except ValueError:
                                    expectation = float("inf")

                                # Identifying the strongest candidate for orthology
                                if expectation > 0 and expectation < min_expectation:
                                    min_expectation = expectation
                                    best_hit = {
                                        "ac": ac,
                                        "description": description,
                                        "expectation": expectation
                                    }

                    #extract and format metadata from the best hit
                    if best_hit:
                        ac = best_hit["ac"]
                        expectation = best_hit["expectation"]

                        description_parts = best_hit["description"].split(" OS=")
                        if len(description_parts) > 1:
                            organism = description_parts[1].split(" OX=")[0].replace(" ", "_")
                        else:
                            organism = "unknown"

