"""Simple tests to verify the converted Python application"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from datetime import datetime
from travel_planner.shared.models import (
    TravelPlanRequest, TravelPlanResponse, TaskStatus, 
    TravelItinerary, BudgetBreakdown
)
from travel_planner.shared.constants import TaskStatusConstants


def test_models():
    """Test that all models can be instantiated"""
    print("Testing models...")
    
    # Test TravelPlanRequest
    request = TravelPlanRequest(
        destination="Tokyo, Japan",
        start_date=datetime(2024, 6, 1),
        end_date=datetime(2024, 6, 5),
        budget=3000,
        interests=["culture", "food"],
        travel_style="moderate"
    )
    assert request.destination == "Tokyo, Japan"
    print("✓ TravelPlanRequest model works")
    
    # Test TravelPlanResponse
    response = TravelPlanResponse(
        task_id="test123",
        status=TaskStatusConstants.QUEUED,
        status_url="http://example.com/status",
        result_url="http://example.com/result"
    )
    assert response.task_id == "test123"
    print("✓ TravelPlanResponse model works")
    
    # Test TaskStatus
    status = TaskStatus(
        id="test123",
        task_id="test123",
        status=TaskStatusConstants.PROCESSING,
        progress_percentage=50,
        current_step="Generating itinerary",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    assert status.progress_percentage == 50
    print("✓ TaskStatus model works")
    
    # Test BudgetBreakdown
    budget = BudgetBreakdown(
        total_budget=3000,
        accommodation=1000,
        food=750,
        activities=600,
        transportation=300,
        shopping=200,
        emergency=150
    )
    assert budget.total_budget == 3000
    print("✓ BudgetBreakdown model works")
    
    print("\nAll model tests passed! ✓")


def test_constants():
    """Test that constants are defined"""
    print("\nTesting constants...")
    
    assert TaskStatusConstants.QUEUED == "queued"
    assert TaskStatusConstants.PROCESSING == "processing"
    assert TaskStatusConstants.COMPLETED == "completed"
    assert TaskStatusConstants.FAILED == "failed"
    
    print("✓ All constants defined correctly")


def test_api_import():
    """Test that the FastAPI app can be imported"""
    print("\nTesting FastAPI app import...")
    
    from travel_planner.api.main import app
    assert app is not None
    assert app.title == "Travel Planner API"
    
    print("✓ FastAPI app imports successfully")


if __name__ == "__main__":
    print("=" * 60)
    print("Running basic verification tests for Python conversion")
    print("=" * 60)
    
    try:
        test_models()
        test_constants()
        test_api_import()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
