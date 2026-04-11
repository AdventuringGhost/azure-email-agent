# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An automated email agent that monitors a Gmail inbox and responds using Claude Sonnet via Azure AI Foundry. Secrets are managed through Azure Key Vault. The agent runs on a Linux VM, infrastructure is provisioned with Terraform, and CI/CD runs on Azure DevOps.

## Architecture

- **Agent** (`agent/`): Python service that polls Gmail via the Gmail API, processes emails, and generates replies using Claude Sonnet through Azure AI Foundry (Azure OpenAI-compatible endpoint).
- **Infrastructure** (`infra/`): Terraform configs provisioning the Linux VM, Key Vault, and supporting Azure resources.
- **CI/CD** (`pipelines/`): Azure DevOps pipeline definitions for build, test, and deploy stages.

## Key Integrations

- **Claude Sonnet**: Accessed via Azure AI Foundry using the `anthropic` SDK or Azure OpenAI-compatible endpoint.
- **Azure Key Vault**: All secrets (Gmail OAuth credentials, API keys) are fetched at runtime using the Azure SDK (`azure-keyvault-secrets`, `azure-identity`).
- **Gmail API**: Uses OAuth2 service account or user credentials stored in Key Vault.

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the agent locally
python -m agent.main

# Run tests
pytest

# Run a single test
pytest tests/test_<module>.py::test_<name> -v

# Lint
ruff check .
# or
flake8 .

# Terraform (from infra/)
terraform init
terraform plan
terraform apply
```

## Secrets & Configuration

All secrets live in Azure Key Vault — never in code or `.env` files committed to the repo. Local development uses `DefaultAzureCredential` (supports `az login`). Key Vault name and other non-secret config are set via environment variables or a config file.

## Portfolio & Cost Rules

- This is a case study project for adventuringghost.com.
- All Azure resources are provisioned then destroyed after proof of completion.
- Never run `terraform apply` without explicit user approval.
- Flag any action that incurs Azure or API cost before proceeding.
