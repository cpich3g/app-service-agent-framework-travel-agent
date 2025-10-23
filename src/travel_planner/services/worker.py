"""Background worker for processing travel plan requests from Service Bus"""
import asyncio
import json
import logging
from datetime import datetime

from azure.identity import DefaultAzureCredential
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey, exceptions

from ..shared.models import TravelPlanMessage, TaskStatus, TravelItineraryDocument
from ..shared.constants import TaskStatusConstants
from .config import Settings
from .travel_agent_service import TravelAgentService

logger = logging.getLogger(__name__)


class TravelPlanWorker:
    """Background worker for processing travel plan requests"""
    
    def __init__(self, settings: Settings):
        """Initialize the worker"""
        self.settings = settings
        self.running = False
        self._service_bus_client = None
        self._cosmos_client = None
        self._container = None
        self._agent_service = None
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Ensure the worker is initialized"""
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
        
        # Initialize agent service
        self._agent_service = TravelAgentService(self.settings)
        
        self._initialized = True
    
    async def start(self):
        """Start the worker"""
        logger.info("Travel Planner Worker starting...")
        await self._ensure_initialized()
        
        self.running = True
        
        receiver = self._service_bus_client.get_queue_receiver(
            queue_name=self.settings.service_bus_queue_name,
            max_wait_time=5
        )
        
        async with receiver:
            logger.info("Worker is now processing messages")
            
            while self.running:
                try:
                    # Receive messages
                    received_msgs = await receiver.receive_messages(
                        max_message_count=1,
                        max_wait_time=5
                    )
                    
                    for msg in received_msgs:
                        await self._process_message(msg, receiver)
                    
                    # Small delay to prevent tight loop
                    await asyncio.sleep(0.1)
                    
                except Exception as ex:
                    logger.error(f"Error in message processing loop: {ex}")
                    await asyncio.sleep(5)  # Back off on error
        
        logger.info("Worker shutting down...")
    
    async def stop(self):
        """Stop the worker"""
        logger.info("Worker stop requested...")
        self.running = False
        if self._agent_service:
            await self._agent_service.close()
        if self._service_bus_client:
            await self._service_bus_client.close()
        if self._cosmos_client:
            await self._cosmos_client.close()
    
    async def _process_message(self, message, receiver):
        """Process a single message"""
        message_body = str(message)
        logger.info(f"Received message: {message.message_id}")
        
        try:
            # Parse the message
            message_data = json.loads(message_body)
            plan_message = TravelPlanMessage(**message_data)
            
            # Check if this task is already completed
            try:
                existing_status = await self._container.read_item(
                    item=plan_message.task_id,
                    partition_key=plan_message.task_id
                )
                
                if existing_status.get('status') == TaskStatusConstants.COMPLETED:
                    logger.info(
                        f"Task {plan_message.task_id} is already completed. "
                        "Skipping reprocessing and completing message."
                    )
                    await receiver.complete_message(message)
                    return
                
                if existing_status.get('status') == TaskStatusConstants.PROCESSING:
                    logger.warning(
                        f"Task {plan_message.task_id} is already being processed. "
                        "This might be a duplicate message."
                    )
            except exceptions.CosmosResourceNotFoundError:
                # Task status doesn't exist yet, this is a new task
                pass
            
            # Update status to processing
            await self._update_task_status_async(
                plan_message.task_id,
                TaskStatusConstants.PROCESSING,
                0,
                "Starting travel plan generation..."
            )
            
            # Create progress callback
            def progress_callback(percentage: int, step: str):
                asyncio.create_task(
                    self._update_task_status_async(
                        plan_message.task_id,
                        TaskStatusConstants.PROCESSING,
                        percentage,
                        step
                    )
                )
            
            # Generate the travel plan
            itinerary = await self._agent_service.generate_travel_plan_async(
                plan_message.request,
                plan_message.task_id,
                progress_callback
            )
            
            # Store the result
            await self._store_result_async(plan_message.task_id, itinerary)
            
            # Update final status
            await self._update_task_status_async(
                plan_message.task_id,
                TaskStatusConstants.COMPLETED,
                100,
                "Travel plan completed successfully!"
            )
            
            # Complete the message
            await receiver.complete_message(message)
            
            logger.info(f"Successfully processed travel plan {plan_message.task_id}")
            
        except Exception as ex:
            logger.error(f"Error processing message {message.message_id}: {ex}")
            
            # Try to update task status to failed
            try:
                message_data = json.loads(message_body)
                task_id = message_data.get('taskId')
                if task_id:
                    await self._update_task_status_async(
                        task_id,
                        TaskStatusConstants.FAILED,
                        0,
                        "An error occurred while generating your travel plan.",
                        str(ex)
                    )
            except:
                pass  # Ignore errors in error handling
            
            # Dead letter the message after max retries
            if message.delivery_count >= 3:
                await receiver.dead_letter_message(
                    message,
                    reason="ProcessingFailed",
                    error_description=str(ex)
                )
            else:
                await receiver.abandon_message(message)
    
    async def _update_task_status_async(
        self,
        task_id: str,
        status: str,
        progress_percentage: int,
        current_step: str,
        error_message: str = None
    ):
        """Update task status in Cosmos DB"""
        # Try to read existing status to preserve CreatedAt timestamp
        created_at = datetime.utcnow()
        try:
            existing_status = await self._container.read_item(
                item=task_id,
                partition_key=task_id
            )
            created_at = datetime.fromisoformat(
                existing_status['createdAt'].replace('Z', '+00:00')
            )
        except exceptions.CosmosResourceNotFoundError:
            # Item doesn't exist yet, use current time
            pass
        
        task_status = TaskStatus(
            id=task_id,
            task_id=task_id,
            status=status,
            progress_percentage=progress_percentage,
            current_step=current_step,
            created_at=created_at,
            updated_at=datetime.utcnow(),
            error_message=error_message
        )
        
        await self._container.upsert_item(
            body=task_status.model_dump(by_alias=True, mode='json')
        )
        
        logger.info(
            f"Updated task {task_id} status: {status} - {progress_percentage}% - {current_step}"
        )
    
    async def _store_result_async(self, task_id: str, itinerary):
        """Store the travel itinerary result in Cosmos DB"""
        result_id = f"{task_id}_result"
        document = TravelItineraryDocument(
            id=result_id,
            itinerary=itinerary
        )
        
        await self._container.upsert_item(
            body=document.model_dump(by_alias=True, mode='json')
        )
        
        logger.info(f"Stored travel itinerary result for task {task_id}")


async def run_worker():
    """Run the worker"""
    from .config import get_settings
    
    settings = get_settings()
    worker = TravelPlanWorker(settings)
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    finally:
        await worker.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(run_worker())
