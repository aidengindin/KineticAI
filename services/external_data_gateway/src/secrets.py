import hvac
from typing import Optional
import logging
from functools import lru_cache
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

class VaultSettings(BaseSettings):
    VAULT_ADDR: str = "http://localhost:8200"
    VAULT_TOKEN: Optional[str] = None
    VAULT_PATH: str = "external-data-gateway"
    VAULT_MOUNT_POINT: str = "kv"
    
    class Config:
        env_file = ".env"

class SecretsManager:
    def __init__(self, settings: Optional[VaultSettings] = None):
        self.settings = settings or VaultSettings()
        self._client = None

    @property
    def client(self) -> hvac.Client:
        if self._client is None:
            self._client = hvac.Client(
                url=self.settings.VAULT_ADDR,
                token=self.settings.VAULT_TOKEN
            )
        return self._client

    def get_secret(self, key: str) -> Optional[str]:
        try:
            if not self.client.is_authenticated():
                logger.warning("Not authenticated to Vault")
                return None

            secret = self.client.secrets.kv.v2.read_secret_version(
                path=f"{self.settings.VAULT_PATH}/{key}",
                mount_point=self.settings.VAULT_MOUNT_POINT
            )
            
            return secret["data"]["data"].get("value")
        except Exception as e:
            logger.error(f"Error retrieving secret {key}: {str(e)}")
            return None

    def set_secret(self, key: str, value: str) -> bool:
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=f"{self.settings.VAULT_PATH}/{key}",
                mount_point=self.settings.VAULT_MOUNT_POINT,
                secret=dict(value=value)
            )
            return True
        except Exception as e:
            logger.error(f"Error setting secret {key}: {str(e)}")
            return False

@lru_cache()
def get_secrets_manager() -> SecretsManager:
    return SecretsManager()
