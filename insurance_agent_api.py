"""
Insurance AI Agent - Production API
FastAPI-based REST API for insurance automation with integrated tools

Features:
- Quote generation
- Underwriting assessment
- Document filling
- API key authentication
- Data encryption
- Comprehensive logging
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Security, status
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn

from langchain.agents import AgentType, initialize_agent
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI

# Import custom tools
from quoting_tool import QuotingTool
from underwriting_tool import UnderwritingTool
from document_filling_tool import DocumentFillingTool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('insurance_agent_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Insurance AI Agent API",
    description="Automated insurance processing with AI-powered tools",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key authentication
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Load API keys from environment
VALID_API_KEYS = set(os.getenv("API_KEYS", "test-key-12345,demo-key-67890").split(","))


# ==================== Security ====================

async def get_api_key(api_key: str = Security(api_key_header)):
    """Validate API key"""
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key required"
        )
    
    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )
    
    return api_key


# ==================== Request/Response Models ====================

class QuoteRequest(BaseModel):
    """Quote request model"""
    customer_data: Dict[str, Any] = Field(..., description="Customer data for quoting")
    
    class Config:
        json_schema_extra = {
            "example": {
                "customer_data": {
                    "age": 30,
                    "gender": "male",
                    "address": "123 Main St, New York, NY",
                    "location_type": "urban",
                    "insurance_type": "auto",
                    "vehicle_details": {
                        "make": "Tesla",
                        "model": "Model 3",
                        "year": 2022,
                        "value": 45000
                    }
                }
            }
        }


class UnderwritingRequest(BaseModel):
    """Underwriting request model"""
    applicant_data: Dict[str, Any] = Field(..., description="Applicant data for underwriting")
    
    class Config:
        json_schema_extra = {
            "example": {
                "applicant_data": {
                    "applicant_id": "APP-001",
                    "name": "John Smith",
                    "age": 35,
                    "credit_score": 750,
                    "annual_income": 75000,
                    "employment_status": "employed",
                    "insurance_type": "auto",
                    "coverage_amount": 100000,
                    "claims_history": {
                        "total_claims": 1,
                        "claims_last_3_years": 0,
                        "total_claimed_amount": 5000,
                        "fraud_indicators": False
                    },
                    "driving_record": {
                        "years_licensed": 15,
                        "accidents_last_5_years": 0,
                        "violations_last_3_years": 1,
                        "dui_history": False,
                        "license_suspended": False
                    }
                }
            }
        }


class DocumentRequest(BaseModel):
    """Document filling request model"""
    customer_data: Dict[str, Any] = Field(..., description="Customer data")
    document_type: str = Field(..., description="Document type")
    policy_data: Optional[Dict[str, Any]] = Field(None, description="Policy data")
    request_signature: bool = Field(default=False, description="Request e-signature")
    
    class Config:
        json_schema_extra = {
            "example": {
                "customer_data": {
                    "full_name": "John Smith",
                    "date_of_birth": "1985-06-15",
                    "email": "john@email.com",
                    "phone": "+1-555-123-4567",
                    "street_address": "123 Main St",
                    "city": "New York",
                    "state": "NY",
                    "zip_code": "10001"
                },
                "document_type": "policy_application",
                "policy_data": {
                    "insurance_type": "Life Insurance",
                    "policy_term": 20,
                    "premium_amount": 150.00,
                    "payment_frequency": "monthly",
                    "effective_date": "2025-11-01"
                },
                "request_signature": False
            }
        }


class AgentRequest(BaseModel):
    """General agent request model"""
    query: str = Field(..., description="Natural language query")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Generate a quote for auto insurance for a 30-year-old with a Tesla Model 3",
                "context": {}
            }
        }


class APIResponse(BaseModel):
    """Standard API response model"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str
    request_id: str


# ==================== Agent Initialization ====================

