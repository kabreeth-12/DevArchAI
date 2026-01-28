"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.loadRiskHtml = loadRiskHtml;
const fs = require("fs");
const path = require("path");
function loadRiskHtml(context, webview, analysisResult) {
    const htmlPath = path.join(context.extensionPath, 'media', 'riskPanel.html');
    let html = fs.readFileSync(htmlPath, 'utf8');
    // Inject ML data safely
    html = html.replace('__DEVARCHAI_DATA__', JSON.stringify(analysisResult));
    return html;
}
//# sourceMappingURL=htmlLoader.js.map