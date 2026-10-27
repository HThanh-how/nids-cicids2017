# How Optimistic Is Your Intrusion-Detection Benchmark?

**Leakage-Resistant Evaluation and Measured Serving Cost**

Huy-Thanh Pham and Tuan-Anh Truong
Faculty of Computer Science and Engineering, Ho Chi Minh City University of
Technology (HCMUT), VNU-HCM, Vietnam

Venue: **SOICT 2026 (Springer CCIS, to appear)**

This repository is the artifact of the paper: the LaTeX source, the
experiment code, the raw result files from which every table and figure is
generated, and the serving benchmark (service, Dockerfile, Kubernetes
manifests and load tests).

## Abstract

Machine-learned intrusion detectors report near-perfect scores on public
benchmarks, yet that performance is not seen in the field. We show that a large
part of the gap comes from the evaluation itself and measure how large it is.
On CICIDS2017, with models, hyperparameters and preprocessing held fixed and
with feature selection, oversampling and scaling re-fitted inside every training
split, we compare a conventional stratified random split with a day-disjoint
split in which no attack family is shared between training and test. For
XGBoost, attack recall falls from 0.9935 to 0.3164 and macro-F1 from 0.9879 to
0.6887. The ranking of models does not survive the change of protocol, and
controls for near-duplicate leakage, temporal shift and unseen attack families
attribute the gap almost entirely to unseen families. We also translate the
measured error rates into precision at operational attack prevalence, and we
measure the trained model served as a containerised endpoint under controlled
load, showing that a throughput extrapolated from per-sample model cost badly
overstates what the service sustains.

## Repository layout

```
main.tex, references.bib      the paper (Springer LNCS/CCIS class)
tables/, figures/             generated LaTeX tables and PDF figures
experiments/
  run_v3.py                   main experimental protocol (stages S1-S8)
  run_revision.py             control experiments (stages R0-R4)
  run_aligned_baseline.py     aligned-feature in-domain baseline (S6b)
  check_numbers.py            checks the numbers quoted in main.tex against the results
  dump_hyperparams.py         dumps the model hyperparameters
  make_tables.py              results_v3/*.json -> tables/*.tex
  make_figures.py             results_v3/*.json -> figures/*.pdf
  results_v3/                 raw results reported in the paper (20 % sample)
  results_full/               re-run on the full corpus (no sampling)
  rev_run.cmd                 Windows launcher for run_revision.py
serving/
  app.py                      FastAPI inference service
  train_serving_model.py      fits and freezes the model the service runs
  breakdown.py                per-stage latency breakdown of one request
  run_benchmark.py            end-to-end serving benchmark in one command
  Dockerfile                  inference image
  k8s/                        Deployment, Service and HPA manifests
  loadtest/                   bench.py (async load generator), k6.js,
                              scale_and_fault.py (replicas and failure recovery)
  README.md                   details of the serving benchmark
scripts/                      helper scripts used while preparing the manuscript
.github/workflows/            GitHub Actions: LaTeX build
```

## Requirements

- Python 3.13 produced the reported results (recorded in
  `experiments/results_v3/S8_environment.json`); the serving image uses
  Python 3.11 (`serving/Dockerfile`).
- Packages, with the versions recorded in `S8_environment.json` and in the
  `Dockerfile`; packages with no recorded version are listed without one.

```bash
# experiments, tables and figures
pip install numpy==2.2.3 pandas==2.2.3 scikit-learn==1.5.2 xgboost==3.4.1 \
            imbalanced-learn==0.14.2 scipy matplotlib huggingface_hub

# serving benchmark (in addition)
pip install fastapi==0.115.5 "uvicorn[standard]==0.32.0" joblib==1.5.3 \
            pydantic httpx psutil
```

