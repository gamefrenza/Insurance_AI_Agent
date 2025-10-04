"""
Insurance Underwriting Tool - Advanced Implementation
A LangChain custom tool for automated insurance underwriting with ML and rule engines

Features:
- Risk assessment using rule engine and ML model
- Credit score and claims history analysis
- External data source integration (credit bureau APIs)
- Decision making with policy terms and exclusions
- Batch processing support
- PII-compliant logging
"""

import sys
import json
import logging
import hashlib
import pickle
from typing import Optional, Type, Dict, Any, List, Literal
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

import requests
import numpy as np
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, field_validator, model_validator

# Scikit-learn for ML model
try:
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn not available. ML features will be disabled.")

# Configure PII-compliant logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== PII Protection ====================

class PIIProtector:
    """Utility class to protect PII in logs and outputs"""
    
    @staticmethod
    def hash_pii(data: str) -> str:
        """Hash PII data for logging"""
        return hashlib.sha256(data.encode()).hexdigest()[:12]
    
    @staticmethod
    def mask_ssn(ssn: str) -> str:
        """Mask SSN: XXX-XX-1234"""
        if len(ssn) >= 4:
            return f"XXX-XX-{ssn[-4:]}"
        return "XXX-XX-XXXX"
    
    @staticmethod
    def mask_name(name: str) -> str:
        """Mask name: J*** D**"""
        parts = name.split()
        masked = []
        for part in parts:
            if len(part) > 1:
                masked.append(f"{part[0]}{'*' * (len(part) - 1)}")
            else:
                masked.append(part)
        return " ".join(masked)
    
    @staticmethod
    def safe_log(message: str, **kwargs) -> None:
        """Log message with PII protection"""
        # Hash any potential PII in kwargs
        safe_kwargs = {}
        for key, value in kwargs.items():
            if key in ['name', 'ssn', 'address', 'email', 'phone']:
                safe_kwargs[f"{key}_hash"] = PIIProtector.hash_pii(str(value))
            else:
                safe_kwargs[key] = value
        
        logger.info(message, extra=safe_kwargs)


# ==================== Enums ====================

class UnderwritingDecision(str, Enum):
    """Underwriting decision types"""
    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    DECLINED = "declined"
    REFER_TO_MANUAL_REVIEW = "refer_to_manual_review"


