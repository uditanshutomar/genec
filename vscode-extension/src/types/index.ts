/**
 * TypeScript type definitions for GenEC VS Code Extension
 */

// ============================================================================
// CLI Output Types
// ============================================================================

export interface GenECResult {
    status: 'success' | 'error' | 'cancelled';
    message: string;
    runtime?: string;
    original_metrics?: ClassMetrics;
    suggestions: RefactoringSuggestion[];
    applied_refactorings?: AppliedRefactoring[];
    graph_data?: GraphData;
    clusters?: ClusterData[];
}

export interface ClusterData {
    name: string;
    members: string[];
    quality_tier?: 'should' | 'could' | 'potential';
    cohesion_score?: number;
}

export interface ClassMetrics {
    lcom5: number;
    tcc: number;
    cbo: number;
    num_methods: number;
    num_fields: number;
}

export interface RefactoringSuggestion {
    name: string;
    verified: boolean;
    new_class_code?: string;
    modified_original_code?: string;
    methods?: string[];
    fields?: string[];
    rationale?: string;
    reasoning?: string;
    confidence_score?: number;
    quality_score?: number;
    quality_tier?: 'should' | 'could' | 'potential';
    quality_reasons?: string[];
    verification_status?: string;
}

export interface AppliedRefactoring {
    success: boolean;
    new_class_path?: string;
    original_class_path?: string;
    error_message?: string;
    commit_hash?: string;
}

export interface GraphData {
    nodes: GraphNode[];
    links: GraphEdge[];
}

export interface GraphNode {
    id: string;
    type?: 'method' | 'field';
    weight?: number;
}

export interface GraphEdge {
    source: string;
    target: string;
    weight?: number;
    type?: string;
}

// ============================================================================
// Progress Events
// ============================================================================

export interface ProgressEvent {
    type: 'progress';
    stage: number;
    total: number;
    percent?: number;
    message: string;
    details?: Record<string, unknown>;
}

export interface ErrorEvent {
    type: 'error';
    message: string;
}

export type GenECEvent = ProgressEvent | ErrorEvent;

// ============================================================================
// State Types
// ============================================================================

export interface AnalysisState {
    targetFile: string;
    repoPath: string;
    startTime: Date;
    result?: GenECResult;
    isRunning: boolean;
}

export interface RefactoringHistory {
    id: string;
    timestamp: Date;
    targetFile: string;
    extractedClass: string;
    extractedClassPath: string;
    backupPath?: string;
    success: boolean;
}

// ============================================================================
// TreeView Types
// ============================================================================

export type SuggestionTreeItemType =
    | 'tier-header'
    | 'suggestion'
    | 'method'
    | 'field'
    | 'info';

export interface SuggestionTreeItem {
    type: SuggestionTreeItemType;
    label: string;
    description?: string;
    tooltip?: string;
    tier?: 'should' | 'could' | 'potential';
    suggestion?: RefactoringSuggestion;
    suggestionIndex?: number;
    children?: SuggestionTreeItem[];
}

// ============================================================================
// Configuration
// ============================================================================

export interface GenECConfig {
    pythonPath: string;
    apiKey?: string;
    autoApply: boolean;
    clustering: {
        minClusterSize: number;
        maxClusterSize: number;
        minCohesion: number;
    };
}

// ============================================================================
// Quality Tiers
// ============================================================================

export const QUALITY_TIERS = {
    should: {
        label: 'SHOULD Refactor',
        icon: 'check-circle',
        color: '#4CAF50',
        description: 'High quality, strong evidence (score ≥70)'
    },
    could: {
        label: 'COULD Refactor',
        icon: 'warning',
        color: '#FF9800',
        description: 'Medium quality, review recommended (score ≥40)'
    },
    potential: {
        label: 'POTENTIAL',
        icon: 'info',
        color: '#9E9E9E',
        description: 'Lower quality, informational (score <40)'
    }
} as const;
