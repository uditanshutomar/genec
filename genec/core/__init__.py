"""Core GenEC modules."""

from genec.core.dependency_analyzer import DependencyAnalyzer, ClassDependencies, MethodInfo, FieldInfo
from genec.core.evolutionary_miner import EvolutionaryMiner, EvolutionaryData
from genec.core.graph_builder import GraphBuilder
from genec.core.cluster_detector import ClusterDetector, Cluster
from genec.core.llm_interface import LLMInterface, RefactoringSuggestion
from genec.core.verification_engine import VerificationEngine, VerificationResult
from genec.core.pipeline import GenECPipeline, PipelineResult

__all__ = [
    'DependencyAnalyzer', 'ClassDependencies', 'MethodInfo', 'FieldInfo',
    'EvolutionaryMiner', 'EvolutionaryData',
    'GraphBuilder',
    'ClusterDetector', 'Cluster',
    'LLMInterface', 'RefactoringSuggestion',
    'VerificationEngine', 'VerificationResult',
    'GenECPipeline', 'PipelineResult',
]