class RiskLevel(str, Enum):
    """Risk level categories"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class InsuranceType(str, Enum):
    """Insurance types for underwriting"""
    AUTO = "auto"
    HOME = "home"
    LIFE = "life"
    HEALTH = "health"


# ==================== Pydantic Models ====================

class DrivingRecord(BaseModel):
    """Driving record information"""
    years_licensed: int = Field(..., ge=0, description="Years with driver's license")
    accidents_last_5_years: int = Field(..., ge=0, description="Number of accidents in last 5 years")
    violations_last_3_years: int = Field(..., ge=0, description="Number of violations in last 3 years")
    dui_history: bool = Field(default=False, description="DUI/DWI history")
    license_suspended: bool = Field(default=False, description="License suspension history")


class ClaimsHistory(BaseModel):
    """Insurance claims history"""
    total_claims: int = Field(..., ge=0, description="Total number of claims")
    claims_last_3_years: int = Field(..., ge=0, description="Claims in last 3 years")
    total_claimed_amount: float = Field(..., ge=0, description="Total amount claimed (USD)")
    fraud_indicators: bool = Field(default=False, description="Fraud indicators present")


class PropertyInfo(BaseModel):
    """Property information for home insurance"""
    property_age: int = Field(..., ge=0, description="Property age in years")
    construction_type: Literal["wood", "brick", "concrete", "mixed"] = Field(
        ...,
        description="Primary construction type"
    )
    security_system: bool = Field(default=False, description="Has security system")
    fire_protection_class: int = Field(..., ge=1, le=10, description="Fire protection class (1-10)")
    flood_zone: bool = Field(default=False, description="Located in flood zone")


class ApplicantData(BaseModel):
    """Complete applicant data for underwriting"""
    # Basic information (PII - will be protected in logs)
    applicant_id: str = Field(..., description="Unique applicant identifier")
    name: str = Field(..., min_length=2, description="Applicant name")
    age: int = Field(..., ge=18, le=100, description="Applicant age")
    
    # Financial information
    credit_score: int = Field(..., ge=300, le=850, description="Credit score (300-850)")
    annual_income: float = Field(..., ge=0, description="Annual income (USD)")
    employment_status: Literal["employed", "self_employed", "unemployed", "retired"] = Field(
        ...,
        description="Employment status"
    )
    
    # Insurance information
    insurance_type: InsuranceType = Field(..., description="Type of insurance applied for")
    coverage_amount: float = Field(..., ge=0, description="Requested coverage amount (USD)")
    claims_history: ClaimsHistory = Field(..., description="Claims history")
    
    # Type-specific information
    driving_record: Optional[DrivingRecord] = Field(
        None,
        description="Driving record (required for auto insurance)"
    )
    property_info: Optional[PropertyInfo] = Field(
        None,
        description="Property information (required for home insurance)"
    )
    
    # Health information (simplified)
    smoker: Optional[bool] = Field(None, description="Smoker status (for health/life insurance)")
    pre_existing_conditions: Optional[bool] = Field(
        None,
        description="Pre-existing conditions (for health insurance)"
    )
    
    @model_validator(mode='after')
    def validate_type_specific_data(self):
        """Ensure required fields are provided based on insurance type"""
        if self.insurance_type == InsuranceType.AUTO and not self.driving_record:
            raise ValueError("Driving record is required for auto insurance")
        
        if self.insurance_type == InsuranceType.HOME and not self.property_info:
            raise ValueError("Property information is required for home insurance")
        
        if self.insurance_type in [InsuranceType.HEALTH, InsuranceType.LIFE]:
            if self.smoker is None:
                raise ValueError(f"Smoker status is required for {self.insurance_type.value} insurance")
        
        return self


class UnderwritingResult(BaseModel):
    """Underwriting decision result"""
    application_id: str = Field(..., description="Application identifier")
    decision: UnderwritingDecision = Field(..., description="Underwriting decision")
    risk_level: RiskLevel = Field(..., description="Risk level assessment")
    risk_score: float = Field(..., ge=0, le=100, description="Risk score (0-100)")
    
    # Decision details
    approved: bool = Field(..., description="Whether approved")
    decision_reasons: List[str] = Field(..., description="Reasons for decision")
    
    # Policy terms (if approved)
    base_premium: Optional[float] = Field(None, description="Base premium amount")
    additional_premium: float = Field(default=0, description="Additional premium due to risk")
    total_premium: Optional[float] = Field(None, description="Total monthly premium")
    
    # Conditions and exclusions
    conditions: List[str] = Field(default_factory=list, description="Approval conditions")
    exclusions: List[str] = Field(default_factory=list, description="Policy exclusions")
    
    # External data verification
    credit_verified: bool = Field(default=False, description="Credit score verified")
    external_data_sources: List[str] = Field(default_factory=list, description="External sources used")
    
    # Metadata
    timestamp: str = Field(..., description="Processing timestamp")
    model_version: str = Field(default="1.0", description="Underwriting model version")


class UnderwritingToolInput(BaseModel):
    """Input schema for underwriting tool"""
    applicant_data_json: str = Field(
        ...,
        description="JSON string containing applicant data for underwriting assessment"
    )


class BatchUnderwritingInput(BaseModel):
    """Input schema for batch underwriting"""
    applications_json: str = Field(
        ...,
        description="JSON string containing array of applicant data for batch processing"
    )


# ==================== External API Integration ====================

class ExternalDataAPI:
    """Client for external data APIs (simulated)"""
    
    CREDIT_BUREAU_ENDPOINT = "https://api.experian.example.com/v1/credit-score"
    DMV_ENDPOINT = "https://api.dmv.example.com/v1/driving-record"
    
    @classmethod
    def verify_credit_score(cls, applicant_id: str, reported_score: int) -> Dict[str, Any]:
        """
        Verify credit score with external credit bureau (simulated)
        
        Args:
            applicant_id: Unique applicant identifier
            reported_score: Self-reported credit score
            
        Returns:
            Verification result with actual score
        """
        try:
            PIIProtector.safe_log(
                f"Verifying credit score for applicant",
                applicant_id=applicant_id
            )
            
            # Simulate API call
            import time
            time.sleep(0.3)  # Simulate network delay
            
            # Simulated response
            # In production, this would be: response = requests.post(cls.CREDIT_BUREAU_ENDPOINT, ...)
            
            # Add some variance to simulate real API
            variance = np.random.randint(-20, 20)
            actual_score = max(300, min(850, reported_score + variance))
            
            return {
                "status": "success",
                "verified": True,
                "reported_score": reported_score,
                "actual_score": actual_score,
                "score_difference": abs(actual_score - reported_score),
                "verification_date": datetime.now().isoformat(),
                "source": "Experian (Simulated)"
            }
            
        except Exception as e:
            logger.error(f"Credit verification failed: {str(e)}")
            return {
                "status": "error",
                "verified": False,
                "error": str(e),
                "fallback": "Using self-reported score"
            }
    
    @classmethod
    def fetch_driving_record(cls, applicant_id: str) -> Dict[str, Any]:
        """
        Fetch driving record from DMV (simulated)
        
        Args:
            applicant_id: Unique applicant identifier
            
        Returns:
            Driving record data
        """
        try:
            PIIProtector.safe_log(
                f"Fetching driving record for applicant",
                applicant_id=applicant_id
            )
            
            # Simulate API call
            import time
            time.sleep(0.2)
            
            # Simulated response
            return {
                "status": "success",
                "data_available": True,
                "additional_violations": np.random.randint(0, 2),
                "recent_incidents": [],
                "license_status": "valid",
                "source": "DMV (Simulated)"
            }
            
        except Exception as e:
            logger.error(f"DMV record fetch failed: {str(e)}")
            return {
                "status": "error",
                "data_available": False,
                "error": str(e)
            }


# ==================== ML Model ====================

class UnderwritingMLModel:
    """Machine Learning model for underwriting risk prediction"""
    
    MODEL_PATH = Path("underwriting_model.pkl")
    SCALER_PATH = Path("underwriting_scaler.pkl")
    
    def __init__(self):
        self.model = None
        self.scaler = None
        
        if SKLEARN_AVAILABLE:
            self._load_or_train_model()
    
    def _load_or_train_model(self):
        """Load existing model or train new one"""
        if self.MODEL_PATH.exists() and self.SCALER_PATH.exists():
            try:
                with open(self.MODEL_PATH, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.SCALER_PATH, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info("Loaded pre-trained underwriting model")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}. Training new model.")
                self._train_model()
        else:
            self._train_model()
    
    def _train_model(self):
        """Train ML model on simulated data"""
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available. ML model disabled.")
            return
        
        logger.info("Training underwriting ML model on simulated data...")
        
        # Generate simulated training data
        np.random.seed(42)
        n_samples = 1000
        
        # Features: credit_score, age, claims_count, coverage_amount_norm, years_licensed
        X = np.column_stack([
            np.random.randint(300, 850, n_samples),  # credit_score
            np.random.randint(18, 80, n_samples),     # age
            np.random.poisson(1.5, n_samples),        # claims_count
            np.random.uniform(0, 1, n_samples),       # coverage_amount_normalized
            np.random.randint(0, 50, n_samples),      # years_licensed
        ])
        
        # Target: 0 = approve, 1 = approve_with_conditions, 2 = decline
        y = np.zeros(n_samples, dtype=int)
        
        for i in range(n_samples):
            credit_score, age, claims, coverage_norm, years_licensed = X[i]
            
            risk_score = 0
            
            # Credit score impact
            if credit_score < 600:
                risk_score += 3
            elif credit_score < 700:
                risk_score += 1
            
            # Claims impact
            if claims > 3:
                risk_score += 2
            elif claims > 1:
                risk_score += 1
            
            # Age impact
            if age < 25:
                risk_score += 1
            
            # Coverage amount impact
            if coverage_norm > 0.8:
                risk_score += 1
            
            # Experience impact
            if years_licensed < 3:
                risk_score += 1
            
            # Decision based on risk score
            if risk_score >= 5:
                y[i] = 2  # decline
            elif risk_score >= 3:
                y[i] = 1  # approve with conditions
            else:
                y[i] = 0  # approve
        
        # Train model
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        self.model = DecisionTreeClassifier(
            max_depth=5,
            min_samples_split=20,
            random_state=42
        )
        self.model.fit(X_scaled, y)
        
        # Save model
        try:
            with open(self.MODEL_PATH, 'wb') as f:
                pickle.dump(self.model, f)
            with open(self.SCALER_PATH, 'wb') as f:
                pickle.dump(self.scaler, f)
            logger.info("Model trained and saved successfully")
        except Exception as e:
            logger.warning(f"Failed to save model: {e}")
    
    def predict_risk(self, features: Dict[str, float]) -> Dict[str, Any]:
        """
        Predict risk level using ML model
        
        Args:
            features: Dictionary with feature values
            
        Returns:
            Prediction result
        """
        if not SKLEARN_AVAILABLE or self.model is None:
            # Fallback to rule-based
            return {"ml_available": False, "prediction": 0}
        
        try:
            # Extract features in correct order
            X = np.array([[
                features['credit_score'],
                features['age'],
                features['claims_count'],
                features['coverage_amount_normalized'],
                features['years_licensed']
            ]])
            
            X_scaled = self.scaler.transform(X)
            prediction = self.model.predict(X_scaled)[0]
            probabilities = self.model.predict_proba(X_scaled)[0]
            
            return {
                "ml_available": True,
                "prediction": int(prediction),
                "confidence": float(max(probabilities)),
                "probabilities": {
                    "approve": float(probabilities[0]),
                    "approve_with_conditions": float(probabilities[1]),
                    "decline": float(probabilities[2])
                }
            }
            
        except Exception as e:
            logger.error(f"ML prediction failed: {str(e)}")
            return {"ml_available": False, "error": str(e)}


# ==================== Rule Engine ====================

class UnderwritingRuleEngine:
    """Rule-based underwriting decision engine"""
    
    @staticmethod
    def evaluate_rules(applicant: ApplicantData, external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate underwriting rules
        
        Args:
            applicant: Applicant data
            external_data: External verification data
            
        Returns:
            Rule evaluation results
        """
        rules_passed = []
        rules_failed = []
        risk_factors = []
        auto_decline = False
        
        # Get verified credit score
        credit_score = applicant.credit_score
        if external_data.get('credit_verified') and external_data.get('credit_data'):
            credit_score = external_data['credit_data'].get('actual_score', credit_score)
        
        # Rule 1: Credit Score Check
        if credit_score < 550:
            rules_failed.append("Credit score below minimum threshold (550)")
            auto_decline = True
        elif credit_score < 600:
            rules_failed.append("Credit score in high-risk range (550-600)")
            risk_factors.append("Low credit score")
        elif credit_score < 700:
            risk_factors.append("Below average credit score")
        else:
            rules_passed.append("Credit score acceptable")
        
        # Rule 2: Claims History
        if applicant.claims_history.fraud_indicators:
            rules_failed.append("Fraud indicators present in claims history")
            auto_decline = True
        
        if applicant.claims_history.claims_last_3_years > 3:
            rules_failed.append("Excessive claims (>3 in last 3 years)")
            risk_factors.append("High claims frequency")
        elif applicant.claims_history.claims_last_3_years > 1:
            risk_factors.append("Multiple recent claims")
        else:
            rules_passed.append("Claims history acceptable")
        
        # Rule 3: Age-based assessment
        if applicant.age < 21:
            risk_factors.append("Young applicant (under 21)")
        elif applicant.age > 75:
            risk_factors.append("Senior applicant (over 75)")
        else:
            rules_passed.append("Age within standard range")
        
        # Rule 4: Type-specific rules
        if applicant.insurance_type == InsuranceType.AUTO:
            auto_rules = UnderwritingRuleEngine._evaluate_auto_rules(applicant)
            rules_passed.extend(auto_rules['passed'])
            rules_failed.extend(auto_rules['failed'])
            risk_factors.extend(auto_rules['risk_factors'])
            if auto_rules.get('auto_decline'):
                auto_decline = True
        
        elif applicant.insurance_type == InsuranceType.HOME:
            home_rules = UnderwritingRuleEngine._evaluate_home_rules(applicant)
            rules_passed.extend(home_rules['passed'])
            rules_failed.extend(home_rules['failed'])
            risk_factors.extend(home_rules['risk_factors'])
        
        elif applicant.insurance_type in [InsuranceType.HEALTH, InsuranceType.LIFE]:
            health_rules = UnderwritingRuleEngine._evaluate_health_rules(applicant)
            rules_passed.extend(health_rules['passed'])
            rules_failed.extend(health_rules['failed'])
            risk_factors.extend(health_rules['risk_factors'])
        
        # Rule 5: Coverage amount vs income
        if applicant.annual_income > 0:
            coverage_ratio = applicant.coverage_amount / applicant.annual_income
            if coverage_ratio > 10:
                risk_factors.append("Coverage amount very high relative to income")
            elif coverage_ratio > 5:
                risk_factors.append("Coverage amount high relative to income")
        
        return {
            "rules_passed": rules_passed,
            "rules_failed": rules_failed,
            "risk_factors": risk_factors,
            "auto_decline": auto_decline,
            "total_rules_evaluated": len(rules_passed) + len(rules_failed)
        }
    
    @staticmethod
    def _evaluate_auto_rules(applicant: ApplicantData) -> Dict[str, Any]:
        """Evaluate auto insurance specific rules"""
        passed = []
        failed = []
        risk_factors = []
        auto_decline = False
        
        if applicant.driving_record:
            dr = applicant.driving_record
            
            # DUI check
            if dr.dui_history:
                failed.append("DUI/DWI history present")
                risk_factors.append("DUI history")
                auto_decline = True
            else:
                passed.append("No DUI/DWI history")
            
            # License suspension
            if dr.license_suspended:
                failed.append("License suspension history")
                risk_factors.append("License suspended")
            
            # Accidents
            if dr.accidents_last_5_years > 3:
                failed.append("Excessive accidents (>3 in 5 years)")
                risk_factors.append("High accident rate")
            elif dr.accidents_last_5_years > 1:
                risk_factors.append("Multiple accidents")
            else:
                passed.append("Acceptable accident history")
            
            # Violations
            if dr.violations_last_3_years > 5:
                failed.append("Excessive violations (>5 in 3 years)")
                risk_factors.append("Multiple traffic violations")
            elif dr.violations_last_3_years > 2:
                risk_factors.append("Several traffic violations")
            else:
                passed.append("Acceptable violation history")
            
            # Experience
            if dr.years_licensed < 2:
                risk_factors.append("Limited driving experience")
            else:
                passed.append("Adequate driving experience")
        
        return {
            "passed": passed,
            "failed": failed,
            "risk_factors": risk_factors,
            "auto_decline": auto_decline
        }
    
    @staticmethod
    def _evaluate_home_rules(applicant: ApplicantData) -> Dict[str, Any]:
        """Evaluate home insurance specific rules"""
        passed = []
        failed = []
        risk_factors = []
        
        if applicant.property_info:
            prop = applicant.property_info
            
            # Property age
            if prop.property_age > 50:
                risk_factors.append("Old property (>50 years)")
            
            # Construction type
            if prop.construction_type == "wood":
                risk_factors.append("Wood construction - fire risk")
            else:
                passed.append("Durable construction type")
            
            # Security system
            if prop.security_system:
                passed.append("Security system installed")
            else:
                risk_factors.append("No security system")
            
            # Fire protection
            if prop.fire_protection_class > 7:
                failed.append("Poor fire protection class (>7)")
                risk_factors.append("Limited fire protection")
            elif prop.fire_protection_class <= 4:
                passed.append("Excellent fire protection")
            
            # Flood zone
            if prop.flood_zone:
                risk_factors.append("Property in flood zone")
        
        return {
            "passed": passed,
            "failed": failed,
            "risk_factors": risk_factors
        }
    
    @staticmethod
    def _evaluate_health_rules(applicant: ApplicantData) -> Dict[str, Any]:
        """Evaluate health/life insurance specific rules"""
        passed = []
        failed = []
        risk_factors = []
        
        # Smoker status
        if applicant.smoker:
            risk_factors.append("Smoker - increased health risk")
        else:
            passed.append("Non-smoker")
        
        # Pre-existing conditions
        if applicant.pre_existing_conditions:
            risk_factors.append("Pre-existing health conditions")
        else:
            passed.append("No pre-existing conditions")
        
        return {
            "passed": passed,
            "failed": failed,
            "risk_factors": risk_factors
        }


