/**
 * SettingsTreeProvider - TreeView for extension settings including API key
 */
import * as vscode from 'vscode';
import { ConfigService } from '../services/ConfigService';

type SettingType = 'header' | 'apiKey' | 'setting' | 'action';

interface SettingData {
    type: SettingType;
    key?: string;
    label: string;
    value?: string | number | boolean;
}

export class SettingTreeItem extends vscode.TreeItem {
    constructor(
        public readonly data: SettingData,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(data.label, collapsibleState);
        this.configure();
    }

    private configure(): void {
        switch (this.data.type) {
            case 'header':
                this.iconPath = new vscode.ThemeIcon('settings-gear');
                this.contextValue = 'header';
                break;
            case 'apiKey':
                this.configureApiKey();
                break;
            case 'setting':
                this.configureSetting();
                break;
            case 'action':
                this.configureAction();
                break;
        }
    }

    private configureApiKey(): void {
        const hasKey = this.data.value && String(this.data.value).length > 0;
        this.label = 'Anthropic API Key';
        this.description = hasKey ? '••••••••' + String(this.data.value).slice(-4) : 'Not configured';
        this.iconPath = new vscode.ThemeIcon(
            hasKey ? 'key' : 'warning',
            hasKey ? undefined : new vscode.ThemeColor('editorWarning.foreground')
        );
        this.tooltip = hasKey
            ? 'Click to update API key'
            : 'API key required for LLM suggestions. Click to configure.';
        this.command = {
            command: 'genec.setApiKey',
            title: 'Set API Key'
        };
        this.contextValue = 'apiKey';
    }

    private configureSetting(): void {
        this.description = String(this.data.value);
        this.iconPath = new vscode.ThemeIcon('symbol-property');
        this.contextValue = 'setting';
    }

    private configureAction(): void {
        this.iconPath = new vscode.ThemeIcon('gear');
        this.command = {
            command: 'genec.configure',
            title: 'Open Settings'
        };
        this.contextValue = 'action';
    }
}

export class SettingsTreeProvider implements vscode.TreeDataProvider<SettingTreeItem>, vscode.Disposable {
    private _onDidChangeTreeData = new vscode.EventEmitter<SettingTreeItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private configService: ConfigService;
    private disposables: vscode.Disposable[] = [];

    constructor() {
        this.configService = ConfigService.getInstance();

        // Refresh when settings change (track disposable to prevent memory leak)
        this.disposables.push(
            vscode.workspace.onDidChangeConfiguration(e => {
                if (e.affectsConfiguration('genec')) {
                    this.refresh();
                }
            })
        );
    }

    public dispose(): void {
        this.disposables.forEach(d => d.dispose());
        this._onDidChangeTreeData.dispose();
    }

    public refresh(): void {
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: SettingTreeItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: SettingTreeItem): Promise<SettingTreeItem[]> {
        if (element) {
            return [];
        }

        // Use async key check to include secret storage
        const apiKey = await this.configService.getApiKeyAsync() || '';
        const config = this.configService.getConfig();
        const items: SettingTreeItem[] = [];

        // API Key (most important)
        items.push(new SettingTreeItem(
            {
                type: 'apiKey',
                key: 'apiKey',
                label: 'Anthropic API Key',
                value: apiKey
            },
            vscode.TreeItemCollapsibleState.None
        ));

        // Python path
        items.push(new SettingTreeItem(
            {
                type: 'setting',
                key: 'pythonPath',
                label: 'Python Path',
                value: config.pythonPath
            },
            vscode.TreeItemCollapsibleState.None
        ));

        // Open full settings
        items.push(new SettingTreeItem(
            {
                type: 'action',
                label: 'Open All Settings...'
            },
            vscode.TreeItemCollapsibleState.None
        ));

        return items;
    }
}
