#!/usr/bin/env python3
"""Main entry point for the Travel Planner application"""
import asyncio
import os
import sys
import logging
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Main entry point"""
    import uvicorn
    from travel_planner.api.main import app
    from travel_planner.services.worker import TravelPlanWorker
    from travel_planner.services.config import get_settings
    
    settings = get_settings()
    
    # Start the background worker in a separate task
    worker = TravelPlanWorker(settings)
    worker_task = asyncio.create_task(worker.start())
    
    # Configure uvicorn
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level="info"
    )
    
    server = uvicorn.Server(config)
    
    try:
        # Run the server
        await server.serve()
    finally:
        # Stop the worker on shutdown
        await worker.stop()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
