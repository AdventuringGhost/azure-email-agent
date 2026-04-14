# Root Terraform module: provision Linux VM, Key Vault, Log Analytics, and supporting Azure resources.
# Auth strategy: system-assigned managed identity on the VM — no secrets in code or env files.

locals {
  tags = {
    project     = var.project_name
    environment = "demo"
  }

  # Key Vault names: 3–24 chars, alphanumeric + hyphens, globally unique.
  # Strip hyphens from project name so we have headroom for the "-kv" suffix.
  kv_name = "${replace(var.project_name, "-", "")}kv"
}

data "azurerm_client_config" "current" {}

# ── Resource Group ─────────────────────────────────────────────────────────────

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}"
  location = var.location
  tags     = local.tags
}

# ── Networking (private only — no public IP) ───────────────────────────────────

resource "azurerm_virtual_network" "main" {
  name                = "vnet-${var.project_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = ["10.0.0.0/16"]
  tags                = local.tags
}

resource "azurerm_subnet" "agent" {
  name                 = "snet-agent"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_network_interface" "agent" {
  name                = "nic-${var.project_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.agent.id
    private_ip_address_allocation = "Dynamic"
    # No public_ip_address_id — VM is intentionally private
  }
}

# ── Linux VM ───────────────────────────────────────────────────────────────────

resource "azurerm_linux_virtual_machine" "agent" {
  name                            = "vm-${var.project_name}"
  location                        = azurerm_resource_group.main.location
  resource_group_name             = azurerm_resource_group.main.name
  size                            = var.vm_size
  admin_username                  = var.admin_username
  disable_password_authentication = true
  network_interface_ids           = [azurerm_network_interface.agent.id]
  tags                            = local.tags

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.admin_ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  # System-assigned managed identity — used to authenticate to Key Vault at runtime
  identity {
    type = "SystemAssigned"
  }
}

# ── Key Vault (RBAC mode) ──────────────────────────────────────────────────────

resource "azurerm_key_vault" "main" {
  name                       = local.kv_name
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true   # access policies replaced by Azure RBAC
  soft_delete_retention_days = 7
  tags                       = local.tags
}

# Grant the VM's managed identity the ability to read secrets — nothing more.
resource "azurerm_role_assignment" "vm_kv_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_virtual_machine.agent.identity[0].principal_id
}

# ── Log Analytics Workspace ────────────────────────────────────────────────────

resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-${var.project_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}
