# Building an AI Email Agent on Azure for $1.50

I built a fully automated email agent that monitors a Gmail inbox, classifies every incoming message with Claude Sonnet, and sends a drafted reply — running on a private Azure VM with no secrets in code, no public IP, and a total cloud bill of $1.50. This is a portfolio case study, not a tutorial: the point is the decision-making, not the steps.

## Why this is harder than it looks

Connecting Gmail to an LLM sounds like a weekend project until you add real constraints. I gave myself five: no secrets in source control or `.env` files, no public IP on the agent VM, all Azure auth through managed identity, every resource provisioned by Terraform and cleanly destroyable in one command, and total Azure spend under two dollars. Meeting all five simultaneously is what separates a DevSecOps project from a scripting exercise. Each constraint ruled out an easy path and forced a considered decision somewhere downstream.

## Architecture and the decisions behind it

The agent polls Gmail every 60 seconds, classifies each unread message, and sends a reply. I chose polling over Gmail's push API because push requires a verified public HTTPS endpoint — which the VM intentionally doesn't have. No public IP means polling; that constraint was settled before I wrote a line of code.

The VM authenticates to Azure Key Vault using its system-assigned managed identity. I chose this over a service principal because there are no credentials to rotate, no client secret expiry to track, and no leak surface for the VM-to-KeyVault auth path. The Key Vault is in RBAC mode and the VM's identity holds exactly one role: `Key Vault Secrets User`. Read-only on secrets, nothing else.

Azure AI Foundry was the original plan for Claude access — it keeps LLM calls inside the Azure perimeter and the Anthropic SDK supports it via a `base_url` override. It hit a wall immediately: my subscription tier didn't include Foundry model access. Rather than stall waiting on a quota increase, I pivoted to the direct Anthropic API with the key stored in Key Vault like any other secret. The architecture held; only the endpoint changed.

## What went wrong and how I fixed it

The first `terraform apply` failed at VM provisioning with `AllocationFailed`. I'd targeted `Standard_B1s` in `eastus2` — the cheapest SKU in a popular region — and the B-series capacity pool was exhausted. I switched to `Standard_D2s_v3` in `eastus`. At under two hours of demo runtime the cost difference is rounding error; availability is not.

Key Vault's soft-delete behavior broke my destroy-rebuild cycle. After `terraform destroy`, the vault enters a 7-day soft-delete retention period and its name stays reserved. A second `terraform apply` fails because Azure still sees the vault as existing. The fix was two provider flags: `purge_soft_delete_on_destroy = true` and `recover_soft_deleted_key_vaults = true`. Clean teardowns now work without touching the portal.

At one point during local testing I ran an `az keyvault secret set` command with a secret value inline, which landed in shell history in plaintext. I caught it, rotated the key immediately, and cleared the history. No exposure window beyond the local machine, but the lesson was obvious: pipe from a file or use `--value @-` from stdin. I'd rather document that it happened and how I responded than pretend the session was clean.

## What this demonstrates

I built, validated, and destroyed a real cloud stack — not a toy sandbox, but a system with identity-based auth, least-privilege RBAC, IaC with a reproducible teardown, and a three-stage CI/CD pipeline with a manual approval gate before any `terraform apply`. The problems I hit were real infrastructure problems: regional capacity constraints, provider breaking changes, Key Vault lifecycle quirks. I diagnosed each one, fixed it at the right layer, and committed the change with a clear message.

## What I'd do differently at production scale

I'd replace the polling loop with Gmail Pub/Sub push notifications behind an Azure Function — eliminates the 60-second latency window. I'd containerize the agent and run it on Azure Container Apps instead of a VM with a `systemd` service and an rsync deploy. I'd move Terraform state to a remote backend in Azure Blob Storage with state locking. And I'd revisit Azure AI Foundry once subscription access is in place — keeping LLM calls inside the Azure perimeter is the right call for anything beyond a personal demo.

## Links

- GitHub: [github.com/AdventuringGhost/azure-email-agent](https://github.com/AdventuringGhost/azure-email-agent)
- Screen recording: adventuringghost.com/projects/azure-email-agent
