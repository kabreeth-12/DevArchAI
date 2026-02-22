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
        placeHolder: 'e.g. D:\\logs or ./logs',
        ignoreFocusOut: true
      });

      const prometheusUrl = await vscode.window.showInputBox({
        prompt: 'Optional Prometheus URL (leave empty to skip)',
        placeHolder: 'e.g. http://localhost:9091',
        ignoreFocusOut: true
      });

      const otelEndpoint = await vscode.window.showInputBox({
        prompt: 'Optional trace metrics URL (leave empty to skip)',
        placeHolder: 'e.g. http://localhost:8088/trace_metrics.json',
        ignoreFocusOut: true
      });

      const debugTelemetry = await vscode.window.showQuickPick(
        [
          { label: 'Yes (show telemetry in UI)', value: true },
          { label: 'No', value: false }
        ],
        {
          placeHolder: 'Show telemetry metrics/traces in the UI?'
        }
      );

      try {
        const response = await fetch('http://localhost:8000/analyse', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_path: projectPath,
            log_path: logPath || null,
            use_gnn: true,
            prometheus_url: prometheusUrl || null,
            otel_endpoint: otelEndpoint || null,
            debug_telemetry: debugTelemetry?.value ?? false
          })
        });

        if (!response.ok) {
          throw new Error(`Backend error: ${response.statusText}`);
        }

        const analysisResult = await response.json() as any;

        let cicdOptimization: any = null;
        try {
          const cicdPath = await vscode.window.showInputBox({
            prompt: 'Optional CI/CD JSON path for optimization (leave empty to skip)',
            placeHolder: 'e.g. D:\\cicd\\run.json',
            ignoreFocusOut: true
          });
          if (cicdPath) {
            const cicdResp = await fetch('http://localhost:8000/cicd/optimize', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                provider: 'github_actions',
                source_path: cicdPath
              })
            });
            if (cicdResp.ok) {
              cicdOptimization = await cicdResp.json();
            }
          }
        } catch {
          cicdOptimization = null;
        }

        if (cicdOptimization) {
          analysisResult.cicd_optimization = cicdOptimization;
        }

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
