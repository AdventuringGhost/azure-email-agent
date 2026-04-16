# Azure Gmail Email Agent — DevSecOps Case Study

> Published at adventuringghost.com — Skipper, DevSecOps Portfolio

---

## Overview

This project is a fully automated email agent that monitors a Gmail inbox, classifies each message with Claude Sonnet via Azure AI Foundry, and sends a drafted reply — all without human intervention. The entire backend runs on a private Linux VM in Azure with zero secrets stored in code or environment files. Infrastructure is reproducible from a single `terraform apply`, the deployment pipeline runs on Azure DevOps, and the whole stack was built, proven, torn down, and rebuilt on camera as portfolio evidence of real infrastructure discipline.

---

## Problem Statement

Inbox triage is a recurring time sink: reading, categorising, and drafting replies to routine messages consumes attention that belongs elsewhere. The deeper engineering challenge was more interesting than the automation itself — how do you wire a Gmail OAuth flow, a proprietary LLM endpoint, and runtime secret injection together in a cloud-native way that a security reviewer would actually approve?

The constraints I set for this project were strict:
- No secrets in source control, `.env` files, or VM disk.
- No public IP on the agent VM.
- All Azure auth flows through managed identity — no long-lived credentials anywhere in the pipeline.
- Every Azure resource provisioned via Terraform, tagged, and destroyable cleanly in one command.
- Total cost under $1 for the demo run.

Meeting all five constraints simultaneously is what makes this a DevSecOps project rather than a scripting exercise.

---

## Architecture Decisions

### Polling over push (Gmail Watch)

Gmail's push API (`watch` + Pub/Sub) requires a verified public HTTPS endpoint. Since the VM has no public IP by design, that option was off the table from the start. The agent uses a 60-second polling loop (`time.sleep(config.poll_interval_seconds)`) instead. For a personal inbox at demo volume, polling latency is irrelevant and the implementation is simpler to operate and debug.

### Azure AI Foundry for Claude access

Azure AI Foundry exposes Claude Sonnet on an Azure OpenAI-compatible endpoint, which the Anthropic Python SDK can target by overriding `base_url`. This keeps the Claude integration inside the Azure perimeter — auth goes through the Foundry API key stored in Key Vault, not through a direct call to api.anthropic.com. Prompt caching is enabled on the system prompt via `"cache_control": {"type": "ephemeral"}` so repeated poll cycles don't re-encode the same instruction tokens.

### System-assigned managed identity over service principals

The VM authenticates to Key Vault using its system-assigned managed identity. No client ID, no client secret, no credential rotation ceremony — the identity is tied to the VM lifecycle and Azure handles the token exchange. `DefaultAzureCredential` in the agent code picks this up transparently in production; locally it falls through to `az login` credentials, so the same code path works in both environments.

### RBAC mode for Key Vault

The Key Vault is provisioned with `rbac_authorization_enabled = true`, using Azure RBAC rather than legacy access policies. The VM's managed identity is granted exactly one role: `Key Vault Secrets User` (read-only on secrets). Nothing else. This follows least-privilege strictly — the VM cannot create, update, or delete secrets even if the process is compromised.

### Single VM, no containers (deliberate)

Containerising the agent would have added image build steps, a registry, and container runtime config to the scope. For a single-process, single-tenant workload this would have been complexity for its own sake. The agent runs as a `systemd` service (`email-agent.service`) on a plain Ubuntu 22.04 LTS VM. The pipeline deploys by rsync-ing the `agent/` directory over SSH and restarting the service — straightforward, auditable, and fast.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Agent runtime | Python 3.11, `anthropic` SDK | Targets Azure AI Foundry via `base_url` override |
| Email | Gmail API v1 (OAuth2) | `gmail.modify` scope; credentials in Key Vault |
| LLM | Claude Sonnet via Azure AI Foundry | Prompt caching on system prompt |
| Secrets | Azure Key Vault (Standard, RBAC) | `gmail-credentials-json`, `foundry-api-key` |
| Auth | System-assigned managed identity | `DefaultAzureCredential` in all SDK calls |
| Observability | Azure Log Analytics (PerGB2018) | 30-day retention, 5 GB/month free tier |
| IaC | Terraform ≥ 1.5, `azurerm ~> 4.0` | Remote state in Azure Blob Storage |
| CI/CD | Azure DevOps Pipelines (3 stages) | Manual approval gate before `terraform apply` |
| Linting | ruff | Enforced in pipeline validate stage |
| Tests | pytest | Unit tests with mocked Azure/Gmail/Anthropic clients |

