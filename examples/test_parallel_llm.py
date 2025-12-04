import time
import logging
import concurrent.futures
from unittest.mock import MagicMock, patch
from genec.core.llm_interface import LLMInterface, RefactoringSuggestion
from genec.core.cluster_detector import Cluster

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def mock_generate_suggestion(cluster, *args, **kwargs):
    """Simulate LLM latency."""
    logger.info(f"Started processing cluster {cluster.id}")
    time.sleep(2)  # Simulate 2 seconds latency
    logger.info(f"Finished processing cluster {cluster.id}")
    return RefactoringSuggestion(
        cluster_id=cluster.id,
        proposed_class_name=f"MockClass{cluster.id}",
        rationale="Mock rationale",
        new_class_code="",
        modified_original_code="",
        cluster=cluster
    )

def test_parallel_execution():
    logger.info("Testing parallel execution...")
    
    # Create mock clusters
    clusters = [Cluster(id=i, member_names=[]) for i in range(5)]
    
    # Initialize LLMInterface
    llm = LLMInterface(api_key="mock_key")
    # Mock availability
    llm._available = True
    
    # Mock the single suggestion generation method
    llm.generate_refactoring_suggestion = MagicMock(side_effect=mock_generate_suggestion)
    
    start_time = time.time()
    
    # Run batch generation
    suggestions = llm.generate_batch_suggestions(
        clusters=clusters,
        original_code="",
        class_deps=MagicMock(),
        max_suggestions=5,
        max_workers=5
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info(f"Total duration: {duration:.2f} seconds")
    logger.info(f"Generated {len(suggestions)} suggestions")
    
    # Verification
    if duration < 3.0:
        logger.info("✅ PASSED: Execution was parallel (took < 3s for 5 tasks of 2s each)")
    else:
        logger.error(f"❌ FAILED: Execution was too slow ({duration:.2f}s), likely sequential")

if __name__ == "__main__":
    test_parallel_execution()
