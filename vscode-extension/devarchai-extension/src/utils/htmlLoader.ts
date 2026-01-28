import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export function loadRiskHtml(
  context: vscode.ExtensionContext,
  webview: vscode.Webview,
  analysisResult: any
): string {

  const htmlPath = path.join(
  context.extensionPath,
  'media',
  'riskPanel.html'
);

  let html = fs.readFileSync(htmlPath, 'utf8');

  // Inject ML data safely
  html = html.replace(
    '__DEVARCHAI_DATA__',
    JSON.stringify(analysisResult)
  );

  return html;
}
