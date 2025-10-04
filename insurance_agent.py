"""
Insurance AI Agent using LangChain Framework
Automates insurance quoting, underwriting, and document filling processes.
"""

import os
import json
import logging
from typing import Optional, Type, Dict, Any
from datetime import datetime

from langchain.agents import AgentType, initialize_agent
from langchain.memory import ConversationBufferMemory
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, validator


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==================== Pydantic Models for Data Validation ====================

class CustomerInfo(BaseModel):
    """Customer information model with validation"""
    age: int = Field(..., ge=18, le=100, description="Customer age (18-100)")
    address: str = Field(..., min_length=5, description="Customer address")
    insurance_type: str = Field(..., description="Type of insurance (auto, home, life, health)")
    
    @validator('insurance_type')
    def validate_insurance_type(cls, v):
        valid_types = ['auto', 'home', 'life', 'health']
        if v.lower() not in valid_types:
            raise ValueError(f"Insurance type must be one of {valid_types}")
        return v.lower()


class VehicleInfo(BaseModel):
    """Vehicle information for auto insurance"""
    model: str = Field(..., description="Vehicle model")
    year: Optional[int] = Field(None, ge=1990, le=2025, description="Vehicle year")
    value: Optional[float] = Field(None, ge=0, description="Vehicle value in currency")


class QuoteInput(BaseModel):
    """Input schema for quoting tool"""
    query: str = Field(..., description="Insurance quote request with customer details")


class UnderwritingInput(BaseModel):
    """Input schema for underwriting tool"""
    query: str = Field(..., description="Underwriting assessment request")


class DocumentInput(BaseModel):
    """Input schema for document filling tool"""
    query: str = Field(..., description="Document filling request with necessary information")


# ==================== Custom Tools ====================

class QuotingTool(BaseTool):
    """Tool for calculating insurance quotes"""
    
    name: str = "insurance_quoting"
    description: str = """
    Use this tool to calculate insurance quotes. 
    Input should contain: age, insurance type (auto/home/life/health), 
    and specific details (e.g., vehicle model for auto insurance, property value for home insurance).
    Returns a detailed quote with premium calculations.
    """
    args_schema: Type[BaseModel] = QuoteInput
    
    def _run(self, query: str) -> str:
        """Calculate insurance quote based on input parameters"""
        try:
            logger.info(f"Quoting tool processing: {query}")
            
            # Parse query for key information
            query_lower = query.lower()
            
            # Extract insurance type
            insurance_type = None
            for itype in ['auto', 'car', 'vehicle', 'home', 'property', 'life', 'health']:
                if itype in query_lower:
                    if itype in ['auto', 'car', 'vehicle']:
                        insurance_type = 'auto'
                    elif itype in ['home', 'property']:
                        insurance_type = 'home'
                    else:
                        insurance_type = itype
                    break
            
            # Extract age
            age = None
            import re
            age_match = re.search(r'age[:\s]+(\d+)', query_lower)
            if age_match:
                age = int(age_match.group(1))
            
            # Calculate base premium based on insurance type and age
            base_premium = self._calculate_base_premium(insurance_type, age, query)
            
            # Create quote response
            quote = {
                "quote_id": f"Q-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "insurance_type": insurance_type or "auto",
                "customer_age": age,
                "base_premium": base_premium,
                "coverage_amount": self._get_coverage_amount(insurance_type),
                "deductible": self._get_deductible(insurance_type),
                "payment_frequency": "monthly",
                "quote_valid_until": "30 days from issue",
                "timestamp": datetime.now().isoformat()
            }
            
            # Format response
            response = f"""
Insurance Quote Generated:
--------------------------
Quote ID: {quote['quote_id']}
Insurance Type: {quote['insurance_type']}
Customer Age: {quote['customer_age']} years
Base Premium: ${quote['base_premium']:.2f}/month
Coverage Amount: ${quote['coverage_amount']:,}
Deductible: ${quote['deductible']:,}
Quote Valid: {quote['quote_valid_until']}

Note: This quote is subject to underwriting approval.
            """
            
            logger.info(f"Quote generated successfully: {quote['quote_id']}")
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error in quoting tool: {str(e)}")
            return f"Error generating quote: {str(e)}"
    
    def _calculate_base_premium(self, insurance_type: str, age: int, query: str) -> float:
        """Calculate base premium based on insurance type and customer profile"""
        base_rates = {
            'auto': 150.0,
            'home': 120.0,
            'life': 80.0,
            'health': 200.0
        }
        
        base = base_rates.get(insurance_type, 150.0)
        
        # Age-based adjustments
        if age:
            if age < 25:
                base *= 1.3  # Higher risk for young drivers
            elif age > 65:
                base *= 1.2  # Higher risk for elderly
        
        # Check for luxury items (increases premium)
        if any(word in query.lower() for word in ['tesla', 'bmw', 'mercedes', 'luxury']):
            base *= 1.4
        
        return round(base, 2)
    
    def _get_coverage_amount(self, insurance_type: str) -> int:
        """Get standard coverage amount by insurance type"""
        coverage = {
            'auto': 100000,
            'home': 250000,
            'life': 500000,
            'health': 50000
        }
        return coverage.get(insurance_type, 100000)
    
    def _get_deductible(self, insurance_type: str) -> int:
        """Get standard deductible by insurance type"""
        deductible = {
            'auto': 1000,
            'home': 2500,
            'life': 0,
            'health': 1500
        }
        return deductible.get(insurance_type, 1000)
    
    async def _arun(self, query: str) -> str:
        """Async version of _run"""
        return self._run(query)


