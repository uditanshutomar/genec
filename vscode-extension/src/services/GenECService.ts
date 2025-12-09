/**
 * GenECService - Handles CLI communication and process management
 */
import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { EventEmitter } from 'events';
import { GenECResult, ProgressEvent, GenECConfig } from '../types';
import { ConfigService } from './ConfigService';

export interface GenECServiceEvents {
    'progress': (event: ProgressEvent) => void;
    'error': (message: string) => void;
    'complete': (result: GenECResult) => void;
    'log': (message: string) => void;
}

export class GenECService extends EventEmitter {
    private currentProcess?: cp.ChildProcess;
    private outputChannel: vscode.OutputChannel;
    private configService: ConfigService;
    private extensionPath: string;

    constructor(extensionPath: string) {
        super();
        this.extensionPath = extensionPath;
        this.outputChannel = vscode.window.createOutputChannel('GenEC');
        this.configService = ConfigService.getInstance();
    }

    /**
     * Check if an analysis is currently running
     */
    public isRunning(): boolean {
        return this.currentProcess !== undefined;
    }

    /**
     * Run GenEC analysis on a Java file
     */
    public async analyze(
        targetFile: string,
        repoPath: string,
        options?: {
            maxSuggestions?: number;
            apiKey?: string;
        }
    ): Promise<GenECResult> {
        if (this.isRunning()) {
            throw new Error('Analysis already in progress');
        }

        this.outputChannel.clear();
        this.outputChannel.show(true);
        this.log(`Starting analysis: ${path.basename(targetFile)}`);
        this.log(`Repository: ${repoPath}`);

        const config = this.configService.getConfig();
        const pythonPath = this.configService.getPythonPath(this.extensionPath);
        const isBinary = pythonPath.endsWith('genec') || pythonPath.endsWith('genec.exe');

        // Build command arguments
        const args: string[] = [];

        if (!isBinary) {
            args.push('-m', 'genec.cli');
        }

        args.push(
            '--target', targetFile,
            '--repo', repoPath,
            '--json'
        );

        // Add clustering config
        args.push(
            '--min-cluster-size', config.clustering.minClusterSize.toString(),
            '--max-cluster-size', config.clustering.maxClusterSize.toString(),
            '--min-cohesion', config.clustering.minCohesion.toString()
        );

        if (options?.maxSuggestions) {
            args.push('--max-suggestions', options.maxSuggestions.toString());
        }

        // Environment with API key
        const env = { ...process.env };
        const apiKey = options?.apiKey || config.apiKey;
        if (apiKey) {
            env.ANTHROPIC_API_KEY = apiKey;
        }

        this.log(`Command: ${pythonPath} ${args.join(' ')}`);

        return new Promise((resolve, reject) => {
            const TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes
            let timeoutId: NodeJS.Timeout | undefined;
            let stdout = '';
            let stderr = '';

            this.currentProcess = cp.spawn(pythonPath, args, {
                cwd: repoPath,
                env
            });

            // Set timeout
            timeoutId = setTimeout(() => {
                if (this.currentProcess) {
                    this.log('[TIMEOUT] Process exceeded 10 minute limit');
                    this.currentProcess.kill('SIGTERM');
                    setTimeout(() => {
                        if (this.currentProcess) {
                            this.currentProcess.kill('SIGKILL');
                        }
                    }, 5000);
                }
            }, TIMEOUT_MS);

            this.currentProcess.stdout?.on('data', (data) => {
                const dataStr = data.toString();
                stdout += dataStr;
            });

            this.currentProcess.stderr?.on('data', (data) => {
                const dataStr = data.toString();
                stderr += dataStr;
                this.parseStderr(dataStr);
            });

            this.currentProcess.on('error', (err) => {
                if (timeoutId) clearTimeout(timeoutId);
                this.currentProcess = undefined;
                this.log(`[ERROR] ${err.message}`);
                reject(new Error(`Failed to start GenEC: ${err.message}`));
            });

            this.currentProcess.on('close', (code) => {
                if (timeoutId) clearTimeout(timeoutId);
                this.currentProcess = undefined;

                if (code === null) {
                    reject(new Error('Process was terminated'));
                    return;
                }

                if (code !== 0) {
                    const errorMsg = this.extractErrorMessage(stderr);
                    reject(new Error(errorMsg || `GenEC failed with code ${code}`));
                    return;
                }

                try {
                    const result = this.parseJsonOutput(stdout);
                    this.log(`Analysis complete: ${result.suggestions?.length || 0} suggestions`);
                    this.emit('complete', result);
                    resolve(result);
                } catch (e) {
                    reject(new Error(`Failed to parse output: ${(e as Error).message}`));
                }
            });
        });
    }

