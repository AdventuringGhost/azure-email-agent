variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
  default     = "7c53922c-d5f6-4754-bb0d-6a80bb46ac22"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus"
}

variable "project_name" {
  description = "Project name used as base for resource naming and tags"
  type        = string
  default     = "azure-email-agent"
}

variable "vm_size" {
  description = "VM SKU (B1s for demo cost control)"
  type        = string
  default     = "Standard_D2s_v3"
}

variable "admin_username" {
  description = "Local admin username on the VM"
  type        = string
  default     = "azureuser"
}

variable "admin_ssh_public_key" {
  description = "SSH public key content for VM access (set via TF_VAR or pipeline secret)"
  type        = string
  sensitive   = true
}
