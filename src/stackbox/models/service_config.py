from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 3306
    username: str = ""
    password: str = ""
    database: str = ""

    @property
    def connection_string(self) -> str:
        return (
            f"mysql+pymysql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class KeystoneAuthConfig(BaseModel):
    auth_url: str = "http://localhost:5000"
    auth_type: str = "password"
    project_domain_name: str = "Default"
    user_domain_name: str = "Default"
    project_name: str = "service"
    username: str = ""
    password: str = ""


class RabbitMQConfig(BaseModel):
    host: str = "localhost"
    port: int = 5672
    username: str = "stackbox"
    password: str = ""
    vhost: str = "/"


class ServiceConfig(BaseModel):
    """Base config shared by all OpenStack services."""

    service_name: str
    database: DatabaseConfig = DatabaseConfig()
    keystone_auth: KeystoneAuthConfig = KeystoneAuthConfig()
    rabbitmq: RabbitMQConfig = RabbitMQConfig()
