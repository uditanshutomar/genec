import logging
import sys
import time
from pathlib import Path
from genec.core.evolutionary_miner import EvolutionaryMiner

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_miner_stall():
    repo_path = "/Users/uditanshutomar/commons-lang-fresh"
    class_file = "src/main/java/org/apache/commons/lang3/ArrayUtils.java"

    logger.info("Starting miner test...")

    miner = EvolutionaryMiner(cache_dir=".genec_cache_test")

    start_time = time.time()
    try:
        # Run with explicit max_workers to test parallelization
        evo_data = miner.mine_method_cochanges(
            class_file=class_file,
            repo_path=repo_path,
            window_months=12,
            min_commits=2,
            max_workers=4  # Force 4 workers
        )

        duration = time.time() - start_time
        logger.info(f"Mining completed in {duration:.2f} seconds")
        logger.info(f"Total commits: {evo_data.total_commits}")
        logger.info(f"Methods found: {len(evo_data.method_names)}")

    except Exception as e:
        logger.error(f"Mining failed: {e}", exc_info=True)

if __name__ == "__main__":
    test_miner_stall()