class UnderwritingTool(BaseTool):
    """Tool for underwriting assessment and risk evaluation"""
    
    name: str = "underwriting_assessment"
    description: str = """
    Use this tool to perform underwriting assessment and risk evaluation.
    Input should contain customer information and insurance details.
    Returns approval status, risk rating, and any conditions or requirements.
    """
    args_schema: Type[BaseModel] = UnderwritingInput
    
    def _run(self, query: str) -> str:
        """Perform underwriting assessment"""
        try:
            logger.info(f"Underwriting tool processing: {query}")
            
            query_lower = query.lower()
            
            # Extract age for risk assessment
            import re
            age_match = re.search(r'age[:\s]+(\d+)', query_lower)
            age = int(age_match.group(1)) if age_match else 35
            
            # Risk assessment factors
            risk_score = 50  # Base risk score
            risk_factors = []
            
            # Age-based risk
            if age < 25:
                risk_score += 20
                risk_factors.append("Young driver - higher accident risk")
            elif age > 70:
                risk_score += 15
                risk_factors.append("Senior driver - increased health considerations")
            else:
                risk_score -= 10
            
            # Location-based risk (simplified)
            high_risk_locations = ['beijing', 'shanghai', 'los angeles', 'new york']
            if any(loc in query_lower for loc in high_risk_locations):
                risk_score += 10
                risk_factors.append("High-density urban area")
            
            # Vehicle/property type risk
            if any(word in query_lower for word in ['tesla', 'luxury', 'sports']):
                risk_score += 15
                risk_factors.append("High-value asset - increased replacement cost")
            
            # Determine approval status
            if risk_score < 40:
                status = "APPROVED"
                risk_rating = "LOW"
            elif risk_score < 70:
                status = "APPROVED WITH CONDITIONS"
                risk_rating = "MEDIUM"
            else:
                status = "REQUIRES MANUAL REVIEW"
                risk_rating = "HIGH"
            
            # Generate underwriting response
            underwriting_result = {
                "assessment_id": f"UW-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "status": status,
                "risk_rating": risk_rating,
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "conditions": self._get_conditions(risk_rating),
                "timestamp": datetime.now().isoformat()
            }
            
            response = f"""
Underwriting Assessment Result:
-------------------------------
Assessment ID: {underwriting_result['assessment_id']}
Status: {underwriting_result['status']}
Risk Rating: {underwriting_result['risk_rating']} (Score: {underwriting_result['risk_score']})

Risk Factors:
{chr(10).join(f"- {factor}" for factor in underwriting_result['risk_factors'])}

Conditions:
{chr(10).join(f"- {condition}" for condition in underwriting_result['conditions'])}

This assessment is valid for 30 days from the timestamp.
            """
            
            logger.info(f"Underwriting completed: {underwriting_result['assessment_id']}")
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error in underwriting tool: {str(e)}")
            return f"Error in underwriting assessment: {str(e)}"
    
    def _get_conditions(self, risk_rating: str) -> list:
        """Get underwriting conditions based on risk rating"""
        conditions_map = {
            "LOW": [
                "Standard coverage applies",
                "No additional documentation required"
            ],
            "MEDIUM": [
                "Provide driving record for last 3 years",
                "May require higher deductible",
                "Annual policy review recommended"
            ],
            "HIGH": [
                "Comprehensive driving record required",
                "Additional documentation needed",
                "Higher premium or deductible may apply",
                "Manager approval required"
            ]
        }
        return conditions_map.get(risk_rating, conditions_map["MEDIUM"])
    
    async def _arun(self, query: str) -> str:
        """Async version of _run"""
        return self._run(query)


