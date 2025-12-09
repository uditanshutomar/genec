/**
 * StateManager - Centralized state management for GenEC extension
 */
import * as vscode from 'vscode';
import { GenECResult, RefactoringSuggestion, RefactoringHistory, AnalysisState } from '../types';

export class StateManager {
    private static instance: StateManager;
    private context: vscode.ExtensionContext;

    // Current analysis state
    private currentAnalysis?: AnalysisState;
    private suggestions: RefactoringSuggestion[] = [];
    private targetFile: string = '';

    // Event emitters
    private readonly _onSuggestionsChanged = new vscode.EventEmitter<RefactoringSuggestion[]>();
    public readonly onSuggestionsChanged = this._onSuggestionsChanged.event;

    private readonly _onHistoryChanged = new vscode.EventEmitter<RefactoringHistory[]>();
    public readonly onHistoryChanged = this._onHistoryChanged.event;

    private readonly _onAnalysisStateChanged = new vscode.EventEmitter<AnalysisState | undefined>();
    public readonly onAnalysisStateChanged = this._onAnalysisStateChanged.event;

    private constructor(context: vscode.ExtensionContext) {
        this.context = context;
    }

    public static initialize(context: vscode.ExtensionContext): StateManager {
        StateManager.instance = new StateManager(context);
        return StateManager.instance;
    }

    public static getInstance(): StateManager {
        if (!StateManager.instance) {
            throw new Error('StateManager not initialized. Call initialize() first.');
        }
        return StateManager.instance;
    }

    // ========================================================================
    // Current Analysis
    // ========================================================================

    public startAnalysis(targetFile: string, repoPath: string): void {
        this.currentAnalysis = {
            targetFile,
            repoPath,
            startTime: new Date(),
            isRunning: true
        };
        this.targetFile = targetFile;
        this.suggestions = [];
        this._onAnalysisStateChanged.fire(this.currentAnalysis);
        this._onSuggestionsChanged.fire([]);
    }

    public completeAnalysis(result: GenECResult): void {
        if (this.currentAnalysis) {
            this.currentAnalysis.result = result;
            this.currentAnalysis.isRunning = false;
        }
        this.suggestions = result.suggestions || [];
        this._onAnalysisStateChanged.fire(this.currentAnalysis);
        this._onSuggestionsChanged.fire(this.suggestions);
    }

    public cancelAnalysis(): void {
        if (this.currentAnalysis) {
            this.currentAnalysis.isRunning = false;
        }
        this._onAnalysisStateChanged.fire(this.currentAnalysis);
    }

    public getCurrentAnalysis(): AnalysisState | undefined {
        return this.currentAnalysis;
    }

    public isAnalysisRunning(): boolean {
        return this.currentAnalysis?.isRunning || false;
    }

    // ========================================================================
    // Suggestions
    // ========================================================================

    public getSuggestions(): RefactoringSuggestion[] {
        return this.suggestions;
    }

    public getSuggestion(index: number): RefactoringSuggestion | undefined {
        return this.suggestions[index];
    }

    public getTargetFile(): string {
        return this.targetFile;
    }

    public getRepoPath(): string | undefined {
        return this.currentAnalysis?.repoPath;
    }

    public getSuggestionsByTier(tier: 'should' | 'could' | 'potential'): RefactoringSuggestion[] {
        return this.suggestions.filter(s => s.quality_tier === tier);
    }

    public clearSuggestions(): void {
        this.suggestions = [];
        this._onSuggestionsChanged.fire([]);
    }

    public removeSuggestion(index: number): void {
        this.suggestions.splice(index, 1);
        this._onSuggestionsChanged.fire(this.suggestions);
    }

    // ========================================================================
    // Refactoring History
    // ========================================================================

    private getHistoryKey(): string {
        return 'genec.refactoringHistory';
    }

    public getHistory(): RefactoringHistory[] {
        return this.context.workspaceState.get<RefactoringHistory[]>(this.getHistoryKey()) || [];
    }

    public async addToHistory(entry: Omit<RefactoringHistory, 'id' | 'timestamp'>): Promise<void> {
        const history = this.getHistory();
        const newEntry: RefactoringHistory = {
            ...entry,
            id: this.generateId(),
            timestamp: new Date()
        };

        history.unshift(newEntry);

        // Keep only last 50 entries
        if (history.length > 50) {
            history.pop();
        }

        await this.context.workspaceState.update(this.getHistoryKey(), history);
        this._onHistoryChanged.fire(history);
    }

    public async removeFromHistory(id: string): Promise<void> {
        const history = this.getHistory().filter(h => h.id !== id);
        await this.context.workspaceState.update(this.getHistoryKey(), history);
        this._onHistoryChanged.fire(history);
    }

    public async clearHistory(): Promise<void> {
        await this.context.workspaceState.update(this.getHistoryKey(), []);
        this._onHistoryChanged.fire([]);
    }

    // ========================================================================
    // Utilities
    // ========================================================================

    private generateId(): string {
        return Date.now().toString(36) + Math.random().toString(36).substring(2);
    }

    public dispose(): void {
        this._onSuggestionsChanged.dispose();
        this._onHistoryChanged.dispose();
        this._onAnalysisStateChanged.dispose();
    }
}