    /**
     * Cancel the current analysis
     */
    public cancel(): void {
        if (!this.currentProcess) {
            return;
        }

        this.log('[USER] Cancellation requested');
        this.currentProcess.kill('SIGINT');

        // Escalate to SIGTERM after 3s
        setTimeout(() => {
            if (this.currentProcess && !this.currentProcess.killed) {
                this.log('[USER] Sending SIGTERM...');
                this.currentProcess.kill('SIGTERM');
            }
        }, 3000);

        // Force kill after 6s
        setTimeout(() => {
            if (this.currentProcess && !this.currentProcess.killed) {
                this.log('[USER] Force killing...');
                this.currentProcess.kill('SIGKILL');
            }
        }, 6000);
    }

    /**
     * Parse stderr for progress updates and errors
     */
    private parseStderr(data: string): void {
        const lines = data.split('\n');

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;

            // Log to output channel
            this.outputChannel.appendLine(trimmed);

            // Parse stage progress
            const stageMatch = trimmed.match(/\[Stage (\d+)\/(\d+)\] (.+)/);
            if (stageMatch) {
                const event: ProgressEvent = {
                    type: 'progress',
                    stage: parseInt(stageMatch[1]),
                    total: parseInt(stageMatch[2]),
                    message: stageMatch[3]
                };
                this.emit('progress', event);
                continue;
            }

            // Parse JSON progress events
            if (trimmed.startsWith('{') && trimmed.includes('"type":"progress"')) {
                try {
                    const event = JSON.parse(trimmed) as ProgressEvent;
                    this.emit('progress', event);
                } catch { }
                continue;
            }

            // Emit errors
            if (trimmed.includes('ERROR') || trimmed.includes('Error:')) {
                const errorMsg = trimmed.replace(/^.*?(ERROR|Error:)\s*/, '').trim();
                if (errorMsg.length > 10) {
                    this.emit('error', errorMsg);
                }
            }
        }
    }

    /**
     * Robustly parse JSON from CLI output
     * Handles cases where INFO/DEBUG log lines are mixed with JSON
     */
    private parseJsonOutput(output: string): GenECResult {
        // Try direct parse first
        try {
            return JSON.parse(output);
        } catch { }

        // Filter out log lines (INFO:, DEBUG:, WARNING:, etc.) and try again
        const lines = output.trim().split('\n');
        const jsonLines = lines.filter(line => {
            const trimmed = line.trim();
            // Skip log lines
            if (trimmed.startsWith('INFO:') ||
                trimmed.startsWith('DEBUG:') ||
                trimmed.startsWith('WARNING:') ||
                trimmed.startsWith('ERROR:') ||
                trimmed.match(/^\d{4}-\d{2}-\d{2}/) ||  // Timestamp lines
                trimmed.match(/^={10,}$/)) {  // Separator lines
                return false;
            }
            return true;
        });

        // Try parsing filtered output
        const filteredOutput = jsonLines.join('\n');
        try {
            return JSON.parse(filteredOutput);
        } catch { }

        // Find the main JSON object (starts with { "status": or similar)
        const jsonStartPatterns = [
            /\{\s*"status"\s*:/,
            /\{\s*"suggestions"\s*:/,
            /\{\s*"message"\s*:/
        ];

        for (const pattern of jsonStartPatterns) {
            const match = output.match(pattern);
            if (match && match.index !== undefined) {
                const jsonStr = output.substring(match.index);
                // Find matching closing brace
                let braceCount = 0;
                let endIndex = 0;
                for (let i = 0; i < jsonStr.length; i++) {
                    if (jsonStr[i] === '{') braceCount++;
                    if (jsonStr[i] === '}') braceCount--;
                    if (braceCount === 0) {
                        endIndex = i + 1;
                        break;
                    }
                }
                if (endIndex > 0) {
                    try {
                        return JSON.parse(jsonStr.substring(0, endIndex));
                    } catch { }
                }
            }
        }

        // Last resort: try from each line backwards
        for (let i = lines.length - 1; i >= 0; i--) {
            const line = lines[i].trim();
            if (line.startsWith('{')) {
                try {
                    return JSON.parse(lines.slice(i).join('\n'));
                } catch {
                    try {
                        return JSON.parse(line);
                    } catch { }
                }
            }
        }

        throw new Error('Could not find valid JSON in output');
    }

    /**
     * Extract meaningful error message from stderr
     */
    private extractErrorMessage(stderr: string): string {
        const lines = stderr.split('\n');
        for (const line of lines.reverse()) {
            if (line.includes('Error:') || line.includes('ERROR')) {
                return line.replace(/^.*?(ERROR|Error:)\s*/, '').trim();
            }
        }
        return stderr.slice(-200) || 'Unknown error';
    }

    /**
     * Log message to output channel
     */
    private log(message: string): void {
        const timestamp = new Date().toISOString().substring(11, 19);
        this.outputChannel.appendLine(`[${timestamp}] ${message}`);
        this.emit('log', message);
    }

    /**
     * Show the output channel
     */
    public showOutput(): void {
        this.outputChannel.show();
    }

    /**
     * Dispose resources
     */
    public dispose(): void {
        this.cancel();
        this.outputChannel.dispose();
    }
}
