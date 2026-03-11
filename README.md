# UniProt BLAST Automation Pipeline

## Overview

This script automates protein homology searches across species by integrating sequence retrieval from UniProt with BLAST queries using the EBI NCBI BLAST REST API.

The script is designed to support cross-species protein mapping workflows, where known proteins from a reference organism are used to identify homologous proteins in target species.


## The workflow performs the following steps:

1. Retrieve protein sequences from UniProt using UniProt accession IDs.

2. Submit sequences to EBI's BLAST REST service.

3. Restrict searches to specified taxonomy IDs.

4. Query the EBI server until jobs complete.

5. Retrieve BLAST results in XML format.

6. Parse the results to identify the best hit (lowest E-value).


## Pipeline Context

This script represents a single component of a larger automated protein annotation pipeline.
Only the UniProt querying and BLAST orchestration logic is included here.


## Requirements
Python

Python 3.7+ recommended.

Python packages

Install required dependencies:

pip install requests
System tools

The script uses curl for multipart BLAST submission.

Ensure curl is installed:

curl --version
Input Format

The script expects input as JSON.
## Running the Script

Example execution:

python blast_pipeline.py blast_inputs.json


The script generates a log file for traceability and reproducibility of pipeline runs.:

uniprot_blast.log

The log records:

- sequence retrieval attempts

- BLAST submission status

- job  progress

- result retrieval

- errors or network failures

## Design Features

The script incorporates several design practices commonly used in bioinformatics pipelines:

- API-based data retrieval (UniProt)

- Automated BLAST job submission

- Retry logic for network robustness

- Asynchronous job polling

- XML result parsing

- structured logging for debugging and reproducibility

## Notes

The script retrieves only the best BLAST hit (lowest E-value) per query.

The e_value and reviewed_only parameters are included for compatibility with a larger pipeline configuration but are not enforced within this script.

## Citation

If using UniProt or EBI BLAST services in published work, please cite:

UniProt Consortium.
UniProt: the universal protein knowledgebase. Nucleic Acids Research.

Madeira et al.
The EMBL-EBI search and sequence analysis tools APIs. Nucleic Acids Research.

## License

This repository is provided for research and educational purposes.
