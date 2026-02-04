import * as vscode from 'vscode';
import { loadRiskHtml } from './utils/htmlLoader';

export function activate(context: vscode.ExtensionContext) {

  const disposable = vscode.commands.registerCommand(
    'devarchai.analyseProject',
    async () => {

      const workspaceFolders = vscode.workspace.workspaceFolders;
      if (!workspaceFolders) {
        vscode.window.showErrorMessage('No workspace folder open.');
        return;
      }

      const projectPath = workspaceFolders[0].uri.fsPath;

      vscode.window.showInformationMessage(
        'DevArchAI: Analysing project using ML model...'
      );

      const logPath = await vscode.window.showInputBox({
        prompt: 'Optional log path for RCA (leave empty to skip)',
        placeHolder: 'e.g. D:\\logs or ./logs'
      });

      try {
        const response = await fetch('http://localhost:8000/analyse', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_path: projectPath,
            log_path: logPath || null,
            use_gnn: true
          })
        });

        if (!response.ok) {
          throw new Error(`Backend error: ${response.statusText}`);
        }

        const analysisResult = await response.json();

        showRiskPanel(context, analysisResult);

      } catch (error: any) {
        vscode.window.showErrorMessage(
          `DevArchAI analysis failed: ${error.message}`
        );
      }
    }
  );

  context.subscriptions.push(disposable);
}

export function deactivate() {}

/* --------------------------------------------------
   WebView Panel
--------------------------------------------------- */

function showRiskPanel(
  context: vscode.ExtensionContext,
  analysisResult: any
) {
  const panel = vscode.window.createWebviewPanel(
    'devarchaiRiskPanel',
    'DevArchAI – ML Risk Analysis',
    vscode.ViewColumn.One,
    { enableScripts: true }
  );

  panel.webview.html = loadRiskHtml(
    context,
    panel.webview,
    analysisResult
  );
}
