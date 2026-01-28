"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = require("vscode");
const htmlLoader_1 = require("./utils/htmlLoader");
function activate(context) {
    const disposable = vscode.commands.registerCommand('devarchai.analyseProject', async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage('No workspace folder open.');
            return;
        }
        const projectPath = workspaceFolders[0].uri.fsPath;
        vscode.window.showInformationMessage('DevArchAI: Analysing project using ML model...');
        try {
            const response = await fetch('http://localhost:8000/analyse', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: projectPath })
            });
            if (!response.ok) {
                throw new Error(`Backend error: ${response.statusText}`);
            }
            const analysisResult = await response.json();
            showRiskPanel(context, analysisResult);
        }
        catch (error) {
            vscode.window.showErrorMessage(`DevArchAI analysis failed: ${error.message}`);
        }
    });
    context.subscriptions.push(disposable);
}
function deactivate() { }
/* --------------------------------------------------
   WebView Panel
--------------------------------------------------- */
function showRiskPanel(context, analysisResult) {
    const panel = vscode.window.createWebviewPanel('devarchaiRiskPanel', 'DevArchAI – ML Risk Analysis', vscode.ViewColumn.One, { enableScripts: true });
    panel.webview.html = (0, htmlLoader_1.loadRiskHtml)(context, panel.webview, analysisResult);
}
//# sourceMappingURL=extension.js.map