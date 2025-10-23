"""Travel agent service for generating AI-powered travel itineraries"""
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Callable

from azure.identity import DefaultAzureCredential
from azure.ai.inference.aio import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage

from ..shared.models import (
    TravelPlanRequest, TravelItinerary, DayPlan, Activity,
    BudgetBreakdown, EmergencyInfo
)
from .config import Settings

logger = logging.getLogger(__name__)


class TravelAgentService:
    """Service for generating AI-powered travel plans using Azure OpenAI"""
    
    def __init__(self, settings: Settings):
        """Initialize the travel agent service"""
        self.settings = settings
        
        if not settings.agent_azure_openai_endpoint:
            raise ValueError("Agent Azure OpenAI endpoint is required")
        
        # Initialize Azure AI client
        credential = DefaultAzureCredential()
        self.client = ChatCompletionsClient(
            endpoint=settings.agent_azure_openai_endpoint,
            credential=credential
        )
        
        self.model_deployment = settings.agent_model_deployment_name
    
    async def generate_travel_plan_async(
        self,
        request: TravelPlanRequest,
        task_id: str,
        progress_callback: Callable[[int, str], None]
    ) -> TravelItinerary:
        """Generate a travel plan using Azure OpenAI"""
        logger.info(f"Starting travel plan generation for task {task_id}")
        
        try:
            # Report progress
            progress_callback(5, "Creating AI travel planner agent...")
            
            # Build the travel request prompt
            progress_callback(15, "Analyzing travel requirements...")
            request_prompt = self._build_travel_request_prompt(request)
            
            # Call Azure OpenAI to generate the travel plan
            progress_callback(20, "Agent analyzing destination and planning itinerary...")
            
            messages = [
                SystemMessage(content=self._get_agent_instructions()),
                UserMessage(content=request_prompt)
            ]
            
            response = await self.client.complete(
                messages=messages,
                model=self.model_deployment,
                temperature=0.7,
                max_tokens=4000
            )
            
            logger.info(f"Agent completed run for task {task_id}")
            
            # Parse the agent's response
            progress_callback(95, "Formatting travel plan...")
            response_text = response.choices[0].message.content if response.choices else ""
            
            itinerary = self._parse_agent_response(response_text, request, task_id)
            
            progress_callback(100, "Travel plan complete!")
            
            logger.info(f"Completed travel plan generation for task {task_id}")
            
            return itinerary
            
        except Exception as ex:
            logger.error(f"Error generating travel plan for task {task_id}: {ex}")
            raise
    
    def _build_travel_request_prompt(self, request: TravelPlanRequest) -> str:
        """Build the prompt for the travel agent"""
        days = (request.end_date - request.start_date).days + 1
        
        special_requests = (
            f"- Special Requests: {request.special_requests}\n"
            if request.special_requests
            else ""
        )
        
        return f"""Create a comprehensive {days}-day travel itinerary for {request.destination}.

TRAVEL DETAILS:
- Destination: {request.destination}
- Start Date: {request.start_date.strftime('%B %d, %Y')}
- End Date: {request.end_date.strftime('%B %d, %Y')}
- Duration: {days} days
- Budget: ${request.budget:,.0f} USD
- Interests: {', '.join(request.interests)}
- Travel Style: {request.travel_style}
{special_requests}
Please provide a detailed itinerary with the following structure:

1. DAILY ITINERARY: For each day, provide:
   - Day theme
   - Morning activity (9:00 AM - 12:00 PM) with location, description, estimated cost
   - Lunch recommendation (12:00 PM - 1:30 PM) with location, description, estimated cost
   - Afternoon activity (2:00 PM - 6:00 PM) with location, description, estimated cost
   - Dinner recommendation (7:00 PM - 9:00 PM) with location, description, estimated cost
   - Optional evening activity if appropriate

2. BUDGET BREAKDOWN: Allocate the ${request.budget:,.0f} budget across:
   - Accommodation
   - Food & Dining
   - Activities & Attractions
   - Transportation
   - Shopping & Souvenirs
   - Emergency Fund

3. TRAVEL TIPS: 5-7 practical tips specific to {request.destination}

4. PACKING LIST: Essential items based on destination, season, and activities

5. EMERGENCY INFORMATION: Local emergency numbers, embassy contacts, healthcare info

Format your response clearly with headers and bullet points for easy parsing."""
    
    def _get_agent_instructions(self) -> str:
        """Get the system instructions for the agent"""
        return """You are an expert travel planner. Create detailed, personalized itineraries with:
- Day-by-day plans with activities, timing, and costs
- Accommodation and dining recommendations
- Local transportation and practical tips
- Cultural considerations and safety advice
Format with clear sections. Be realistic about timing and budgets. Prioritize the traveler's interests."""
    
    def _parse_agent_response(
        self, response_text: str, request: TravelPlanRequest, task_id: str
    ) -> TravelItinerary:
        """Parse the agent's response into a structured itinerary"""
        logger.info(f"Agent response length: {len(response_text)} characters")
        
        # Extract travel tips from the response
        travel_tips = self._extract_travel_tips(response_text)
        
        # Return the agent's actual response in a simple format
        days = (request.end_date - request.start_date).days + 1
        
        return TravelItinerary(
            task_id=task_id,
            destination=request.destination,
            start_date=request.start_date,
            end_date=request.end_date,
            daily_plans=[
                DayPlan(
                    day_number=1,
                    date=request.start_date,
                    theme=f"{days}-Day {request.destination} Itinerary",
                    morning=Activity(
                        time="",
                        title="",
                        location=request.destination,
                        description=response_text,
                        estimated_cost=0
                    ),
                    lunch=Activity(),
                    afternoon=Activity(),
                    dinner=Activity()
                )
            ],
            budget=self._allocate_budget(request.budget, days),
            travel_tips=travel_tips,
            packing_list=self._generate_packing_list(request),
            emergency_contacts=self._get_emergency_info(request.destination)
        )
    
    def _extract_travel_tips(self, response_text: str) -> List[str]:
        """Extract travel tips from the response"""
        tips = []
        
        # Try to find a TRAVEL TIPS section
        tips_match = re.search(
            r'(?:TRAVEL TIPS|Tips|TIPS):?\s*([\s\S]*?)(?:\n\n|###|PACKING|$)',
            response_text,
            re.IGNORECASE
        )
        
        if tips_match:
            tips_section = tips_match.group(1)
            lines = tips_section.split('\n')
            
            for line in lines:
                trimmed = line.strip().lstrip('-*•0123456789.)').strip()
                if trimmed and len(trimmed) > 10:
                    tips.append(trimmed)
        
        # If no tips found, provide generic ones
        if not tips:
            tips = [
                "Check the weather forecast before your trip",
                "Book popular attractions in advance",
                "Keep important documents and valuables secure",
                "Learn a few basic phrases in the local language",
                "Stay hydrated and take breaks between activities"
            ]
        
        return tips[:7]
    
    def _generate_packing_list(self, request: TravelPlanRequest) -> List[str]:
        """Generate a packing list based on the request"""
        packing_list = [
            "Passport and travel documents",
            "Comfortable walking shoes",
            "Weather-appropriate clothing",
            "Phone charger and power adapter",
            "Reusable water bottle",
            "Sunscreen and sunglasses",
            "Basic first aid kit",
            "Travel insurance documents"
        ]
        
        # Add interest-specific items
        for interest in request.interests:
            if 'hiking' in interest.lower():
                packing_list.append("Hiking boots and backpack")
            elif 'beach' in interest.lower():
                packing_list.append("Swimsuit and beach towel")
            elif 'photography' in interest.lower():
                packing_list.append("Camera equipment and extra memory cards")
        
        return packing_list
    
    def _allocate_budget(self, total_budget: float, days: int) -> BudgetBreakdown:
        """Allocate the budget across categories"""
        return BudgetBreakdown(
            total_budget=total_budget,
            accommodation=total_budget * 0.35,  # 35%
            food=total_budget * 0.25,           # 25%
            activities=total_budget * 0.20,     # 20%
            transportation=total_budget * 0.10, # 10%
            shopping=total_budget * 0.05,       # 5%
            emergency=total_budget * 0.05       # 5%
        )
    
    def _get_emergency_info(self, destination: str) -> EmergencyInfo:
        """Get emergency information for the destination"""
        return EmergencyInfo(
            local_emergency_number="112 (EU) or 911 (US)",
            nearest_embassy=f"Contact your embassy in {destination}",
            healthcare_info="Travel with comprehensive health insurance. Keep emergency numbers saved in your phone."
        )
    
    async def close(self):
        """Close the client"""
        await self.client.close()