class DocumentFillingTool(BaseTool):
    """Tool for filling insurance documents and forms"""
    
    name: str = "document_filling"
    description: str = """
    Use this tool to fill out insurance documents and generate policy forms.
    Input should contain all necessary customer and policy information.
    Returns formatted document data ready for submission.
    """
    args_schema: Type[BaseModel] = DocumentInput
    
    def _run(self, query: str) -> str:
        """Fill out insurance documents"""
        try:
            logger.info(f"Document filling tool processing: {query}")
            
            query_lower = query.lower()
            
            # Extract information from query
            import re
            age_match = re.search(r'age[:\s]+(\d+)', query_lower)
            age = age_match.group(1) if age_match else "N/A"
            
            # Extract address
            address_keywords = ['address', 'location', 'beijing', 'shanghai', 'new york', 'los angeles']
            address = "Not specified"
            for keyword in address_keywords:
                if keyword in query_lower:
                    address = keyword.title()
                    break
            
            # Generate document
            document_id = f"DOC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            document_data = {
                "document_id": document_id,
                "document_type": "Insurance Application Form",
                "sections": {
                    "applicant_information": {
                        "age": age,
                        "address": address,
                        "application_date": datetime.now().strftime('%Y-%m-%d')
                    },
                    "policy_information": {
                        "policy_type": self._extract_insurance_type(query),
                        "effective_date": "Upon approval",
                        "term_length": "12 months"
                    },
                    "declarations": {
                        "accuracy_statement": "I certify that all information provided is accurate",
                        "consent_to_process": "I consent to processing of my personal data per GDPR/privacy laws",
                        "signature_required": True
                    },
                    "privacy_notice": {
                        "data_retention": "Data will be retained per regulatory requirements",
                        "data_usage": "Data used only for insurance purposes",
                        "data_protection": "GDPR compliant - data encrypted and secured"
                    }
                },
                "status": "DRAFT",
                "timestamp": datetime.now().isoformat()
            }
            
            response = f"""
Insurance Document Generated:
-----------------------------
Document ID: {document_data['document_id']}
Document Type: {document_data['document_type']}

SECTION 1: APPLICANT INFORMATION
- Age: {document_data['sections']['applicant_information']['age']}
- Address: {document_data['sections']['applicant_information']['address']}
- Application Date: {document_data['sections']['applicant_information']['application_date']}

SECTION 2: POLICY INFORMATION
- Policy Type: {document_data['sections']['policy_information']['policy_type']}
- Effective Date: {document_data['sections']['policy_information']['effective_date']}
- Term Length: {document_data['sections']['policy_information']['term_length']}

SECTION 3: DECLARATIONS & CONSENT
- {document_data['sections']['declarations']['accuracy_statement']}
- {document_data['sections']['declarations']['consent_to_process']}
- Signature Required: Yes

PRIVACY NOTICE (GDPR Compliance):
- {document_data['sections']['privacy_notice']['data_retention']}
- {document_data['sections']['privacy_notice']['data_usage']}
- {document_data['sections']['privacy_notice']['data_protection']}

Document Status: {document_data['status']}
Note: This document is in DRAFT status. Customer signature required for submission.
            """
            
            logger.info(f"Document generated successfully: {document_id}")
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error in document filling tool: {str(e)}")
            return f"Error generating document: {str(e)}"
    
    def _extract_insurance_type(self, query: str) -> str:
        """Extract insurance type from query"""
        query_lower = query.lower()
        if any(word in query_lower for word in ['auto', 'car', 'vehicle']):
            return "Auto Insurance"
        elif any(word in query_lower for word in ['home', 'property', 'house']):
            return "Home Insurance"
        elif 'life' in query_lower:
            return "Life Insurance"
        elif 'health' in query_lower:
            return "Health Insurance"
        return "General Insurance"
    
    async def _arun(self, query: str) -> str:
        """Async version of _run"""
        return self._run(query)


# ==================== Agent Setup ====================

