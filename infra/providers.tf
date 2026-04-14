terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  subscription_id             = var.subscription_id
  resource_provider_registrations = "none"

  features {
    key_vault {
      # Allows clean re-provision during demo teardown/rebuild cycles
      purge_soft_delete_on_destroy    = true
      recover_soft_deleted_key_vaults = true
    }
  }
}
