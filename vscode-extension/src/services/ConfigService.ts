/**
 * ConfigService - Handles VS Code settings and environment configuration
 */
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { GenECConfig } from '../types';

export class ConfigService {
    private static instance: ConfigService;
    private secretStorage?: vscode.SecretStorage;

    private constructor() { }

    public setContext(context: vscode.ExtensionContext): void {
        this.secretStorage = context.secrets;
    }

    public static getInstance(): ConfigService {
        if (!ConfigService.instance) {
            ConfigService.instance = new ConfigService();
        }
        return ConfigService.instance;
    }

    /**
     * Get the complete GenEC configuration
     */
    public getConfig(): GenECConfig {
        const config = vscode.workspace.getConfiguration('genec');

        return {
            pythonPath: config.get<string>('pythonPath') || 'python3',
            apiKey: this.getApiKey(),
            autoApply: config.get<boolean>('autoApply') || false,
            analysisTimeout: config.get<number>('analysisTimeout') || 10,
        };
    }

    /**
     * Get API key from settings or environment (synchronous fallback)
     */
    public getApiKey(): string | undefined {
        // Secret storage is checked asynchronously via getApiKeyAsync
        // Fallback to settings and env var
        const config = vscode.workspace.getConfiguration('genec');
        const settingsKey = config.get<string>('apiKey');

        if (settingsKey && settingsKey.trim()) {
            return settingsKey;
        }

        return process.env.ANTHROPIC_API_KEY;
    }

    /**
     * Get API key, checking secret storage first
     */
    public async getApiKeyAsync(): Promise<string | undefined> {
        if (this.secretStorage) {
            const secretKey = await this.secretStorage.get('genec.apiKey');
            if (secretKey) return secretKey;
        }
        return this.getApiKey();
    }

    /**
     * Store API key using secret storage when available, falling back to settings
     */
    public async setApiKey(apiKey: string): Promise<void> {
        if (this.secretStorage) {
            await this.secretStorage.store('genec.apiKey', apiKey);
        } else {
            const config = vscode.workspace.getConfiguration('genec');
            await config.update('apiKey', apiKey, vscode.ConfigurationTarget.Global);
        }
    }

    /**
     * Prompt user for API key if not configured
     */
    public async promptForApiKey(): Promise<string | undefined> {
        const existingKey = await this.getApiKeyAsync();
        if (existingKey) {
            return existingKey;
        }

        const apiKey = await vscode.window.showInputBox({
            prompt: 'Enter your Anthropic API Key',
            password: true,
            ignoreFocusOut: true,
            placeHolder: 'sk-ant-...'
        });

        if (apiKey) {
            await this.setApiKey(apiKey);
        }

        return apiKey;
    }

    /**
     * Get Python path, checking for bundled binary first
     */
    public getPythonPath(extensionPath: string): string {

        // Check for bundled binary
        const bundledPath = path.join(extensionPath, 'dist', 'genec');
        const bundledExePath = path.join(extensionPath, 'dist', 'genec.exe');

        if (fs.existsSync(bundledPath)) {
            return bundledPath;
        }
        if (fs.existsSync(bundledExePath)) {
            return bundledExePath;
        }

        return this.getConfig().pythonPath;
    }

    /**
     * Check if using bundled binary
     */
    public isBundled(extensionPath: string): boolean {

        const bundledPath = path.join(extensionPath, 'dist', 'genec');
        const bundledExePath = path.join(extensionPath, 'dist', 'genec.exe');

        return fs.existsSync(bundledPath) || fs.existsSync(bundledExePath);
    }
}
