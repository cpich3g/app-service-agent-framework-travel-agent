"""Travel plan service for managing requests, status, and results"""
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from azure.identity import DefaultAzureCredential
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey, exceptions

from ..shared.models import (
    TravelPlanRequest, TravelPlanResponse, TaskStatus, 
    TravelItinerary, TravelPlanMessage, TravelItineraryDocument
)
from ..shared.constants import TaskStatusConstants
from .config import Settings

logger = logging.getLogger(__name__)


class TravelPlanService:
    """Service for managing travel plan requests, task status tracking, and itinerary retrieval"""
    
    def __init__(self, settings: Settings):
        """Initialize the travel plan service"""
        self.settings = settings
        self._service_bus_client = None
        self._sender = None
        self._cosmos_client = None
        self._container = None
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Ensure the service is initialized"""
        if self._initialized:
            return
        
        # Initialize Service Bus client
        if self.settings.service_bus_namespace:
            # Production: Use managed identity
            credential = DefaultAzureCredential()
            self._service_bus_client = ServiceBusClient(
                fully_qualified_namespace=self.settings.service_bus_namespace,
                credential=credential
            )
        elif self.settings.service_bus_connection_string:
            # Local development: Use connection string
            self._service_bus_client = ServiceBusClient.from_connection_string(
                self.settings.service_bus_connection_string
            )
        else:
            raise ValueError("Service Bus configuration is missing")
        
        self._sender = self._service_bus_client.get_queue_sender(
            queue_name=self.settings.service_bus_queue_name
        )
        
        # Initialize Cosmos DB client
        if self.settings.cosmos_db_endpoint:
            credential = DefaultAzureCredential()
            self._cosmos_client = CosmosClient(
                url=self.settings.cosmos_db_endpoint,
                credential=credential
            )
            
            database = self._cosmos_client.get_database_client(
                self.settings.cosmos_db_database_name
            )
            self._container = database.get_container_client(
                self.settings.cosmos_db_container_name
            )
        else:
            raise ValueError("Cosmos DB configuration is missing")
        
        self._initialized = True
    
    async def create_travel_plan_async(
        self, request: TravelPlanRequest
    ) -> TravelPlanResponse:
        """Create a new travel plan request and queue it for processing"""
        await self._ensure_initialized()
        
        task_id = uuid4().hex
        
        logger.info(
            f"Creating travel plan task {task_id} for destination {request.destination}"
        )
        
        # Create the message for Service Bus
        message_data = TravelPlanMessage(
            task_id=task_id,
            request=request,
            enqueued_at=datetime.utcnow()
        )
        
        # Send to Service Bus queue
        message = ServiceBusMessage(
            body=message_data.model_dump_json(),
            content_type="application/json",
            message_id=task_id
        )
        
        await self._sender.send_messages(message)
        
        # Store initial status in Cosmos DB
        task_status = TaskStatus(
            id=task_id,
            task_id=task_id,
            status=TaskStatusConstants.QUEUED,
            progress_percentage=0,
            current_step="Request queued for processing",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        await self._store_task_status_async(task_status)
        
        base_url = self.settings.app_base_url
        
        return TravelPlanResponse(
            task_id=task_id,
            status=TaskStatusConstants.QUEUED,
            status_url=f"{base_url}/api/travel-plans/{task_id}/status",
            result_url=f"{base_url}/api/travel-plans/{task_id}/result",
            message="Your travel plan is being created. Please check the status URL for updates."
        )
    
    async def get_task_status_async(self, task_id: str) -> Optional[TaskStatus]:
        """Get the current status of a travel planning task"""
        await self._ensure_initialized()
        
        try:
            item = await self._container.read_item(
                item=task_id,
                partition_key=task_id
            )
            return TaskStatus(**item)
        except exceptions.CosmosResourceNotFoundError:
            return None
    
    async def get_travel_itinerary_async(
        self, task_id: str
    ) -> Optional[TravelItinerary]:
        """Retrieve the completed travel itinerary for a task"""
        await self._ensure_initialized()
        
        try:
            result_id = f"{task_id}_result"
            item = await self._container.read_item(
                item=result_id,
                partition_key=result_id
            )
            doc = TravelItineraryDocument(**item)
            return doc.itinerary
        except exceptions.CosmosResourceNotFoundError:
            return None
    
    async def _store_task_status_async(self, status: TaskStatus) -> None:
        """Store task status in Cosmos DB"""
        await self._container.upsert_item(
            body=status.model_dump(by_alias=True, mode='json')
        )
    
    async def close(self):
        """Close connections"""
        if self._sender:
            await self._sender.close()
        if self._service_bus_client:
            await self._service_bus_client.close()
        if self._cosmos_client:
            await self._cosmos_client.close()

