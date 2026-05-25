---
name: hodge-autoresearch
description: Executes an autonomous research loop to optimize Hodge Rank Clustering parameters or logic based on benchmark ARI.
---

# Hodge AutoResearch Skill

## Goal
Improve the Adjusted Rand Index (ARI) of the Discrete Hodge Rank Clustering algorithm by iteratively modifying the monolithic code and verifying results against the internal benchmark.

## Instructions
1. **Analyze:** Read `hodge_clustering.py` and the current `results.tsv` (if it exists).
2. **Propose:** Identify a potential optimization (e.g., modifying `tau`, adjusting `k` neighbors, or damping logic).
3. **Modify:** Edit the monolithic file `hodge_clustering.py` with the new hypothesis.
4. **Execute:** Run the `scripts/experiment_harness.py`.
5. **Evaluate:** Parse the ARI score from the output.
6. **Refine:**
   - If **ARI improves**: Commit the change and update the baseline.
   - If **ARI fails or drops**: Revert the change to the previous best state.
7. **Loop:** Repeat until the performance plateaus or the compute budget is exhausted.

## Constraints
- **Never Stop:** Do not ask for human permission once the loop starts.
- **One Change:** Only modify one logical component or parameter per iteration to maintain causal clarity.
- **Preserve Interface:** Do not change the `fit_predict` signature.
