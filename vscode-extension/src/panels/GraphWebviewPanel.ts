/**
 * GraphWebviewPanel - Standalone webview panel for method dependency graph visualization
 * Uses simple canvas-based rendering instead of vis-network to avoid module loading issues
 */
import * as vscode from 'vscode';
import { GraphData } from '../types';

export class GraphWebviewPanel {
    public static currentPanel: GraphWebviewPanel | undefined;
    public static readonly viewType = 'genec.graphView';

    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    private constructor(
        panel: vscode.WebviewPanel,
        extensionUri: vscode.Uri
    ) {
        this._panel = panel;
        this._extensionUri = extensionUri;

        // Set up webview content
        this._panel.webview.html = this._getHtmlForWebview();

        // Handle disposal
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
    }

    public static createOrShow(extensionUri: vscode.Uri): GraphWebviewPanel {
        // If panel exists, reveal it
        if (GraphWebviewPanel.currentPanel) {
            GraphWebviewPanel.currentPanel._panel.reveal(vscode.ViewColumn.Beside);
            return GraphWebviewPanel.currentPanel;
        }

        // Create new panel
        const panel = vscode.window.createWebviewPanel(
            GraphWebviewPanel.viewType,
            'GenEC: Method Graph',
            vscode.ViewColumn.Beside,
            {
                enableScripts: true,
                retainContextWhenHidden: true
            }
        );

        GraphWebviewPanel.currentPanel = new GraphWebviewPanel(panel, extensionUri);
        return GraphWebviewPanel.currentPanel;
    }

    /**
     * Update the graph with new data
     */
    public updateGraph(graphData: GraphData, clusters?: any[]): void {
        this._panel.webview.postMessage({
            type: 'updateGraph',
            graphData,
            clusters
        });
    }

    /**
     * Highlight specific nodes
     */
    public highlightNodes(nodeIds: string[]): void {
        this._panel.webview.postMessage({
            type: 'highlightNodes',
            nodeIds
        });
    }