class InsuranceAgentManager:
    """Manage Insurance AI Agent instances"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not set. Agent will not be available.")
            self.agent = None
            self._initialized = True
            return
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.2,
            openai_api_key=self.openai_api_key
        )
        
        # Initialize tools
        self.tools = [
            QuotingTool(),
            UnderwritingTool(),
            DocumentFillingTool()
        ]
        
        # Initialize memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="output"
        )
        
        # Initialize agent
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5
        )
        
        self._initialized = True
        logger.info("Insurance Agent initialized successfully")
    
    def run_agent(self, query: str) -> Dict[str, Any]:
        """Run agent with query"""
        if not self.agent:
            raise HTTPException(
                status_code=503,
                detail="Agent not available. OPENAI_API_KEY not configured."
            )
        
        try:
            response = self.agent.invoke({"input": query})
            return {
                "success": True,
                "output": response.get("output", ""),
                "intermediate_steps": response.get("intermediate_steps", [])
            }
        except Exception as e:
            logger.error(f"Agent execution error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def clear_memory(self):
        """Clear agent memory"""
        if self.memory:
            self.memory.clear()


# Initialize agent manager
agent_manager = InsuranceAgentManager()


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Insurance AI Agent API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "quote": "/api/v1/quote",
            "underwriting": "/api/v1/underwriting",
            "document": "/api/v1/document",
            "agent": "/api/v1/agent"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "agent_available": agent_manager.agent is not None,
        "tools": {
            "quoting": "available",
            "underwriting": "available",
            "document_filling": "available"
        }
    }


@app.post("/api/v1/quote", response_model=APIResponse)
async def generate_quote(
    request: QuoteRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Generate insurance quote
    
    Requires valid API key in X-API-Key header
    """
    request_id = f"QT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    try:
        logger.info(f"Quote request: {request_id}")
        
        tool = QuotingTool()
        result = tool._run(json.dumps(request.customer_data))
        
        return APIResponse(
            success=True,
            message="Quote generated successfully",
            data={"result": result},
            timestamp=datetime.now().isoformat(),
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"Quote generation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Quote generation failed: {str(e)}"
        )


@app.post("/api/v1/underwriting", response_model=APIResponse)
async def perform_underwriting(
    request: UnderwritingRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Perform underwriting assessment
    
    Requires valid API key in X-API-Key header
    """
    request_id = f"UW-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    try:
        logger.info(f"Underwriting request: {request_id}")
        
        tool = UnderwritingTool()
        result = tool._run(json.dumps(request.applicant_data))
        
        return APIResponse(
            success=True,
            message="Underwriting completed successfully",
            data={"result": result},
            timestamp=datetime.now().isoformat(),
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"Underwriting error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Underwriting failed: {str(e)}"
        )


@app.post("/api/v1/document", response_model=APIResponse)
async def fill_document(
    request: DocumentRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Fill insurance document
    
    Requires valid API key in X-API-Key header
    """
    request_id = f"DOC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    try:
        logger.info(f"Document request: {request_id}")
        
        tool = DocumentFillingTool()
        result = tool._run(
            json.dumps(request.customer_data),
            request.document_type,
            json.dumps(request.policy_data) if request.policy_data else None,
            request.request_signature
        )
        
        return APIResponse(
            success=True,
            message="Document generated successfully",
            data={"result": result},
            timestamp=datetime.now().isoformat(),
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"Document generation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Document generation failed: {str(e)}"
        )


@app.post("/api/v1/agent", response_model=APIResponse)
async def run_agent(
    request: AgentRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Run AI agent with natural language query
    
    Requires valid API key in X-API-Key header
    """
    request_id = f"AG-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    try:
        logger.info(f"Agent request: {request_id}")
        
        result = agent_manager.run_agent(request.query)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Unknown error")
            )
        
        return APIResponse(
            success=True,
            message="Agent completed successfully",
            data=result,
            timestamp=datetime.now().isoformat(),
            request_id=request_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed: {str(e)}"
        )


@app.post("/api/v1/agent/clear-memory")
async def clear_agent_memory(api_key: str = Depends(get_api_key)):
    """Clear agent conversation memory"""
    try:
        agent_manager.clear_memory()
        return {
            "success": True,
            "message": "Memory cleared successfully",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear memory: {str(e)}"
        )


@app.get("/api/v1/documents/{document_id}")
async def download_document(
    document_id: str,
    api_key: str = Depends(get_api_key)
):
    """Download generated document"""
    try:
        # Search for document in generated_documents directory
        from pathlib import Path
        doc_dir = Path("generated_documents")
        
        # Find document with matching ID
        for doc_path in doc_dir.glob(f"*{document_id}*"):
            return FileResponse(
                path=str(doc_path),
                filename=doc_path.name,
                media_type="application/pdf"
            )
        
        raise HTTPException(
            status_code=404,
            detail=f"Document {document_id} not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document download error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Document download failed"
        )


# ==================== Error Handlers ====================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )


# ==================== Startup/Shutdown ====================

@app.on_event("startup")
async def startup_event():
    """Startup event"""
    logger.info("Starting Insurance AI Agent API...")
    logger.info(f"API Keys configured: {len(VALID_API_KEYS)}")
    logger.info(f"Agent available: {agent_manager.agent is not None}")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event"""
    logger.info("Shutting down Insurance AI Agent API...")


# ==================== Main ====================

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"
    
    logger.info(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        "insurance_agent_api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

