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
    configService.setContext(context); // Enable secret storage for API key

    // Prompt for API key on first activation if not set
    (async () => {
        const existingKey = await configService.getApiKeyAsync();
        if (!existingKey) {
            const action = await vscode.window.showWarningMessage(
                'GenEC: No Anthropic API key configured. LLM-powered naming will be disabled.',
                'Set API Key',
                'Later'
            );
            if (action === 'Set API Key') {
                void vscode.commands.executeCommand('genec.setApiKey');
            }
        }
    })();

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
            if (genecService.isRunning()) {
                vscode.window.showWarningMessage('GenEC analysis is already running. Please wait for it to complete.');
                return;
            }

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
                    void vscode.commands.executeCommand('genec.focusSuggestions');
                } else if (action === 'Show Graph') {
                    void vscode.commands.executeCommand('genec.showGraph');
                }

            } catch (error) {
                stateManager.cancelAnalysis();
                statusBarItem.hide();
                vscode.window.showErrorMessage(`GenEC failed: ${error instanceof Error ? error.message : String(error)}`);
            }
        })
    );

    // ==========================================================================
    // Command: Apply Suggestion
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.applySuggestion', async (indexOrItem?: number | { data?: { suggestionIndex?: number } }) => {
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

            // Guard: warn if the user switched files since the analysis
            const currentFile = vscode.window.activeTextEditor?.document.uri.fsPath;
            const analysisFile = targetFile;
            if (currentFile && analysisFile && currentFile !== analysisFile) {
                vscode.window.showWarningMessage(
                    `Analysis was run on ${path.basename(analysisFile)}, but you're viewing ${path.basename(currentFile)}. Switch to the analyzed file first.`
                );
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
                const repoPath = stateManager.getRepoPath();

                // Validate class name BEFORE constructing any paths
                if (!isValidJavaClassName(suggestion.name)) {
                    vscode.window.showErrorMessage(
                        `Invalid Java class name: "${suggestion.name}". ` +
                        'Class names must start with a letter, underscore, or $, ' +
                        'and cannot be a Java reserved keyword.'
                    );
                    return;
                }

                const targetDir = path.dirname(targetFile);
                const newClassPath = path.join(targetDir, `${suggestion.name}.java`);

                // Auto-save any dirty buffers before applying
                const dirtyDocs = vscode.workspace.textDocuments.filter(doc => doc.isDirty);
                if (dirtyDocs.length > 0) {
                    const saved = await vscode.workspace.saveAll(false);
                    if (!saved) {
                        vscode.window.showWarningMessage('Save cancelled. Refactoring not applied.');
                        return;
                    }
                }

                // Validate paths are within the analysis repository
                if (!repoPath) {
                    vscode.window.showErrorMessage('No repository context. Please re-run analysis.');
                    return;
                }
                validatePath(newClassPath, repoPath);
                validatePath(targetFile, repoPath);

                // Write files atomically with rollback
                const originalBackup = fs.readFileSync(targetFile, 'utf8');
                try {
                    fs.writeFileSync(newClassPath, suggestion.new_class_code, 'utf8');
                    fs.writeFileSync(targetFile, suggestion.modified_original_code, 'utf8');
                } catch (writeError) {
                    // Rollback: restore original file, remove new class
                    try { fs.writeFileSync(targetFile, originalBackup, 'utf8'); } catch { }
                    try { fs.unlinkSync(newClassPath); } catch { }
                    throw writeError;
                }

                // Add to history
                await stateManager.addToHistory({
                    targetFile,
                    extractedClass: suggestion.name,
                    extractedClassPath: newClassPath,
                    success: true
                });

                // Remove only the applied suggestion (keep others for multiple extractions)
                stateManager.removeSuggestion(index);

                const action = await vscode.window.showInformationMessage(
                    `Created ${suggestion.name}.java`,
                    'Open File'
                );
                if (action === 'Open File') {
                    try {
                        const doc = await vscode.workspace.openTextDocument(newClassPath);
                        await vscode.window.showTextDocument(doc);
                    } catch { }
                }

            } catch (error) {
                vscode.window.showErrorMessage(`Failed to apply: ${error instanceof Error ? error.message : String(error)}`);
            }
        })
    );

    // ==========================================================================
    // Command: Preview Suggestion
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.previewSuggestion', async (indexOrItem?: number | { data?: { suggestionIndex?: number } }) => {
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

            // Guard: warn if the user switched files since the analysis
            const currentFile = vscode.window.activeTextEditor?.document.uri.fsPath;
            if (currentFile && targetFile && currentFile !== targetFile) {
                vscode.window.showWarningMessage(
                    `Analysis was run on ${path.basename(targetFile)}, but you're viewing ${path.basename(currentFile)}. Switch to the analyzed file first.`
                );
                return;
            }

            if (!suggestion.modified_original_code) {
                vscode.window.showErrorMessage('Modified code not available');
                return;
            }

            // Create temp file for diff
            const os = require('os');
            const tempDir = os.tmpdir();
            const timestamp = Date.now();
            const tempModifiedPath = path.join(tempDir, `genec_${timestamp}_${path.basename(targetFile)}`);
            const tempNewClassPath = path.join(tempDir, `genec_${timestamp}_${suggestion.name}.java`);

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
                    try { fs.unlinkSync(tempModifiedPath); } catch (e) { /* temp file, ok to fail */ }
                    try { fs.unlinkSync(tempNewClassPath); } catch (e) { /* temp file, ok to fail */ }
                }, 60000);

            } catch (error) {
                vscode.window.showErrorMessage(`Preview failed: ${error instanceof Error ? error.message : String(error)}`);
            }
        })
    );

    // ==========================================================================
    // Command: Undo Last Refactoring
    // ==========================================================================
    context.subscriptions.push(
        vscode.commands.registerCommand('genec.undoLast', async (historyItem?: { entry?: { id?: string } }) => {
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

            await stateManager.removeFromHistory(entryId);
            vscode.window.showInformationMessage(
                `Removed "${entry.extractedClass}" from history. ` +
                'To restore the original code, use Git: git checkout -- <file>'
            );
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

    // Register disposables for providers and services
    context.subscriptions.push(codeLensProvider);
    context.subscriptions.push(suggestionsProvider);
    context.subscriptions.push(historyProvider);
    context.subscriptions.push(settingsProvider);
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

function isValidJavaClassName(name: string): boolean {
    // Must be non-empty, start with a letter or underscore, contain only valid chars
    // Must not be a Java reserved keyword
    const JAVA_KEYWORDS = new Set([
        'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char',
        'class', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
        'extends', 'final', 'finally', 'float', 'for', 'goto', 'if', 'implements',
        'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new',
        'package', 'private', 'protected', 'public', 'return', 'short', 'static',
        'strictfp', 'super', 'switch', 'synchronized', 'this', 'throw', 'throws',
        'transient', 'try', 'void', 'volatile', 'while'
    ]);
    if (!name || name.length === 0 || name.length > 255) {
        return false;
    }
    if (!/^[a-zA-Z_$][a-zA-Z0-9_$]*$/.test(name)) {
        return false;
    }
    return !JAVA_KEYWORDS.has(name);
}

function validatePath(filePath: string, repoPath: string): void {
    if (!repoPath) {
        throw new Error(
            'Security validation failed: No repository context. ' +
            'Please open a folder or workspace before using GenEC.'
        );
    }

    const resolved = path.resolve(filePath);

    // First, validate against the repo path used for analysis
    // This is the source of truth - GenEC analyzes files within this repo
    const relative = path.relative(repoPath, resolved);
    if (!relative.startsWith('..') && !path.isAbsolute(relative)) {
        return; // Valid - within the analysis repo
    }

    // Fallback: check against VS Code workspace folders
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (workspaceFolders) {
        const isWithinWorkspace = workspaceFolders.some(folder => {
            const wsRelative = path.relative(folder.uri.fsPath, resolved);
            return !wsRelative.startsWith('..') && !path.isAbsolute(wsRelative);
        });

        if (isWithinWorkspace) {
            return; // Valid - within workspace
        }
    }

    throw new Error(
        `Path outside allowed boundaries: ${resolved}. ` +
        `File must be within the workspace or repository.`
    );
}

export function deactivate() {
    if (genecService) {
        genecService.dispose();
    }
    if (stateManager) {
        stateManager.dispose();
    }
}
