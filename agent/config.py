"""Non-secret config from environment variables; secrets fetched from Azure Key Vault."""
import os
from dataclasses import dataclass, field

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


@dataclass
class Config:
    key_vault_name: str
    foundry_deployment: str
    poll_interval_seconds: int
    # Populated by _load_secrets(); not passed to __init__
    gmail_credentials_json: str = field(default="", init=False)
    foundry_api_key: str = field(default="", init=False)


def load_config() -> Config:
    """Load environment config then pull secrets from Key Vault."""
    cfg = Config(
        key_vault_name=os.environ["KEY_VAULT_NAME"],
        foundry_deployment=os.environ["AZURE_FOUNDRY_DEPLOYMENT"],
        poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "60")),
    )
    _load_secrets(cfg)
    return cfg


def _load_secrets(cfg: Config) -> None:
    vault_url = f"https://{cfg.key_vault_name}.vault.azure.net"
    kv = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
    cfg.gmail_credentials_json = kv.get_secret("gmail-credentials-json").value
    cfg.foundry_api_key = kv.get_secret("foundry-api-key").value
