import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { GenECViewProvider } from './GenECViewProvider';

export function activate(context: vscode.ExtensionContext) {
    console.log('GenEC extension is now active!');

    // Register Webview View Provider
    const provider = new GenECViewProvider(context.extensionUri, context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(GenECViewProvider.viewType, provider)
    );

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
