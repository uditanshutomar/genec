# Metric Baseline Cluster — AbstractFuture

## Members (11 )
- get(long,TimeUnit)
- get()
- getFromAlreadyDoneTrustedFuture()
- getDoneValue(Object)
- getUninterruptiblyInternal(Future<V>)
- isCancelled()
- getFutureValue(ListenableFuture<?>)
- getUninterruptibly(Future<V>)
- tryInternalFastPathGetFailure()
- executeListener(Runnable,Executor)
- cancellationExceptionWithCause(String,Throwable)

## Top Internal Dependency Edges
- get(long,TimeUnit) ↔ get() (weight 0.50)
- get(long,TimeUnit) ↔ getFromAlreadyDoneTrustedFuture() (weight 0.50)
- get(long,TimeUnit) ↔ getFutureValue(ListenableFuture<?>) (weight 0.50)
- get(long,TimeUnit) ↔ getUninterruptibly(Future<V>) (weight 0.50)
- get(long,TimeUnit) ↔ tryInternalFastPathGetFailure() (weight 0.50)

## Metrics
| Metric | Original Class | Baseline Cluster |
| --- | --- | --- |
| LCOM5 | 0.000 | 0.000 |
| TCC | 0.114 | 0.000 |
| CBO | 9 | 8 |

**Metric rationale:** High mutual call weights keep LCOM5 at zero and barely reduce CBO (9→8), so the metric-only heuristic marks this group as highly cohesive.

**Semantic reality:** Mixes cancellation/error handling (`isCancelled`, `tryInternalFastPathGetFailure`) with listener execution (`executeListener`) and value retrieval, combining distinct responsibilities.
