"""
Unit Tests for Insurance AI Agent Tools
Tests quoting, underwriting, and document filling functionality
"""

import pytest
import json
from pathlib import Path

# Import tools
from quoting_tool import QuotingTool, CustomerData, InsuranceType
from underwriting_tool import UnderwritingTool, ApplicantData
from document_filling_tool import DocumentFillingTool, CustomerInfo


# ==================== Quoting Tool Tests ====================

class TestQuotingTool:
    """Test suite for QuotingTool"""
    
    @pytest.fixture
    def quoting_tool(self):
        """Create QuotingTool instance"""
        return QuotingTool()
    
    @pytest.fixture
    def valid_auto_data(self):
        """Valid auto insurance data"""
        return {
            "age": 30,
            "gender": "male",
            "address": "123 Main St, New York, NY",
            "location_type": "urban",
            "insurance_type": "auto",
            "vehicle_details": {
                "make": "Honda",
                "model": "Accord",
                "year": 2020,
                "value": 28000,
                "usage": "personal"
            }
        }
    
    @pytest.fixture
    def valid_health_data(self):
        """Valid health insurance data"""
        return {
            "age": 35,
            "gender": "female",
            "address": "456 Elm St, Los Angeles, CA",
            "location_type": "suburban",
            "insurance_type": "health",
            "health_details": {
                "smoker": False,
                "pre_existing_conditions": False,
                "bmi": 24.5,
                "exercise_frequency": "regular"
            }
        }
    
    def test_auto_insurance_quote(self, quoting_tool, valid_auto_data):
        """Test auto insurance quote generation"""
        result = quoting_tool._run(json.dumps(valid_auto_data))
        
        assert "INSURANCE QUOTE - DETAILED REPORT" in result
        assert "TOTAL MONTHLY PREMIUM:" in result
        assert "AUTO" in result
        assert "Honda Accord" in result
    
    def test_health_insurance_quote(self, quoting_tool, valid_health_data):
        """Test health insurance quote generation"""
        result = quoting_tool._run(json.dumps(valid_health_data))
        
        assert "INSURANCE QUOTE - DETAILED REPORT" in result
        assert "TOTAL MONTHLY PREMIUM:" in result
        assert "HEALTH" in result
        assert "Non-smoker" in result
    
    def test_missing_vehicle_details(self, quoting_tool):
        """Test error handling for missing vehicle details"""
        invalid_data = {
            "age": 30,
            "gender": "male",
            "address": "123 Main St",
            "location_type": "urban",
            "insurance_type": "auto"
            # Missing vehicle_details
        }
        
        result = quoting_tool._run(json.dumps(invalid_data))
        assert "ERROR" in result or "required" in result.lower()
    
    def test_invalid_json(self, quoting_tool):
        """Test error handling for invalid JSON"""
        result = quoting_tool._run("not valid json")
        assert "ERROR" in result
        assert "JSON" in result
    
    def test_young_driver_premium(self, quoting_tool, valid_auto_data):
        """Test that young drivers get higher premiums"""
        valid_auto_data["age"] = 22
        result = quoting_tool._run(json.dumps(valid_auto_data))
        
        assert "Age Factor: 1.20" in result  # Young driver factor


# ==================== Underwriting Tool Tests ====================

