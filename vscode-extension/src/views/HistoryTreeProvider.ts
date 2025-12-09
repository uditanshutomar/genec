/**
 * HistoryTreeProvider - TreeView for displaying applied refactoring history
 */
import * as vscode from 'vscode';
import * as path from 'path';
import { RefactoringHistory } from '../types';
import { StateManager } from '../services/StateManager';

export class HistoryTreeItem extends vscode.TreeItem {
    constructor(
        public readonly entry: RefactoringHistory,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(entry.extractedClass, collapsibleState);
        this.configure();
    }

    private configure(): void {
        // Description with timestamp and source file
        const date = new Date(this.entry.timestamp);
        const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
        this.description = `${dateStr} ${timeStr} • from ${path.basename(this.entry.targetFile)}`;

        // Icon based on success
        this.iconPath = new vscode.ThemeIcon(
            this.entry.success ? 'check' : 'error',
            new vscode.ThemeColor(
                this.entry.success ? 'testing.iconPassed' : 'testing.iconFailed'
            )
        );

        // Tooltip with full paths
        this.tooltip = new vscode.MarkdownString(
            `**${this.entry.extractedClass}**\n\n` +
            `- Source: \`${this.entry.targetFile}\`\n` +
            `- Created: \`${this.entry.extractedClassPath}\`\n` +
            `- Time: ${date.toLocaleString()}`
        );

        // Click to open the created file
        if (this.entry.success && this.entry.extractedClassPath) {
            this.command = {
                command: 'vscode.open',
                title: 'Open File',
                arguments: [vscode.Uri.file(this.entry.extractedClassPath)]
            };
        }

        this.contextValue = 'historyItem';
    }
}

export class HistoryTreeProvider implements vscode.TreeDataProvider<HistoryTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<HistoryTreeItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private stateManager: StateManager;

    constructor() {
        this.stateManager = StateManager.getInstance();

        // Refresh when history changes
        this.stateManager.onHistoryChanged(() => {
            this.refresh();
        });
    }

    public refresh(): void {
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: HistoryTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: HistoryTreeItem): Thenable<HistoryTreeItem[]> {
        if (element) {
            // No children for history items
            return Promise.resolve([]);
        }

        const history = this.stateManager.getHistory();

        if (history.length === 0) {
            // Return empty - VS Code will show "No items" message
            return Promise.resolve([]);
        }

        return Promise.resolve(
            history.map(entry => new HistoryTreeItem(
                entry,
                vscode.TreeItemCollapsibleState.None
            ))
        );
    }
}
