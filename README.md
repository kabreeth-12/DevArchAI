# DevArchAI
AI-powered DevOps architecture assistant (prototype)


# DevArchAI

DevArchAI is an AI-powered DevOps architecture assistant that analyzes microservice
architectures using dependency reasoning, real telemetry (metrics + traces), and
log-based RCA. It integrates directly into the IDE and provides explainable, unified
DevArchAI model outputs for risk analysis and CI/CD optimization.

## Unified DevArchAI Model (Single System View)

The system is presented as a single DevArchAI Unified Model that combines:
- Graph-based dependency reasoning
- Telemetry-aware risk prediction
- RCA summarization layer
- CI/CD analysis inputs (ingestion and optimization signals)

Internally, specialized components support the unified pipeline, but all outputs are
exposed as a single DevArchAI model response for a consistent system view.

## Key Capabilities
- Dependency-aware risk analysis for microservices
- Prometheus metrics integration (real telemetry)
- Zipkin trace ingestion (real trace signals)
- Explainable RCA from service logs
- CI/CD ingestion and optimization suggestions
- VS Code plugin with live UI results

## System Runtime Flow (How DevArchAI Operates)
DevArchAI runs as a backend service and an IDE client. The system accepts real inputs
and produces unified analysis results from a single DevArchAI model pipeline.

**Inputs accepted by the system**
- Project path (microservice repository root)
- Prometheus URL (metrics source)
- Trace metrics URL (trace source)
- Log path (service logs for RCA)
- CI/CD JSON path (pipeline run data)

**What the system does with these inputs**
1) **Service Discovery**  
   Detects microservices from the project structure.
2) **Dependency Graph Reasoning**  
   Builds a service dependency graph and computes graph metrics.
3) **Telemetry Ingestion**  
   Pulls real metrics from Prometheus and trace signals from the trace source.
4) **Unified Feature Construction**  
   Merges structural, telemetry, and fault indicators into one feature vector.
5) **Risk Prediction (Unified DevArchAI Model)**  
   Predicts risk level + confidence per service with explainable output.
6) **RCA Summarization**  
   Indexes logs and produces a concise RCA summary (LLM if available, fallback otherwise).
7) **CI/CD Optimization Suggestions**  
   Analyzes pipeline data and outputs optimization actions (bottlenecks, caching, test splits).
8) **IDE Presentation**  
   Displays risk, RCA, telemetry, and CI/CD optimization in the VS Code UI.

## Repository Structure

- core/  
  Python-based backend (FastAPI, AI models, reasoning engine)

- vscode-extension/  
  VS Code extension used as the developer interface

- docs/  
  Architecture notes, demo material, and documentation

## Train-Ticket Demo
See `docs/train_ticket_demo.md` for a fast end-to-end demo using a subset of Train-Ticket services
with Jaeger + Prometheus and Low/Medium/High architectural risk output.