    private _getHtmlForWebview(): string {
        const nonce = this._getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'nonce-${nonce}'; style-src 'unsafe-inline';">
    <title>GenEC Method Graph</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 0;
            overflow: hidden;
            background: #1a1a2e;
            color: #d4d4d4;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        #container {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        #toolbar {
            padding: 10px 16px;
            background: #252545;
            border-bottom: 1px solid #3a3a5a;
            display: flex;
            gap: 16px;
            align-items: center;
        }
        #toolbar label {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            cursor: pointer;
        }
        #stats {
            margin-left: auto;
            font-size: 12px;
            color: #888;
        }
        #graph-wrapper {
            flex: 1;
            position: relative;
            overflow: hidden;
        }
        canvas {
            display: block;
        }
        #info {
            padding: 10px 16px;
            background: #252545;
            border-top: 1px solid #3a3a5a;
            font-size: 12px;
            min-height: 36px;
        }
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: #888;
            font-size: 14px;
            gap: 8px;
        }
        .legend {
            display: flex;
            gap: 16px;
            font-size: 11px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .legend-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
    </style>
</head>
<body>
    <div id="container">
        <div id="toolbar">
            <label>
                <input type="checkbox" id="hideUnclustered">
                Hide unclustered
            </label>
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-dot" style="background: #4ECDC4;"></div>
                    Method
                </div>
                <div class="legend-item">
                    <div class="legend-dot" style="background: #95E1D3;"></div>
                    Field
                </div>
                <div class="legend-item">
                    <div class="legend-dot" style="background: #FF6B6B;"></div>
                    Clustered
                </div>
            </div>
            <div id="stats"></div>
        </div>
        <div id="graph-wrapper">
            <div class="empty-state" id="empty-state">
                <span>📊</span>
                <span>Run GenEC analysis to see the method dependency graph</span>
            </div>
            <canvas id="graph-canvas"></canvas>
        </div>
        <div id="info">Hover over nodes to see details</div>
    </div>
    
    <script nonce="${nonce}">
        const canvas = document.getElementById('graph-canvas');
        const ctx = canvas.getContext('2d');
        const wrapper = document.getElementById('graph-wrapper');
        const infoDiv = document.getElementById('info');
        const statsDiv = document.getElementById('stats');
        const emptyState = document.getElementById('empty-state');
        const hideUnclusteredCheckbox = document.getElementById('hideUnclustered');

        let nodes = [];
        let edges = [];
        let clusteredNodeIds = new Set();
        let hideUnclustered = false;
        let scale = 1;
        let offsetX = 0, offsetY = 0;
        let isDragging = false;
        let dragStartX, dragStartY;
        let hoveredNode = null;

        // Resize canvas
        function resizeCanvas() {
            canvas.width = wrapper.clientWidth;
            canvas.height = wrapper.clientHeight;
            render();
        }
        window.addEventListener('resize', resizeCanvas);

        // Handle messages from extension
        window.addEventListener('message', event => {
            const message = event.data;
            if (message.type === 'updateGraph') {
                setupGraph(message.graphData, message.clusters);
            }
        });

        // Toolbar
        hideUnclusteredCheckbox.addEventListener('change', (e) => {
            hideUnclustered = e.target.checked;
            render();
        });

        // Mouse interactions
        canvas.addEventListener('mousedown', (e) => {
            isDragging = true;
            dragStartX = e.clientX - offsetX;
            dragStartY = e.clientY - offsetY;
        });

        canvas.addEventListener('mousemove', (e) => {
            if (isDragging) {
                offsetX = e.clientX - dragStartX;
                offsetY = e.clientY - dragStartY;
                render();
            } else {
                // Check hover
                const rect = canvas.getBoundingClientRect();
                const mouseX = (e.clientX - rect.left - offsetX) / scale;
                const mouseY = (e.clientY - rect.top - offsetY) / scale;

                hoveredNode = null;
                for (const node of nodes) {
                    if (hideUnclustered && !clusteredNodeIds.has(node.id)) continue;
                    const dx = mouseX - node.x;
                    const dy = mouseY - node.y;
                    if (Math.sqrt(dx*dx + dy*dy) < node.radius) {
                        hoveredNode = node;
                        break;
                    }
                }
                infoDiv.textContent = hoveredNode ? hoveredNode.id : 'Hover over nodes to see details';
                canvas.style.cursor = hoveredNode ? 'pointer' : 'grab';
            }
        });

        canvas.addEventListener('mouseup', () => isDragging = false);
        canvas.addEventListener('mouseleave', () => isDragging = false);

        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            scale *= delta;
            scale = Math.max(0.1, Math.min(5, scale));
            render();
        });

        function setupGraph(graphData, clusters) {
            if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
                emptyState.style.display = 'flex';
                canvas.style.display = 'none';
                return;
            }

            emptyState.style.display = 'none';
            canvas.style.display = 'block';

            clusteredNodeIds.clear();
            if (clusters) {
                const clusterColors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD', '#D4A5A5', '#9B59B6', '#3498DB', '#E67E22', '#2ECC71'];
                clusters.forEach((cluster, i) => {
                    if (cluster.members && cluster.members.length >= 2) {
                        cluster.members.forEach(id => {
                            clusteredNodeIds.add(id);
                        });
                    }
                });
            }

            // Create node map
            const nodeMap = {};
            nodes = graphData.nodes.map((n, i) => {
                const angle = (2 * Math.PI * i) / graphData.nodes.length;
                const radius = Math.min(canvas.width, canvas.height) * 0.35;
                const node = {
                    id: n.id,
                    type: n.type || 'method',
                    x: canvas.width/2 + radius * Math.cos(angle),
                    y: canvas.height/2 + radius * Math.sin(angle),
                    radius: clusteredNodeIds.has(n.id) ? 8 : 5,
                    color: clusteredNodeIds.has(n.id) ? '#FF6B6B' : (n.type === 'field' ? '#95E1D3' : '#4ECDC4')
                };
                nodeMap[n.id] = node;
                return node;
            });

            edges = (graphData.links || []).map(e => ({
                source: nodeMap[e.source],
                target: nodeMap[e.target],
                weight: e.weight || 0.5
            })).filter(e => e.source && e.target);

            // Force layout (simple spring embedding)
            for (let iter = 0; iter < 100; iter++) {
                for (const node of nodes) {
                    let fx = 0, fy = 0;
                    // Repulsion
                    for (const other of nodes) {
                        if (node === other) continue;
                        const dx = node.x - other.x;
                        const dy = node.y - other.y;
                        const dist = Math.max(1, Math.sqrt(dx*dx + dy*dy));
                        const force = 5000 / (dist * dist);
                        fx += (dx / dist) * force;
                        fy += (dy / dist) * force;
                    }
                    node.fx = fx;
                    node.fy = fy;
                }
                // Attraction (edges)
                for (const edge of edges) {
                    const dx = edge.target.x - edge.source.x;
                    const dy = edge.target.y - edge.source.y;
                    const dist = Math.sqrt(dx*dx + dy*dy);
                    const force = dist * 0.01;
                    edge.source.fx += (dx / dist) * force;
                    edge.source.fy += (dy / dist) * force;
                    edge.target.fx -= (dx / dist) * force;
                    edge.target.fy -= (dy / dist) * force;
                }
                // Apply forces
                for (const node of nodes) {
                    node.x += (node.fx || 0) * 0.1;
                    node.y += (node.fy || 0) * 0.1;
                }
            }

            // Center graph
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            for (const node of nodes) {
                minX = Math.min(minX, node.x);
                minY = Math.min(minY, node.y);
                maxX = Math.max(maxX, node.x);
                maxY = Math.max(maxY, node.y);
            }
            const graphWidth = maxX - minX;
            const graphHeight = maxY - minY;
            offsetX = (canvas.width - graphWidth) / 2 - minX;
            offsetY = (canvas.height - graphHeight) / 2 - minY;
            scale = Math.min(
                canvas.width / (graphWidth + 100),
                canvas.height / (graphHeight + 100)
            );

            statsDiv.textContent = nodes.length + ' nodes, ' + edges.length + ' edges';
            resizeCanvas();
        }

        function render() {
            if (!canvas.width) return;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.save();
            ctx.translate(offsetX, offsetY);
            ctx.scale(scale, scale);

            // Draw edges
            ctx.strokeStyle = 'rgba(100, 100, 150, 0.3)';
            ctx.lineWidth = 0.5;
            for (const edge of edges) {
                if (hideUnclustered && (!clusteredNodeIds.has(edge.source.id) || !clusteredNodeIds.has(edge.target.id))) continue;
                ctx.beginPath();
                ctx.moveTo(edge.source.x, edge.source.y);
                ctx.lineTo(edge.target.x, edge.target.y);
                ctx.stroke();
            }

            // Draw nodes
            for (const node of nodes) {
                if (hideUnclustered && !clusteredNodeIds.has(node.id)) continue;
                ctx.beginPath();
                ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
                ctx.fillStyle = node === hoveredNode ? '#ffffff' : node.color;
                ctx.fill();
            }

            ctx.restore();
        }

        resizeCanvas();
    </script>
</body>
</html>`;
    }

    private _getNonce(): string {
        let text = '';
        const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        for (let i = 0; i < 32; i++) {
            text += possible.charAt(Math.floor(Math.random() * possible.length));
        }
        return text;
    }

    public dispose(): void {
        GraphWebviewPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const disposable = this._disposables.pop();
            if (disposable) {
                disposable.dispose();
            }
        }
    }
}
