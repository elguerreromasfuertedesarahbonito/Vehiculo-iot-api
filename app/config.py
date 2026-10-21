from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    db_host: str = "instancia-rds-iot.ccptpkt3evuy.us-east-1.rds.amazonaws.com"
    db_port: int = 3306
    db_user: str = "admin"
    db_password: str = "perroloco123"
    db_name: str = "vehiculo_iot"
    db_ssl: bool = True
    db_ssl_ca: str = "certs/global-bundle.pem" 
    allowed_origins: str = "*"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")] if self.allowed_origins != "*" else ["*"]

settings = Settings()