class TestUnderwritingTool:
    """Test suite for UnderwritingTool"""
    
    @pytest.fixture
    def underwriting_tool(self):
        """Create UnderwritingTool instance"""
        return UnderwritingTool()
    
    @pytest.fixture
    def good_applicant_data(self):
        """Good risk applicant data"""
        return {
            "applicant_id": "TEST-001",
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
                "violations_last_3_years": 0,
                "dui_history": False,
                "license_suspended": False
            }
        }
    
    @pytest.fixture
    def high_risk_applicant_data(self):
        """High risk applicant data"""
        return {
            "applicant_id": "TEST-002",
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
    
    def test_approve_good_risk(self, underwriting_tool, good_applicant_data):
        """Test approval of good risk applicant"""
        result = underwriting_tool._run(json.dumps(good_applicant_data))
        
        assert "UNDERWRITING DECISION REPORT" in result
        assert "[APPROVED]" in result
        assert "TEST-001" in result
    
    def test_high_risk_conditions(self, underwriting_tool, high_risk_applicant_data):
        """Test high risk applicant gets conditions"""
        result = underwriting_tool._run(json.dumps(high_risk_applicant_data))
        
        assert "UNDERWRITING DECISION REPORT" in result
        # Should be approved with conditions or referred
        assert ("APPROVED WITH CONDITIONS" in result or "REFER" in result)
    
    def test_dui_decline(self, underwriting_tool, good_applicant_data):
        """Test DUI history leads to decline"""
        good_applicant_data["driving_record"]["dui_history"] = True
        result = underwriting_tool._run(json.dumps(good_applicant_data))
        
        assert "DECLINED" in result or "DUI" in result
    
    def test_risk_score_calculation(self, underwriting_tool, good_applicant_data):
        """Test risk score is calculated"""
        result = underwriting_tool._run(json.dumps(good_applicant_data))
        
        assert "Risk Score:" in result
        assert "/100" in result
    
    def test_missing_driving_record(self, underwriting_tool):
        """Test error for missing driving record in auto insurance"""
        invalid_data = {
            "applicant_id": "TEST-003",
            "name": "Test User",
            "age": 30,
            "credit_score": 700,
            "annual_income": 50000,
            "employment_status": "employed",
            "insurance_type": "auto",
            "coverage_amount": 50000,
            "claims_history": {
                "total_claims": 0,
                "claims_last_3_years": 0,
                "total_claimed_amount": 0,
                "fraud_indicators": False
            }
            # Missing driving_record
        }
        
        result = underwriting_tool._run(json.dumps(invalid_data))
        assert "ERROR" in result or "required" in result.lower()


# ==================== Document Filling Tool Tests ====================

class TestDocumentFillingTool:
    """Test suite for DocumentFillingTool"""
    
    @pytest.fixture
    def document_tool(self):
        """Create DocumentFillingTool instance"""
        return DocumentFillingTool()
    
    @pytest.fixture
    def valid_customer_data(self):
        """Valid customer data"""
        return {
            "full_name": "John Smith",
            "date_of_birth": "1985-06-15",
            "email": "john@email.com",
            "phone": "+1-555-123-4567",
            "street_address": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001"
        }
    
    @pytest.fixture
    def valid_policy_data(self):
        """Valid policy data"""
        return {
            "insurance_type": "Life Insurance",
            "policy_term": 20,
            "premium_amount": 150.00,
            "payment_frequency": "monthly",
            "effective_date": "2025-11-01"
        }
    
    def test_consent_form_generation(self, document_tool, valid_customer_data):
        """Test consent form generation"""
        result = document_tool._run(
            json.dumps(valid_customer_data),
            "consent_form"
        )
        
        assert "DOCUMENT GENERATION REPORT" in result
        assert "consent_form" in result.lower()
        assert "[COMPLETE]" in result
    
    def test_policy_application_with_data(
        self,
        document_tool,
        valid_customer_data,
        valid_policy_data
    ):
        """Test policy application generation"""
        # Add coverage_amount to customer data
        valid_customer_data["coverage_amount"] = 500000
        
        result = document_tool._run(
            json.dumps(valid_customer_data),
            "policy_application",
            json.dumps(valid_policy_data)
        )
        
        assert "DOCUMENT GENERATION REPORT" in result
        assert "policy_application" in result.lower()
    
    def test_missing_required_fields(self, document_tool):
        """Test error for missing required fields"""
        incomplete_data = {
            "full_name": "Test User",
            "email": "test@email.com"
            # Missing many required fields
        }
        
        result = document_tool._run(
            json.dumps(incomplete_data),
            "consent_form"
        )
        
        assert "ERROR" in result or "Missing" in result
    
    def test_file_generation(self, document_tool, valid_customer_data):
        """Test that PDF file is actually generated"""
        result = document_tool._run(
            json.dumps(valid_customer_data),
            "consent_form"
        )
        
        # Extract file path from result
        if "File Path:" in result:
            lines = result.split('\n')
            for line in lines:
                if "File Path:" in line:
                    file_path = line.split("File Path:")[1].strip()
                    # Check if file exists
                    assert Path(file_path).exists()
                    # Clean up
                    Path(file_path).unlink()
                    break
    
    def test_invalid_document_type(self, document_tool, valid_customer_data):
        """Test error for invalid document type"""
        result = document_tool._run(
            json.dumps(valid_customer_data),
            "invalid_type"
        )
        
        assert "ERROR" in result or "Unsupported" in result


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_complete_workflow(self):
        """Test complete quote -> underwriting -> document workflow"""
        # Step 1: Generate quote
        quoting_tool = QuotingTool()
        quote_data = {
            "age": 30,
            "gender": "male",
            "address": "123 Main St, New York, NY",
            "location_type": "urban",
            "insurance_type": "auto",
            "vehicle_details": {
                "make": "Honda",
                "model": "Accord",
                "year": 2020,
                "value": 28000
            }
        }
        
        quote_result = quoting_tool._run(json.dumps(quote_data))
        assert "TOTAL MONTHLY PREMIUM:" in quote_result
        
        # Step 2: Underwriting
        underwriting_tool = UnderwritingTool()
        uw_data = {
            "applicant_id": "INT-001",
            "name": "John Smith",
            "age": 30,
            "credit_score": 720,
            "annual_income": 60000,
            "employment_status": "employed",
            "insurance_type": "auto",
            "coverage_amount": 100000,
            "claims_history": {
                "total_claims": 0,
                "claims_last_3_years": 0,
                "total_claimed_amount": 0,
                "fraud_indicators": False
            },
            "driving_record": {
                "years_licensed": 10,
                "accidents_last_5_years": 0,
                "violations_last_3_years": 0,
                "dui_history": False,
                "license_suspended": False
            }
        }
        
        uw_result = underwriting_tool._run(json.dumps(uw_data))
        assert "[APPROVED]" in uw_result
        
        # Step 3: Document generation
        document_tool = DocumentFillingTool()
        doc_data = {
            "full_name": "John Smith",
            "date_of_birth": "1994-01-15",
            "email": "john@email.com",
            "phone": "+1-555-123-4567",
            "street_address": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001"
        }
        
        doc_result = document_tool._run(
            json.dumps(doc_data),
            "consent_form"
        )
        assert "DOCUMENT GENERATION REPORT" in doc_result


# ==================== Pytest Configuration ====================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment"""
    # Create directories if they don't exist
    Path("generated_documents").mkdir(exist_ok=True)
    Path("document_templates").mkdir(exist_ok=True)
    
    yield
    
    # Cleanup after tests
    # Remove test-generated documents
    doc_dir = Path("generated_documents")
    for doc in doc_dir.glob("*TEST*"):
        doc.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

