# Metrics vs Intent Summary

| Project | Class | Cluster | LCOM5 (before→after) | TCC (before→after) | CBO (before→after) | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Guava | `AbstractFuture` | Metric-only “get/execute” cluster | 0.000→0.000 | 0.094→0.000 | 27→8 | Metrics stay flat while cancellation + listeners mix. |
| Commons IO | `IOUtils` | Scratch-buffer helper cluster (fused) | 0.993→0.000* | 0.091→0.000* | 37→0* | Static graph found nothing; fused captures thread-local scratch helpers (internal weight 1.25, external 0). “*” uses simulated structural deltas pending actual extraction. |

*Simulated structural deltas because helper methods live in nested classes outside the current static-analysis scope. Implementing the proposed state-accessor/facade would isolate these helpers cleanly.*