---

## Security Approach

Security was a first-class requirement, not a retrofit.

**No secrets at rest anywhere in the pipeline.** The two runtime secrets — the Gmail OAuth2 token JSON and the Azure AI Foundry API key — live exclusively in Key Vault. The agent fetches them on startup via `SecretClient` authenticated through the VM's managed identity. The pipeline injects only the SSH public key (a non-secret) into Terraform as a variable; the SSH private key used for deployment is stored as an Azure DevOps pipeline secret variable and written to a temp file that is explicitly deleted in an `always()`-condition cleanup step.

**No public network exposure.** The VM has no `public_ip_address_id` in its NIC configuration. Pipeline deployment reaches the VM via SSH through an Azure-internal network path. Access for interactive debugging would go through Azure Bastion or a VPN — not a public SSH port.

**RBAC scoping.** The `azurerm_role_assignment` for the VM's managed identity is scoped to the Key Vault resource ID, not the subscription or resource group. The role definition is `Key Vault Secrets User` — the narrowest built-in role that allows secret reads.

**Terraform provider-level Key Vault safety.** The `azurerm` provider block configures `recover_soft_deleted_key_vaults = true` so that Terraform can adopt a soft-deleted vault during re-provision rather than failing; and `purge_soft_delete_on_destroy = true` so that `terraform destroy` actually cleans up rather than leaving a zombie vault in soft-delete limbo.

**Committed-secret prevention.** `.env` files are in `.gitignore`. The `.env.example` contains only placeholder strings. `CLAUDE.md` explicitly prohibits committing secrets.

---

## IaC Strategy

The Terraform config provisions six resources in a single root module: resource group, virtual network, subnet, NIC, Linux VM, Key Vault, role assignment, and Log Analytics workspace. There are no child modules — at this scale a flat structure is easier to follow and there is no re-use case that would justify the indirection.

**Resource naming convention:** all names are derived from `var.project_name` with a type prefix — `rg-azure-email-agent`, `vm-azure-email-agent`, `law-azure-email-agent`. The Key Vault name strips hyphens to stay within the 24-character limit (`azureemailagentkv`).

**Tagging:** every resource carries `project = var.project_name` and `environment = "demo"` tags. This makes cost attribution unambiguous in Azure Cost Management and allows bulk deletion by tag if needed.

**Remote state:** `terraform init` is configured with Azure Blob Storage as the backend (`TF_BACKEND_*` variables in the pipeline). The state file key is `email-agent.tfstate`. This means any pipeline agent — or any operator with the right subscription access — can run plan or apply against the same live state.

**Destroy discipline:** The cost model for this project is build-demo-destroy. `terraform destroy` is the final step after recording proof of completion. The Key Vault soft-delete behavior (described below) was the main friction point in making clean destroy cycles reliable.

---

## CI/CD Design

The Azure DevOps pipeline (`pipelines/azure-pipelines.yml`) has three sequential stages gated on success.

**Stage 1 — Validate:** Runs on `ubuntu-latest`, installs dependencies from `requirements.txt` plus `ruff` and `pytest`, then runs `ruff check .` and `pytest --tb=short -q`. This stage runs on every push to `main` and must pass before any infrastructure work begins.

