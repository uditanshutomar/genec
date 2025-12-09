/**
 * SuggestionsTreeProvider - TreeView for displaying refactoring suggestions
 */
import * as vscode from 'vscode';
import { RefactoringSuggestion, QUALITY_TIERS } from '../types';
import { StateManager } from '../services/StateManager';

type TreeItemData = {
    type: 'tier' | 'suggestion' | 'method' | 'field' | 'info';
    tier?: 'should' | 'could' | 'potential';
    suggestion?: RefactoringSuggestion;
    suggestionIndex?: number;
    label?: string;
};

export class SuggestionTreeItem extends vscode.TreeItem {
    constructor(
        public readonly data: TreeItemData,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super('', collapsibleState);
        this.configure();
    }

    private configure(): void {
        switch (this.data.type) {
            case 'tier':
                this.configureTier();
                break;
            case 'suggestion':
                this.configureSuggestion();
                break;
            case 'method':
                this.configureMethod();
                break;
            case 'field':
                this.configureField();
                break;
            case 'info':
                this.configureInfo();
                break;
        }
    }

    private configureTier(): void {
        const tier = this.data.tier!;
        const tierInfo = QUALITY_TIERS[tier];
        this.label = tierInfo.label;
        this.description = tierInfo.description;
        this.iconPath = new vscode.ThemeIcon(
            tierInfo.icon,
            new vscode.ThemeColor(
                tier === 'should' ? 'testing.iconPassed' :
                    tier === 'could' ? 'editorWarning.foreground' :
                        'descriptionForeground'
            )
        );
        this.contextValue = 'tier';
    }

    private configureSuggestion(): void {
        const suggestion = this.data.suggestion!;
        this.label = suggestion.name;

        // Build description with score and verification status
        const parts: string[] = [];
        if (suggestion.quality_score !== undefined) {
            parts.push(`${Math.round(suggestion.quality_score)}/100`);
        }
        if (suggestion.verified) {
            parts.push('✓ Verified');
        }
        if (suggestion.methods?.length) {
            parts.push(`${suggestion.methods.length} methods`);
        }
        this.description = parts.join(' • ');

        // Tooltip with rationale
        if (suggestion.rationale || suggestion.reasoning) {
            this.tooltip = new vscode.MarkdownString(
                `**${suggestion.name}**\n\n${suggestion.rationale || suggestion.reasoning}`
            );
        }

        // Icon based on tier
        const tier = suggestion.quality_tier || 'potential';
        this.iconPath = new vscode.ThemeIcon(
            'symbol-class',
            new vscode.ThemeColor(
                tier === 'should' ? 'testing.iconPassed' :
                    tier === 'could' ? 'editorWarning.foreground' :
                        'descriptionForeground'
            )
        );

        this.contextValue = 'suggestion';
    }

    private configureMethod(): void {
        this.label = this.data.label;
        this.iconPath = new vscode.ThemeIcon('symbol-method');
        this.contextValue = 'method';
    }

    private configureField(): void {
        this.label = this.data.label;
        this.iconPath = new vscode.ThemeIcon('symbol-field');
        this.contextValue = 'field';
    }

    private configureInfo(): void {
        this.label = this.data.label;
        this.iconPath = new vscode.ThemeIcon('info');
        this.contextValue = 'info';
    }
}

export class SuggestionsTreeProvider implements vscode.TreeDataProvider<SuggestionTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<SuggestionTreeItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private stateManager: StateManager;

    constructor() {
        this.stateManager = StateManager.getInstance();

        // Refresh when suggestions change
        this.stateManager.onSuggestionsChanged(() => {
            this.refresh();
        });
    }

    public refresh(): void {
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: SuggestionTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: SuggestionTreeItem): Thenable<SuggestionTreeItem[]> {
        if (!element) {
            return Promise.resolve(this.getRootItems());
        }

        if (element.data.type === 'tier') {
            return Promise.resolve(this.getSuggestionsForTier(element.data.tier!));
        }

        if (element.data.type === 'suggestion') {
            return Promise.resolve(this.getSuggestionDetails(element.data.suggestion!));
        }

        return Promise.resolve([]);
    }

    private getRootItems(): SuggestionTreeItem[] {
        const suggestions = this.stateManager.getSuggestions();

        if (suggestions.length === 0) {
            // Show info when no suggestions
            const analysisState = this.stateManager.getCurrentAnalysis();
            if (analysisState?.isRunning) {
                return [new SuggestionTreeItem(
                    { type: 'info', label: 'Analysis in progress...' },
                    vscode.TreeItemCollapsibleState.None
                )];
            }
            return [new SuggestionTreeItem(
                { type: 'info', label: 'No suggestions. Analyze a Java class to start.' },
                vscode.TreeItemCollapsibleState.None
            )];
        }

        // Group by tier
        const tiers: ('should' | 'could' | 'potential')[] = ['should', 'could', 'potential'];
        const items: SuggestionTreeItem[] = [];

        for (const tier of tiers) {
            const tierSuggestions = suggestions.filter(s => s.quality_tier === tier);
            if (tierSuggestions.length > 0) {
                items.push(new SuggestionTreeItem(
                    { type: 'tier', tier },
                    vscode.TreeItemCollapsibleState.Expanded
                ));
            }
        }

        // Handle suggestions without tier
        const untypedSuggestions = suggestions.filter(s => !s.quality_tier);
        if (untypedSuggestions.length > 0 && items.length === 0) {
            // No tiers, show all suggestions directly
            return this.getSuggestionsForTier(undefined);
        }

        return items;
    }

    private getSuggestionsForTier(tier?: 'should' | 'could' | 'potential'): SuggestionTreeItem[] {
        const allSuggestions = this.stateManager.getSuggestions();
        const suggestions = tier
            ? allSuggestions.filter(s => s.quality_tier === tier)
            : allSuggestions;

        return suggestions.map((suggestion, idx) => {
            const globalIndex = allSuggestions.indexOf(suggestion);
            return new SuggestionTreeItem(
                { type: 'suggestion', suggestion, suggestionIndex: globalIndex },
                vscode.TreeItemCollapsibleState.Collapsed
            );
        });
    }

    private getSuggestionDetails(suggestion: RefactoringSuggestion): SuggestionTreeItem[] {
        const items: SuggestionTreeItem[] = [];

        // Add methods
        if (suggestion.methods && suggestion.methods.length > 0) {
            for (const method of suggestion.methods) {
                items.push(new SuggestionTreeItem(
                    { type: 'method', label: method },
                    vscode.TreeItemCollapsibleState.None
                ));
            }
        }

        // Add fields
        if (suggestion.fields && suggestion.fields.length > 0) {
            for (const field of suggestion.fields) {
                items.push(new SuggestionTreeItem(
                    { type: 'field', label: field },
                    vscode.TreeItemCollapsibleState.None
                ));
            }
        }

        return items;
    }
}
