output "resource_group_name" {
  description = "Name of the provisioned resource group"
  value       = azurerm_resource_group.main.name
}

output "key_vault_uri" {
  description = "URI of the Key Vault — used by the agent to fetch secrets at runtime"
  value       = azurerm_key_vault.main.vault_uri
}

output "vm_principal_id" {
  description = "Object ID of the VM's system-assigned managed identity"
  value       = azurerm_linux_virtual_machine.agent.identity[0].principal_id
}

output "vm_private_ip" {
  description = "Private IP of the agent VM (no public IP — access via Azure Bastion or VPN)"
  value       = azurerm_network_interface.agent.private_ip_address
}

output "log_analytics_workspace_id" {
  description = "Resource ID of the Log Analytics workspace"
  value       = azurerm_log_analytics_workspace.main.id
}
