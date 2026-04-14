# Azure Gmail Email Agent — DevSecOps Case Study

> Published at adventuringghost.com — Skipper, DevSecOps Portfolio

---

## Overview

_Placeholder: one-paragraph summary of what the project does and why it exists._

## Problem Statement

_Placeholder: the real-world problem this agent solves — automated inbox triage, reducing manual response time, demonstrating end-to-end cloud-native workflow._

## Architecture Decisions

_Placeholder: key choices — polling vs. push (Gmail watch), managed identity over service principals, Azure AI Foundry for Claude access, single-VM deployment for cost control._

## Tech Stack

_Placeholder: Python 3.12, Azure Linux VM (B1s), Azure Key Vault, Azure AI Foundry / Claude Sonnet, Gmail API (OAuth2), Terraform, Azure DevOps Pipelines._

## Security Approach

_Placeholder: no secrets in code or env files, managed identity for all Azure auth, RBAC-scoped Key Vault access, no public IP on VM, all credentials rotated through Key Vault._

## IaC Strategy

_Placeholder: Terraform modules, remote state in Azure Blob Storage, variable-driven config, resource tagging convention, destroy-after-demo cost discipline._

## CI/CD Design

_Placeholder: Azure DevOps pipeline stages — lint/test, terraform plan (PR gate), terraform apply + deploy on merge to main, pipeline service connection uses federated identity._

## Challenges & Solutions

_Placeholder: specific problems hit during the build and how they were resolved — e.g. Gmail OAuth flow in a headless VM, Key Vault soft-delete on re-provision, Azure AI Foundry endpoint config._

## Cost Model

_Placeholder: estimated monthly cost breakdown — VM ~$7.50, Key Vault ~$0, Log Analytics ~$2, AI Foundry token cost at demo volume. See docs/cost-model.md for detail._

## Results & Evidence

_Placeholder: screenshots / logs showing agent receiving email, calling Claude, sending reply. Links to pipeline run, Key Vault audit log, Log Analytics query._

## Lessons Learned

_Placeholder: what would be done differently — e.g. event-driven vs. polling, containerise the agent, add dead-letter queue for failed sends._
