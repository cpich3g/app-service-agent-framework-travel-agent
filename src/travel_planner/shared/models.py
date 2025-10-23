"""Data models for the travel planner application"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TravelPlanRequest(BaseModel):
    """Request to create a new travel plan"""
    destination: str = Field(..., description="Travel destination")
    start_date: datetime = Field(..., alias="startDate")
    end_date: datetime = Field(..., alias="endDate")
    budget: float = Field(..., description="Total budget in USD")
    interests: List[str] = Field(default_factory=list, description="List of interests")
    travel_style: str = Field(..., alias="travelStyle", description="Travel style preference")
    special_requests: Optional[str] = Field(None, alias="specialRequests", description="Special requests")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "destination": "Tokyo, Japan",
                "startDate": "2024-06-01T00:00:00Z",
                "endDate": "2024-06-05T00:00:00Z",
                "budget": 3000,
                "interests": ["culture", "food", "technology"],
                "travelStyle": "moderate",
                "specialRequests": "Vegetarian meals preferred"
            }
        }


class TravelPlanResponse(BaseModel):
    """Response when a travel planning task is initiated"""
    task_id: str = Field(..., alias="taskId")
    status: str
    status_url: str = Field(..., alias="statusUrl")
    result_url: str = Field(..., alias="resultUrl")
    message: Optional[str] = None

    class Config:
        populate_by_name = True


class Activity(BaseModel):
    """Activity within a day plan"""
    time: str = ""
    title: str = ""
    location: str = ""
    description: str = ""
    estimated_cost: float = Field(0, alias="estimatedCost")
    notes: Optional[str] = None

    class Config:
        populate_by_name = True


class DayPlan(BaseModel):
    """Plan for a single day"""
    day_number: int = Field(..., alias="dayNumber")
    date: datetime
    theme: str = ""
    morning: Activity = Field(default_factory=Activity)
    lunch: Activity = Field(default_factory=Activity)
    afternoon: Activity = Field(default_factory=Activity)
    dinner: Activity = Field(default_factory=Activity)
    evening: Optional[Activity] = None

    class Config:
        populate_by_name = True


class BudgetBreakdown(BaseModel):
    """Budget allocation breakdown"""
    total_budget: float = Field(..., alias="totalBudget")
    accommodation: float = 0
    food: float = 0
    activities: float = 0
    transportation: float = 0
    shopping: float = 0
    emergency: float = 0

    class Config:
        populate_by_name = True


class EmergencyInfo(BaseModel):
    """Emergency contact information"""
    local_emergency_number: str = Field("", alias="localEmergencyNumber")
    nearest_embassy: str = Field("", alias="nearestEmbassy")
    healthcare_info: str = Field("", alias="healthcareInfo")

    class Config:
        populate_by_name = True


class TravelItinerary(BaseModel):
    """Complete travel itinerary result"""
    task_id: str = Field(..., alias="taskId")
    destination: str
    start_date: datetime = Field(..., alias="startDate")
    end_date: datetime = Field(..., alias="endDate")
    daily_plans: List[DayPlan] = Field(default_factory=list, alias="dailyPlans")
    budget: BudgetBreakdown = Field(default_factory=BudgetBreakdown)
    travel_tips: List[str] = Field(default_factory=list, alias="travelTips")
    packing_list: List[str] = Field(default_factory=list, alias="packingList")
    emergency_contacts: EmergencyInfo = Field(default_factory=EmergencyInfo, alias="emergencyContacts")

    class Config:
        populate_by_name = True


class TaskStatus(BaseModel):
    """Current status of a travel planning task"""
    id: str = Field(..., description="Document ID for Cosmos DB")
    task_id: str = Field(..., alias="taskId")
    status: str
    progress_percentage: int = Field(0, alias="progressPercentage")
    current_step: Optional[str] = Field(None, alias="currentStep")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    result: Optional[TravelItinerary] = None

    class Config:
        populate_by_name = True

    def __init__(self, **data):
        if 'task_id' in data and 'id' not in data:
            data['id'] = data['task_id']
        elif 'id' in data and 'task_id' not in data:
            data['task_id'] = data['id']
        super().__init__(**data)


class TravelPlanMessage(BaseModel):
    """Message sent to Service Bus queue to process a travel plan"""
    task_id: str = Field(..., alias="taskId")
    request: TravelPlanRequest
    enqueued_at: datetime = Field(..., alias="enqueuedAt")

    class Config:
        populate_by_name = True


class TravelItineraryDocument(BaseModel):
    """Cosmos DB document for storing travel itinerary"""
    id: str
    itinerary: TravelItinerary

    class Config:
        populate_by_name = True
