"""Conceptual similarity analysis using method name and body token similarity."""

import re

import networkx as nx

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def _camel_case_split(name: str) -> list[str]:
    """Split camelCase and PascalCase names into tokens."""
    # Split on uppercase boundaries: getUserName -> [get, User, Name]
    tokens = re.sub(r'([A-Z])', r' \1', name).split()
    # Also split on underscores
    result = []
    for t in tokens:
        result.extend(t.split('_'))
    return [t.lower() for t in result if len(t) > 1]


def _extract_method_tokens(method) -> str:
    """Extract meaningful tokens from a method's name, parameters, and body identifiers."""
    tokens = []

    # Method name tokens
    tokens.extend(_camel_case_split(method.name))

    # Parameter type tokens (if available)
    if hasattr(method, 'parameters') and method.parameters:
        for param in method.parameters:
            if isinstance(param, dict):
                param_type = param.get('type', '')
                param_name = param.get('name', '')
            else:
                param_type = getattr(param, 'type', '')
                param_name = getattr(param, 'name', '')
            tokens.extend(_camel_case_split(str(param_type)))
            tokens.extend(_camel_case_split(str(param_name)))

    # Return type tokens
    if hasattr(method, 'return_type') and method.return_type:
        tokens.extend(_camel_case_split(str(method.return_type)))

    # Body identifier tokens (lightweight - just camelCase identifiers)
    if hasattr(method, 'body') and method.body:
        # Extract Java identifiers from body
        identifiers = re.findall(r'\b[a-zA-Z_]\w*\b', method.body)
        # Filter out Java keywords and very short names.
        # NOTE: This keyword set is intentionally scoped to body-token extraction
        # and kept separate from other keyword lists (e.g., in parsers) because
        # each module needs a different subset for its specific filtering purpose.
        java_keywords = {'if', 'else', 'for', 'while', 'return', 'new', 'this', 'null',
                         'true', 'false', 'int', 'long', 'double', 'float', 'boolean',
                         'void', 'String', 'public', 'private', 'protected', 'static',
                         'final', 'class', 'try', 'catch', 'throw', 'throws', 'import'}
        for ident in identifiers:
            if ident not in java_keywords and len(ident) > 2:
                tokens.extend(_camel_case_split(ident))

    return ' '.join(tokens)


def build_conceptual_graph(methods: list, min_similarity: float = 0.1) -> nx.Graph:
    """Build a graph where edges represent conceptual similarity between methods.

    Args:
        methods: List of MethodInfo objects with name, body, parameters, return_type
        min_similarity: Minimum cosine similarity to create an edge (0.0-1.0)

    Returns:
        NetworkX graph with methods as nodes and similarity-weighted edges
    """
    if not SKLEARN_AVAILABLE:
        logger.warning("scikit-learn not available; returning empty conceptual graph")
        return nx.Graph()

    if len(methods) < 2:
        G = nx.Graph()
        for m in methods:
            sig = getattr(m, 'signature', m.name)
            G.add_node(sig, type="method")
        return G

    # Extract tokens for each method
    method_sigs = []
    documents = []
    for m in methods:
        sig = getattr(m, 'signature', m.name)
        method_sigs.append(sig)
        documents.append(_extract_method_tokens(m))

    # Filter out empty documents
    valid_indices = [i for i, d in enumerate(documents) if d.strip()]
    if len(valid_indices) < 2:
        G = nx.Graph()
        for sig in method_sigs:
            G.add_node(sig, type="method")
        return G

    valid_sigs = [method_sigs[i] for i in valid_indices]
    valid_docs = [documents[i] for i in valid_indices]

    # Compute TF-IDF similarity
    try:
        vectorizer = TfidfVectorizer(max_features=500, min_df=1)
        tfidf_matrix = vectorizer.fit_transform(valid_docs)
        sim_matrix = cosine_similarity(tfidf_matrix)
    except ValueError as e:
        logger.warning(f"TF-IDF failed: {e}")
        G = nx.Graph()
        for sig in method_sigs:
            G.add_node(sig, type="method")
        return G

    # Build graph
    G = nx.Graph()
    for sig in method_sigs:
        G.add_node(sig, type="method")

    for i in range(len(valid_sigs)):
        for j in range(i + 1, len(valid_sigs)):
            similarity = float(sim_matrix[i, j])
            if similarity >= min_similarity:
                G.add_edge(valid_sigs[i], valid_sigs[j], weight=similarity)

    logger.info(f"Conceptual graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G