**Stage 2 — Terraform Plan:** Runs `terraform init` with the Blob Storage backend, then `terraform plan -out=tfplan`. The plan artifact is published to the pipeline. A `ManualValidation@0` task then pauses the pipeline for up to 24 hours, notifying the approver by email. The pipeline rejects automatically on timeout. This gate exists because `terraform apply` incurs real Azure spend and provisions real infrastructure — no automation should bypass a human sign-off on that.

**Stage 3 — Deploy:** Downloads the saved plan artifact, re-runs `terraform init`, and executes `terraform apply tfplan` (no re-plan, executes exactly what was approved). Once the VM is up, a second job writes the SSH private key from a pipeline secret, rsyncs the `agent/` directory to `/opt/email-agent/agent/` on the VM, installs dependencies, restarts the `email-agent` systemd service, and immediately shreds the key from the ephemeral agent filesystem.

The pipeline service connection uses a federated credential (workload identity federation) — no client secrets in ADO either.

---

## Challenges & Solutions

### 1. B-series VM capacity failure in eastus2

The initial Terraform config targeted `eastus2` with `Standard_B1s` — the cheapest general-purpose SKU for a demo workload. `terraform apply` failed at VM provisioning with an `AllocationFailed` error: the B-series capacity pool in eastus2 was exhausted for the requested SKU at that time. Azure capacity allocation is regional and SKU-specific; B-series is heavily subscribed because it is the free-tier and trial-account default.

**Fix:** Changed `var.location` from `eastus2` to `eastus` and upgraded the SKU to `Standard_D2s_v3`. The D2s_v3 (2 vCPU, 8 GiB) is more expensive per hour but has far broader regional availability. For a sub-hour demo run, the cost difference is negligible. The change is committed as `fix: switch to eastus, D2s_v3 due to B-series capacity limits in eastus2`.

### 2. Key Vault soft-delete blocking re-provision

Azure Key Vault has soft-delete enabled by default (minimum 7-day retention, non-disableable on newer API versions). After a `terraform destroy`, the vault enters a soft-deleted state. A subsequent `terraform apply` with the same vault name fails because the name is still reserved — Azure treats the soft-deleted vault as occupying the namespace.

This turned destroy-rebuild cycles into a manual chore: either wait 7 days, or go into the Azure portal and explicitly purge the vault, or use the Azure CLI to force-purge. None of these are acceptable in a demo context where the whole point is to show reproducible infra.

**Fix:** The `azurerm` provider block in `providers.tf` sets `purge_soft_delete_on_destroy = true` and `recover_soft_deleted_key_vaults = true` under the `key_vault {}` features block. With these flags, `terraform destroy` purges the vault completely (no soft-delete retention), and `terraform apply` can recover a soft-deleted vault if one exists with the same name instead of erroring. Clean destroy-rebuild cycles now work without manual portal intervention.

### 3. azurerm v4 provider RBAC rename

The Terraform `azurerm` provider v4 renamed the Key Vault access policy argument. The legacy `access_policy` block is gone; RBAC-mode vaults use `rbac_authorization_enabled = true` on the `azurerm_key_vault` resource, and permissions are granted via `azurerm_role_assignment` resources. The corresponding `azurerm_key_vault_access_policy` resource was also removed from the provider.

This is a breaking change from v3 patterns that most online Terraform examples still use. Updating required replacing the access policy block with a role assignment and ensuring the role definition name matched Azure's built-in role naming exactly (`Key Vault Secrets User`, not `KeyVaultSecretsUser` or any variation). The fix is in the commit `fix: provider v4, rbac rename, confirmed private VM`.

### 4. Gmail OAuth2 in a headless environment

The standard Gmail OAuth2 flow opens a browser redirect to capture an authorization code. The agent VM has no display and no browser. The solution is to complete the OAuth2 authorization flow once locally — on a machine with a browser — generate the `credentials.json` token file, then store the entire JSON blob as the `gmail-credentials-json` secret in Key Vault. The `GmailClient` deserializes this at startup using `Credentials.from_authorized_user_info()`, and the `google-auth` library handles token refresh automatically using the embedded refresh token. No browser is ever needed on the VM.

---

## Cost Model