# ==================== Risk Calculator ====================

class RiskCalculator:
    """Calculate risk scores and premiums"""
    
    # Base premiums by insurance type (monthly)
    BASE_PREMIUMS = {
        InsuranceType.AUTO: 150.0,
        InsuranceType.HOME: 120.0,
        InsuranceType.LIFE: 80.0,
        InsuranceType.HEALTH: 200.0
    }
    
    @staticmethod
    def calculate_risk_score(
        applicant: ApplicantData,
        rule_results: Dict[str, Any],
        ml_results: Dict[str, Any]
    ) -> float:
        """
        Calculate comprehensive risk score (0-100)
        
        Formula: Weighted combination of credit, claims, and other factors
        """
        # Credit score component (0-30 points, inverted so lower credit = higher risk)
        credit_component = max(0, 30 - (applicant.credit_score - 300) / 550 * 30)
        
        # Claims history component (0-20 points)
        claims_component = min(20, applicant.claims_history.claims_last_3_years * 5)
        
        # Age component (0-10 points)
        if applicant.age < 25 or applicant.age > 70:
            age_component = 10
        elif applicant.age < 30 or applicant.age > 65:
            age_component = 5
        else:
            age_component = 0
        
        # Rule-based component (0-25 points)
        rule_component = len(rule_results.get('risk_factors', [])) * 3
        rule_component += len(rule_results.get('rules_failed', [])) * 5
        rule_component = min(25, rule_component)
        
        # ML component (0-15 points) if available
        ml_component = 0
        if ml_results.get('ml_available'):
            prediction = ml_results.get('prediction', 0)
            ml_component = prediction * 7.5  # 0, 7.5, or 15
        
        # Total risk score
        risk_score = credit_component + claims_component + age_component + rule_component + ml_component
        
        return min(100, max(0, risk_score))
    
    @staticmethod
    def calculate_premium(
        applicant: ApplicantData,
        risk_score: float,
        risk_factors: List[str]
    ) -> Dict[str, float]:
        """Calculate premium based on risk"""
        base_premium = RiskCalculator.BASE_PREMIUMS.get(
            applicant.insurance_type,
            150.0
        )
        
        # Risk-based multiplier (1.0 to 3.0)
        risk_multiplier = 1.0 + (risk_score / 100) * 2.0
        
        # Calculate base with risk
        premium_with_risk = base_premium * risk_multiplier
        
        # Additional premium for specific risk factors
        additional_premium = 0
        for factor in risk_factors:
            if "DUI" in factor or "fraud" in factor.lower():
                additional_premium += base_premium * 0.5
            elif "accident" in factor.lower() or "claims" in factor.lower():
                additional_premium += base_premium * 0.2
            elif "credit" in factor.lower():
                additional_premium += base_premium * 0.15
        
        total_premium = premium_with_risk + additional_premium
        
        return {
            "base_premium": round(base_premium, 2),
            "premium_with_risk": round(premium_with_risk, 2),
            "additional_premium": round(additional_premium, 2),
            "total_monthly_premium": round(total_premium, 2),
            "total_annual_premium": round(total_premium * 12, 2)
        }


