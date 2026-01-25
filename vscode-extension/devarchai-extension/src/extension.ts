import * as vscode from "vscode";

/**
 * Expected response structure from DevArchAI backend
 * This mirrors the FastAPI AnalyseResponse model
 */
interface DevArchAIAnalyseResponse {
    project_path: string;
    detected_services: string[];
    suspected_root_cause: string;
    explanation: string;
    risk_analysis: {
        service: string;
        predicted_risk_level: number;
        risk_confidence: number;
        reason?: string;
    }[];
    improvements: string[];
}

export function activate(context: vscode.ExtensionContext) {
    console.log("DevArchAI Extension activated");

    const command = vscode.commands.registerCommand(
        "devarchai.analyseProject",
        async () => {
            const workspaceFolders = vscode.workspace.workspaceFolders;

            if (!workspaceFolders) {
                vscode.window.showErrorMessage("No project folder open");
                return;
            }

            const projectPath = workspaceFolders[0].uri.fsPath;

            try {
                const response = await fetch("http://127.0.0.1:8000/analyse", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        project_path: projectPath,
                    }),
                });

                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }

                // Explicitly type the response
                const result = (await response.json()) as DevArchAIAnalyseResponse;

                vscode.window.showInformationMessage(
                    `DevArchAI Analysis Complete. Root Risk: ${result.suspected_root_cause}`
                );

                console.log("DevArchAI Result:", result);

            } catch (error) {
                vscode.window.showErrorMessage(
                    "DevArchAI backend not reachable. Ensure backend is running."
                );
                console.error(error);
            }
        }
    );

    context.subscriptions.push(command);
}

export function deactivate() {}