All resources were provisioned for the demo run and destroyed immediately after recording proof of completion. The total Azure spend for the full build-demo-destroy cycle was under $1.

| Resource | SKU | Approx. hourly | Notes |
|---|---|---|---|
| Linux VM | Standard_D2s_v3 | ~$0.096/hr | Demo runtime: <2 hours total |
| Azure Key Vault | Standard | ~$0.00003/operation | Well within 10,000 free ops/month |
| Log Analytics | PerGB2018 | ~$2.30/GB after 5 GB free | Demo log volume: <50 MB |
| Azure AI Foundry | Claude Sonnet token pricing | Varies | Demo volume: handful of API calls |
| Azure DevOps | Free tier (1 Microsoft-hosted job) | $0 | Free tier covers all pipeline runs |
| Azure Blob (tfstate) | LRS, Standard | ~$0.002/month | Negligible |
| **Total (demo run)** | | | **< $1 actual spend** |

The D2s_v3 at ~$0.10/hr running for under two hours costs less than $0.20. Key Vault operations at demo volume are fractions of a cent. The AI Foundry token spend for classifying a handful of test emails is similarly negligible. The month's free tier on Log Analytics absorbs the demo log volume entirely.

---

## Results & Evidence

The completed demo shows:

1. **Pipeline run:** All three stages — validate, terraform plan (with manual approval), deploy — pass green in Azure DevOps. The plan artifact is inspectable in the pipeline artifacts viewer.

2. **Infrastructure:** `terraform output` shows the resource group name, Key Vault URI, VM principal ID, VM private IP, and Log Analytics workspace ID — confirming all resources provisioned correctly.

3. **Agent operation:** The agent starts, authenticates to Key Vault via managed identity, fetches both secrets successfully, then enters the poll loop. Incoming test emails appear in the structured log output with their classification (`urgent`, `routine`, or `spam`) and summary.

4. **Claude integration:** Classified emails that are not spam trigger a `send_reply` call. The reply arrives in the sender's inbox with the correct subject prefix (`Re: ...`) and a coherent drafted response.

5. **Clean teardown:** `terraform destroy` completes without manual intervention. The Key Vault is purged (not soft-deleted), the VM is deallocated and deleted, and the resource group is removed. A second `terraform apply` immediately after reproduces the full stack from scratch — the IaC rebuild demo recorded as portfolio evidence.

---

## Lessons Learned

**Azure regional capacity is real.** B-series VMs are the tutorial SKU and they fill up fast in popular regions. For any project where you need a VM to actually provision reliably, test with a more available SKU (D-series or E-series) from the start. The cost difference at demo scale is rounding error.

**Read provider changelogs before major version bumps.** The azurerm v4 breaking changes around Key Vault access policies and RBAC are well-documented — they were just easy to skip when reaching for the latest provider. An hour of changelog reading would have saved the debugging cycle.

**Soft-delete is not optional on modern Key Vaults.** Plan for it from the start. The `purge_soft_delete_on_destroy` provider flag is the right tool for destroy-rebuild workflows; do not assume `terraform destroy` leaves a clean namespace without it.

**Managed identity removes an entire credential management surface.** There is no rotation ceremony, no secret expiry, no credential leak risk for the VM-to-KeyVault auth path. Every project that runs on Azure compute should use managed identity over service principals for the internal auth path.

**What I would change for production:**

- Replace polling with Gmail Pub/Sub push notifications behind an Azure API Management endpoint or Azure Function — eliminates the 60-second latency window and drops the VM's idle CPU to zero.
- Containerise the agent and run on Azure Container Apps. Removes the need to rsync code and manage a systemd service; blue/green deploys become trivial.
- Add a dead-letter queue (Azure Service Bus) for emails that fail classification or reply sending. Currently failed poll cycles log an exception and retry on the next tick — a durable queue would allow inspection and replay of failed messages.
- Add Azure Monitor alerts on Log Analytics query results (e.g., error rate > N per hour) and wire them to a notification channel.