Optional: Docker and a Kubernetes cluster for `serving/k8s/`, and
[k6](https://k6.io) for `serving/loadtest/k6.js`.

## Datasets

The datasets are **not included** in this repository.

- **CICIDS2017** (Canadian Institute for Cybersecurity):
  <https://www.unb.ca/cic/datasets/ids-2017.html>
- **UNSW-NB15** (UNSW Canberra):
  <https://research.unsw.edu.au/projects/unsw-nb15-dataset>

The scripts do not read a local data path. `experiments/run_v3.py` downloads
the CSV files itself through `huggingface_hub` from the public Hugging Face
mirrors `c01dsnap/CIC-IDS2017` (the eight MachineLearningCVE files) and
`Mouwiya/UNSW-NB15`, and caches them locally (standard Hugging Face cache
settings such as `HF_HOME` apply). No account is needed. The environment
variables the scripts read are:

| Variable | Used by | Default | Meaning |
|---|---|---|---|
| `STAGES` | `run_v3.py` | `S1,S2,S3,S4,S5,S6,S7,S8` | stages to run |
| `SAMPLE_FRAC` | `run_v3.py` | `0.20` | fraction of each CICIDS2017 file used |
| `SEEDS_HOLDOUT` | `run_v3.py` | `42,1,2,3,4` | seeds of the repeated holdout |
| `SEEDS_DAY` | `run_v3.py` | `42,1,2` | seeds of the day-disjoint protocol |
| `OUT_DIR` | `run_v3.py` | `results_v3` | output directory |
| `REV_STAGES` | `run_revision.py` | `R0,R1,R2,R3,R4` | control-experiment stages |
| `SEEDS_R1`, `SEEDS_R2`, `SEEDS_R3` | `run_revision.py` | `42,1,2,3,4` / `42,1,2` / `42,1,2,3,4` | seeds per stage |
| `ARTIFACT_DIR` | `serving/app.py` | `serving/artifacts` | where the service loads the frozen model from |

## Reproducing the results

Run the experiment scripts from `experiments/`. Every stage writes a JSON
file and the run can be resumed stage by stage.

```bash
cd experiments

# 1. main protocol (reported run: 20 % sample)
python run_v3.py
STAGES=S1,S2 python run_v3.py            # a subset of stages

# full-corpus re-run, written to a separate directory
SAMPLE_FRAC=1.0 OUT_DIR=results_full STAGES=S1,S2,S8 python run_v3.py

# 2. control experiments (near-duplicates, temporal shift, unseen families)
REV_STAGES=R0,R1,R2,R3,R4 python run_revision.py
#    on Windows: experiments\rev_run.cmd  (runs R1-R4, logs to rev_run.log)

# 3. check that every number quoted in main.tex matches a result file
python check_numbers.py                  # add -v to show where each match comes from

# 4. regenerate the tables and figures from the JSON results
python make_tables.py
python make_figures.py
```

Serving benchmark (run on an otherwise idle machine; see `serving/README.md`):

```bash
cd serving

# freeze the model the service runs (same pipeline as run_v3.py)
python train_serving_model.py

# per-stage latency breakdown of a single-flow request
# (writes experiments/results_v3/S11_serving_breakdown.json)
python breakdown.py

# the whole serving measurement in one command (writes S9_serving.json)
python run_benchmark.py

# or step by step
uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
python loadtest/bench.py --url http://127.0.0.1:8000 --concurrency 1,8,32,128 --duration 20
```

The paper's tables and figures are generated from the JSON files, so no
measured number is typed by hand.

## Where the results are

- `experiments/results_v3/` - the raw results reported in the paper
  (`S1_holdout.json`, `S2_day_disjoint.json`, ..., `S9_serving.json`,
  `S10_scaling.json`, `S11_serving_breakdown.json`, and the control
  experiments `R0`-`R4`).
- `experiments/results_full/` - the protocol re-run on the full corpus
  (stages S0, S1, S2, S8), written there so that the reported run stays
  untouched.
- `tables/` and `figures/` - generated from those files.

Timings depend on the machine; the environment of each run is recorded in the
corresponding `S8_environment.json`.

## Building the paper

```bash
latexmk -pdf main.tex
```

This needs a TeX Live (or MiKTeX) installation with the Springer `llncs`
class and `splncs04.bst`, plus the `bbding` and `tikz` packages. The workflow
`.github/workflows/build.yml` compiles `main.tex` on GitHub Actions for every
push.

## Citation

The paper has been accepted and will appear in the proceedings; there is no
DOI, volume or page range yet. Until then, please cite it as:

```bibtex
@inproceedings{pham2026optimistic,
  author    = {Pham, Huy-Thanh and Truong, Tuan-Anh},
  title     = {How Optimistic Is Your Intrusion-Detection Benchmark?
               Leakage-Resistant Evaluation and Measured Serving Cost},
  booktitle = {SOICT 2026},
  series    = {Communications in Computer and Information Science},
  publisher = {Springer},
  year      = {2026},
  note      = {To appear}
}
```

Citation metadata for the repository is also available in `CITATION.cff`.

## License

- **Code** in this repository is released under the [MIT License](LICENSE).
- **Paper text and PDF** (`main.tex` and its compiled output) are copyright of
  the authors; publication rights are held by Springer.
