"""
Insurance Quoting Tool - Advanced Implementation
A LangChain custom tool for automated insurance quoting with external API integration

Features:
- Comprehensive rate table calculations for auto and health insurance
- Pydantic models for data validation
- External API integration (simulated Guidewire)
- Async support
- Detailed error handling
"""

import sys
import json
import logging
import asyncio

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
from typing import Optional, Type, Dict, Any, Literal
from datetime import datetime, timedelta
from enum import Enum

import requests
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, field_validator, model_validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== Enums for Type Safety ====================

class InsuranceType(str, Enum):
    """Supported insurance types"""
    AUTO = "auto"
    HEALTH = "health"


class Gender(str, Enum):
    """Gender options"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class LocationType(str, Enum):
    """Location risk categories"""
    URBAN = "urban"
    SUBURBAN = "suburban"
    RURAL = "rural"


# ==================== Pydantic Models ====================

class VehicleDetails(BaseModel):
    """Vehicle information for auto insurance"""
    make: str = Field(..., description="Vehicle manufacturer (e.g., Tesla, BMW)")
    model: str = Field(..., description="Vehicle model (e.g., Model 3, X5)")
    year: int = Field(..., ge=1990, le=2026, description="Vehicle year")
    value: float = Field(..., ge=0, description="Vehicle value in USD")
    usage: Literal["personal", "commercial"] = Field(
        default="personal",
        description="Vehicle usage type"
    )
    
    @field_validator('make', 'model')
    @classmethod
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Make and model cannot be empty")
        return v.strip()


class HealthDetails(BaseModel):
    """Health information for health insurance"""
    smoker: bool = Field(default=False, description="Whether the customer is a smoker")
    pre_existing_conditions: bool = Field(
        default=False,
        description="Whether there are pre-existing conditions"
    )
    bmi: Optional[float] = Field(None, ge=10, le=60, description="Body Mass Index")
    exercise_frequency: Literal["none", "occasional", "regular", "frequent"] = Field(
        default="occasional",
        description="Exercise frequency"
    )


class CustomerData(BaseModel):
    """Complete customer data for insurance quoting"""
    age: int = Field(..., ge=18, le=100, description="Customer age (18-100)")
    gender: Gender = Field(..., description="Customer gender")
    address: str = Field(..., min_length=5, description="Customer address")
    location_type: LocationType = Field(..., description="Location type (urban/suburban/rural)")
    insurance_type: InsuranceType = Field(..., description="Type of insurance (auto/health)")
    
    # Optional fields depending on insurance type
    vehicle_details: Optional[VehicleDetails] = Field(
        None,
        description="Vehicle details (required for auto insurance)"
    )
    health_details: Optional[HealthDetails] = Field(
        None,
        description="Health details (required for health insurance)"
    )
    
    @model_validator(mode='after')
    def validate_insurance_specific_data(self):
        """Ensure required fields are provided based on insurance type"""
        if self.insurance_type == InsuranceType.AUTO and not self.vehicle_details:
            raise ValueError(
                "Vehicle details are required for auto insurance. "
                "Please provide: make, model, year, value"
            )
        
        if self.insurance_type == InsuranceType.HEALTH and not self.health_details:
            raise ValueError(
                "Health details are required for health insurance. "
                "Please provide: smoker status, pre-existing conditions"
            )
        
        return self
    
    @field_validator('address')
    @classmethod
    def validate_address(cls, v):
        if not v or not v.strip():
            raise ValueError("Address cannot be empty")
        return v.strip()


class QuoteResult(BaseModel):
    """Insurance quote result"""
    quote_id: str = Field(..., description="Unique quote identifier")
    customer_age: int = Field(..., description="Customer age")
    insurance_type: str = Field(..., description="Insurance type")
    base_premium: float = Field(..., description="Base premium amount")
    age_factor: float = Field(..., description="Age multiplier")
    location_factor: float = Field(..., description="Location multiplier")
    additional_factors: Dict[str, float] = Field(
        default_factory=dict,
        description="Additional risk factors"
    )
    total_premium: float = Field(..., description="Total monthly premium")
    annual_premium: float = Field(..., description="Total annual premium")
    coverage_details: Dict[str, Any] = Field(..., description="Coverage information")
    deductible: float = Field(..., description="Policy deductible")
    effective_date: str = Field(..., description="Policy effective date")
    expiry_date: str = Field(..., description="Policy expiry date")
    quote_valid_until: str = Field(..., description="Quote validity date")
    timestamp: str = Field(..., description="Quote generation timestamp")


class QuotingToolInput(BaseModel):
    """Input schema for the quoting tool"""
    customer_data_json: str = Field(
        ...,
        description=(
            "JSON string containing customer data with fields: age, gender, address, "
            "location_type (urban/suburban/rural), insurance_type (auto/health), "
            "and either vehicle_details or health_details depending on insurance type"
        )
    )


# ==================== Rate Tables ====================

class RateTables:
    """Pre-defined rate tables for insurance premium calculations"""
    
    # Base rates (monthly premium in USD)
    BASE_RATES = {
        InsuranceType.AUTO: 1000.0,
        InsuranceType.HEALTH: 500.0
    }
    
    # Age factors
    AGE_FACTORS = {
        "young": 1.20,      # < 25 years
        "standard": 1.0,     # 25-65 years
        "senior": 1.15       # > 65 years
    }
    
    # Location factors
    LOCATION_FACTORS = {
        LocationType.URBAN: 1.10,      # Cities - higher risk
        LocationType.SUBURBAN: 1.0,    # Standard
        LocationType.RURAL: 0.90       # Lower risk
    }
    
    # Vehicle value factors (for auto insurance)
    VEHICLE_VALUE_TIERS = [
        (20000, 1.0),
        (40000, 1.15),
        (60000, 1.30),
        (100000, 1.50),
        (float('inf'), 1.80)
    ]
    
    # Health factors (for health insurance)
    HEALTH_FACTORS = {
        "smoker": 1.30,
        "pre_existing": 1.25,
        "bmi_high": 1.15,  # BMI > 30
        "bmi_low": 1.10,   # BMI < 18.5
        "exercise_none": 1.10,
        "exercise_frequent": 0.95
    }
    
    # Coverage details by insurance type
    COVERAGE_DETAILS = {
        InsuranceType.AUTO: {
            "liability": 100000,
            "collision": 50000,
            "comprehensive": 50000,
            "medical_payments": 10000,
            "uninsured_motorist": 50000
        },
        InsuranceType.HEALTH: {
            "annual_max": 1000000,
            "preventive_care": "100% covered",
            "emergency_room": "80% after deductible",
            "prescription_drugs": "Covered with copay",
            "hospital_stay": "80% after deductible"
        }
    }
    
    # Deductibles by insurance type
    DEDUCTIBLES = {
        InsuranceType.AUTO: 1000,
        InsuranceType.HEALTH: 2500
    }


# ==================== External API Integration ====================

class InsuranceAPIClient:
    """Client for external insurance API (simulated Guidewire integration)"""
    
    # Simulated API endpoint
    API_ENDPOINT = "https://api.insurance-provider.example.com/v1/quotes"
    API_TIMEOUT = 10  # seconds
    
    @classmethod
    def submit_quote(cls, quote_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit quote to external API (simulated)
        
        Args:
            quote_data: Quote information to submit
            
        Returns:
            API response with confirmation
        """
        try:
            # In production, this would be an actual API call:
            # response = requests.post(
            #     cls.API_ENDPOINT,
            #     json=quote_data,
            #     timeout=cls.API_TIMEOUT,
            #     headers={"Authorization": "Bearer YOUR_API_KEY"}
            # )
            # response.raise_for_status()
            # return response.json()
            
            # Simulated API response
            logger.info(f"Simulating API call to {cls.API_ENDPOINT}")
            
            # Simulate network delay
            import time
            time.sleep(0.5)
            
            api_response = {
                "status": "success",
                "api_quote_id": f"API-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "confirmation_number": f"CONF-{hash(str(quote_data)) % 1000000:06d}",
                "message": "Quote submitted successfully to underwriting system",
                "next_steps": [
                    "Quote has been recorded in the system",
                    "Underwriting review will be completed within 24 hours",
                    "Customer will receive confirmation email"
                ],
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"API response received: {api_response['api_quote_id']}")
            return api_response
            
        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return {
                "status": "error",
                "error": f"Failed to connect to insurance API: {str(e)}",
                "fallback": "Quote generated locally, manual submission required"
            }
        except Exception as e:
            logger.error(f"Unexpected error in API call: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    @classmethod
    async def submit_quote_async(cls, quote_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Async version of submit_quote
        
        Args:
            quote_data: Quote information to submit
            
        Returns:
            API response with confirmation
        """
        try:
            # In production with async requests:
            # async with aiohttp.ClientSession() as session:
            #     async with session.post(
            #         cls.API_ENDPOINT,
            #         json=quote_data,
            #         timeout=cls.API_TIMEOUT
            #     ) as response:
            #         return await response.json()
            
            # Simulate async operation
            logger.info(f"Simulating async API call to {cls.API_ENDPOINT}")
            await asyncio.sleep(0.5)  # Simulate network delay
            
            api_response = {
                "status": "success",
                "api_quote_id": f"API-ASYNC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "confirmation_number": f"CONF-{hash(str(quote_data)) % 1000000:06d}",
                "message": "Quote submitted successfully (async) to underwriting system",
                "next_steps": [
                    "Quote has been recorded in the system",
                    "Underwriting review will be completed within 24 hours",
                    "Customer will receive confirmation email"
                ],
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Async API response received: {api_response['api_quote_id']}")
            return api_response
            
        except Exception as e:
            logger.error(f"Async API call failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "fallback": "Quote generated locally, manual submission required"
            }


# ==================== Premium Calculator ====================

class PremiumCalculator:
    """Calculate insurance premiums based on customer data and rate tables"""
    
    @staticmethod
    def calculate_auto_insurance(customer: CustomerData) -> Dict[str, Any]:
        """
        Calculate auto insurance premium
        
        Formula: base_rate * age_factor * location_factor * vehicle_factor
        """
        base_premium = RateTables.BASE_RATES[InsuranceType.AUTO]
        
        # Age factor
        if customer.age < 25:
            age_factor = RateTables.AGE_FACTORS["young"]
        elif customer.age > 65:
            age_factor = RateTables.AGE_FACTORS["senior"]
        else:
            age_factor = RateTables.AGE_FACTORS["standard"]
        
        # Location factor
        location_factor = RateTables.LOCATION_FACTORS[customer.location_type]
        
        # Vehicle value factor
        vehicle_value = customer.vehicle_details.value
        vehicle_factor = 1.0
        for threshold, factor in RateTables.VEHICLE_VALUE_TIERS:
            if vehicle_value <= threshold:
                vehicle_factor = factor
                break
        
        # Additional factors
        additional_factors = {}
        
        # Commercial use adds 20%
        if customer.vehicle_details.usage == "commercial":
            additional_factors["commercial_use"] = 1.20
        
        # Newer vehicles (< 5 years) get small discount
        current_year = datetime.now().year
        vehicle_age = current_year - customer.vehicle_details.year
        if vehicle_age <= 5:
            additional_factors["new_vehicle_discount"] = 0.95
        elif vehicle_age > 15:
            additional_factors["old_vehicle_surcharge"] = 1.10
        
        # Gender factor (in some regions, for demonstration)
        if customer.gender == Gender.MALE and customer.age < 25:
            additional_factors["young_male_surcharge"] = 1.10
        
        # Calculate total premium
        premium = base_premium * age_factor * location_factor * vehicle_factor
        
        for factor_value in additional_factors.values():
            premium *= factor_value
        
        return {
            "base_premium": base_premium,
            "age_factor": age_factor,
            "location_factor": location_factor,
            "vehicle_factor": vehicle_factor,
            "additional_factors": additional_factors,
            "total_monthly_premium": round(premium, 2),
            "total_annual_premium": round(premium * 12, 2)
        }
    
    @staticmethod
    def calculate_health_insurance(customer: CustomerData) -> Dict[str, Any]:
        """
        Calculate health insurance premium
        
        Considers: age, smoking status, pre-existing conditions, BMI, exercise
        """
        base_premium = RateTables.BASE_RATES[InsuranceType.HEALTH]
        
        # Age factor
        if customer.age < 25:
            age_factor = 0.85  # Younger people pay less for health insurance
        elif customer.age > 65:
            age_factor = 1.50  # Seniors pay more
        else:
            age_factor = 1.0
        
        # Location factor (healthcare costs vary by region)
        location_factor = RateTables.LOCATION_FACTORS[customer.location_type]
        
        # Health-specific factors
        health_factors = {}
        health = customer.health_details
        
        if health.smoker:
            health_factors["smoker"] = RateTables.HEALTH_FACTORS["smoker"]
        
        if health.pre_existing_conditions:
            health_factors["pre_existing_conditions"] = RateTables.HEALTH_FACTORS["pre_existing"]
        
        if health.bmi:
            if health.bmi > 30:
                health_factors["high_bmi"] = RateTables.HEALTH_FACTORS["bmi_high"]
            elif health.bmi < 18.5:
                health_factors["low_bmi"] = RateTables.HEALTH_FACTORS["bmi_low"]
        
        if health.exercise_frequency == "none":
            health_factors["no_exercise"] = RateTables.HEALTH_FACTORS["exercise_none"]
        elif health.exercise_frequency == "frequent":
            health_factors["frequent_exercise"] = RateTables.HEALTH_FACTORS["exercise_frequent"]
        
        # Calculate total premium
        premium = base_premium * age_factor * location_factor
        
        for factor_value in health_factors.values():
            premium *= factor_value
        
        return {
            "base_premium": base_premium,
            "age_factor": age_factor,
            "location_factor": location_factor,
            "health_factors": health_factors,
            "additional_factors": {},
            "total_monthly_premium": round(premium, 2),
            "total_annual_premium": round(premium * 12, 2)
        }


# ==================== Main Quoting Tool ====================

class QuotingTool(BaseTool):
    """
    Advanced Insurance Quoting Tool
    
    Calculates insurance premiums using comprehensive rate tables,
    validates customer data, and integrates with external APIs.
    """
    
    name: str = "advanced_insurance_quoting"
    description: str = """
    Use this tool to generate detailed insurance quotes for auto or health insurance.
    
    Input must be a JSON string containing:
    - age: customer age (18-100)
    - gender: male/female/other
    - address: customer address
    - location_type: urban/suburban/rural
    - insurance_type: auto/health
    
    For AUTO insurance, also include vehicle_details:
    - make: vehicle manufacturer
    - model: vehicle model
    - year: vehicle year (1990-2026)
    - value: vehicle value in USD
    - usage: personal/commercial (optional)
    
    For HEALTH insurance, also include health_details:
    - smoker: true/false
    - pre_existing_conditions: true/false
    - bmi: body mass index (optional)
    - exercise_frequency: none/occasional/regular/frequent (optional)
    
    Returns a comprehensive quote with premium breakdown, coverage details, and API confirmation.
    """
    args_schema: Type[BaseModel] = QuotingToolInput
    
    def _run(self, customer_data_json: str) -> str:
        """
        Calculate insurance quote
        
        Args:
            customer_data_json: JSON string with customer data
            
        Returns:
            Formatted quote string with all details
        """
        try:
            # Parse and validate customer data
            logger.info("Parsing customer data...")
            customer_data_dict = json.loads(customer_data_json)
            
            try:
                customer = CustomerData(**customer_data_dict)
            except Exception as validation_error:
                error_msg = self._format_validation_error(validation_error)
                logger.warning(f"Validation error: {error_msg}")
                return error_msg
            
            # Calculate premium based on insurance type
            logger.info(f"Calculating {customer.insurance_type.value} insurance premium...")
            
            if customer.insurance_type == InsuranceType.AUTO:
                calculation = PremiumCalculator.calculate_auto_insurance(customer)
            else:
                calculation = PremiumCalculator.calculate_health_insurance(customer)
            
            # Generate quote ID and dates
            quote_id = f"QT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{customer.insurance_type.value.upper()}"
            now = datetime.now()
            effective_date = now + timedelta(days=1)
            expiry_date = effective_date + timedelta(days=365)
            valid_until = now + timedelta(days=30)
            
            # Prepare coverage details
            coverage = RateTables.COVERAGE_DETAILS[customer.insurance_type]
            deductible = RateTables.DEDUCTIBLES[customer.insurance_type]
            
            # Create quote result
            quote = QuoteResult(
                quote_id=quote_id,
                customer_age=customer.age,
                insurance_type=customer.insurance_type.value,
                base_premium=calculation["base_premium"],
                age_factor=calculation["age_factor"],
                location_factor=calculation["location_factor"],
                additional_factors=calculation.get("additional_factors", {}),
                total_premium=calculation["total_monthly_premium"],
                annual_premium=calculation["total_annual_premium"],
                coverage_details=coverage,
                deductible=deductible,
                effective_date=effective_date.strftime("%Y-%m-%d"),
                expiry_date=expiry_date.strftime("%Y-%m-%d"),
                quote_valid_until=valid_until.strftime("%Y-%m-%d"),
                timestamp=now.isoformat()
            )
            
            # Submit to external API
            logger.info("Submitting quote to external API...")
            api_response = InsuranceAPIClient.submit_quote(quote.model_dump())
            
            # Format response
            response = self._format_quote_response(customer, quote, calculation, api_response)
            
            logger.info(f"Quote generated successfully: {quote_id}")
            return response
            
        except json.JSONDecodeError as e:
            error_msg = f"""
ERROR: Invalid JSON format
------------------------
The input must be a valid JSON string.

Error details: {str(e)}

Example format:
{{
    "age": 30,
    "gender": "male",
    "address": "123 Main St, New York, NY",
    "location_type": "urban",
    "insurance_type": "auto",
    "vehicle_details": {{
        "make": "Tesla",
        "model": "Model 3",
        "year": 2022,
        "value": 45000
    }}
}}
            """
            logger.error(f"JSON decode error: {str(e)}")
            return error_msg.strip()
            
        except Exception as e:
            logger.error(f"Error in quoting tool: {str(e)}", exc_info=True)
            return f"ERROR: Failed to generate quote - {str(e)}"
    
    async def _arun(self, customer_data_json: str) -> str:
        """
        Async version of quote calculation
        
        Args:
            customer_data_json: JSON string with customer data
            
        Returns:
            Formatted quote string with all details
        """
        try:
            # Parse and validate customer data
            logger.info("Parsing customer data (async)...")
            customer_data_dict = json.loads(customer_data_json)
            
            try:
                customer = CustomerData(**customer_data_dict)
            except Exception as validation_error:
                error_msg = self._format_validation_error(validation_error)
                logger.warning(f"Validation error: {error_msg}")
                return error_msg
            
            # Calculate premium based on insurance type
            logger.info(f"Calculating {customer.insurance_type.value} insurance premium (async)...")
            
            if customer.insurance_type == InsuranceType.AUTO:
                calculation = PremiumCalculator.calculate_auto_insurance(customer)
            else:
                calculation = PremiumCalculator.calculate_health_insurance(customer)
            
            # Generate quote ID and dates
            quote_id = f"QT-ASYNC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{customer.insurance_type.value.upper()}"
            now = datetime.now()
            effective_date = now + timedelta(days=1)
            expiry_date = effective_date + timedelta(days=365)
            valid_until = now + timedelta(days=30)
            
            # Prepare coverage details
            coverage = RateTables.COVERAGE_DETAILS[customer.insurance_type]
            deductible = RateTables.DEDUCTIBLES[customer.insurance_type]
            
            # Create quote result
            quote = QuoteResult(
                quote_id=quote_id,
                customer_age=customer.age,
                insurance_type=customer.insurance_type.value,
                base_premium=calculation["base_premium"],
                age_factor=calculation["age_factor"],
                location_factor=calculation["location_factor"],
                additional_factors=calculation.get("additional_factors", {}),
                total_premium=calculation["total_monthly_premium"],
                annual_premium=calculation["total_annual_premium"],
                coverage_details=coverage,
                deductible=deductible,
                effective_date=effective_date.strftime("%Y-%m-%d"),
                expiry_date=expiry_date.strftime("%Y-%m-%d"),
                quote_valid_until=valid_until.strftime("%Y-%m-%d"),
                timestamp=now.isoformat()
            )
            
            # Submit to external API (async)
            logger.info("Submitting quote to external API (async)...")
            api_response = await InsuranceAPIClient.submit_quote_async(quote.model_dump())
            
            # Format response
            response = self._format_quote_response(customer, quote, calculation, api_response)
            
            logger.info(f"Quote generated successfully (async): {quote_id}")
            return response
            
        except json.JSONDecodeError as e:
            error_msg = f"ERROR: Invalid JSON format - {str(e)}"
            logger.error(error_msg)
            return error_msg
            
        except Exception as e:
            logger.error(f"Error in async quoting tool: {str(e)}", exc_info=True)
            return f"ERROR: Failed to generate quote (async) - {str(e)}"
    
    def _format_validation_error(self, error: Exception) -> str:
        """Format validation error messages for user"""
        error_str = str(error)
        
        return f"""
ERROR: Data Validation Failed
------------------------------
{error_str}

Required fields:
1. Basic Information:
   - age (18-100)
   - gender (male/female/other)
   - address (minimum 5 characters)
   - location_type (urban/suburban/rural)
   - insurance_type (auto/health)

2. For AUTO insurance, provide vehicle_details:
   - make (vehicle manufacturer)
   - model (vehicle model)
   - year (1990-2026)
   - value (vehicle value in USD)

3. For HEALTH insurance, provide health_details:
   - smoker (true/false)
   - pre_existing_conditions (true/false)

Please ensure all required fields are provided with valid values.
        """
    
    def _format_quote_response(
        self,
        customer: CustomerData,
        quote: QuoteResult,
        calculation: Dict[str, Any],
        api_response: Dict[str, Any]
    ) -> str:
        """Format comprehensive quote response"""
        
        # Format additional factors
        factors_text = ""
        all_factors = {**calculation.get("health_factors", {}), **quote.additional_factors}
        if all_factors:
            factors_text = "\n".join(
                f"   - {key.replace('_', ' ').title()}: {value:.2f}x"
                for key, value in all_factors.items()
            )
        else:
            factors_text = "   - None"
        
        # Format coverage details
        coverage_text = "\n".join(
            f"   - {key.replace('_', ' ').title()}: {value}"
            for key, value in quote.coverage_details.items()
        )
        
        # Insurance-specific details
        specific_details = ""
        if customer.insurance_type == InsuranceType.AUTO:
            vehicle = customer.vehicle_details
            specific_details = f"""
Vehicle Information:
   - Make/Model: {vehicle.make} {vehicle.model}
   - Year: {vehicle.year}
   - Value: ${vehicle.value:,.2f}
   - Usage: {vehicle.usage.title()}
            """
        else:
            health = customer.health_details
            specific_details = f"""
Health Information:
   - Smoker: {'Yes' if health.smoker else 'No'}
   - Pre-existing Conditions: {'Yes' if health.pre_existing_conditions else 'No'}
   - BMI: {health.bmi if health.bmi else 'Not provided'}
   - Exercise Frequency: {health.exercise_frequency.title()}
            """
        
        # API integration details
        api_status = "[OK]" if api_response.get("status") == "success" else "[ERROR]"
        api_details = ""
        if api_response.get("status") == "success":
            api_details = f"""
API Integration Status: {api_status} - SUCCESS
   - API Quote ID: {api_response.get('api_quote_id')}
   - Confirmation #: {api_response.get('confirmation_number')}
   - Message: {api_response.get('message')}
            """
        else:
            api_details = f"""
API Integration Status: {api_status} - FALLBACK MODE
   - Note: {api_response.get('fallback', 'Quote generated locally')}
            """
        
        response = f"""
========================================================================
              INSURANCE QUOTE - DETAILED REPORT
========================================================================

Quote ID: {quote.quote_id}
Generated: {quote.timestamp}
Valid Until: {quote.quote_valid_until}

─────────────────────────────────────────────────────────────────────

CUSTOMER INFORMATION:
   - Age: {customer.age} years
   - Gender: {customer.gender.value.title()}
   - Location: {customer.address}
   - Location Type: {customer.location_type.value.title()}
   - Insurance Type: {customer.insurance_type.value.upper()}
{specific_details}
─────────────────────────────────────────────────────────────────────

PREMIUM CALCULATION:
   Base Premium: ${quote.base_premium:.2f}/month
   
   Multiplier Factors:
   - Age Factor: {quote.age_factor:.2f}x
   - Location Factor: {quote.location_factor:.2f}x
   
   Additional Risk Factors:
{factors_text}

   ─────────────────────────────
   TOTAL MONTHLY PREMIUM: ${quote.total_premium:.2f}
   TOTAL ANNUAL PREMIUM:  ${quote.annual_premium:.2f}
   ─────────────────────────────

─────────────────────────────────────────────────────────────────────

COVERAGE DETAILS:
{coverage_text}

   Deductible: ${quote.deductible:,.2f}

─────────────────────────────────────────────────────────────────────

POLICY PERIOD:
   - Effective Date: {quote.effective_date}
   - Expiry Date: {quote.expiry_date}
   - Term: 12 months

─────────────────────────────────────────────────────────────────────
{api_details}
─────────────────────────────────────────────────────────────────────

IMPORTANT NOTES:
   - This quote is subject to underwriting approval
   - Final premium may vary based on complete application review
   - All information must be accurate; misrepresentation may void coverage
   - Quote is valid for 30 days from generation date
   - GDPR compliant - your data is encrypted and secured

Next Steps:
   1. Review the quote details carefully
   2. Prepare required documentation
   3. Complete the insurance application
   4. Submit for underwriting review

========================================================================
        """
        
        return response.strip()


# ==================== Standalone Usage Example ====================

def example_usage():
    """Demonstrate the QuotingTool usage"""
    print("=" * 80)
    print("Advanced Insurance Quoting Tool - Standalone Demo")
    print("=" * 80)
    
    tool = QuotingTool()
    
    # Example 1: Auto Insurance Quote
    print("\n\n" + "=" * 80)
    print("EXAMPLE 1: Auto Insurance Quote")
    print("=" * 80)
    
    auto_quote_data = {
        "age": 23,
        "gender": "male",
        "address": "789 Broadway, New York, NY 10003",
        "location_type": "urban",
        "insurance_type": "auto",
        "vehicle_details": {
            "make": "Tesla",
            "model": "Model 3",
            "year": 2023,
            "value": 48000,
            "usage": "personal"
        }
    }
    
    result = tool._run(json.dumps(auto_quote_data))
    print(result)
    
    # Example 2: Health Insurance Quote
    print("\n\n" + "=" * 80)
    print("EXAMPLE 2: Health Insurance Quote")
    print("=" * 80)
    
    health_quote_data = {
        "age": 35,
        "gender": "female",
        "address": "456 Elm Street, Los Angeles, CA 90001",
        "location_type": "suburban",
        "insurance_type": "health",
        "health_details": {
            "smoker": True,
            "pre_existing_conditions": False,
            "bmi": 24.5,
            "exercise_frequency": "regular"
        }
    }
    
    result = tool._run(json.dumps(health_quote_data))
    print(result)
    
    # Example 3: Error Handling - Incomplete Data
    print("\n\n" + "=" * 80)
    print("EXAMPLE 3: Error Handling - Incomplete Data")
    print("=" * 80)
    
    incomplete_data = {
        "age": 30,
        "gender": "male",
        "insurance_type": "auto"
        # Missing required fields
    }
    
    result = tool._run(json.dumps(incomplete_data))
    print(result)
    
    # Example 4: Async Usage
    print("\n\n" + "=" * 80)
    print("EXAMPLE 4: Async Quote Generation")
    print("=" * 80)
    
    async def async_example():
        result = await tool._arun(json.dumps(auto_quote_data))
        print(result)
    
    asyncio.run(async_example())
    
    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)


if __name__ == "__main__":
    example_usage()

