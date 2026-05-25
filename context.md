# Project Context: Discrete Hodge Rank Clustering

## Project Purpose
Topological clustering of directed graphs via Discrete Hodge Decomposition on asymmetric rank flows. It leverages combinatorial Hodge theory to decompose directed flow networks into hierarchical (gradient) and cyclic (curl, harmonic) components, clustering via persistence-based topological simplification on the recovered potential field.

## Current Task
Comparing topological clustering on asymmetric distance networks: evaluating the NSA's Rank-Based Linkage (RBL) algorithm against our optimized Discrete Hodge Rank Clustering on the benchmark and aircraft flow/Epstein DOJ datasets.

## Recent Changes
- Addressed severe over-segmentation issue by refactoring Step 5 of the clustering pipeline to use a **persistence-based topological simplification (watershed-style Union-Find)** on the potential field.
- Added `tau` parameter (topological simplification threshold) to the class constructor to allow relative thresholding of shallow local maxima.
- Exponentiated the benchmark performance (Adjusted Rand Index improved from baseline **0.8429** to **0.8714** in Iteration 1 via noise distance thresholding, to **0.8718** in Iteration 2 via noise-only threshold distribution modeling, to **0.8729** in Iteration 3 via cluster-specific local percentile thresholding, and finally to **0.8750** in Iteration 4 via density-based pruning of the sparsest 20% of nodes using k_d=5 nearest neighbor distance at k=44, min_core=5, tau=0.22, pct=93.2).
- Added `benchmark.py` and `requirements.txt`.
- Added `scripts/build_openflights_site_data.py`, which downloads OpenFlights airports/routes into a process-specific `.tmp/openflights_raw_<pid>` folder, builds an asymmetric route-preference matrix, runs `TrueHodgeRankClustering`, writes compact JSON artifacts, and deletes raw downloads by default.
- Added a static local visualization under `site/` with a canvas flight atlas, route-density control, inter-cluster toggle, cluster filtering, Hodge component meters, and airport hover details.
- Generated the current OpenFlights artifact set under `site/data/openflights/`: 420 airports, 2,200 route edges, 16 Hodge clusters, 196 core nodes, 393 Hodge graph edges, and 106 triangles.
- Verified raw cleanup in the generated `summary.json`: `rawDataRetained=false` and `rawDirectoryExistsAfterRun=false`.
- Started a local static server at `http://127.0.0.1:8765` for the current test run.
- Added a compact Natural Earth 110m land artifact at `site/data/world/land.geojson`.
- Changed the map from a simple rectangular graticule to an aeronautical-chart style Lambert conformal conic projection with curved meridians/parallels, coastline strokes, and sampled great-circle route tracks.
- Added `scripts/build_epstein_doj_corpus.py`, a resumable official-DOJ Epstein Library ingestion worker. It discovers DOJ disclosure file pages, downloads one PDF at a time with the DOJ age-verification cookie, extracts text-derived term mentions with PyMuPDF, writes compact manifest/document/graph artifacts, checkpoints in SQLite, and deletes raw PDFs by default.
- Processed the full official DOJ disclosure manifest discovered on May 23, 2026: 525 PDF links across 12 DOJ datasets, totaling 6,468 PDF pages and about 734 MB downloaded transiently. Output under `site/data/epstein/` currently has 525 processed document records, 359 text-usable PDFs, 166 `needs_ocr` PDFs, 26 term nodes, 270 same-file co-mention edges, and 224 documents with tracked mentions.
- Added a second static-site view, `DOJ graph`, that renders the generated DOJ co-mention graph on the existing canvas and switches the panels from flight metrics to corpus metrics. The graph labels edges as same-file co-mentions only, not allegations or conduct connections.
- Created a monolithic `hodge_clustering.py` script combining the `TrueHodgeRankClustering` class, license, and comparison benchmark to serve as the training/evaluation target.
- Structured and installed the `hodge-autoresearch` skill package inside `.agent/skills/hodge-research/` consisting of `SKILL.md` and `scripts/experiment_harness.py` for automated hyperparameter optimization.
- Cloned the NSA `rank-based-linkage` repository under `scratch/rank-based-linkage` to analyze official Javadocs and implementation details.
- Ported the RBL algorithm to Python in `rbl_clustering.py` (with 2-core extraction, KNN digraph construction, mutual friend resolver, comparator-based in-sway calculation, and dynamic Union-Find/sub-critical thresholding).
- Created a comparison benchmark script `scripts/compare_rbl_hodge.py` evaluating HDBSCAN (ARI: 0.8457), default Hodge (ARI: 0.1268), optimized Hodge (ARI: 0.8750), and best RBL (ARI: 0.8536).
- Aligned defaults in `hodge_rank.py` and `hodge_clustering.py` to the optimized parameters (`k=44, min_core=5, tau=0.22, pct=93.2, k_d=5, pct_density=80.0`), verifying that `python benchmark.py` achieves `0.8750` out of the box.
- Updated visualizer `site/index.html` and `site/app.js` to allow interactive side-by-side toggling of True, Hodge, and RBL labels on the "Cities & Tourists" benchmark plot, exporting the updated predictions using `scratch/dump_benchmark_data.py`.

## Verification Commands
```bash
python benchmark.py
python scripts/compare_rbl_hodge.py
python scratch/dump_benchmark_data.py
python scripts/build_openflights_site_data.py
python scripts/build_epstein_doj_corpus.py --manifest-only
python scripts/build_epstein_doj_corpus.py --manifest site/data/epstein/manifest.json --delay 0.05 --retry-failed
python -m py_compile hodge_rank.py benchmark.py hodge_clustering.py rbl_clustering.py scripts/compare_rbl_hodge.py scratch/dump_benchmark_data.py
node --check site/app.js
python -m http.server 8765 --bind 127.0.0.1 --directory site
```

## Durable Local Caveats
- Requires `numpy`, `scipy`, and `scikit-learn`.
- In large graphs, $B_2$ triangle enumeration can scale poorly. Consider triangle sparsification if memory/performance limits are reached.
- OpenFlights route data is historical and should be treated as a public demo dataset, not a current airline schedule.
- The visual map projection is a global Lambert conformal conic approximation inspired by aviation chart projections. It is for visual exploration, not certified navigation.
- The OpenFlights builder keeps only compact site artifacts by default. Use `--keep-raw` only when debugging the data loader.
- The builder's default Hodge visualization settings are intentionally local (`max_airports=420`, `max_edges=2200`, `k=8`, `tau=0.005`) to expose route basins that are visually legible.
- The DOJ graph is a source-text co-mention graph. An edge only means two tracked terms appeared in the same DOJ PDF; it must not be presented as guilt, involvement, conduct, or a personal relationship.
- The DOJ Library warns that some formats, including handwritten text and some images, may not be reliably searchable. The local worker marks low-text PDFs as `needs_ocr` and does not fake OCR.
- DOJ also warns that sensitive or non-public personal information may remain despite redactions. The local site artifacts avoid storing raw extracted text and keep source URLs/derived counts instead.
- The local Python environment prints conda entry-point warnings about `typing_extensions.Sentinel`; these warnings did not block the benchmark, artifact build, or site verification.
