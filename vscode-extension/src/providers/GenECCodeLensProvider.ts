/**
 * GenECCodeLensProvider - Provides inline CodeLens above Java class declarations
 */
import * as vscode from 'vscode';
import { StateManager } from '../services/StateManager';

export class GenECCodeLensProvider implements vscode.CodeLensProvider {
    private _onDidChangeCodeLenses = new vscode.EventEmitter<void>();
    public readonly onDidChangeCodeLenses = this._onDidChangeCodeLenses.event;

    private stateManager: StateManager;

    constructor() {
        this.stateManager = StateManager.getInstance();

        // Refresh CodeLens when suggestions change
        this.stateManager.onSuggestionsChanged(() => {
            this._onDidChangeCodeLenses.fire();
        });

        this.stateManager.onAnalysisStateChanged(() => {
            this._onDidChangeCodeLenses.fire();
        });
    }

    public refresh(): void {
        this._onDidChangeCodeLenses.fire();
    }

    provideCodeLenses(
        document: vscode.TextDocument,
        token: vscode.CancellationToken
    ): vscode.ProviderResult<vscode.CodeLens[]> {
        if (document.languageId !== 'java') {
            return [];
        }

        const codeLenses: vscode.CodeLens[] = [];
        const text = document.getText();

        // Find class declarations
        // Matches: public class ClassName, class ClassName, public abstract class, etc.
        const classRegex = /^\s*(public\s+)?(abstract\s+)?(final\s+)?class\s+(\w+)/gm;
        let match;

        while ((match = classRegex.exec(text)) !== null) {
            const line = document.lineAt(document.positionAt(match.index).line);
            const range = new vscode.Range(line.range.start, line.range.end);
            const className = match[4];

            // Check if this file is the current target
            const currentAnalysis = this.stateManager.getCurrentAnalysis();
            const isCurrentFile = currentAnalysis?.targetFile === document.uri.fsPath;

            if (isCurrentFile && currentAnalysis?.isRunning) {
                // Show "Analyzing..." while running
                codeLenses.push(new vscode.CodeLens(range, {
                    title: '$(loading~spin) GenEC: Analyzing...',
                    command: 'genec.showOutput',
                    tooltip: 'Click to show GenEC output'
                }));
            } else if (isCurrentFile && this.stateManager.getSuggestions().length > 0) {
                // Show suggestion count if analysis complete
                const count = this.stateManager.getSuggestions().length;
                const verified = this.stateManager.getSuggestions().filter(s => s.verified).length;

                codeLenses.push(new vscode.CodeLens(range, {
                    title: `$(beaker) GenEC: ${count} suggestions (${verified} verified)`,
                    command: 'genec.focusSuggestions',
                    tooltip: 'Click to view suggestions'
                }));

                // Add quick apply for SHOULD tier
                const shouldSuggestions = this.stateManager.getSuggestionsByTier('should');
                if (shouldSuggestions.length > 0) {
                    codeLenses.push(new vscode.CodeLens(range, {
                        title: `$(play) Apply ${shouldSuggestions[0].name}`,
                        command: 'genec.applySuggestion',
                        arguments: [0],
                        tooltip: 'Apply the top SHOULD suggestion'
                    }));
                }
            } else {
                // Show analyze action
                codeLenses.push(new vscode.CodeLens(range, {
                    title: '$(beaker) GenEC: Analyze Class',
                    command: 'genec.analyzeClass',
                    tooltip: 'Analyze this class for Extract Class refactoring opportunities'
                }));
            }
        }

        return codeLenses;
    }
}
