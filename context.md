# Project Context: Discrete Hodge Rank Clustering

## Project Purpose
Topological clustering of directed graphs via Discrete Hodge Decomposition on asymmetric rank flows. It leverages combinatorial Hodge theory to decompose directed flow networks into hierarchical (gradient) and cyclic (curl, harmonic) components, clustering via persistence-based topological simplification on the recovered potential field.

## Current Task
Going through the repository to critique it and fix any issues found (specifically over-segmentation under simple steepest ascent).

## Recent Changes
- Addressed severe over-segmentation issue by refactoring Step 5 of the clustering pipeline to use a **persistence-based topological simplification (watershed-style Union-Find)** on the potential field.
- Added `tau` parameter (topological simplification threshold) to the class constructor to allow relative thresholding of shallow local maxima.
- Exponentiated the benchmark performance (Adjusted Rand Index improved from **0.0894** to **0.8429**).
- Added `benchmark.py` and `requirements.txt`.

## Verification Commands
```bash
python benchmark.py
```

## Durable Local Caveats
- Requires `numpy`, `scipy`, and `scikit-learn`.
- In large graphs, $B_2$ triangle enumeration can scale poorly. Consider triangle sparsification if memory/performance limits are reached.
