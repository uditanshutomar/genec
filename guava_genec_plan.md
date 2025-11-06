# GenEC Proposed Extraction — AbstractFuture

**Proposed class name:** `AbstractFutureOperations`

**Rationale:** Separate value retrieval & listener execution logic from cancellation control using the generated state-accessor scaffold.

**Members (9 )**
- get(long,TimeUnit)
- get()
- getFromAlreadyDoneTrustedFuture()
- getUninterruptiblyInternal(Future<V>)
- isCancelled()
- getFutureValue(ListenableFuture<?>)
- getUninterruptibly(Future<V>)
- tryInternalFastPathGetFailure()
- executeListener(Runnable,Executor)

**Structural plan:** `/Users/uditanshutomar/genec/data/outputs/structural_plans/AbstractFuture/cluster_02_structural_plan.md`