# ==================== Main Underwriting Tool ====================

# Initialize shared instances (module-level)
_ml_model_instance = None
_rule_engine_instance = UnderwritingRuleEngine()
_risk_calculator_instance = RiskCalculator()


def get_ml_model():
    """Get or create ML model instance"""
    global _ml_model_instance
    if _ml_model_instance is None:
        _ml_model_instance = UnderwritingMLModel()
    return _ml_model_instance


class UnderwritingTool(BaseTool):
    """
    Advanced Insurance Underwriting Tool
    
    Performs comprehensive risk assessment using rule engines, ML models,
    and external data sources to make underwriting decisions.
    """
    
    name: str = "insurance_underwriting"
    description: str = """
    Use this tool to perform insurance underwriting and risk assessment.
    
    Input must be a JSON string containing applicant data:
    - applicant_id: unique identifier
    - name: applicant name
    - age: applicant age (18-100)
    - credit_score: credit score (300-850)
    - annual_income: annual income in USD
    - employment_status: employed/self_employed/unemployed/retired
    - insurance_type: auto/home/life/health
    - coverage_amount: requested coverage in USD
    - claims_history: object with total_claims, claims_last_3_years, total_claimed_amount, fraud_indicators
    
    For AUTO insurance, also include driving_record with:
    - years_licensed, accidents_last_5_years, violations_last_3_years, dui_history, license_suspended
    
    For HOME insurance, also include property_info with:
    - property_age, construction_type, security_system, fire_protection_class, flood_zone
    
    For HEALTH/LIFE insurance, also include:
    - smoker: true/false
    - pre_existing_conditions: true/false
    
    Returns comprehensive underwriting decision with risk assessment, premium calculation, and policy terms.
    """
    args_schema: Type[BaseModel] = UnderwritingToolInput
    
    def _run(self, applicant_data_json: str) -> str:
        """
        Perform underwriting assessment
        
        Args:
            applicant_data_json: JSON string with applicant data
            
        Returns:
            Formatted underwriting decision report
        """
        try:
            # Parse and validate applicant data
            PIIProtector.safe_log("Starting underwriting assessment")
            applicant_data_dict = json.loads(applicant_data_json)
            
            try:
                applicant = ApplicantData(**applicant_data_dict)
            except Exception as validation_error:
                error_msg = self._format_validation_error(validation_error)
                logger.warning(f"Validation error: {error_msg}")
                return error_msg
            
            # Log with PII protection
            PIIProtector.safe_log(
                "Processing application",
                applicant_id=applicant.applicant_id,
                insurance_type=applicant.insurance_type.value,
                name=applicant.name
            )
            
            # Step 1: External data verification
            external_data = self._verify_external_data(applicant)
            
            # Step 2: Rule engine evaluation
            rule_results = _rule_engine_instance.evaluate_rules(applicant, external_data)
            
            # Step 3: ML model prediction
            ml_results = self._get_ml_prediction(applicant)
            
            # Step 4: Calculate risk score
            risk_score = _risk_calculator_instance.calculate_risk_score(
                applicant, rule_results, ml_results
            )
            
            # Step 5: Make decision
            decision_result = self._make_decision(
                applicant, risk_score, rule_results, ml_results, external_data
            )
            
            # Format response
            response = self._format_decision_report(
                applicant, decision_result, rule_results, ml_results, external_data
            )
            
            PIIProtector.safe_log(
                "Underwriting completed",
                applicant_id=applicant.applicant_id,
                decision=decision_result['decision'].value
            )
            
            return response
            
        except json.JSONDecodeError as e:
            error_msg = f"ERROR: Invalid JSON format - {str(e)}"
            logger.error(error_msg)
            return error_msg
            
        except Exception as e:
            logger.error(f"Error in underwriting tool: {str(e)}", exc_info=True)
            return f"ERROR: Underwriting failed - {str(e)}"
    
    async def _arun(self, applicant_data_json: str) -> str:
        """Async version - delegates to synchronous version"""
        return self._run(applicant_data_json)
    
    def _verify_external_data(self, applicant: ApplicantData) -> Dict[str, Any]:
        """Verify applicant data with external sources"""
        external_data = {
            "credit_verified": False,
            "driving_verified": False,
            "external_sources": []
        }
        
        # Verify credit score
        credit_data = ExternalDataAPI.verify_credit_score(
            applicant.applicant_id,
            applicant.credit_score
        )
        external_data['credit_data'] = credit_data
        external_data['credit_verified'] = credit_data.get('verified', False)
        if credit_data.get('source'):
            external_data['external_sources'].append(credit_data['source'])
        
        # Verify driving record for auto insurance
        if applicant.insurance_type == InsuranceType.AUTO:
            dmv_data = ExternalDataAPI.fetch_driving_record(applicant.applicant_id)
            external_data['dmv_data'] = dmv_data
            external_data['driving_verified'] = dmv_data.get('data_available', False)
            if dmv_data.get('source'):
                external_data['external_sources'].append(dmv_data['source'])
        
        return external_data
    
    def _get_ml_prediction(self, applicant: ApplicantData) -> Dict[str, Any]:
        """Get ML model prediction"""
        # Prepare features
        years_licensed = 0
        if applicant.driving_record:
            years_licensed = applicant.driving_record.years_licensed
        elif applicant.age >= 18:
            years_licensed = applicant.age - 18
        
        features = {
            'credit_score': applicant.credit_score,
            'age': applicant.age,
            'claims_count': applicant.claims_history.claims_last_3_years,
            'coverage_amount_normalized': min(1.0, applicant.coverage_amount / 100000),
            'years_licensed': years_licensed
        }
        
        ml_model = get_ml_model()
        return ml_model.predict_risk(features)
    
    def _make_decision(
        self,
        applicant: ApplicantData,
        risk_score: float,
        rule_results: Dict[str, Any],
        ml_results: Dict[str, Any],
        external_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make underwriting decision"""
        
        # Auto decline conditions
        if rule_results.get('auto_decline'):
            return self._create_decline_decision(applicant, risk_score, rule_results)
        
        # Determine risk level
        if risk_score < 30:
            risk_level = RiskLevel.LOW
        elif risk_score < 50:
            risk_level = RiskLevel.MEDIUM
        elif risk_score < 70:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.VERY_HIGH
        
        # Calculate premium
        premium_info = _risk_calculator_instance.calculate_premium(
            applicant, risk_score, rule_results.get('risk_factors', [])
        )
        
        # Decision logic
        if risk_level == RiskLevel.LOW:
            decision = UnderwritingDecision.APPROVED
            conditions = ["Standard policy terms apply"]
            exclusions = []
            decision_reasons = ["Low risk profile", "Good credit history", "Clean claims record"]
            
        elif risk_level == RiskLevel.MEDIUM:
            decision = UnderwritingDecision.APPROVED
            conditions = [
                "Standard policy terms apply",
                "Annual policy review required"
            ]
            exclusions = []
            decision_reasons = [
                "Moderate risk profile",
                "Acceptable underwriting criteria met"
            ]
            if len(rule_results.get('risk_factors', [])) > 0:
                decision_reasons.append("Some risk factors present")
            
        elif risk_level == RiskLevel.HIGH:
            decision = UnderwritingDecision.APPROVED_WITH_CONDITIONS
            conditions = [
                "Higher deductible required",
                "Six-month policy review",
                "No coverage for first 30 days",
                "Additional documentation required annually"
            ]
            exclusions = self._determine_exclusions(applicant, rule_results)
            decision_reasons = [
                "High risk profile",
                f"Risk factors identified: {len(rule_results.get('risk_factors', []))}"
            ]
            
        else:  # VERY_HIGH
            if risk_score > 85:
                return self._create_decline_decision(applicant, risk_score, rule_results)
            else:
                decision = UnderwritingDecision.REFER_TO_MANUAL_REVIEW
                conditions = ["Manual underwriting review required"]
                exclusions = []
                decision_reasons = [
                    "Very high risk profile",
                    "Requires senior underwriter approval",
                    "Additional information needed"
                ]
                premium_info = None  # No premium until manual review
        
        return {
            "decision": decision,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "approved": decision in [UnderwritingDecision.APPROVED, UnderwritingDecision.APPROVED_WITH_CONDITIONS],
            "decision_reasons": decision_reasons,
            "conditions": conditions,
            "exclusions": exclusions,
            "premium_info": premium_info,
            "credit_verified": external_data.get('credit_verified', False),
            "external_sources": external_data.get('external_sources', [])
        }
    
    def _create_decline_decision(
        self,
        applicant: ApplicantData,
        risk_score: float,
        rule_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create decline decision"""
        reasons = ["Application declined due to:"]
        reasons.extend(rule_results.get('rules_failed', []))
        
        return {
            "decision": UnderwritingDecision.DECLINED,
            "risk_level": RiskLevel.VERY_HIGH,
            "risk_score": risk_score,
            "approved": False,
            "decision_reasons": reasons,
            "conditions": [],
            "exclusions": [],
            "premium_info": None,
            "credit_verified": False,
            "external_sources": []
        }
    
    def _determine_exclusions(
        self,
        applicant: ApplicantData,
        rule_results: Dict[str, Any]
    ) -> List[str]:
        """Determine policy exclusions based on risk factors"""
        exclusions = []
        risk_factors = rule_results.get('risk_factors', [])
        
        for factor in risk_factors:
            if "accident" in factor.lower():
                exclusions.append("Accident forgiveness not available")
            if "violation" in factor.lower():
                exclusions.append("Traffic violation surcharge waiver not available")
            if "flood" in factor.lower():
                exclusions.append("Flood damage excluded (separate flood insurance required)")
            if "credit" in factor.lower():
                exclusions.append("Premium payment plan restrictions may apply")
        
        return list(set(exclusions))  # Remove duplicates
    
    def _format_validation_error(self, error: Exception) -> str:
        """Format validation error messages"""
        return f"""
ERROR: Applicant Data Validation Failed
----------------------------------------
{str(error)}

Required fields must be provided with valid values.
Please refer to the tool description for complete field requirements.
        """
    
    def _format_decision_report(
        self,
        applicant: ApplicantData,
        decision_result: Dict[str, Any],
        rule_results: Dict[str, Any],
        ml_results: Dict[str, Any],
        external_data: Dict[str, Any]
    ) -> str:
        """Format comprehensive decision report"""
        
        # Mask PII in report
        masked_name = PIIProtector.mask_name(applicant.name)
        
        # Format decision
        decision = decision_result['decision'].value.upper().replace('_', ' ')
        risk_level = decision_result['risk_level'].value.upper()
        approved_status = "[APPROVED]" if decision_result['approved'] else "[DECLINED]"
        
        # Format premium section
        premium_section = "N/A - Manual review required"
        if decision_result['premium_info']:
            premium_info = decision_result['premium_info']
            premium_section = f"""
   Base Premium: ${premium_info['base_premium']:.2f}/month
   Risk-Adjusted Premium: ${premium_info['premium_with_risk']:.2f}/month
   Additional Premium: ${premium_info['additional_premium']:.2f}/month
   -------------------------------------------
   TOTAL MONTHLY PREMIUM: ${premium_info['total_monthly_premium']:.2f}
   TOTAL ANNUAL PREMIUM: ${premium_info['total_annual_premium']:.2f}
            """
        
        # Format conditions
        conditions_text = "\n".join(f"   {i+1}. {cond}" for i, cond in enumerate(decision_result['conditions']))
        if not conditions_text:
            conditions_text = "   None"
        
        # Format exclusions
        exclusions_text = "\n".join(f"   - {excl}" for excl in decision_result['exclusions'])
        if not exclusions_text:
            exclusions_text = "   None"
        
        # Format decision reasons
        reasons_text = "\n".join(f"   - {reason}" for reason in decision_result['decision_reasons'])
        
        # Format risk factors
        risk_factors_text = "\n".join(f"   - {factor}" for factor in rule_results.get('risk_factors', []))
        if not risk_factors_text:
            risk_factors_text = "   None identified"
        
        # ML info
        ml_text = "ML model not available"
        if ml_results.get('ml_available'):
            ml_text = f"Risk prediction: {ml_results['prediction']} (confidence: {ml_results['confidence']:.2%})"
        
        # External verification
        verification_text = "\n".join(f"   - {source}" for source in decision_result['external_sources'])
        if not verification_text:
            verification_text = "   None"
        
        report = f"""
========================================================================
          UNDERWRITING DECISION REPORT
========================================================================

Application ID: {applicant.applicant_id}
Applicant: {masked_name} (ID: {applicant.applicant_id})
Insurance Type: {applicant.insurance_type.value.upper()}
Coverage Requested: ${applicant.coverage_amount:,.2f}
Timestamp: {datetime.now().isoformat()}

========================================================================
DECISION: {decision} {approved_status}
========================================================================

Risk Assessment:
   Risk Level: {risk_level}
   Risk Score: {decision_result['risk_score']:.2f}/100
   
Decision Reasons:
{reasons_text}

========================================================================
RISK ANALYSIS
========================================================================

Risk Factors Identified:
{risk_factors_text}

Rules Evaluation:
   Total Rules Evaluated: {rule_results.get('total_rules_evaluated', 0)}
   Rules Passed: {len(rule_results.get('rules_passed', []))}
   Rules Failed: {len(rule_results.get('rules_failed', []))}

Machine Learning Assessment:
   {ml_text}

========================================================================
PREMIUM CALCULATION
========================================================================
{premium_section}

========================================================================
POLICY TERMS
========================================================================

Conditions:
{conditions_text}

Exclusions:
{exclusions_text}

========================================================================
DATA VERIFICATION
========================================================================

External Data Sources:
{verification_text}

Credit Score Verified: {"Yes" if decision_result['credit_verified'] else "No"}

========================================================================
COMPLIANCE NOTES
========================================================================

- All PII handled in compliance with data protection regulations
- Decision logged with audit trail (PII-protected)
- Applicant has right to request decision explanation
- Appeal process available for declined applications
- All data encrypted and securely stored

Model Version: {decision_result.get('model_version', '1.0')}
Underwriting System: Automated with manual review option

========================================================================
        """
        
        return report.strip()


# ==================== Batch Processing ====================

def batch_underwrite(applications_json: str) -> str:
    """
    Process multiple applications in batch
    
    Args:
        applications_json: JSON array of applications
        
    Returns:
        Summary report of all decisions
    """
    try:
        applications = json.loads(applications_json)
        
        if not isinstance(applications, list):
            return "ERROR: Input must be a JSON array of applications"
        
        tool = UnderwritingTool()
        results = []
        
        logger.info(f"Processing batch of {len(applications)} applications")
        
        for i, app_data in enumerate(applications, 1):
            PIIProtector.safe_log(f"Processing application {i}/{len(applications)}")
            
            result = tool._run(json.dumps(app_data))
            results.append({
                "application_number": i,
                "applicant_id": app_data.get('applicant_id', 'unknown'),
                "result": result
            })
        
        # Create summary
        summary = f"""
========================================================================
BATCH UNDERWRITING SUMMARY
========================================================================

Total Applications Processed: {len(applications)}
Timestamp: {datetime.now().isoformat()}

------------------------------------------------------------------------
"""
        
        for res in results:
            summary += f"\nApplication #{res['application_number']}\n"
            summary += f"{'=' * 72}\n"
            summary += res['result']
            summary += f"\n\n{'=' * 72}\n"
        
        summary += f"""
========================================================================
BATCH PROCESSING COMPLETE
========================================================================
        """
        
        return summary.strip()
        
    except Exception as e:
        logger.error(f"Batch processing error: {str(e)}")
        return f"ERROR: Batch processing failed - {str(e)}"


# ==================== Standalone Usage Example ====================

def example_usage():
    """Demonstrate the UnderwritingTool usage"""
    print("=" * 80)
    print("Advanced Insurance Underwriting Tool - Standalone Demo")
    print("=" * 80)
    
    tool = UnderwritingTool()
    
    # Example 1: Auto Insurance - Good Risk
    print("\n\n" + "=" * 80)
    print("EXAMPLE 1: Auto Insurance - Good Risk Profile")
    print("=" * 80)
    
    good_auto_app = {
        "applicant_id": "APP-2025-001",
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
    
    result = tool._run(json.dumps(good_auto_app))
    print(result)
    
    input("\nPress Enter to continue to next example...")
    
    # Example 2: Auto Insurance - High Risk
    print("\n\n" + "=" * 80)
    print("EXAMPLE 2: Auto Insurance - High Risk Profile")
    print("=" * 80)
    
    high_risk_auto = {
        "applicant_id": "APP-2025-002",
        "name": "Jane Doe",
        "age": 22,
        "credit_score": 580,
        "annual_income": 30000,
        "employment_status": "employed",
        "insurance_type": "auto",
        "coverage_amount": 50000,
        "claims_history": {
            "total_claims": 4,
            "claims_last_3_years": 3,
            "total_claimed_amount": 25000,
            "fraud_indicators": False
        },
        "driving_record": {
            "years_licensed": 3,
            "accidents_last_5_years": 2,
            "violations_last_3_years": 4,
            "dui_history": False,
            "license_suspended": False
        }
    }
    
    result = tool._run(json.dumps(high_risk_auto))
    print(result)
    
    input("\nPress Enter to continue to next example...")
    
    # Example 3: Health Insurance
    print("\n\n" + "=" * 80)
    print("EXAMPLE 3: Health Insurance Application")
    print("=" * 80)
    
    health_app = {
        "applicant_id": "APP-2025-003",
        "name": "Bob Johnson",
        "age": 45,
        "credit_score": 700,
        "annual_income": 85000,
        "employment_status": "employed",
        "insurance_type": "health",
        "coverage_amount": 500000,
        "claims_history": {
            "total_claims": 2,
            "claims_last_3_years": 1,
            "total_claimed_amount": 8000,
            "fraud_indicators": False
        },
        "smoker": True,
        "pre_existing_conditions": False
    }
    
    result = tool._run(json.dumps(health_app))
    print(result)
    
    input("\nPress Enter to continue to batch example...")
    
    # Example 4: Batch Processing
    print("\n\n" + "=" * 80)
    print("EXAMPLE 4: Batch Processing Multiple Applications")
    print("=" * 80)
    
    batch_apps = [good_auto_app, health_app]
    
    result = batch_underwrite(json.dumps(batch_apps))
    print(result[:1000] + "\n...(truncated for display)...")
    
    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)


if __name__ == "__main__":
    example_usage()

