import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

export class GenECViewProvider implements vscode.WebviewViewProvider {

    public static readonly viewType = 'genec.refactorView';

    private _view?: vscode.WebviewView;
    private _currentProcess?: cp.ChildProcess;
    private _currentSuggestions: any[] = [];
    private _targetFilePath: string = '';

    private _outputChannel: vscode.OutputChannel;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _context: vscode.ExtensionContext
    ) {
        this._outputChannel = vscode.window.createOutputChannel('GenEC Refactoring');
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                this._extensionUri
            ]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(async (data) => {
            switch (data.type) {
                case 'refactor': {
                    const config = vscode.workspace.getConfiguration('genec');
                    const pythonPath = config.get<string>('pythonPath') || 'python3';
                    const autoApply = config.get<boolean>('autoApply') || false;
                    const minClusterSize = config.get<number>('clustering.minClusterSize');
                    const maxClusterSize = config.get<number>('clustering.maxClusterSize');
                    const minCohesion = config.get<number>('clustering.minCohesion');

                    // Sync API Key to settings if provided
                    if (data.apiKey) {
                        await config.update('apiKey', data.apiKey, vscode.ConfigurationTarget.Global);
                    }

                    this._runRefactoring(pythonPath, data.apiKey, autoApply, minClusterSize, maxClusterSize, minCohesion);
                    break;
                }
                case 'stop': {
                    this._stopRefactoring();
                    break;
                }
                case 'apply': {
                    this._applyRefactoring(data.index);
                    break;
                }
                case 'undo': {
                    this._undoRefactoring(data.apiKey);
                    break;
                }
                case 'preview': {
                    this._previewRefactoring(data.index);
                    break;
                }
                case 'openFile': {
                    // Handle file open requests from webview
                    if (data.path) {
                        const uri = vscode.Uri.file(data.path);
                        vscode.commands.executeCommand('vscode.open', uri);
                    }
                    break;
                }
                case 'getSettings': {
                    this._sendSettings();
                    break;
                }
                case 'saveSettings': {
                    this._saveSettings(data.settings);
                    break;
                }
            }
        });
    }

    private async _sendSettings() {
        if (!this._view) return;
        const config = vscode.workspace.getConfiguration('genec');
        const settings = {
            pythonPath: config.get<string>('pythonPath'),
            apiKey: config.get<string>('apiKey'),
            autoApply: config.get<boolean>('autoApply'),
            minClusterSize: config.get<number>('clustering.minClusterSize'),
            maxClusterSize: config.get<number>('clustering.maxClusterSize'),
            minCohesion: config.get<number>('clustering.minCohesion')
        };
        this._safePostMessage({ type: 'settings', value: settings });
    }

    /**
     * Safe wrapper for postMessage that handles disposed webview gracefully.
     * Prevents crashes when user closes sidebar during long-running operations.
     */
    private _safePostMessage(message: any): boolean {
        try {
            if (this._view && this._view.webview) {
                this._safePostMessage(message);
                return true;
            }
            console.log('GenEC: Webview not available, skipping message:', message.type);
            return false;
        } catch (error: any) {
            // Webview may be disposed - this is not an error, just log it
            console.log('GenEC: Failed to post message (webview may be disposed):', error.message);
            return false;
        }
    }

    private async _saveSettings(settings: any) {
        if (!this._view) return;
        const config = vscode.workspace.getConfiguration('genec');
        await config.update('pythonPath', settings.pythonPath, vscode.ConfigurationTarget.Global);
        await config.update('apiKey', settings.apiKey, vscode.ConfigurationTarget.Global);
        await config.update('autoApply', settings.autoApply, vscode.ConfigurationTarget.Global);
        await config.update('clustering.minClusterSize', settings.minClusterSize, vscode.ConfigurationTarget.Global);
        await config.update('clustering.maxClusterSize', settings.maxClusterSize, vscode.ConfigurationTarget.Global);
        await config.update('clustering.minCohesion', settings.minCohesion, vscode.ConfigurationTarget.Global);

        this._safePostMessage({ type: 'settings', value: settings, status: 'Settings saved!' });
    }

    private async _previewRefactoring(index: number) {
        const suggestion = this._currentSuggestions[index];
        if (!suggestion || !this._targetFilePath) {
            vscode.window.showErrorMessage('Could not preview refactoring: Missing data.');
            return;
        }

        if (!suggestion.new_class_code || !suggestion.modified_original_code) {
            vscode.window.showErrorMessage('Could not preview refactoring: Code not available. Please re-run analysis.');
            return;
        }

        // Use OS temp directory to avoid polluting project
        const os = require('os');
        const tempDir = os.tmpdir();
        const tempModifiedPath = path.join(tempDir, `genec_preview_${path.basename(this._targetFilePath)}`);
        const tempNewClassPath = path.join(tempDir, `genec_preview_${suggestion.name}.java`);

        // Track temp files for cleanup
        const tempFiles: string[] = [tempModifiedPath, tempNewClassPath];

        try {
            // Create temp file for modified original
            const originalUri = vscode.Uri.file(this._targetFilePath);

            // Write modified content to temp file
            fs.writeFileSync(tempModifiedPath, suggestion.modified_original_code, 'utf8');
            const modifiedUri = vscode.Uri.file(tempModifiedPath);

            // Open Diff View
            await vscode.commands.executeCommand('vscode.diff',
                originalUri,
                modifiedUri,
                `Diff: ${path.basename(this._targetFilePath)} ↔ Modified`
            );

            // Open new class in a new tab (read-only if possible, or just a file)
            fs.writeFileSync(tempNewClassPath, suggestion.new_class_code, 'utf8');
            const newClassDoc = await vscode.workspace.openTextDocument(tempNewClassPath);
            await vscode.window.showTextDocument(newClassDoc, { viewColumn: vscode.ViewColumn.Beside, preview: true });

            // Schedule cleanup when tabs are closed (fire and forget)
            setTimeout(() => {
                for (const tempFile of tempFiles) {
                    try {
                        if (fs.existsSync(tempFile)) {
                            fs.unlinkSync(tempFile);
                            this._outputChannel.appendLine(`[CLEANUP] Removed temp file: ${tempFile}`);
                        }
                    } catch (e) {
                        // Ignore cleanup errors
                    }
                }
            }, 60000); // Cleanup after 1 minute

        } catch (e: any) {
            vscode.window.showErrorMessage(`Failed to preview refactoring: ${e.message}`);
            // Immediate cleanup on error
            for (const tempFile of tempFiles) {
                try { fs.unlinkSync(tempFile); } catch (e) { /* ignore */ }
            }
        }
    }

    /**
     * Robustly parse JSON from CLI output that may contain DEBUG logs.
     * Tries multiple strategies to extract valid JSON.
     */
    private parseJsonOutput(output: string): any {
        // Try parsing directly first
        try {
            return JSON.parse(output);
        } catch (e) {
            // Ignore, try fallback
        }

        // Try to find JSON starting from each line (working backwards)
        const lines = output.trim().split('\n');
        for (let i = lines.length - 1; i >= 0; i--) {
            try {
                // Try parsing from this line to the end
                const candidate = lines.slice(i).join('\n');
                return JSON.parse(candidate);
            } catch (e) {
                // Try just this line
                try {
                    return JSON.parse(lines[i]);
                } catch (e2) {
                    // Continue to next line
                }
            }
        }

        // Try finding the first '{' and parsing from there as last resort
        const jsonStart = output.indexOf('{');
        if (jsonStart !== -1) {
            try {
                return JSON.parse(output.substring(jsonStart));
            } catch (e) {
                // Ignore
            }
        }

        // All parsing attempts failed
        throw new Error('Could not find valid JSON in CLI output. Output may not contain valid JSON or may be malformed.');
    }

    private async _undoRefactoring(apiKey: string) {
        if (!this._targetFilePath) {
            vscode.window.showErrorMessage('No target file selected.');
            return;
        }

        const config = vscode.workspace.getConfiguration('genec');
        const pythonPath = config.get<string>('pythonPath') || 'python3';
        const repoPath = vscode.workspace.workspaceFolders?.[0].uri.fsPath || '';

        this._safePostMessage({ type: 'status', value: 'Undoing last refactoring...' });

        try {
            const args = ['-m', 'genec.cli', '--target', this._targetFilePath, '--repo', repoPath, '--rollback', '--json'];

            // Pass API key just in case, though rollback doesn't need it
            const env = { ...process.env };
            if (apiKey) env.ANTHROPIC_API_KEY = apiKey;

            const output = await new Promise<string>((resolve, reject) => {
                cp.execFile(pythonPath, args, { cwd: repoPath, env: env }, (error, stdout, stderr) => {
                    if (error) {
                        reject(new Error(stderr || stdout || error.message));
                    } else {
                        resolve(stdout);
                    }
                });
            });

            const result = this.parseJsonOutput(output);
            if (result.status === 'success') {
                vscode.window.showInformationMessage('Undo successful! Restored original file.');
                this._safePostMessage({ type: 'status', value: 'Undo successful.' });
                this._safePostMessage({ type: 'clear', value: 'Undo successful. Original file restored.' });
            } else {
                vscode.window.showErrorMessage(`Undo failed: ${result.message || 'Unknown error'}`);
                this._safePostMessage({ type: 'error', value: `Undo failed: ${result.message}` });
            }

        } catch (e: any) {
            vscode.window.showErrorMessage(`Undo failed: ${e.message}`);
            this._safePostMessage({ type: 'error', value: e.message });
        }
    }

    private _stopRefactoring() {
        if (this._currentProcess) {
            this._outputChannel.appendLine('[USER] Stop requested, sending SIGINT...');

            // Graceful shutdown chain: SIGINT -> SIGTERM -> SIGKILL
            // SIGINT allows Python to run cleanup handlers
            this._currentProcess.kill('SIGINT');

            const process = this._currentProcess;

            // If still running after 3s, escalate to SIGTERM
            setTimeout(() => {
                if (process && !process.killed) {
                    this._outputChannel.appendLine('[USER] Process still running, sending SIGTERM...');
                    process.kill('SIGTERM');
                }
            }, 3000);

            // If still running after 6s, force kill
            setTimeout(() => {
                if (process && !process.killed) {
                    this._outputChannel.appendLine('[USER] Force killing process with SIGKILL...');
                    process.kill('SIGKILL');
                }
            }, 6000);

            this._currentProcess = undefined;
            if (this._view) {
                this._safePostMessage({ type: 'status', value: 'Refactoring stopped by user.' });
                this._safePostMessage({ type: 'stopped' });
            }
        }
    }

    private _validatePath(filePath: string): void {
        /**
         * Validate that a file path is safe to write to.
         * Prevents path traversal attacks and ensures writes stay within workspace.
         */
        const resolved = path.resolve(filePath);
        const workspaceFolders = vscode.workspace.workspaceFolders;

        if (!workspaceFolders || workspaceFolders.length === 0) {
            throw new Error('No workspace folder is open');
        }

        // Check if the resolved path is within any workspace folder
        const isWithinWorkspace = workspaceFolders.some(folder => {
            const workspacePath = folder.uri.fsPath;
            const relative = path.relative(workspacePath, resolved);
            return !relative.startsWith('..') && !path.isAbsolute(relative);
        });

        if (!isWithinWorkspace) {
            const workspacePaths = workspaceFolders.map(f => f.uri.fsPath).join(', ');
            throw new Error(`Attempted to write outside workspace: ${resolved}. Workspace folders: ${workspacePaths}`);
        }

        // Additional check: ensure no path traversal sequences
        const normalizedPath = path.normalize(filePath);
        if (normalizedPath.includes('..')) {
            throw new Error(`Invalid path contains traversal sequence: ${filePath}`);
        }
    }

    private async _applyRefactoring(index: number) {
        const suggestion = this._currentSuggestions[index];
        if (!suggestion || !this._targetFilePath) {
            vscode.window.showErrorMessage('Could not apply refactoring: Missing data.');
            return;
        }

        const targetDir = path.dirname(this._targetFilePath);
        const newClassPath = path.join(targetDir, `${suggestion.name}.java`);

        try {
            // Validate paths before writing
            this._validatePath(newClassPath);
            this._validatePath(this._targetFilePath);

            // Write new class file
            fs.writeFileSync(newClassPath, suggestion.new_class_code, 'utf8');

            // Update original file
            fs.writeFileSync(this._targetFilePath, suggestion.modified_original_code, 'utf8');

            vscode.window.showInformationMessage(`Refactoring applied! Created ${suggestion.name}.java`);

            // Clear suggestions to prevent conflicting edits
            this._currentSuggestions = [];

            if (this._view) {
                this._safePostMessage({
                    type: 'clear',
                    value: `Applied ${suggestion.name}. The file has changed. Please re-run to find more refactorings.`
                });
            }

            // Open the new file
            const doc = await vscode.workspace.openTextDocument(newClassPath);
            await vscode.window.showTextDocument(doc);

        } catch (e: any) {
            vscode.window.showErrorMessage(`Failed to apply refactoring: ${e.message}`);
        }
    }

    private async _runRefactoring(
        pythonPath: string,
        finalApiKey: string,
        autoApply: boolean,
        minClusterSize?: number,
        maxClusterSize?: number,
        minCohesion?: number
    ) {
        if (!this._view) {
            return;
        }

        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('No active editor found.');
            return;
        }

        const document = editor.document;
        if (document.languageId !== 'java') {
            vscode.window.showErrorMessage('GenEC only supports Java files.');
            return;
        }

        this._targetFilePath = document.fileName;
        const className = path.basename(this._targetFilePath);
        if (this._view) {
            this._safePostMessage({ type: 'status', value: 'Initializing GenEC...' });
            this._safePostMessage({ type: 'clear', value: 'Initializing...' }); // Clear previous results
        }

        // Get configuration
        const config = vscode.workspace.getConfiguration('genec');

        const repoPath = this._findGitRoot(this._targetFilePath);

        // Get API key if not already provided (e.g., from webview)
        if (!finalApiKey) {
            let storedApiKey = config.get<string>('apiKey') || process.env.ANTHROPIC_API_KEY;
            if (!storedApiKey) {
                storedApiKey = await vscode.window.showInputBox({
                    prompt: 'Enter your Anthropic API Key',
                    password: true,
                    ignoreFocusOut: true
                });

                if (storedApiKey) {
                    await config.update('apiKey', storedApiKey, vscode.ConfigurationTarget.Global);
                }
            }
            finalApiKey = storedApiKey || ''; // Ensure finalApiKey is set
        }


        this._safePostMessage({
            type: 'start',
            target: className,
            value: `Running refactoring on ${className}...`
        });

        try {
            // Find a free port for WebSocket
            const wsPort = 9876; // Default port, could be dynamic

            const args = ['-m', 'genec.cli', '--target', this._targetFilePath, '--repo', repoPath, '--json'];

            // Enable WebSocket progress
            args.push('--websocket', wsPort.toString());

            if (autoApply) {
                args.push('--apply-all');
            }
            if (minClusterSize !== undefined) {
                args.push('--min-cluster-size', minClusterSize.toString());
            }
            if (maxClusterSize !== undefined) {
                args.push('--max-cluster-size', maxClusterSize.toString());
            }
            if (minCohesion !== undefined) {
                args.push('--min-cohesion', minCohesion.toString());
            }

            // Start WebSocket client
            this._connectWebSocket(wsPort);

            // Pass API key via environment variable for security (not visible in process list)
            const env = { ...process.env };
            if (finalApiKey) {
                env.ANTHROPIC_API_KEY = finalApiKey;
            }

            // LOGGING FOR DEBUGGING
            this._outputChannel.appendLine('--- GenEC Debug Info ---');
            this._outputChannel.appendLine(`Python Path: ${pythonPath}`);
            this._outputChannel.appendLine(`Command: ${pythonPath} ${args.join(' ')}`);
            this._outputChannel.appendLine(`CWD: ${repoPath}`);
            this._outputChannel.appendLine('------------------------');

            const output = await new Promise<string>((resolve, reject) => {
                // Timeout: 10 minutes max (prevents hanging forever)
                const TIMEOUT_MS = 10 * 60 * 1000;
                let timeoutId: NodeJS.Timeout | undefined;

                this._currentProcess = cp.spawn(pythonPath, args, {
                    cwd: repoPath,
                    env: env
                });

                let stdout = '';
                let stderr = '';

                // Set up timeout
                timeoutId = setTimeout(() => {
                    if (this._currentProcess) {
                        this._outputChannel.appendLine('[TIMEOUT] Process exceeded 10 minute limit, terminating...');
                        this._safePostMessage({ type: 'status', value: 'Timeout: killing process...' });

                        // Graceful shutdown: SIGTERM first, then SIGKILL after 5s
                        this._currentProcess.kill('SIGTERM');
                        setTimeout(() => {
                            if (this._currentProcess) {
                                this._currentProcess.kill('SIGKILL');
                            }
                        }, 5000);
                    }
                }, TIMEOUT_MS);

                this._currentProcess.stdout?.on('data', (data) => {
                    const dataStr = data.toString();
                    stdout += dataStr;
                    // Log stdout for debugging
                    this._outputChannel.appendLine(`[STDOUT] ${dataStr.trim()}`);
                });

                this._currentProcess.stderr?.on('data', (data) => {
                    const dataStr = data.toString();
                    stderr += dataStr;
                    // Log stderr for debugging
                    this._outputChannel.appendLine(`[STDERR] ${dataStr.trim()}`);

                    // Parse each line for progress/errors
                    const lines = dataStr.split('\n');
                    for (const line of lines) {
                        const trimmedLine = line.trim();
                        if (!trimmedLine) continue;

                        // Try to parse JSON progress events first
                        if (trimmedLine.startsWith('{') && trimmedLine.includes('"type":"progress"')) {
                            try {
                                const progressEvent = JSON.parse(trimmedLine);
                                if (progressEvent.type === 'progress') {
                                    this._safePostMessage({
                                        type: 'status',
                                        value: `[${progressEvent.stage}/${progressEvent.total}] ${progressEvent.message}`
                                    });
                                }
                            } catch { }
                        }

                        // Parse Stage progress from log format
                        const stageMatch = trimmedLine.match(/\[Stage \d+\/\d+\] .+/);
                        if (stageMatch) {
                            this._safePostMessage({
                                type: 'status',
                                value: stageMatch[0].trim()
                            });
                        }

                        // Show ERROR messages prominently to user
                        if (trimmedLine.includes('ERROR') || trimmedLine.includes('Error:')) {
                            const errorMsg = trimmedLine.replace(/^.*?(ERROR|Error:)\s*/, '').trim();
                            if (errorMsg.length > 10) {  // Avoid empty/short errors
                                this._safePostMessage({
                                    type: 'error',
                                    value: errorMsg
                                });
                            }
                        }

                        // Show critical warnings to user
                        if (trimmedLine.includes('File too large') ||
                            trimmedLine.includes('CONFLICT DETECTED') ||
                            trimmedLine.includes('OOM') ||
                            trimmedLine.includes('out of memory')) {
                            this._safePostMessage({
                                type: 'warning',
                                value: trimmedLine.replace(/^.*?WARNING\s*:?\s*/, '').trim()
                            });
                        }
                    }
                });

                this._currentProcess.on('close', (code) => {
                    // Clear timeout on close
                    if (timeoutId) {
                        clearTimeout(timeoutId);
                    }
                    this._currentProcess = undefined;
                    this._outputChannel.appendLine(`Process exited with code: ${code}`);

                    if (code === 0) {
                        resolve(stdout);
                    } else if (code === null) {
                        // Process killed
                        reject(new Error('Process terminated'));
                    } else {
                        // Send the actual stderr as the error message
                        reject(new Error(stderr || `GenEC failed with code ${code}`));
                    }
                });

                this._currentProcess.on('error', (err) => {
                    if (timeoutId) {
                        clearTimeout(timeoutId);
                    }
                    this._outputChannel.appendLine(`[ERROR] Process error: ${err.message}`);
                    reject(new Error(`Failed to start GenEC: ${err.message}`));
                });
            });

            try {
                const result = this.parseJsonOutput(output);

                // Always send graph data if available
                if (result.graph_data) {
                    this._safePostMessage({ type: 'graph_data', value: result });
                }

                // Check if any refactorings were applied
                if (result.applied_refactorings && result.applied_refactorings.length > 0) {
                    const successfulApps = result.applied_refactorings.filter((app: any) => app.success);

                    if (successfulApps.length > 0) {
                        const classNames = successfulApps.map((app: any) => path.basename(app.new_class_path || app.new_class)).join(', ');

                        // Create links for the webview
                        const fileLinks = successfulApps.map((app: any) => {
                            const filePath = app.new_class_path || app.new_class;
                            const fileName = path.basename(filePath);
                            return `<a href="command:vscode.open?${encodeURIComponent(JSON.stringify(vscode.Uri.file(filePath)))}">${fileName}</a>`;
                        }).join(', ');

                        vscode.window.showInformationMessage(`Successfully extracted: ${classNames}`);

                        const failedApps = result.applied_refactorings.filter((app: any) => !app.success);

                        // Build complete summary showing ALL suggestions by tier
                        let summaryHtml = `<h3>Refactoring Summary</h3>`;

                        // Section 1: Successfully Applied (SHOULD tier)
                        if (successfulApps.length > 0) {
                            summaryHtml += `<div class="tier-section" style="border-left: 4px solid #4CAF50; padding-left: 12px; margin-bottom: 15px;">`;
                            summaryHtml += `<strong style="color: #4CAF50;">✅ Extracted Classes (SHOULD tier - Auto-applied):</strong><br>`;
                            summaryHtml += `<p style="font-size: 11px; color: var(--vscode-descriptionForeground); margin: 5px 0;">High quality, strong evidence (score ≥70)</p>`;
                            summaryHtml += `<ul style="margin: 5px 0; padding-left: 20px;">`;
                            summaryHtml += successfulApps.map((app: any) => {
                                const filePath = app.new_class_path || app.new_class;
                                const fileName = path.basename(filePath);
                                // Use onclick with postMessage instead of command: href (works in webview)
                                return `<li><a href="#" class="file-link" data-path="${filePath.replace(/"/g, '&quot;')}" style="color: var(--vscode-textLink-foreground); cursor: pointer;">${fileName}</a></li>`;
                            }).join('');
                            summaryHtml += `</ul></div>`;
                        }

                        // Get suggestions that were NOT applied (COULD and POTENTIAL tiers)
                        const allSuggestions = result.suggestions || [];
                        const appliedNames = new Set(successfulApps.map((app: any) => {
                            const filePath = app.new_class_path || app.new_class;
                            return path.basename(filePath).replace('.java', '');
                        }));
                        const notApplied = allSuggestions.filter((s: any) => !appliedNames.has(s.name));
                        const couldSuggestions = notApplied.filter((s: any) => s.quality_tier === 'could');
                        const potentialSuggestions = notApplied.filter((s: any) => s.quality_tier === 'potential');

                        // Section 2: COULD tier (for review)
                        if (couldSuggestions.length > 0) {
                            summaryHtml += `<div class="tier-section" style="border-left: 4px solid #FF9800; padding-left: 12px; margin-bottom: 15px;">`;
                            summaryHtml += `<strong style="color: #FF9800;">⚠️ Available for Review (COULD tier):</strong><br>`;
                            summaryHtml += `<p style="font-size: 11px; color: var(--vscode-descriptionForeground); margin: 5px 0;">Medium quality, conditional recommendation (score ≥40)</p>`;
                            summaryHtml += `<ul style="margin: 5px 0; padding-left: 20px;">`;
                            summaryHtml += couldSuggestions.map((s: any) => {
                                const scoreText = s.quality_score !== undefined ? ` (${Math.round(s.quality_score)}/100)` : '';
                                return `<li><strong>${s.name}</strong>${scoreText}${s.verified ? ' ✓ Verified' : ''}</li>`;
                            }).join('');
                            summaryHtml += `</ul></div>`;
                        }

                        // Section 3: POTENTIAL tier (informational)
                        if (potentialSuggestions.length > 0) {
                            summaryHtml += `<div class="tier-section" style="border-left: 4px solid #9E9E9E; padding-left: 12px; margin-bottom: 15px;">`;
                            summaryHtml += `<strong style="color: #9E9E9E;">💡 Informational (POTENTIAL tier):</strong><br>`;
                            summaryHtml += `<p style="font-size: 11px; color: var(--vscode-descriptionForeground); margin: 5px 0;">Lower quality, structural detection only (score <40)</p>`;
                            summaryHtml += `<ul style="margin: 5px 0; padding-left: 20px;">`;
                            summaryHtml += potentialSuggestions.map((s: any) => {
                                const scoreText = s.quality_score !== undefined ? ` (${Math.round(s.quality_score)}/100)` : '';
                                return `<li>${s.name}${scoreText}</li>`;
                            }).join('');
                            summaryHtml += `</ul></div>`;
                        }

                        // Section 4: Failed refactorings
                        if (failedApps.length > 0) {
                            summaryHtml += `<div class="tier-section" style="border-left: 4px solid var(--vscode-errorForeground); padding-left: 12px; margin-bottom: 15px;">`;
                            summaryHtml += `<strong style="color: var(--vscode-errorForeground);">❌ Failed Refactorings:</strong><br>`;
                            summaryHtml += `<ul style="margin: 5px 0; padding-left: 20px;">`;
                            summaryHtml += failedApps.map((app: any) => `<li>${app.error_message || 'Unknown error'}</li>`).join('');
                            summaryHtml += `</ul></div>`;
                        }

                        summaryHtml += `<p style="font-size: 12px; margin-top: 10px;">The original file has been updated. COULD/POTENTIAL suggestions can be applied manually below.</p>`;

                        // Store summary in result to be sent to frontend
                        result.summary = summaryHtml;

                        // Open the last created file
                        const lastApp = successfulApps[successfulApps.length - 1];
                        const lastFilePath = lastApp.new_class_path || lastApp.new_class;
                        const doc = await vscode.workspace.openTextDocument(lastFilePath);
                        await vscode.window.showTextDocument(doc);

                        // Continue to show suggestions (COULD/POTENTIAL tiers)
                    }
                }

                this._currentSuggestions = result.suggestions || [];

                // If we are in apply-all mode (which we always are now), we should NOT show tiles
                // unless explicitly requested or if something went wrong but we still want to show options.
                // But user requested "i dont want these apply refactoring boxes anymore".

                if (result.applied_refactorings && result.applied_refactorings.length > 0) {
                    // Already handled above
                } else {
                    // No refactorings applied
                    let message = `Analysis complete but no refactorings were applied automatically.<br><br>Suggestions found: ${this._currentSuggestions.length}`;

                    // Add graph metrics if available
                    if (result.graph_data) {
                        const nodes = result.graph_data.nodes?.length || 0;
                        const edges = result.graph_data.links?.length || 0;
                        message += `<br><br><b>Graph Metrics:</b><br>`;
                        message += `• Nodes: ${nodes}<br>`;
                        message += `• Edges: ${edges}<br>`;
                        if (nodes > 0 && edges > 0) {
                            const density = (2 * edges / (nodes * (nodes - 1))).toFixed(4);
                            message += `• Density: ${density}`;
                        }
                    }

                    // Add cluster info if available
                    if (result.clusters && result.clusters.length > 0) {
                        message += `<br><br><b>Clustering:</b><br>`;
                        message += `• Total clusters: ${result.clusters.length}<br>`;
                        const viableClusters = result.clusters.filter((c: any) => c.members?.length >= 3);
                        message += `• Clusters with 3+ members: ${viableClusters.length}`;
                    }

                    // Add verification details if available
                    if (result.verification_results && result.verification_results.length > 0) {
                        const failures = result.verification_results.filter((r: any) => r.status !== 'PASSED_ALL');
                        if (failures.length > 0) {
                            message += '<br><br><b>Verification Failures:</b><br>';
                            message += failures.map((f: any) => {
                                return `• Suggestion ${f.suggestion_id}: ${f.status}<br>&nbsp;&nbsp;${f.error_message || 'No details'}`;
                            }).join('<br>');
                        }
                    }

                    this._safePostMessage({
                        type: 'clear',
                        value: message,
                        graph_data: result.graph_data  // Include graph data for rendering
                    });
                }

                // Send results to frontend
                this._safePostMessage({ type: 'results', value: result });
            } catch (e) {
                console.error('Failed to parse JSON:', output);
                this._safePostMessage({
                    type: 'error',
                    value: 'Failed to parse GenEC output. Output length: ' + output.length + '. First 100 chars: ' + output.substring(0, 100)
                });
            }

        } catch (e: any) {
            if (e.message !== 'Process terminated') {
                const msg = e.message.trim();
                this._safePostMessage({ type: 'error', value: msg });
            }
        }
    }

    private _updateWebview(result: any, output: string) {
        if (this._view) {
            let message = `Analysis complete but no refactorings were applied automatically.<br><br>Suggestions found: ${this._currentSuggestions.length}`;

            if (this._currentSuggestions.length === 0) {
                if (result.clusters && result.clusters.length > 0) {
                    const total = result.clusters.length;
                    const viable = result.clusters.filter((c: any) => c.members.length >= 2).length;
                    message += `<br><br>Clustering:<br>• Total clusters: ${total}<br>• Clusters with 3+ members: ${viable}`;
                }
            }

            this._safePostMessage({
                type: 'clear',
                value: message,
                graph_data: result.graph_data
            });
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        // Get path to vis-network script (bundled in resources folder)
        const visPathOnDisk = vscode.Uri.joinPath(this._extensionUri, 'resources', 'vis-network.min.js');
        const visUri = webview.asWebviewUri(visPathOnDisk);

        return `<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>GenEC Refactoring</title>
            <script type="text/javascript" src="${visUri}"></script>
            <style>
                body { font-family: var(--vscode-font-family); padding: 10px; }
                .container { display: flex; flex-direction: column; gap: 10px; }
                input { padding: 5px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); }
                button { padding: 8px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; cursor: pointer; }
                button:hover { background: var(--vscode-button-hoverBackground); }
                button:disabled { opacity: 0.5; cursor: not-allowed; }
                .result-item { border: 1px solid var(--vscode-panel-border); padding: 10px; margin-top: 10px; }
                .class-name { font-weight: bold; font-size: 1.1em; }
                .rationale { margin-top: 5px; font-style: italic; }
                .verified { color: var(--vscode-testing-iconPassed); }
                .error { color: var(--vscode-errorForeground); border: 1px solid var(--vscode-errorForeground); padding: 10px; margin-top: 10px; white-space: pre-wrap; }
                #targetInfo { font-size: 0.9em; color: var(--vscode-descriptionForeground); margin-bottom: 5px; }
                .apply-btn { margin-top: 10px; width: 100%; background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); }
                .apply-btn:hover { background: var(--vscode-button-secondaryHoverBackground); }

                #graph-container {
                    width: 100%;
                    height: 400px;
                    border: 1px solid var(--vscode-panel-border);
                    background-color: var(--vscode-editor-background);
                    display: none; /* Hidden by default */
                }
                .tab-container { display: flex; gap: 5px; margin-bottom: 5px; }
                .tab { padding: 5px 10px; cursor: pointer; border-bottom: 2px solid transparent; }
                .tab.active { border-bottom-color: var(--vscode-button-background); font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <h3>GenEC Refactoring</h3>
                <div id="targetInfo"></div>

                <div class="tab-container">
                    <div class="tab active" onclick="switchTab('run', event)">Run</div>
                    <div class="tab" onclick="switchTab('graph', event)">Graph</div>
                    <div class="tab" onclick="switchTab('settings', event)">Settings</div>
                </div>

                <div id="tab-run" class="tab-content">
                    <label for="apiKey">Anthropic API Key:</label>
                    <input type="password" id="apiKey" placeholder="sk-ant-...">
                    <div style="display: flex; gap: 10px; margin-top: 10px;">
                        <button id="refactorBtn" style="flex: 1;">Refactor Current Class</button>
                        <button id="stopBtn" style="flex: 1;" disabled>Stop</button>
                    </div>
                    <div style="margin-top: 10px;">
                         <button id="undoBtn" style="width: 100%;">Undo Last Refactoring</button>
                    </div>
                    <div id="status" style="margin-top: 10px;"></div>
                    <div id="results"></div>
                </div>

                <div id="tab-graph" class="tab-content" style="display: none;">
                    <div id="graph-container"></div>
                    <div id="cluster-info" style="margin-top: 10px;"></div>
                </div>

                <div id="tab-settings" class="tab-content" style="display: none;">
                    <div class="setting-item">
                        <label for="setting-pythonPath">Python Path:</label>
                        <input type="text" id="setting-pythonPath" placeholder="python3 or /path/to/python">
                    </div>
                    <div class="setting-item">
                        <label for="setting-apiKey">Anthropic API Key:</label>
                        <input type="password" id="setting-apiKey" placeholder="sk-ant-...">
                    </div>
                    <div class="setting-item">
                        <label style="display: flex; align-items: center; gap: 10px;">
                            <input type="checkbox" id="setting-autoApply" style="width: auto;">
                            Auto-Apply Refactorings
                        </label>
                        <small style="display: block; color: var(--vscode-descriptionForeground);">If checked, GenEC will automatically apply the best suggestion.</small>
                    </div>

                    <h4 style="margin-top: 20px; border-bottom: 1px solid var(--vscode-settings-headerBorder);">Clustering Parameters</h4>
                    <div class="setting-item">
                        <label for="setting-minClusterSize">Min Cluster Size:</label>
                        <input type="number" id="setting-minClusterSize" min="1" value="2">
                    </div>
                    <div class="setting-item">
                        <label for="setting-maxClusterSize">Max Cluster Size:</label>
                        <input type="number" id="setting-maxClusterSize" min="5" value="20">
                    </div>
                    <div class="setting-item">
                        <label for="setting-minCohesion">Min Cohesion (0.0 - 1.0):</label>
                        <input type="number" id="setting-minCohesion" min="0" max="1" step="0.1" value="0.1">
                    </div>

                    <button id="saveSettingsBtn" style="width: 100%; margin-top: 10px;">Save Settings</button>
                    <div id="settingsStatus" style="margin-top: 5px; color: var(--vscode-descriptionForeground);"></div>
                </div>
            </div>
            <script>
                const vscode = acquireVsCodeApi();
                const refactorBtn = document.getElementById('refactorBtn');
                const stopBtn = document.getElementById('stopBtn');
                const undoBtn = document.getElementById('undoBtn');
                const apiKeyInput = document.getElementById('apiKey');
                const statusDiv = document.getElementById('status');
                const resultsDiv = document.getElementById('results');
                const targetInfoDiv = document.getElementById('targetInfo');
                const graphContainer = document.getElementById('graph-container');
                const clusterInfoDiv = document.getElementById('cluster-info');

                // Settings elements
                const settingPythonPath = document.getElementById('setting-pythonPath');
                const settingApiKey = document.getElementById('setting-apiKey');
                let network = null;

                // Initialize
                window.addEventListener('message', event => {
                    const message = event.data;
                    switch (message.type) {
                        case 'status':
                            document.getElementById('status').textContent = message.value;
                            break;
                        case 'results':
                            displayResults(message.value);
                            renderGraph(message.value);
                            break;
                        case 'settings':
                            updateSettingsUI(message.value);
                            if (message.status) {
                                const statusDiv = document.getElementById('settingsStatus');
                                statusDiv.textContent = message.status;
                                setTimeout(() => statusDiv.textContent = '', 3000);
                            }
                            break;
                        case 'stopped':
                            document.getElementById('status').textContent = 'Refactoring stopped.';
                            document.getElementById('refactorBtn').disabled = false;
                            document.getElementById('stopBtn').disabled = true;
                            break;
                        case 'clear':
                            document.getElementById('results').innerHTML = message.value;
                            if (message.graph_data) {
                                renderGraph({ graph_data: message.graph_data });
                            }
                            break;
                        case 'graph_data':
                            renderGraph({ graph_data: message.value.graph_data });
                            break;
                        case 'error':
                            document.getElementById('results').innerHTML = \`<div class="result-item" style="border-color: var(--vscode-errorForeground);"><strong style="color: var(--vscode-errorForeground);">Error:</strong> \${message.value}</div>\`;
                            document.getElementById('status').textContent = 'Error occurred.';
                            document.getElementById('refactorBtn').disabled = false;
                            document.getElementById('stopBtn').disabled = true;
                            break;
                    }
                });

                // Request settings on load
                vscode.postMessage({ type: 'getSettings' });

                function updateSettingsUI(settings) {
                    if (settings.pythonPath) document.getElementById('setting-pythonPath').value = settings.pythonPath;
                    if (settings.apiKey) {
                        document.getElementById('apiKey').value = settings.apiKey;
                        document.getElementById('setting-apiKey').value = settings.apiKey;
                    } else {
                        document.getElementById('apiKey').value = ''; // Clear if not set
                        document.getElementById('setting-apiKey').value = ''; // Clear if not set
                    }
                    if (settings.autoApply !== undefined) document.getElementById('setting-autoApply').checked = settings.autoApply;
                    if (settings.minClusterSize) document.getElementById('setting-minClusterSize').value = settings.minClusterSize;
                    if (settings.maxClusterSize) document.getElementById('setting-maxClusterSize').value = settings.maxClusterSize;
                    if (settings.minCohesion) document.getElementById('setting-minCohesion').value = settings.minCohesion;
                }

                function switchTab(tabName, event) {
                    document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
                    document.getElementById('tab-' + tabName).style.display = 'block';

                    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
                    if (event && event.target) {
                        event.target.classList.add('active');
                    }
                }

                document.getElementById('refactorBtn').addEventListener('click', () => {
                    const apiKey = document.getElementById('apiKey').value;
                    document.getElementById('status').textContent = 'Starting refactoring...';
                    document.getElementById('results').innerHTML = '';
                    document.getElementById('refactorBtn').disabled = true;
                    document.getElementById('stopBtn').disabled = false;

                    vscode.postMessage({
                        type: 'refactor',
                        apiKey: apiKey
                    });
                });

                document.getElementById('stopBtn').addEventListener('click', () => {
                    vscode.postMessage({ type: 'stop' });
                    document.getElementById('status').textContent = 'Stopping...';
                    document.getElementById('refactorBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = true;
                });

                document.getElementById('undoBtn').addEventListener('click', () => {
                    const apiKey = document.getElementById('apiKey').value;
                    if (confirm('Are you sure you want to undo the last refactoring? This will revert changes to the file.')) {
                        vscode.postMessage({ type: 'undo', apiKey: apiKey });
                    }
                });

                document.getElementById('saveSettingsBtn').addEventListener('click', () => {
                    const settings = {
                        pythonPath: document.getElementById('setting-pythonPath').value,
                        apiKey: document.getElementById('setting-apiKey').value,
                        autoApply: document.getElementById('setting-autoApply').checked,
                        minClusterSize: parseInt(document.getElementById('setting-minClusterSize').value),
                        maxClusterSize: parseInt(document.getElementById('setting-maxClusterSize').value),
                        minCohesion: parseFloat(document.getElementById('setting-minCohesion').value)
                    };
                    vscode.postMessage({ type: 'saveSettings', settings: settings });
                });

                function displayResults(data) {
                    const resultsDiv = document.getElementById('results');
                    const clusterInfoDiv = document.getElementById('cluster-info');
                    const graphContainer = document.getElementById('graph-container');

                    document.getElementById('refactorBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = true;
                    document.getElementById('status').textContent = 'Analysis complete.';

                    resultsDiv.innerHTML = '';

                    // Display summary if available (e.g. auto-applied refactorings)
                    if (data.summary) {
                        resultsDiv.innerHTML = data.summary;
                        resultsDiv.innerHTML += '<hr style="margin: 20px 0; border: 0; border-top: 1px solid var(--vscode-widget-border);">';

                        // Add click handlers for file links in the summary
                        resultsDiv.querySelectorAll('.file-link').forEach(link => {
                            link.addEventListener('click', (e) => {
                                e.preventDefault();
                                const filePath = link.getAttribute('data-path');
                                if (filePath) {
                                    vscode.postMessage({ type: 'openFile', path: filePath });
                                }
                            });
                        });
                    }

                    // Show suggestions if available
                    if (data.suggestions && data.suggestions.length > 0) {
                        // Filter out suggestions that were already applied
                        let suggestions = data.suggestions;
                        if (data.applied_refactorings && data.applied_refactorings.length > 0) {
                            const appliedNames = new Set(data.applied_refactorings
                                .filter((app: any) => app.success)
                                .map((app: any) => {
                                    const filePath = app.new_class_path || app.new_class;
                                    // Handle both full path and basename just in case, usually suggestion.name is simple class name
                                    return filePath.split(/[/\\]/).pop().replace('.java', '');
                                }));

                            suggestions = suggestions.filter(s => !appliedNames.has(s.name));
                        }

                        // Group suggestions by tier
                        const shouldSuggestions = suggestions.filter(s => s.quality_tier === 'should');
                        const couldSuggestions = suggestions.filter(s => s.quality_tier === 'could');
                        const potentialSuggestions = suggestions.filter(s => s.quality_tier === 'potential');

                        // Helper function to create tier section
                        const createTierSection = (title, emoji, suggestions, tierClass) => {
                            if (suggestions.length === 0) return;

                            const sectionHeader = document.createElement('h3');
                            sectionHeader.style.marginTop = '20px';
                            sectionHeader.style.marginBottom = '10px';
                            // Removed emoji from display as requested
                            sectionHeader.innerHTML = title + ' (' + suggestions.length + ')';
                            resultsDiv.appendChild(sectionHeader);

                            suggestions.forEach((suggestion, index) => {
                                const div = document.createElement('div');
                                div.className = 'result-item ' + tierClass;
                                div.style.borderLeft = tierClass === 'tier-should' ? '4px solid #4CAF50' :
                                                       tierClass === 'tier-could' ? '4px solid #FF9800' :
                                                       '4px solid #9E9E9E';
                                div.style.paddingLeft = '12px';

                                // Name and tier badge
                                const nameDiv = document.createElement('div');
                                nameDiv.className = 'class-name';
                                nameDiv.style.display = 'flex';
                                nameDiv.style.alignItems = 'center';
                                nameDiv.style.gap = '10px';

                                const nameSpan = document.createElement('span');
                                nameSpan.textContent = suggestion.name;
                                nameDiv.appendChild(nameSpan);

                                // Quality score badge
                                if (suggestion.quality_score !== undefined) {
                                    const scoreBadge = document.createElement('span');
                                    scoreBadge.style.padding = '2px 8px';
                                    scoreBadge.style.borderRadius = '12px';
                                    scoreBadge.style.fontSize = '11px';
                                    scoreBadge.style.fontWeight = 'bold';
                                    scoreBadge.style.background = tierClass === 'tier-should' ? '#4CAF50' :
                                                                   tierClass === 'tier-could' ? '#FF9800' :
                                                                   '#9E9E9E';
                                    scoreBadge.style.color = 'white';
                                    scoreBadge.textContent = Math.round(suggestion.quality_score) + '/100';
                                    nameDiv.appendChild(scoreBadge);
                                }

                                if (suggestion.verified) {
                                    const verifiedSpan = document.createElement('span');
                                    verifiedSpan.className = 'verified';
                                    verifiedSpan.textContent = ' (Verified)';
                                    nameDiv.appendChild(verifiedSpan);
                                }
                                div.appendChild(nameDiv);

                                // Quality reasons
                                if (suggestion.quality_reasons && suggestion.quality_reasons.length > 0) {
                                    const reasonsDiv = document.createElement('div');
                                    reasonsDiv.style.fontSize = '12px';
                                    reasonsDiv.style.color = 'var(--vscode-descriptionForeground)';
                                    reasonsDiv.style.marginTop = '5px';
                                    reasonsDiv.style.marginBottom = '8px';
                                    reasonsDiv.innerHTML = '<b>Quality:</b> ' + suggestion.quality_reasons.slice(0, 3).join(', ');
                                    div.appendChild(reasonsDiv);
                                }

                                if (suggestion.rationale) {
                                    const rationaleDiv = document.createElement('div');
                                    rationaleDiv.className = 'rationale';
                                    rationaleDiv.textContent = suggestion.rationale;
                                    div.appendChild(rationaleDiv);
                                }

                                const applyBtn = document.createElement('button');
                                applyBtn.className = 'apply-btn';
                                applyBtn.textContent = 'Apply Refactoring';
                                applyBtn.onclick = () => {
                                    vscode.postMessage({
                                        type: 'apply',
                                        index: data.suggestions.indexOf(suggestion)
                                    });
                                };
                                div.appendChild(applyBtn);

                                const previewBtn = document.createElement('button');
                                previewBtn.className = 'apply-btn';
                                previewBtn.style.marginTop = '5px';
                                previewBtn.style.background = 'var(--vscode-button-secondaryHoverBackground)';
                                previewBtn.textContent = 'Preview Diff';
                                previewBtn.onclick = () => {
                                    vscode.postMessage({
                                        type: 'preview',
                                        index: data.suggestions.indexOf(suggestion)
                                    });
                                };
                                div.appendChild(previewBtn);

                                resultsDiv.appendChild(div);
                            });
                        };

                        // Display suggestions by tier with descriptions
                        if (shouldSuggestions.length > 0) {
                            const shouldDesc = document.createElement('p');
                            shouldDesc.style.fontSize = '12px';
                            shouldDesc.style.color = 'var(--vscode-descriptionForeground)';
                            shouldDesc.style.marginTop = '5px';
                            shouldDesc.style.marginBottom = '15px';
                            shouldDesc.innerHTML = '<b>Auto-applied:</b> High quality, strong evidence (score ≥70)';
                            resultsDiv.appendChild(shouldDesc);
                        }
                        createTierSection('SHOULD Refactor (Auto-Applied)', '', shouldSuggestions, 'tier-should');

                        if (couldSuggestions.length > 0) {
                            const couldDesc = document.createElement('p');
                            couldDesc.style.fontSize = '12px';
                            couldDesc.style.color = 'var(--vscode-descriptionForeground)';
                            couldDesc.style.marginTop = '5px';
                            couldDesc.style.marginBottom = '15px';
                            couldDesc.innerHTML = '<b>For review:</b> Medium quality, conditional recommendation (score ≥40)';
                            resultsDiv.appendChild(couldDesc);
                        }
                        createTierSection('COULD Refactor', '', couldSuggestions, 'tier-could');

                        if (potentialSuggestions.length > 0) {
                            const potentialDesc = document.createElement('p');
                            potentialDesc.style.fontSize = '12px';
                            potentialDesc.style.color = 'var(--vscode-descriptionForeground)';
                            potentialDesc.style.marginTop = '5px';
                            potentialDesc.style.marginBottom = '15px';
                            potentialDesc.innerHTML = '<b>Informational:</b> Low quality, structural-only detection (score <40)';
                            resultsDiv.appendChild(potentialDesc);
                        }
                        createTierSection('POTENTIAL Refactoring', '', potentialSuggestions, 'tier-potential');

                    } else {
                        // Fallback: Show detected clusters if no suggestions
                        if (data.clusters && data.clusters.length > 0) {
                             const viableClusters = data.clusters.filter(c => c.members.length >= 2);
                             if (viableClusters.length > 0) {
                                 const header = document.createElement('h4');
                                 header.textContent = 'Found ' + viableClusters.length + ' Potential Clusters (No Refactoring Suggested)';
                                 resultsDiv.appendChild(header);

                                 const list = document.createElement('ul');
                                 viableClusters.forEach(c => {
                                     const li = document.createElement('li');
                                     li.textContent = 'Cluster ' + c.id + ': ' + c.members.length + ' members (Cohesion: ' + c.cohesion.toFixed(2) + ')';
                                     li.style.cursor = 'pointer';
                                     li.style.textDecoration = 'underline';
                                     li.onclick = () => {
                                         // Switch to graph tab and select nodes
                                         switchTab('graph');
                                         if (network) {
                                             network.selectNodes(c.members);
                                             clusterInfoDiv.textContent = 'Cluster ' + c.id + ': ' + c.members.join(', ');
                                         }
                                     };
                                     list.appendChild(li);
                                 });
                                 resultsDiv.appendChild(list);

                                 const tip = document.createElement('p');
                                 tip.style.fontStyle = 'italic';
                                 tip.style.fontSize = '0.9em';
                                 tip.textContent = "Tip: Try adjusting 'Max Cluster Size' in Settings if clusters are too large, or check your API Key.";
                                 resultsDiv.appendChild(tip);
                             } else {
                                 resultsDiv.textContent = 'No suggestions generated and no viable clusters found.';
                             }
                        } else {
                            resultsDiv.textContent = 'No suggestions generated.';
                        }
                    }
                }

                function renderGraph(data) {
                    if (!data.graph_data) return;

                    const graphContainer = document.getElementById('graph-container');
                    const clusterInfoDiv = document.getElementById('cluster-info');
                    graphContainer.style.display = 'block';

                    // Add controls if not present
                    let controls = document.getElementById('graph-controls');
                    if (!controls) {
                        controls = document.createElement('div');
                        controls.id = 'graph-controls';
                        controls.style.marginBottom = '10px';
                        controls.innerHTML = '<label><input type="checkbox" id="hideUnclustered"> Hide Unclustered Nodes</label>' +
                                             '<label style="margin-left: 10px;"><input type="checkbox" id="physicsToggle" checked> Physics</label>';
                        graphContainer.parentNode.insertBefore(controls, graphContainer);

                        document.getElementById('hideUnclustered').addEventListener('change', (e) => {
                             updateGraphVisibility(e.target.checked);
                        });
                         document.getElementById('physicsToggle').addEventListener('change', (e) => {
                             if (network) network.setOptions({ physics: { enabled: e.target.checked } });
                        });
                    }

                    const nodes = new vis.DataSet(data.graph_data.nodes.map(n => ({
                        id: n.id,
                        label: n.id.length > 20 ? n.id.substring(0, 20) + '...' : n.id,
                        group: n.type || 'method',
                        title: n.id,
                        value: n.weight || 1
                    })));

                    const edges = new vis.DataSet(data.graph_data.links.map(e => ({
                        from: e.source,
                        to: e.target,
                        value: e.weight
                    })));

                    // Color clusters
                    const clusteredNodeIds = new Set();
                    if (data.clusters) {
                        data.clusters.forEach((cluster, i) => {
                            // Only color viable clusters to reduce noise
                            if (cluster.members.length >= 2) {
                                const color = getColor(i);
                                cluster.members.forEach(memberId => {
                                    const node = nodes.get(memberId);
                                    if (node) {
                                        nodes.update({
                                            id: memberId,
                                            color: {background: color, border: color},
                                            size: 20 // Highlight clustered nodes
                                        });
                                        clusteredNodeIds.add(memberId);
                                    }
                                });
                            }
                        });
                    }

                    // Store for filtering
                    window.allNodes = nodes;
                    window.clusteredNodeIds = clusteredNodeIds;

                    const container = document.getElementById('graph-container');
                    const options = {
                        nodes: {
                            shape: 'dot',
                            scaling: {
                                min: 10,
                                max: 30
                            },
                            font: {
                                size: 12,
                                face: 'Tahoma'
                            }
                        },
                        edges: {
                            color: { inherit: 'from' },
                            smooth: {
                                type: 'continuous'
                            }
                        },
                        physics: {
                            stabilization: {
                                enabled: true,
                                iterations: 1000
                            },
                            barnesHut: {
                                gravitationalConstant: -30000,
                                centralGravity: 0.3,
                                springLength: 95,
                                springConstant: 0.04,
                                damping: 0.09,
                                avoidOverlap: 0.1
                            }
                        },
                        interaction: {
                            tooltipDelay: 200,
                            hideEdgesOnDrag: true
                        }
                    };

                    network = new vis.Network(container, {nodes, edges}, options);

                    network.on("click", function (params) {
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0];
                            clusterInfoDiv.textContent = "Selected: " + nodeId;
                        }
                    });
                }

                function updateGraphVisibility(hideUnclustered) {
                    if (!network || !window.allNodes) return;

                    const nodesToUpdate = [];
                    window.allNodes.forEach(node => {
                        const isClustered = window.clusteredNodeIds.has(node.id);
                        if (hideUnclustered && !isClustered) {
                            nodesToUpdate.push({id: node.id, hidden: true});
                        } else {
                            nodesToUpdate.push({id: node.id, hidden: false});
                        }
                    });
                    window.allNodes.update(nodesToUpdate);
                }

                function getColor(index) {
                    // Expanded palette
                    const colors = [
                        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD',
                        '#D4A5A5', '#9B59B6', '#3498DB', '#E67E22', '#2ECC71',
                        '#F1C40F', '#E74C3C', '#1ABC9C', '#8E44AD', '#2C3E50'
                    ];
                    return colors[index % colors.length];
                }
            </script>
        </body>
        </html>`;
    }
    private _findGitRoot(startPath: string): string {
        try {
            let current = path.dirname(startPath);
            const root = path.parse(current).root;
            while (current !== root) {
                if (fs.existsSync(path.join(current, '.git'))) {
                    return current;
                }
                current = path.dirname(current);
            }
        } catch (e) {
            console.error('Error finding git root:', e);
        }

        // Fallback to workspace folder
        const workspaceFolder = vscode.workspace.getWorkspaceFolder(vscode.Uri.file(startPath));
        return workspaceFolder ? workspaceFolder.uri.fsPath : path.dirname(startPath);
    }

    private _connectWebSocket(port: number) {
        // WebSocket is available in VS Code extension host environment (Node.js)
        const WebSocket = require('ws');

        // Wait a bit for server to start
        setTimeout(() => {
            try {
                const ws = new WebSocket(`ws://localhost:${port}`);

                ws.on('open', () => {
                    this._outputChannel.appendLine(`WebSocket connected on port ${port}`);
                });

                ws.on('message', (data: any) => {
                    try {
                        const message = JSON.parse(data.toString());

                        if (message.type === 'progress') {
                            this._safePostMessage({
                                type: 'progress',
                                stage: message.stage,
                                total: message.total,
                                percent: message.percent,
                                message: message.message
                            });
                        } else if (message.type === 'error') {
                            this._outputChannel.appendLine(`WebSocket Error: ${message.message}`);
                        }
                    } catch (e) {
                        // Ignore parse errors
                    }
                });

                ws.on('error', (error: any) => {
                    this._outputChannel.appendLine(`WebSocket connection error: ${error.message}`);
                });

                // Close when process ends
                if (this._currentProcess) {
                    this._currentProcess.on('exit', () => {
                        try { ws.close(); } catch (e) { }
                    });
                }
            } catch (e) {
                this._outputChannel.appendLine(`Failed to create WebSocket: ${e}`);
            }
        }, 1000); // 1s delay to let Python server start
    }
}
