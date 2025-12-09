/**
 * GenEC VS Code Extension - Main Entry Point
 * 
 * A redesigned extension for Extract Class refactoring using native VS Code patterns.
 */
import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

// Services
import { ConfigService } from './services/ConfigService';
import { GenECService } from './services/GenECService';
import { StateManager } from './services/StateManager';

// Views
import { SuggestionsTreeProvider } from './views/SuggestionsTreeProvider';
import { HistoryTreeProvider } from './views/HistoryTreeProvider';
import { SettingsTreeProvider } from './views/SettingsTreeProvider';

// Providers
import { GenECCodeLensProvider } from './providers/GenECCodeLensProvider';

// Panels
import { GraphWebviewPanel } from './panels/GraphWebviewPanel';

let genecService: GenECService;
let stateManager: StateManager;
let statusBarItem: vscode.StatusBarItem;

export function activate(context: vscode.ExtensionContext) {
    console.log('GenEC extension activated');

    // Initialize services
    stateManager = StateManager.initialize(context);
    genecService = new GenECService(context.extensionPath);
    const configService = ConfigService.getInstance();

    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.command = 'genec.showOutput';
    context.subscriptions.push(statusBarItem);

    // Set up progress listener
    genecService.on('progress', (event) => {
        statusBarItem.text = `$(beaker~spin) GenEC: ${event.message}`;
        statusBarItem.show();
    });

    // Register TreeView providers
    const suggestionsProvider = new SuggestionsTreeProvider();
    const historyProvider = new HistoryTreeProvider();
    const settingsProvider = new SettingsTreeProvider();

    context.subscriptions.push(
        vscode.window.registerTreeDataProvider('genec.suggestions', suggestionsProvider),
        vscode.window.registerTreeDataProvider('genec.history', historyProvider),
        vscode.window.registerTreeDataProvider('genec.settings', settingsProvider)
    );

    // Register CodeLens provider for Java
    const codeLensProvider = new GenECCodeLensProvider();
    context.subscriptions.push(
        vscode.languages.registerCodeLensProvider(
            { language: 'java', scheme: 'file' },
            codeLensProvider
        )
    );

    // ==========================================================================
    // Command: Analyze Class
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.analyzeClass', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showErrorMessage('No active editor');
                return;
            }

            if (editor.document.languageId !== 'java') {
                vscode.window.showErrorMessage('GenEC only supports Java files');
                return;
            }

            const targetFile = editor.document.fileName;
            const repoPath = findGitRoot(targetFile);

            // Get API key
            const apiKey = await configService.promptForApiKey();
            if (!apiKey) {
                vscode.window.showWarningMessage('GenEC requires an Anthropic API key');
                return;
            }

            // Start analysis
            statusBarItem.text = '$(beaker~spin) GenEC: Starting...';
            statusBarItem.show();

            stateManager.startAnalysis(targetFile, repoPath);

            try {
                const result = await genecService.analyze(targetFile, repoPath, { apiKey });
                stateManager.completeAnalysis(result);

                statusBarItem.text = `$(beaker) GenEC: ${result.suggestions.length} suggestions`;

                // Show success message
                const action = await vscode.window.showInformationMessage(
                    `GenEC found ${result.suggestions.length} refactoring suggestions`,
                    'View Suggestions',
                    'Show Graph'
                );

                if (action === 'View Suggestions') {
                    vscode.commands.executeCommand('genec.focusSuggestions');
                } else if (action === 'Show Graph') {
                    vscode.commands.executeCommand('genec.showGraph');
                }

            } catch (error) {
                stateManager.cancelAnalysis();
                statusBarItem.hide();
                vscode.window.showErrorMessage(`GenEC failed: ${(error as Error).message}`);
            }
        })
    );

    // ==========================================================================
    // Command: Apply Suggestion
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.applySuggestion', async (indexOrItem?: number | any) => {
            let index: number;

            if (typeof indexOrItem === 'number') {
                index = indexOrItem;
            } else if (indexOrItem?.data?.suggestionIndex !== undefined) {
                index = indexOrItem.data.suggestionIndex;
            } else {
                // Prompt user to select
                const suggestions = stateManager.getSuggestions();
                if (suggestions.length === 0) {
                    vscode.window.showInformationMessage('No suggestions available');
                    return;
                }

                const items = suggestions.map((s, i) => ({
                    label: s.name,
                    description: s.quality_tier?.toUpperCase() || '',
                    detail: s.rationale,
                    index: i
                }));

                const selected = await vscode.window.showQuickPick(items, {
                    placeHolder: 'Select a suggestion to apply'
                });

                if (!selected) return;
                index = selected.index;
            }

            const suggestion = stateManager.getSuggestion(index);
            if (!suggestion) {
                vscode.window.showErrorMessage('Suggestion not found');
                return;
            }

            const targetFile = stateManager.getTargetFile();
            if (!targetFile) {
                vscode.window.showErrorMessage('No target file');
                return;
            }

            // Validate code is available
            if (!suggestion.new_class_code || !suggestion.modified_original_code) {
                vscode.window.showErrorMessage('Code not available. Please re-run analysis.');
                return;
            }

            // Show preview first
            const previewAction = await vscode.window.showInformationMessage(
                `Apply refactoring: Extract ${suggestion.name}?`,
                'Preview Diff',
                'Apply',
                'Cancel'
            );

            if (previewAction === 'Cancel' || !previewAction) return;

            if (previewAction === 'Preview Diff') {
                await vscode.commands.executeCommand('genec.previewSuggestion', index);
                return;
            }

            // Apply the refactoring
            try {
                const targetDir = path.dirname(targetFile);
                const newClassPath = path.join(targetDir, `${suggestion.name}.java`);
                const repoPath = stateManager.getRepoPath();

                // Validate paths are within the analysis repository
                validatePath(newClassPath, repoPath);
                validatePath(targetFile, repoPath);

                // Write files
                fs.writeFileSync(newClassPath, suggestion.new_class_code, 'utf8');
                fs.writeFileSync(targetFile, suggestion.modified_original_code, 'utf8');

                // Add to history
                await stateManager.addToHistory({
                    targetFile,
                    extractedClass: suggestion.name,
                    extractedClassPath: newClassPath,
                    success: true
                });

                // Remove only the applied suggestion (keep others for multiple extractions)
                stateManager.removeSuggestion(index);

                vscode.window.showInformationMessage(
                    `Created ${suggestion.name}.java`,
                    'Open File'
                ).then(action => {
                    if (action === 'Open File') {
                        vscode.workspace.openTextDocument(newClassPath)
                            .then(doc => vscode.window.showTextDocument(doc));
                    }
                });

            } catch (error) {
                vscode.window.showErrorMessage(`Failed to apply: ${(error as Error).message}`);
            }
        })
    );

    // ==========================================================================
    // Command: Preview Suggestion
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.previewSuggestion', async (indexOrItem?: number | any) => {
            let index: number;

            if (typeof indexOrItem === 'number') {
                index = indexOrItem;
            } else if (indexOrItem?.data?.suggestionIndex !== undefined) {
                index = indexOrItem.data.suggestionIndex;
            } else {
                return;
            }

            const suggestion = stateManager.getSuggestion(index);
            const targetFile = stateManager.getTargetFile();

            if (!suggestion || !targetFile) {
                vscode.window.showErrorMessage('Missing data for preview');
                return;
            }

            if (!suggestion.modified_original_code) {
                vscode.window.showErrorMessage('Modified code not available');
                return;
            }

            // Create temp file for diff
            const os = require('os');
            const tempDir = os.tmpdir();
            const tempModifiedPath = path.join(tempDir, `genec_${path.basename(targetFile)}`);
            const tempNewClassPath = path.join(tempDir, `genec_${suggestion.name}.java`);

            try {
                // Write modified original to temp
                fs.writeFileSync(tempModifiedPath, suggestion.modified_original_code, 'utf8');

                // Show diff
                await vscode.commands.executeCommand('vscode.diff',
                    vscode.Uri.file(targetFile),
                    vscode.Uri.file(tempModifiedPath),
                    `${path.basename(targetFile)} ↔ Modified`
                );

                // Show new class
                if (suggestion.new_class_code) {
                    fs.writeFileSync(tempNewClassPath, suggestion.new_class_code, 'utf8');
                    const doc = await vscode.workspace.openTextDocument(tempNewClassPath);
                    await vscode.window.showTextDocument(doc, vscode.ViewColumn.Beside, true);
                }

                // Cleanup after 60s
                setTimeout(() => {
                    try { fs.unlinkSync(tempModifiedPath); } catch { }
                    try { fs.unlinkSync(tempNewClassPath); } catch { }
                }, 60000);

            } catch (error) {
                vscode.window.showErrorMessage(`Preview failed: ${(error as Error).message}`);
            }
        })
    );

    // ==========================================================================
    // Command: Undo Last Refactoring
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.undoLast', async (historyItem?: any) => {
            let entryId: string | undefined;

            if (historyItem?.entry?.id) {
                entryId = historyItem.entry.id;
            } else {
                // Get most recent
                const history = stateManager.getHistory();
                if (history.length === 0) {
                    vscode.window.showInformationMessage('No refactoring history');
                    return;
                }
                entryId = history[0].id;
            }

            if (!entryId) {
                return;
            }

            const history = stateManager.getHistory();
            const entry = history.find(h => h.id === entryId);
            if (!entry) {
                vscode.window.showErrorMessage('History entry not found');
                return;
            }

            const confirm = await vscode.window.showWarningMessage(
                `Undo extraction of ${entry.extractedClass}? This will restore the original file.`,
                'Undo',
                'Cancel'
            );

            if (confirm !== 'Undo') return;

            // Note: Full undo would require backup files, which GenEC CLI handles
            // For now, we just remove from history
            await stateManager.removeFromHistory(entryId);
            vscode.window.showInformationMessage('Removed from history. Use Git to restore files if needed.');
        })
    );

    // ==========================================================================
    // Command: Show Graph
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.showGraph', () => {
            const panel = GraphWebviewPanel.createOrShow(context.extensionUri);

            const analysis = stateManager.getCurrentAnalysis();
            if (analysis?.result?.graph_data) {
                // Pass both graph_data and clusters for visualization
                panel.updateGraph(analysis.result.graph_data, analysis.result.clusters);
            }
        })
    );

    // ==========================================================================
    // Command: Show Output
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.showOutput', () => {
            genecService.showOutput();
        })
    );

    // ==========================================================================
    // Command: Focus Suggestions View
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.focusSuggestions', () => {
            vscode.commands.executeCommand('genec.suggestions.focus');
        })
    );

    // ==========================================================================
    // Command: Cancel Analysis
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.cancel', () => {
            genecService.cancel();
            stateManager.cancelAnalysis();
            statusBarItem.hide();
            vscode.window.showInformationMessage('GenEC analysis cancelled');
        })
    );

    // ==========================================================================
    // Command: Configure Settings
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.configure', () => {
            vscode.commands.executeCommand('workbench.action.openSettings', 'genec');
        })
    );

    // ==========================================================================
    // Command: Set API Key
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.setApiKey', async () => {
            const apiKey = await vscode.window.showInputBox({
                prompt: 'Enter your Anthropic API Key',
                password: true,
                ignoreFocusOut: true,
                placeHolder: 'sk-ant-api03-...',
                validateInput: (value) => {
                    if (!value || value.trim().length === 0) {
                        return 'API key is required';
                    }
                    if (!value.startsWith('sk-ant-')) {
                        return 'API key should start with sk-ant-';
                    }
                    return null;
                }
            });

            if (apiKey) {
                await configService.setApiKey(apiKey);
                settingsProvider.refresh();
                vscode.window.showInformationMessage('API key saved successfully');
            }
        })
    );

    // Register disposables
    context.subscriptions.push(genecService);
    context.subscriptions.push(stateManager);
}

