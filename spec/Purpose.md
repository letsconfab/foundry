# Purpose

## Overview

Foundry is the monorepo for **Let's Confab** — a platform for building, saving, and managing AI agent configurations called **confabs**. A confab is a structured, version-controlled definition of an AI agent that includes its purpose, guardrails, test scenarios, and deployment settings.

## Goals

1. **Democratize AI agent creation** — Provide a guided, conversational interface that walks users through defining an AI agent step-by-step, without requiring deep technical expertise.
2. **Version-controlled agent definitions** — Store every confab as structured files (TOML + Markdown) in GitHub repositories, giving users full ownership, auditability, and collaboration via pull requests.
3. **LLM Agnostic** — BYOK (Bring Your Own Key). Support multiple LLM providers (OpenAI, Anthropic, Google, Cohere) so users can plug in their own API keys and choose the model that fits their needs.
4. **Multiple Cloud Targets** — Deploy confabs to any major cloud provider (AWS, Azure, GCP, DigitalOcean), letting users choose the infrastructure that fits their requirements.
5. **Local-first execution** — Allow users to run confabs entirely on their own device using Ollama with open-source LLM models (e.g., Llama, Mistral, Gemma) as the inference engine, paired with agent runtimes such as LangChain, LangGraph, CrewAI, or AutoGen. No cloud API keys or external services required.
6. **Multi-agent orchestration** — Enable users to compose systems of multiple confabs that interact, with configurable participant roles, moderator rules, and conflict resolution.

## What Is a Confab?

A confab is a directory stored in a GitHub repository containing:

| File | Purpose |
|------|---------|
| `Confab.toml` | Configuration metadata (name, description, version, timestamps) |
| `PURPOSE.md` | Purpose, objectives, use cases, and expected behavior |
| `GUARDRAILS.md` | Safety constraints, behavioral boundaries, and content guidelines |
| `TESTS.md` | Unit, integration, performance, and security test scenarios |

Each confab is created on its own branch and submitted as a pull request, enabling review workflows before merging into the main repository.

## Target Users

- Developers and teams who want to define AI agents declaratively and manage them like code.
- Organizations that need auditable, reviewable, and version-controlled AI configurations.
- Non-technical users who benefit from the guided chat-based agent creation wizard.
- Privacy-conscious users who want to run AI agents locally without sending data to external APIs.
