import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { GenECViewProvider } from './GenECViewProvider';

export function activate(context: vscode.ExtensionContext) {
    console.log('GenEC extension is now active!');

    // Check for bundled binary
    const bundledPath = path.join(context.extensionPath, 'dist', 'genec');
    const bundledExePath = path.join(context.extensionPath, 'dist', 'genec.exe');
    const isBundled = fs.existsSync(bundledPath) || fs.existsSync(bundledExePath);

    if (isBundled) {
        console.log('GenEC: Running in bundled mode (binary found)');
    } else {
        // Validate Python installation at startup
        const config = vscode.workspace.getConfiguration('genec');
        const pythonPath = config.get<string>('pythonPath') || 'python3';

        validatePythonInstallation(pythonPath).then(valid => {
            if (!valid) {
                vscode.window.showWarningMessage(
                    `GenEC: Python not found at '${pythonPath}'. Please configure genec.pythonPath in settings.`,
                    'Open Settings'
                ).then(selection => {
                    if (selection === 'Open Settings') {
                        vscode.commands.executeCommand('workbench.action.openSettings', 'genec.pythonPath');
                    }
                });
            } else {
                // Python found - check and install dependencies
                ensureDependencies(pythonPath, context);
            }
        });
    }

    // Cleanup any recovery files from previous crashes
    cleanupRecoveryFiles();

    // Register Webview View Provider
    const provider = new GenECViewProvider(context.extensionUri, context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(GenECViewProvider.viewType, provider)
    );

    async function ensureDependencies(pythonPath: string, context: vscode.ExtensionContext) {
        // Check if genec module is importable
        const checkCmd = `${pythonPath} -c "import genec; print('ok')"`;

        cp.exec(checkCmd, async (error, stdout) => {
            if (error || !stdout.includes('ok')) {
                console.log('GenEC: Dependencies not found, offering to install...');

                const selection = await vscode.window.showInformationMessage(
                    'GenEC requires Python dependencies. Install now?',
                    'Install Dependencies',
                    'Later'
                );

                if (selection === 'Install Dependencies') {
                    await installDependencies(pythonPath, context);
                }
            } else {
                console.log('GenEC: All dependencies already installed');
            }
        });
    }

    async function installDependencies(pythonPath: string, context: vscode.ExtensionContext) {
        // Find requirements.txt in extension directory or genec project
        const extensionPath = context.extensionPath;
        let requirementsPath = path.join(extensionPath, '..', 'requirements.txt');

        // Also check common locations
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders) {
            for (const folder of workspaceFolders) {
                const wsReq = path.join(folder.uri.fsPath, 'requirements.txt');
                if (fs.existsSync(wsReq)) {
                    requirementsPath = wsReq;
                    break;
                }
            }
        }

        // Show progress while installing
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'GenEC: Installing Python dependencies...',
            cancellable: false
        }, async (progress) => {
            return new Promise<void>((resolve, reject) => {
                // Install with pip
                let installCmd: string;
                if (fs.existsSync(requirementsPath)) {
                    installCmd = `${pythonPath} -m pip install -r "${requirementsPath}"`;
                } else {
                    // Fallback: install core packages directly
                    installCmd = `${pythonPath} -m pip install anthropic gitpython networkx pyyaml websockets`;
                }

                console.log(`GenEC: Running: ${installCmd}`);
                progress.report({ message: 'This may take a minute...' });

                cp.exec(installCmd, { maxBuffer: 10 * 1024 * 1024 }, (error, stdout, stderr) => {
                    if (error) {
                        console.log(`GenEC: Install failed: ${error.message}`);
                        vscode.window.showErrorMessage(
                            `Failed to install dependencies: ${error.message}. ` +
                            `Try manually: pip install -r requirements.txt`
                        );
                        reject(error);
                    } else {
                        console.log('GenEC: Dependencies installed successfully');
                        vscode.window.showInformationMessage('GenEC: Dependencies installed successfully!');
                        resolve();
                    }
                });
            });
        });
    }

    async function validatePythonInstallation(pythonPath: string): Promise<boolean> {
        return new Promise((resolve) => {
            cp.exec(`${pythonPath} --version`, (error, stdout, stderr) => {
                if (error) {
                    console.log(`GenEC: Python validation failed: ${error.message}`);
                    resolve(false);
                } else {
                    console.log(`GenEC: Python found: ${stdout.trim() || stderr.trim()}`);
                    resolve(true);
                }
            });
        });
    }

    function cleanupRecoveryFiles() {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) return;

        for (const folder of workspaceFolders) {
            const markerFile = path.join(folder.uri.fsPath, '.genec_verification_in_progress');
            const backupDir = path.join(folder.uri.fsPath, '.genec_verification_backup');

            // Clean up marker file
            if (fs.existsSync(markerFile)) {
                try {
                    fs.unlinkSync(markerFile);
                    console.log(`GenEC: Cleaned up recovery marker: ${markerFile}`);
                } catch (e) {
                    console.log(`GenEC: Failed to clean up marker: ${e}`);
                }
            }

            // Clean up backup directory
            if (fs.existsSync(backupDir)) {
                try {
                    fs.rmSync(backupDir, { recursive: true, force: true });
                    console.log(`GenEC: Cleaned up recovery backup: ${backupDir}`);
                } catch (e) {
                    console.log(`GenEC: Failed to clean up backup: ${e}`);
                }
            }
        }
    }

    let disposable = vscode.commands.registerCommand('genec.refactorClass', async () => {
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

        const filePath = document.fileName;
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage('Please open a workspace folder.');
            return;
        }
        const repoPath = workspaceFolders[0].uri.fsPath;

        // Get configuration
        const config = vscode.workspace.getConfiguration('genec');
        const pythonPath = config.get<string>('pythonPath') || 'python3';
        const apiKey = config.get<string>('apiKey');

        // Check if genec is available
        try {
            cp.execSync(`${pythonPath} -m genec.cli --help`);
        } catch (e) {
            vscode.window.showErrorMessage(`GenEC not found. Please install it using 'pip install genec' or check your Python path configuration.`);
            return;
        }

        // Output channel for logs
        const outputChannel = vscode.window.createOutputChannel('GenEC');
        outputChannel.show();
        outputChannel.appendLine(`Starting GenEC on ${filePath}...`);
        outputChannel.appendLine(`Repository: ${repoPath}`);
        outputChannel.appendLine(`Python: ${pythonPath}`);
        outputChannel.appendLine('');

        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "GenEC: Refactoring Class...",
            cancellable: true
        }, (progress, token) => {
            return new Promise<void>((resolve, reject) => {
                const args = ['-m', 'genec.cli', '--target', filePath, '--repo', repoPath, '--verbose'];
                if (apiKey) {
                    args.push('--api-key', apiKey);
                }

                // Log the command being executed
                outputChannel.appendLine(`Executing: ${pythonPath} ${args.join(' ')}`);
                outputChannel.appendLine('---');
                outputChannel.appendLine('');

                const childProcess = cp.spawn(pythonPath, args, {
                    cwd: repoPath,
                    env: { ...process.env, PYTHONUNBUFFERED: '1' }
                });

                // Add error handler for spawn failure
                childProcess.on('error', (err: Error) => {
                    outputChannel.appendLine(`ERROR: Failed to spawn process: ${err.message}`);
                    reject(err);
                });

                token.onCancellationRequested(() => {
                    childProcess.kill();
                    reject();
                });

                childProcess.stdout.on('data', (data: Buffer) => {
                    outputChannel.append(data.toString());
                });

                childProcess.stderr.on('data', (data: Buffer) => {
                    outputChannel.append(data.toString());
                });

                childProcess.on('close', (code: number | null) => {
                    if (code === 0) {
                        vscode.window.showInformationMessage('GenEC refactoring completed successfully!', 'Show Output')
                            .then(selection => {
                                if (selection === 'Show Output') {
                                    outputChannel.show();
                                }
                            });
                        resolve();
                    } else {
                        vscode.window.showErrorMessage(`GenEC failed with exit code ${code}.`, 'Show Output')
                            .then(selection => {
                                if (selection === 'Show Output') {
                                    outputChannel.show();
                                }
                            });
                        reject();
                    }
                });
            });
        });
    });

    context.subscriptions.push(disposable);
}

export function deactivate() { }
