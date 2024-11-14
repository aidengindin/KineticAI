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
    """A class for managing secrets using HashiCorp Vault.
    This class provides an interface for interacting with HashiCorp Vault to securely store and retrieve secrets.
    It handles authentication, connection management, and provides methods for getting and setting secrets.
        settings (VaultSettings): Configuration settings for the Vault connection
        _client (hvac.Client): Internal Vault client instance, initialized lazily
    Methods:
        client: Property that returns configured hvac.Client instance
        get_secret(key): Retrieves a secret from Vault by key
        set_secret(key, value): Stores a secret in Vault
    Example:
        secrets = SecretsManager()
        my_secret = secrets.get_secret("api_key")
        success = secrets.set_secret("new_secret", "secret_value")
        This class requires valid Vault credentials to be configured in VaultSettings.
        All methods handle errors gracefully and log issues rather than raising exceptions.
    """
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
        """Retrieves a secret value from HashiCorp Vault.
        Attempts to read a secret from Vault at the specified path if authenticated. Returns None if
        authentication fails or if any error occurs during retrieval.
        Args:
            key (str): The key name of the secret to retrieve from Vault.
        Returns:
            Optional[str]: The secret value if successfully retrieved, None otherwise.
        Raises:
            No exceptions are raised - all exceptions are caught and logged.
        """
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
        """Set a secret in HashiCorp Vault.

        This method creates or updates a secret in the Vault at the specified path.

        Args:
            key (str): The key/name of the secret to be stored
            value (str): The value to be stored as the secret

        Returns:
            bool: True if the secret was successfully set, False if an error occurred

        Raises:
            None: Exceptions are caught and logged, returning False instead
        """
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
