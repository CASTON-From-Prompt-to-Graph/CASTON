# CASTON — From Prompt to Graph

CASTON provides resources for casting-domain ontology construction, combining term extraction, relation extraction, and conversion of curated triples into an ontology. This repository is maintained under the **CASTON-From-Prompt-to-Graph** organization.

## Current contents

```text
CASTON/
├── ICL/
│   ├── NER.py                 # Term-extraction placeholder
│   └── RE.py                  # Relation-extraction placeholder
├── dataset/
│   ├── data-inventory.json
│   └── train/
│       ├── NER_train173_0520.jsonl
│       └── RE_train96_0528_no_sibling.jsonl
├── triple2onto.py            # CSV triples and annotations to ontology
├── LICENSE
└── README.md
```

`ICL/NER.py` and `ICL/RE.py` are currently empty placeholders. The repository does not yet provide an executable end-to-end ICL extraction pipeline. `triple2onto.py` is a separate ontology-conversion script supplied by He Tan and retained without changes.

## Training datasets

| Task | File | Records |
| --- | --- | ---: |
| Term extraction (NER) | [NER_train173_0520.jsonl](dataset/train/NER_train173_0520.jsonl) | 173 |
| Relation extraction (RE) | [RE_train96_0528_no_sibling.jsonl](dataset/train/RE_train96_0528_no_sibling.jsonl) | 96 |

Each non-empty JSONL line is one JSON object with a `messages` array containing `system`, `user`, and `assistant` messages. The assistant message provides the reference response for that training example. Original annotation text and label spelling are retained.

These are the previously supplied training datasets from the Final_dataset archive. Their parsed records match the earlier CASTON training package. They are training resources, not independent validation datasets or reported model predictions. Validation datasets and experimental results are not included here.

The existing [data inventory](dataset/data-inventory.json) lists the same record counts, but its path strings still use `data/training/`. The actual files in this repository are under `dataset/train/`, as linked above.

To read the training examples:

```python
import json
from pathlib import Path

path = Path("dataset/train/NER_train173_0520.jsonl")
records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
```

## Ontology conversion with triple2onto.py

The script converts curated CSV triples and annotation tables into an ontology. It creates classes and object properties, handles `isa` as a subclass relation, adds property hierarchies, and attaches labels and annotations. It does not run a reasoner.

### Requirements

Install the Python dependencies:

```bash
python -m pip install pandas owlready2 rdflib
```

The script loads SKOS from `http://www.w3.org/2004/02/skos/core`, so that resource must be reachable when it runs.

### Input files

Provide the following three CSV files in the working directory. These ontology inputs are not included in this repository and are separate from the JSONL training datasets.

| Filename expected by the script | Required columns |
| --- | --- |
| `seed_onto_v5_v2.7_ordered_normalized_dedup.csv` | `subject`, `predicate`, `object` |
| `seed_onto_v5_class_annotation.csv` | `name`, `label`, `definition`, `altLabel1`, `altLabel2`, `altLabel3`, `scope` |
| `seed_onto_v5_property_annotation.csv` | `name`, `label`, `definition`, `altLabel`, `subproperty_of` |

Use consistent, non-empty entity and property names. The filenames are set directly in the script; edit those assignments if your local input names differ. The script has no command-line arguments.

From the repository root, with the input files available:

```bash
python triple2onto.py
```

### Generated files and implementation notes

Running the script writes `CastOnto.owl` (RDF/XML), `CastOnto.nt` (N-Triples), `CastOnto.ttl` (Turtle), and `CastOnto.jsonld` (JSON-LD) into the working directory. A temporary `CastOnto_ns.nt` is removed at the end. Existing files with these names may be overwritten. Generated ontology files are not distributed in this repository.

The ontology IRI is `http://inmost-research.org/ontologies/caston#`. The later namespace-binding call uses `http://inmost.org/ontologies/caston#`; binding a prefix does not rewrite the ontology IRIs. This difference is retained from the supplied script. The property annotation `altLabel` is currently appended to the property's regular label list. Users should review these conventions for their intended ontology release.

The supplied script has been checked for Python syntax. End-to-end conversion has not been verified here because its three CSV inputs are not bundled.

## License

See the repository's [MIT License](LICENSE).
