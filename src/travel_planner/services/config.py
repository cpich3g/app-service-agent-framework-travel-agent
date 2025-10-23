"""Configuration settings for the application"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # App settings
    app_base_url: str = "http://localhost:8000"
    
    # Service Bus settings
    service_bus_namespace: Optional[str] = None
    service_bus_connection_string: Optional[str] = None
    service_bus_queue_name: str = "travel-plans"
    
    # Cosmos DB settings
    cosmos_db_endpoint: Optional[str] = None
    cosmos_db_database_name: str = "TravelPlanner"
    cosmos_db_container_name: str = "travel-plans"
    
    # Agent settings
    agent_azure_openai_endpoint: Optional[str] = None
    agent_model_deployment_name: str = "gpt-4o"
    
    # Logging
    log_level: str = "INFO"

    class Config:
        env_prefix = ""
        case_sensitive = False
        env_file = ".env"
        env_nested_delimiter = "__"


def get_settings() -> Settings:
    """Get application settings"""
    return Settings()
