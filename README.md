# DevArchAI
AI-powered DevOps architecture assistant (prototype)


# DevArchAI

DevArchAI is an AI-powered DevOps architecture assistant designed to help developers
understand CI/CD pipeline failures in microservice-based systems using dependency-aware
and explainable reasoning.

This repository contains the prototype implementation for the Final Year Project (IPD).

## Unified DevArchAI Model

The system is presented as a single DevArchAI Unified Model that combines:
- Graph-based dependency reasoning
- Telemetry-aware risk prediction
- RCA summarization layer
- CI/CD analysis inputs (ingestion and optimization signals)

Internally, specialized components support the unified pipeline, but all outputs are
exposed as a single DevArchAI model response for consistency with the proposal.

## Repository Structure

- core/  
  Python-based backend (FastAPI, AI models, reasoning engine)

- vscode-extension/  
  VS Code extension used as the developer interface

- docs/  
  Architecture notes, demo material, and documentation
