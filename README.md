# Azure Email Agent

[![Build Status](https://dev.azure.com/adventuringghost/azure-email-agent/_apis/build/status/azure-email-agent?branchName=main)](https://dev.azure.com/adventuringghost/azure-email-agent/_build/latest?definitionId=1&branchName=main)

An automated email agent that monitors a Gmail inbox and generates replies using **Claude Sonnet** via **Azure AI Foundry**. Secrets are managed through **Azure Key Vault** using a VM-assigned managed identity. Infrastructure is provisioned with Terraform; CI/CD runs on Azure DevOps.

> Full write-up and demo evidence: [adventuringghost.com — Azure Email Agent Case Study](https://adventuringghost.com)

---

## Architecture

```
Gmail inbox
    │  (OAuth2 / Gmail API)
    ▼
Linux VM (Standard_B1s, private IP)
    ├── agent/main.py          poll loop
    ├── agent/gmail_client.py  read + reply
    ├── agent/claude_client.py Azure AI Foundry → Claude Sonnet
    └── agent/email_processor  orchestrates each email
         │
         │  (managed identity)
         ▼
    Azure Key Vault            gmail-credentials-json, foundry-api-key
         │
         └── Azure AI Foundry  Claude Sonnet deployment
```

| Component | Technology |
|---|---|
| Agent runtime | Python 3.11, `anthropic` SDK |
| Email | Gmail API (OAuth2) |
| LLM | Claude Sonnet via Azure AI Foundry |
| Secrets | Azure Key Vault (RBAC, managed identity) |
| Observability | Azure Log Analytics |
| IaC | Terraform (remote state in Azure Blob) |
| CI/CD | Azure DevOps Pipelines (3 stages) |

---

## CI/CD Pipeline

The pipeline (`pipelines/azure-pipelines.yml`) runs on every push to `main` with three sequential stages:

| Stage | What it does |
|---|---|
| **validate** | `pip install`, `ruff check`, `pytest` |
| **terraform-plan** | `terraform init` + `terraform plan`; plan saved as artifact; **manual approval gate** before next stage |
| **deploy** | `terraform apply` from saved plan; `rsync agent/` to VM via SSH; restart `email-agent` systemd service |

---

## Cost Model

All resources are provisioned for demo, then destroyed. Estimated spend per full demo cycle:

| Resource | SKU | Est. monthly | Notes |
|---|---|---|---|
| Linux VM | Standard_B1s (1 vCPU, 1 GiB) | ~$7.50 | Stops billing immediately on `terraform destroy` |
| Azure Key Vault | Standard | ~$0.03 | 10 000 ops/month free tier |
| Log Analytics | Pay-per-GB (PerGB2018) | ~$0.50–$2 | 5 GB/month free tier |
| Azure AI Foundry | Claude Sonnet token pricing | Variable | Demo volume: <$1 |
| Azure DevOps | Free tier (1 Microsoft-hosted job) | $0 | — |
| **Total (demo run)** | | **< $12** | Destroyed after proof of completion |

See [`docs/cost-model.md`](docs/cost-model.md) for the detailed breakdown.

---

## Setup

### Prerequisites

- Python 3.11+
- Azure CLI (`az login` for local dev)
- Terraform ≥ 1.7
- A Gmail account with the Gmail API enabled and OAuth2 credentials

### Local development

```bash
# 1. Clone and install
git clone https://github.com/Adventuringghost/azure-email-agent.git
cd azure-email-agent
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — set KEY_VAULT_NAME, AZURE_FOUNDRY_ENDPOINT, AZURE_FOUNDRY_DEPLOYMENT

# 3. Authenticate to Azure (DefaultAzureCredential picks this up)
az login
az account set --subscription <YOUR_SUBSCRIPTION_ID>

# 4. Run the agent
python -m agent.main
```

### Secrets in Key Vault

The agent expects two secrets in Key Vault (names are hard-coded in `agent/config.py`):

| Secret name | Contents |
|---|---|
| `gmail-credentials-json` | Full JSON of the Gmail OAuth2 token/credentials |
| `foundry-api-key` | Azure AI Foundry API key |

### Infrastructure (Terraform)

```bash
cd infra
terraform init   # configure backend variables first
terraform plan   # review before applying
# terraform apply — run only after explicit approval (see CLAUDE.md)
```

Pipeline variables required (set in Azure DevOps variable groups or pipeline secrets):

| Variable | Description |
|---|---|
| `ARM_SERVICE_CONNECTION` | ADO service connection name for Azure |
| `TF_BACKEND_RESOURCE_GROUP` | Resource group holding tfstate storage |
| `TF_BACKEND_STORAGE_ACCOUNT` | Storage account for remote tfstate |
| `TF_BACKEND_CONTAINER` | Blob container for tfstate |
| `ADMIN_SSH_PUBLIC_KEY` | SSH public key for VM access |
| `AGENT_SSH_PRIVATE_KEY` | SSH private key used by pipeline to deploy |
| `AGENT_VM_USER` | VM admin username (`azureuser`) |
| `AGENT_VM_IP` | VM private IP (from `terraform output vm_private_ip`) |
| `APPROVER_EMAIL` | Email notified for the manual approval gate |

### Running tests

```bash
pytest --tb=short -q
```

### Linting

```bash
ruff check .
```

---

## Project structure

```
azure-email-agent/
├── agent/                  Python agent service
│   ├── config.py           Env var + Key Vault config loader
│   ├── gmail_client.py     Gmail API read/reply
│   ├── claude_client.py    Azure AI Foundry → Claude Sonnet
│   ├── email_processor.py  Orchestrates per-email workflow
│   └── main.py             Entry point / poll loop
├── infra/                  Terraform (VM, Key Vault, Log Analytics)
├── pipelines/              Azure DevOps pipeline definition
├── tests/                  pytest test suite
├── docs/                   Architecture notes and case study draft
├── .env.example            Environment variable template
└── requirements.txt        Python dependencies
```

---

## Security notes

- No secrets in code or committed `.env` files.
- The VM authenticates to Key Vault using its **system-assigned managed identity** — no API keys on disk.
- Key Vault uses **RBAC mode**; the VM's identity has only the `Key Vault Secrets User` role.
- The VM has **no public IP** — pipeline deployment uses SSH through a private network path.
- All Azure resources are tagged and scoped to a single resource group for clean teardown.

---

## License

MIT
