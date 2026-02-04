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
  const nonce = getNonce();
  const cspSource = webview.cspSource;
  const scriptUri = webview.asWebviewUri(
    vscode.Uri.joinPath(context.extensionUri, 'media', 'riskPanel.js')
  );

  // Inject ML data safely (escape '<' to avoid script injection issues)
  const payload = JSON.stringify(analysisResult).replace(/</g, '\\u003c');
  html = html.replace('__DEVARCHAI_DATA__', payload);
  html = html.replace(/__CSP_NONCE__/g, nonce);
  html = html.replace(/__WEBVIEW_CSP__/g, cspSource);
  html = html.replace(/__SCRIPT_URI__/g, scriptUri.toString());

  return html;
}

function getNonce() {
  let text = '';
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}