class InsuranceAgent:
    """Main Insurance AI Agent class"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize the Insurance Agent
        
        Args:
            openai_api_key: OpenAI API key. If None, will use OPENAI_API_KEY env variable
        """
        # Set up API key
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Please provide it as parameter or set OPENAI_API_KEY environment variable."
            )
        
        # Initialize LLM (GPT-4)
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.2,  # Lower temperature for more consistent responses
            openai_api_key=self.api_key
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
        
        # Initialize agent with ReAct type
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
            early_stopping_method="generate"
        )
        
        logger.info("Insurance Agent initialized successfully")
    
    def run(self, query: str) -> Dict[str, Any]:
        """
        Run the agent with a user query
        
        Args:
            query: User's insurance-related query
            
        Returns:
            Dictionary containing the response and metadata
        """
        try:
            logger.info(f"Processing query: {query}")
            
            # Add compliance reminder to system
            enhanced_query = f"""
{query}

IMPORTANT: Ensure all responses comply with:
- GDPR and data privacy regulations
- Insurance industry standards
- Do not store or display sensitive personal information unnecessarily
            """
            
            # Run the agent
            response = self.agent.invoke({"input": enhanced_query})
            
            # Format output
            result = {
                "success": True,
                "query": query,
                "response": response.get("output", ""),
                "timestamp": datetime.now().isoformat(),
                "compliance_note": "All data handled per GDPR and privacy regulations"
            }
            
            logger.info("Query processed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def clear_memory(self):
        """Clear conversation memory"""
        self.memory.clear()
        logger.info("Memory cleared")
    
    def get_conversation_history(self) -> str:
        """Get conversation history"""
        return self.memory.load_memory_variables({}).get("chat_history", "")


# ==================== Main Function ====================

def main():
    """Main function to demonstrate the Insurance Agent"""
    
    print("=" * 70)
    print("Insurance AI Agent - LangChain Framework")
    print("=" * 70)
    print()
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  Warning: OPENAI_API_KEY not found in environment variables")
        print("Please set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key-here'  (Linux/Mac)")
        print("  set OPENAI_API_KEY=your-api-key-here  (Windows)")
        print()
        print("For demonstration, you can enter it here (not recommended for production):")
        api_key = input("Enter your OpenAI API key (or press Enter to continue with demo mode): ").strip()
        
        if not api_key:
            print("\n⚠️  Running in DEMO mode without actual LLM - showing tool capabilities only\n")
            # Demo mode - just show tools working
            demo_tools()
            return
    
    try:
        # Initialize agent
        print("Initializing Insurance Agent...")
        agent = InsuranceAgent(openai_api_key=api_key)
        print("✓ Agent initialized successfully\n")
        
        # Example queries
        example_queries = [
            "计算汽车保险报价：年龄25，车辆型号Tesla Model 3，地址北京",
            "Calculate auto insurance quote for a 25-year-old with Tesla Model 3 in Beijing",
            "Perform underwriting assessment for the quote above",
            "Generate insurance application document with the information provided"
        ]
        
        print("Running example queries...\n")
        
        for i, query in enumerate(example_queries, 1):
            print(f"\n{'=' * 70}")
            print(f"Example {i}: {query}")
            print('=' * 70)
            
            result = agent.run(query)
            
            if result["success"]:
                print("\n📊 Response:")
                print(result["response"])
                print(f"\n⏰ Timestamp: {result['timestamp']}")
                print(f"🔒 {result['compliance_note']}")
            else:
                print(f"\n❌ Error: {result['error']}")
            
            # Wait between queries in demo
            if i < len(example_queries):
                input("\nPress Enter to continue to next example...")
        
        # Interactive mode
        print("\n" + "=" * 70)
        print("Entering Interactive Mode")
        print("=" * 70)
        print("You can now ask questions about insurance. Type 'quit' to exit.")
        print()
        
        while True:
            user_input = input("\n💬 Your query: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nThank you for using Insurance AI Agent!")
                break
            
            if not user_input:
                continue
            
            if user_input.lower() == 'clear':
                agent.clear_memory()
                print("✓ Conversation memory cleared")
                continue
            
            result = agent.run(user_input)
            
            if result["success"]:
                print(f"\n🤖 Agent Response:\n{result['response']}")
            else:
                print(f"\n❌ Error: {result['error']}")
    
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        print(f"\n❌ Error: {str(e)}")
        print("\nPlease check your configuration and try again.")


def demo_tools():
    """Demonstrate tools without requiring LLM API key"""
    print("=" * 70)
    print("DEMO MODE - Tool Capabilities")
    print("=" * 70)
    
    # Demonstrate each tool
    quoting_tool = QuotingTool()
    underwriting_tool = UnderwritingTool()
    document_tool = DocumentFillingTool()
    
    test_query = "Calculate auto insurance quote: age 25, vehicle model Tesla Model 3, address Beijing"
    
    print("\n1. QUOTING TOOL")
    print("-" * 70)
    result = quoting_tool._run(test_query)
    print(result)
    
    print("\n\n2. UNDERWRITING TOOL")
    print("-" * 70)
    result = underwriting_tool._run(test_query)
    print(result)
    
    print("\n\n3. DOCUMENT FILLING TOOL")
    print("-" * 70)
    result = document_tool._run(test_query)
    print(result)
    
    print("\n" + "=" * 70)
    print("Demo complete! Set OPENAI_API_KEY to use full agent capabilities.")
    print("=" * 70)


if __name__ == "__main__":
    main()