// ==========================================================================
// Utility Functions
// ==========================================================================

function findGitRoot(startPath: string): string {
    let current = path.dirname(startPath);
    const root = path.parse(current).root;

    while (current !== root) {
        if (fs.existsSync(path.join(current, '.git'))) {
            return current;
        }
        current = path.dirname(current);
    }

    // Fallback to workspace folder
    const workspaceFolder = vscode.workspace.getWorkspaceFolder(vscode.Uri.file(startPath));
    return workspaceFolder?.uri.fsPath || path.dirname(startPath);
}

function validatePath(filePath: string, repoPath?: string): void {
    const resolved = path.resolve(filePath);

    // First, validate against the repo path used for analysis
    // This is the source of truth - GenEC analyzes files within this repo
    if (repoPath) {
        const relative = path.relative(repoPath, resolved);
        if (!relative.startsWith('..') && !path.isAbsolute(relative)) {
            return; // Valid - within the analysis repo
        }
    }

    // Fallback: check against VS Code workspace folders
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (workspaceFolders) {
        const isWithinWorkspace = workspaceFolders.some(folder => {
            const relative = path.relative(folder.uri.fsPath, resolved);
            return !relative.startsWith('..') && !path.isAbsolute(relative);
        });

        if (isWithinWorkspace) {
            return; // Valid - within workspace
        }
    }

    // If no repoPath and no workspace folders, allow any path within 
    // the target file's directory (for standalone file analysis)
    if (!repoPath && !workspaceFolders) {
        return; // Allow - no workspace context
    }

    throw new Error('Path outside workspace');
}

export function deactivate() {
    if (genecService) {
        genecService.dispose();
    }
}
