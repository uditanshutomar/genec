"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = require("vscode");
const cp = require("child_process");
const GenECViewProvider_1 = require("./GenECViewProvider");
function activate(context) {
    console.log('GenEC extension is now active!');
    // Register Webview View Provider
    const provider = new GenECViewProvider_1.GenECViewProvider(context.extensionUri, context);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(GenECViewProvider_1.GenECViewProvider.viewType, provider));
    let disposable = vscode.commands.registerCommand('genec.refactorClass', () => __awaiter(this, void 0, void 0, function* () {
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
        const pythonPath = config.get('pythonPath') || 'python3';
        const apiKey = config.get('apiKey');
        // Check if genec is available
        try {
            cp.execSync(`${pythonPath} -m genec.cli --help`);
        }
        catch (e) {
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
            return new Promise((resolve, reject) => {
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
                    env: Object.assign(Object.assign({}, process.env), { PYTHONUNBUFFERED: '1' })
                });
                // Add error handler for spawn failure
                childProcess.on('error', (err) => {
                    outputChannel.appendLine(`ERROR: Failed to spawn process: ${err.message}`);
                    reject(err);
                });
                token.onCancellationRequested(() => {
                    childProcess.kill();
                    reject();
                });
                childProcess.stdout.on('data', (data) => {
                    outputChannel.append(data.toString());
                });
                childProcess.stderr.on('data', (data) => {
                    outputChannel.append(data.toString());
                });
                childProcess.on('close', (code) => {
                    if (code === 0) {
                        vscode.window.showInformationMessage('GenEC refactoring completed successfully!', 'Show Output')
                            .then(selection => {
                            if (selection === 'Show Output') {
                                outputChannel.show();
                            }
                        });
                        resolve();
                    }
                    else {
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
    }));
    context.subscriptions.push(disposable);
}
function deactivate() { }
//# sourceMappingURL=extension.js.map