"""FastAPI main application"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from ..shared.models import TravelPlanRequest, TravelPlanResponse, TaskStatus, TravelItinerary
from ..shared.constants import TaskStatusConstants
from ..services.config import get_settings
from ..services.travel_plan_service import TravelPlanService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Global service instance
travel_plan_service: TravelPlanService = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Lifespan context manager for startup and shutdown"""
    global travel_plan_service
    
    # Startup
    logger.info("Starting up Travel Planner API...")
    travel_plan_service = TravelPlanService(settings)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Travel Planner API...")
    if travel_plan_service:
        await travel_plan_service.close()


# Create FastAPI app
app = FastAPI(
    title="Travel Planner API",
    description="AI-Powered Travel Itinerary Generator using Azure OpenAI and Agent Framework",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/api/travel-plans",
    response_model=TravelPlanResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Travel Plans"]
)
async def create_travel_plan(request: TravelPlanRequest) -> TravelPlanResponse:
    """
    Create a new travel plan request
    
    This endpoint accepts a travel plan request and queues it for asynchronous processing.
    Returns immediately with a task ID that can be used to check status and retrieve results.
    """
    logger.info(f"Received travel plan request for {request.destination}")
    
    try:
        response = await travel_plan_service.create_travel_plan_async(request)
        return response
    except Exception as ex:
        logger.error(f"Error creating travel plan: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create travel plan request"
        )


@app.get(
    "/api/travel-plans/{task_id}",
    response_model=TaskStatus,
    tags=["Travel Plans"]
)
async def get_task_status(task_id: str) -> TaskStatus:
    """
    Get the current status of a travel plan task
    
    Returns the current status, progress percentage, and result (if completed).
    """
    task_status = await travel_plan_service.get_task_status_async(task_id)
    
    if not task_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    # If completed, include the result in the response
    if task_status.status == TaskStatusConstants.COMPLETED:
        itinerary = await travel_plan_service.get_travel_itinerary_async(task_id)
        task_status.result = itinerary
    
    return task_status


@app.get(
    "/api/travel-plans/{task_id}/result",
    response_model=TravelItinerary,
    tags=["Travel Plans"]
)
async def get_travel_itinerary(task_id: str) -> TravelItinerary:
    """
    Get the completed travel itinerary
    
    Returns the full travel itinerary for a completed task.
    Returns 425 (Too Early) if the task is not yet completed.
    """
    # First check the status
    task_status = await travel_plan_service.get_task_status_async(task_id)
    
    if not task_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    if task_status.status != TaskStatusConstants.COMPLETED:
        raise HTTPException(
            status_code=425,  # Too Early
            detail=f"Task is not yet completed. Current status: {task_status.status}"
        )
    
    itinerary = await travel_plan_service.get_travel_itinerary_async(task_id)
    
    if not itinerary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Result for task {task_id} not found"
        )
    
    return itinerary


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z"
    }


@app.get("/", include_in_schema=False)
async def root():
    """Serve the main page"""
    return FileResponse("src/travel_planner/static/index.html")


# Mount static files
import os
static_path = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")
