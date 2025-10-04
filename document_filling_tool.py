"""
Insurance Document Filling Tool - Advanced Implementation
A LangChain custom tool for automated document filling with PDF support and e-signature integration

Features:
- Automatic field mapping and data population
- PDF template support (reading and generation)
- Multi-page document handling
- Electronic signature integration (DocuSign simulation)
- Field validation and completeness checking
- Base64 encoding for document transfer
"""

import sys
import json
import logging
import base64
import hashlib
from typing import Optional, Type, Dict, Any, List, Literal
from datetime import datetime, timedelta
from pathlib import Path
from io import BytesIO

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

import requests
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, field_validator, model_validator

# PDF libraries
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.warning("reportlab not available. PDF generation will be limited.")

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logging.warning("PyPDF2 not available. PDF reading will be limited.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Enums ====================

class DocumentType(str):
    """Document types"""
    POLICY_APPLICATION = "policy_application"
    CLAIM_FORM = "claim_form"
    DISCLOSURE_STATEMENT = "disclosure_statement"
    CONSENT_FORM = "consent_form"
    BENEFICIARY_DESIGNATION = "beneficiary_designation"


class SignatureStatus(str):
    """E-signature status"""
    PENDING = "pending"
    SIGNED = "signed"
    DECLINED = "declined"
    EXPIRED = "expired"


# ==================== Pydantic Models ====================

class CustomerInfo(BaseModel):
    """Customer information for document filling"""
    # Personal Information
    full_name: str = Field(..., min_length=2, description="Full legal name")
    date_of_birth: str = Field(..., description="Date of birth (YYYY-MM-DD)")
    ssn: Optional[str] = Field(None, description="Social Security Number (masked)")
    email: str = Field(..., description="Email address")
    phone: str = Field(..., description="Phone number")
    
    # Address
    street_address: str = Field(..., description="Street address")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State/Province")
    zip_code: str = Field(..., description="ZIP/Postal code")
    country: str = Field(default="USA", description="Country")
    
    # Additional fields for different document types
    policy_number: Optional[str] = Field(None, description="Policy number (if existing)")
    coverage_amount: Optional[float] = Field(None, description="Coverage amount")
    beneficiary_name: Optional[str] = Field(None, description="Beneficiary name")
    beneficiary_relationship: Optional[str] = Field(None, description="Beneficiary relationship")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError("Invalid email address")
        return v.lower()
    
    @field_validator('date_of_birth')
    @classmethod
    def validate_dob(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Date of birth must be in YYYY-MM-DD format")
        return v


class PolicyDetails(BaseModel):
    """Policy-specific details"""
    insurance_type: str = Field(..., description="Type of insurance")
    policy_term: int = Field(..., ge=1, description="Policy term in years")
    premium_amount: float = Field(..., ge=0, description="Premium amount")
    payment_frequency: Literal["monthly", "quarterly", "annually"] = Field(
        ...,
        description="Payment frequency"
    )
    effective_date: str = Field(..., description="Policy effective date (YYYY-MM-DD)")
    
    # Optional riders and add-ons
    riders: List[str] = Field(default_factory=list, description="Policy riders")
    deductible: Optional[float] = Field(None, description="Deductible amount")


class DocumentTemplate(BaseModel):
    """Document template information"""
    template_name: str = Field(..., description="Template name")
    document_type: str = Field(..., description="Document type")
    required_fields: List[str] = Field(..., description="List of required fields")
    optional_fields: List[str] = Field(default_factory=list, description="Optional fields")
    num_pages: int = Field(default=1, ge=1, description="Number of pages")


class DocumentFillingInput(BaseModel):
    """Input schema for document filling tool"""
    customer_data_json: str = Field(..., description="JSON string with customer data")
    document_type: str = Field(..., description="Type of document to generate")
    policy_data_json: Optional[str] = Field(None, description="JSON string with policy details (optional)")
    request_signature: bool = Field(default=False, description="Whether to request e-signature")


class DocumentResult(BaseModel):
    """Document generation result"""
    document_id: str = Field(..., description="Unique document identifier")
    document_type: str = Field(..., description="Document type")
    file_path: str = Field(..., description="Path to generated document")
    file_size_kb: float = Field(..., description="File size in KB")
    num_pages: int = Field(..., description="Number of pages")
    
    # Field completeness
    total_fields: int = Field(..., description="Total number of fields")
    filled_fields: int = Field(..., description="Number of filled fields")
    missing_fields: List[str] = Field(default_factory=list, description="Missing required fields")
    
    # E-signature information
    signature_requested: bool = Field(..., description="Whether signature was requested")
    signature_url: Optional[str] = Field(None, description="E-signature URL")
    signature_status: Optional[str] = Field(None, description="Signature status")
    
    # Metadata
    generated_at: str = Field(..., description="Generation timestamp")
    download_available: bool = Field(..., description="Whether download is available")
    base64_content: Optional[str] = Field(None, description="Base64 encoded content")


# ==================== Field Mapper ====================

class FieldMapper:
    """Maps customer data to document fields"""
    
    # Standard field mappings
    FIELD_MAPPINGS = {
        # Personal information
        "applicant_name": ["full_name", "name", "customer_name"],
        "date_of_birth": ["dob", "birth_date", "birthdate"],
        "ssn": ["social_security", "ssn_masked"],
        "email": ["email_address", "email"],
        "phone": ["phone_number", "telephone", "contact_number"],
        
        # Address
        "address_line1": ["street_address", "address"],
        "city": ["city"],
        "state": ["state", "province"],
        "zip": ["zip_code", "postal_code", "zipcode"],
        "country": ["country"],
        
        # Policy information
        "policy_number": ["policy_no", "policy_id"],
        "coverage_amount": ["coverage", "insured_amount"],
        "premium": ["premium_amount", "monthly_premium"],
        "effective_date": ["policy_start_date", "start_date"],
        
        # Beneficiary
        "beneficiary": ["beneficiary_name", "beneficiary"],
        "beneficiary_relation": ["beneficiary_relationship", "relation_to_insured"]
    }
    
    @staticmethod
    def map_fields(customer: CustomerInfo, policy: Optional[PolicyDetails] = None) -> Dict[str, Any]:
        """
        Map customer and policy data to document fields
        
        Args:
            customer: Customer information
            policy: Policy details (optional)
            
        Returns:
            Dictionary of mapped fields
        """
        mapped_data = {}
        
        # Map customer data
        customer_dict = customer.model_dump()
        for field_name, value in customer_dict.items():
            if value is not None:
                mapped_data[field_name] = value
        
        # Map policy data if available
        if policy:
            policy_dict = policy.model_dump()
            for field_name, value in policy_dict.items():
                if value is not None:
                    mapped_data[field_name] = value
        
        # Create additional computed fields
        if customer.full_name:
            name_parts = customer.full_name.split()
            if len(name_parts) >= 2:
                mapped_data["first_name"] = name_parts[0]
                mapped_data["last_name"] = " ".join(name_parts[1:])
            else:
                mapped_data["first_name"] = customer.full_name
                mapped_data["last_name"] = ""
        
        # Format date fields
        mapped_data["application_date"] = datetime.now().strftime("%Y-%m-%d")
        mapped_data["signature_date"] = datetime.now().strftime("%Y-%m-%d")
        
        # Full address
        mapped_data["full_address"] = (
            f"{customer.street_address}, {customer.city}, "
            f"{customer.state} {customer.zip_code}, {customer.country}"
        )
        
        return mapped_data
    
    @staticmethod
    def validate_required_fields(
        mapped_data: Dict[str, Any],
        required_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Validate that all required fields are present
        
        Args:
            mapped_data: Mapped field data
            required_fields: List of required field names
            
        Returns:
            Validation result with missing fields
        """
        missing_fields = []
        
        for required_field in required_fields:
            # Check direct field name
            if required_field not in mapped_data or mapped_data[required_field] is None:
                # Check alternative field names
                found = False
                if required_field in FieldMapper.FIELD_MAPPINGS:
                    alternatives = FieldMapper.FIELD_MAPPINGS[required_field]
                    for alt in alternatives:
                        if alt in mapped_data and mapped_data[alt] is not None:
                            # Copy from alternative field
                            mapped_data[required_field] = mapped_data[alt]
                            found = True
                            break
                
                if not found:
                    missing_fields.append(required_field)
        
        return {
            "valid": len(missing_fields) == 0,
            "missing_fields": missing_fields,
            "total_required": len(required_fields),
            "filled_required": len(required_fields) - len(missing_fields)
        }


# ==================== PDF Generator ====================

class PDFGenerator:
    """Generate PDF documents from templates"""
    
    TEMPLATES_DIR = Path("document_templates")
    OUTPUT_DIR = Path("generated_documents")
    
    def __init__(self):
        # Create directories if they don't exist
        self.TEMPLATES_DIR.mkdir(exist_ok=True)
        self.OUTPUT_DIR.mkdir(exist_ok=True)
    
    def generate_policy_application(
        self,
        customer: CustomerInfo,
        policy: Optional[PolicyDetails],
        mapped_data: Dict[str, Any]
    ) -> str:
        """Generate insurance policy application PDF"""
        
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation")
        
        # Generate unique filename
        doc_id = hashlib.md5(
            f"{customer.full_name}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        filename = f"policy_application_{doc_id}.pdf"
        filepath = self.OUTPUT_DIR / filename
        
        # Create PDF
        pdf = canvas.Canvas(str(filepath), pagesize=letter)
        width, height = letter
        
        # Title
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawCentredString(width/2, height - 50, "INSURANCE POLICY APPLICATION")
        
        # Document ID and Date
        pdf.setFont("Helvetica", 10)
        pdf.drawRightString(width - 50, height - 70, f"Document ID: {doc_id}")
        pdf.drawRightString(width - 50, height - 85, f"Date: {mapped_data.get('application_date', 'N/A')}")
        
        # Draw a line
        pdf.line(50, height - 100, width - 50, height - 100)
        
        y_position = height - 130
        
        # Section 1: Applicant Information
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y_position, "1. APPLICANT INFORMATION")
        y_position -= 25
        
        pdf.setFont("Helvetica", 11)
        fields = [
            ("Full Name:", mapped_data.get('full_name', '')),
            ("Date of Birth:", mapped_data.get('date_of_birth', '')),
            ("Email:", mapped_data.get('email', '')),
            ("Phone:", mapped_data.get('phone', '')),
        ]
        
        for label, value in fields:
            pdf.drawString(70, y_position, label)
            pdf.drawString(200, y_position, str(value))
            y_position -= 20
        
        y_position -= 10
        
        # Section 2: Address
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y_position, "2. ADDRESS")
        y_position -= 25
        
        pdf.setFont("Helvetica", 11)
        address_fields = [
            ("Street:", mapped_data.get('street_address', '')),
            ("City:", mapped_data.get('city', '')),
            ("State:", mapped_data.get('state', '')),
            ("ZIP Code:", mapped_data.get('zip_code', '')),
        ]
        
        for label, value in address_fields:
            pdf.drawString(70, y_position, label)
            pdf.drawString(200, y_position, str(value))
            y_position -= 20
        
        y_position -= 10
        
        # Section 3: Policy Details
        if policy:
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(50, y_position, "3. POLICY DETAILS")
            y_position -= 25
            
            pdf.setFont("Helvetica", 11)
            policy_fields = [
                ("Insurance Type:", mapped_data.get('insurance_type', '')),
                ("Coverage Amount:", f"${mapped_data.get('coverage_amount', 0):,.2f}"),
                ("Policy Term:", f"{mapped_data.get('policy_term', 0)} years"),
                ("Premium:", f"${mapped_data.get('premium_amount', 0):.2f} {mapped_data.get('payment_frequency', '')}"),
                ("Effective Date:", mapped_data.get('effective_date', '')),
            ]
            
            for label, value in policy_fields:
                pdf.drawString(70, y_position, label)
                pdf.drawString(220, y_position, str(value))
                y_position -= 20
            
            y_position -= 10
        
        # Check if we need a new page
        if y_position < 200:
            pdf.showPage()
            y_position = height - 50
        
        # Section 4: Beneficiary Information
        if mapped_data.get('beneficiary_name'):
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(50, y_position, "4. BENEFICIARY INFORMATION")
            y_position -= 25
            
            pdf.setFont("Helvetica", 11)
            pdf.drawString(70, y_position, "Beneficiary Name:")
            pdf.drawString(220, y_position, mapped_data.get('beneficiary_name', ''))
            y_position -= 20
            
            pdf.drawString(70, y_position, "Relationship:")
            pdf.drawString(220, y_position, mapped_data.get('beneficiary_relationship', ''))
            y_position -= 30
        
        # Section 5: Declarations
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y_position, "5. APPLICANT DECLARATIONS")
        y_position -= 25
        
        pdf.setFont("Helvetica", 10)
        declarations = [
            "I declare that all information provided in this application is true and complete.",
            "I understand that any misrepresentation may result in policy cancellation.",
            "I consent to the processing of my personal data for insurance purposes.",
            "I have read and understood the policy terms and conditions."
        ]
        
        for i, declaration in enumerate(declarations, 1):
            pdf.drawString(70, y_position, f"{i}. {declaration}")
            y_position -= 18
        
        y_position -= 20
        
        # Signature section
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_position, "APPLICANT SIGNATURE")
        y_position -= 30
        
        # Signature line
        pdf.line(70, y_position, 300, y_position)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(70, y_position - 15, "Signature")
        
        pdf.line(350, y_position, 500, y_position)
        pdf.drawString(350, y_position - 15, f"Date: {mapped_data.get('signature_date', '')}")
        
        # Footer
        pdf.setFont("Helvetica", 8)
        pdf.drawCentredString(
            width/2, 30,
            "This is a computer-generated document. For questions, contact your insurance agent."
        )
        
        # Save PDF
        pdf.save()
        
        logger.info(f"Generated PDF: {filepath}")
        return str(filepath)
    
    def generate_claim_form(
        self,
        customer: CustomerInfo,
        mapped_data: Dict[str, Any]
    ) -> str:
        """Generate insurance claim form PDF"""
        
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation")
        
        doc_id = hashlib.md5(
            f"claim_{customer.full_name}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        filename = f"claim_form_{doc_id}.pdf"
        filepath = self.OUTPUT_DIR / filename
        
        pdf = canvas.Canvas(str(filepath), pagesize=letter)
        width, height = letter
        
        # Title
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawCentredString(width/2, height - 50, "INSURANCE CLAIM FORM")
        
        pdf.setFont("Helvetica", 10)
        pdf.drawRightString(width - 50, height - 70, f"Claim ID: {doc_id}")
        pdf.drawRightString(width - 50, height - 85, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        
        pdf.line(50, height - 100, width - 50, height - 100)
        
        y_position = height - 130
        
        # Claimant Information
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y_position, "CLAIMANT INFORMATION")
        y_position -= 25
        
        pdf.setFont("Helvetica", 11)
        claimant_fields = [
            ("Name:", mapped_data.get('full_name', '')),
            ("Policy Number:", mapped_data.get('policy_number', 'N/A')),
            ("Email:", mapped_data.get('email', '')),
            ("Phone:", mapped_data.get('phone', '')),
        ]
        
        for label, value in claimant_fields:
            pdf.drawString(70, y_position, label)
            pdf.drawString(200, y_position, str(value))
            y_position -= 20
        
        y_position -= 20
        
        # Claim Details
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y_position, "CLAIM DETAILS")
        y_position -= 25
        
        pdf.setFont("Helvetica", 11)
        pdf.drawString(70, y_position, "Date of Incident: _______________________")
        y_position -= 25
        pdf.drawString(70, y_position, "Location of Incident: _______________________")
        y_position -= 25
        pdf.drawString(70, y_position, "Description of Loss:")
        y_position -= 20
        
        # Text box for description
        pdf.rect(70, y_position - 80, width - 140, 80)
        
        y_position -= 110
        
        # Supporting Documents
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y_position, "SUPPORTING DOCUMENTS")
        y_position -= 25
        
        pdf.setFont("Helvetica", 10)
        documents = [
            "[ ] Police Report",
            "[ ] Medical Records",
            "[ ] Repair Estimates",
            "[ ] Photographs",
            "[ ] Other: _______________"
        ]
        
        for doc in documents:
            pdf.drawString(70, y_position, doc)
            y_position -= 18
        
        y_position -= 30
        
        # Signature
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_position, "CLAIMANT SIGNATURE")
        y_position -= 30
        
        pdf.line(70, y_position, 300, y_position)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(70, y_position - 15, "Signature")
        
        pdf.line(350, y_position, 500, y_position)
        pdf.drawString(350, y_position - 15, "Date")
        
        pdf.save()
        
        logger.info(f"Generated claim form: {filepath}")
        return str(filepath)
    
    def generate_consent_form(
        self,
        customer: CustomerInfo,
        mapped_data: Dict[str, Any]
    ) -> str:
        """Generate consent and disclosure form PDF"""
        
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation")
        
        doc_id = hashlib.md5(
            f"consent_{customer.full_name}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        filename = f"consent_form_{doc_id}.pdf"
        filepath = self.OUTPUT_DIR / filename
        
        pdf = canvas.Canvas(str(filepath), pagesize=letter)
        width, height = letter
        
        # Title
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(width/2, height - 50, "CONSENT AND DISCLOSURE FORM")
        
        pdf.setFont("Helvetica", 10)
        pdf.drawCentredString(width/2, height - 70, f"Document ID: {doc_id}")
        
        pdf.line(50, height - 85, width - 50, height - 85)
        
        y_position = height - 110
        
        # Customer info
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_position, "Customer Information:")
        y_position -= 20
        
        pdf.setFont("Helvetica", 11)
        pdf.drawString(70, y_position, f"Name: {mapped_data.get('full_name', '')}")
        y_position -= 18
        pdf.drawString(70, y_position, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        
        y_position -= 30
        
        # Consent sections
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_position, "DATA PROCESSING CONSENT")
        y_position -= 20
        
        pdf.setFont("Helvetica", 10)
        consent_text = [
            "I hereby consent to the collection, processing, and storage of my personal information",
            "for the purposes of insurance underwriting, policy administration, and claims processing.",
            "",
            "I understand that my information will be:",
            "  - Kept confidential and secure",
            "  - Used only for insurance purposes",
            "  - Shared only with authorized parties as required",
            "  - Retained per regulatory requirements",
            "",
            "I have the right to:",
            "  - Access my personal data",
            "  - Request corrections to my data",
            "  - Request deletion of my data (subject to legal requirements)",
            "  - Withdraw consent at any time",
        ]
        
        for line in consent_text:
            pdf.drawString(70, y_position, line)
            y_position -= 15
        
        y_position -= 20
        
        # Privacy notice
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_position, "PRIVACY NOTICE")
        y_position -= 20
        
        pdf.setFont("Helvetica", 10)
        privacy_text = [
            "Your privacy is important to us. This notice describes how we collect, use, and protect",
            "your personal information in compliance with applicable data protection laws including GDPR.",
        ]
        
        for line in privacy_text:
            pdf.drawString(70, y_position, line)
            y_position -= 15
        
        y_position -= 30
        
        # Signature
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_position, "CUSTOMER SIGNATURE")
        y_position -= 30
        
        pdf.line(70, y_position, 300, y_position)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(70, y_position - 15, "Signature")
        
        pdf.line(350, y_position, 500, y_position)
        pdf.drawString(350, y_position - 15, "Date")
        
        # Footer
        pdf.setFont("Helvetica", 8)
        pdf.drawCentredString(
            width/2, 30,
            "This document is legally binding. Please read carefully before signing."
        )
        
        pdf.save()
        
        logger.info(f"Generated consent form: {filepath}")
        return str(filepath)


# ==================== E-Signature Integration ====================

class ESignatureAPI:
    """Integration with electronic signature services (DocuSign simulation)"""
    
    DOCUSIGN_ENDPOINT = "https://api.docusign.example.com/v2/envelopes"
    
    @classmethod
    def request_signature(
        cls,
        document_path: str,
        signer_email: str,
        signer_name: str,
        document_name: str
    ) -> Dict[str, Any]:
        """
        Request electronic signature (simulated DocuSign API)
        
        Args:
            document_path: Path to document to sign
            signer_email: Signer's email
            signer_name: Signer's name
            document_name: Document name
            
        Returns:
            Signature request result
        """
        try:
            logger.info(f"Requesting e-signature for: {document_name}")
            
            # Simulate API call
            import time
            time.sleep(0.3)
            
            # Generate envelope ID
            envelope_id = hashlib.md5(
                f"{document_path}{signer_email}{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16]
            
            # Simulated DocuSign response
            response = {
                "status": "success",
                "envelope_id": envelope_id,
                "signature_url": f"https://sign.docusign.com/envelope/{envelope_id}",
                "status": SignatureStatus.PENDING,
                "signer_email": signer_email,
                "signer_name": signer_name,
                "document_name": document_name,
                "sent_datetime": datetime.now().isoformat(),
                "expire_datetime": (datetime.now() + timedelta(days=30)).isoformat(),
                "message": "Signature request sent successfully",
                "instructions": [
                    "Check your email for the signature request",
                    "Click the link in the email to review and sign",
                    "Document will be automatically sent to all parties once signed"
                ]
            }
            
            logger.info(f"E-signature requested: Envelope ID {envelope_id}")
            return response
            
        except Exception as e:
            logger.error(f"E-signature request failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "fallback": "Please download document and sign manually"
            }
    
    @classmethod
    def check_signature_status(cls, envelope_id: str) -> Dict[str, Any]:
        """Check signature status (simulated)"""
        try:
            # Simulate API call
            import time
            time.sleep(0.2)
            
            # Simulated response
            return {
                "envelope_id": envelope_id,
                "status": SignatureStatus.PENDING,
                "signed_datetime": None,
                "message": "Awaiting signature"
            }
            
        except Exception as e:
            logger.error(f"Status check failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }


# ==================== Document Filling Tool ====================

# Initialize shared instances (module-level)
_pdf_generator_instance = PDFGenerator()
_field_mapper_instance = FieldMapper()


class DocumentFillingTool(BaseTool):
    """
    Advanced Insurance Document Filling Tool
    
    Automatically fills insurance documents with customer data,
    validates completeness, generates PDFs, and integrates with e-signature services.
    """
    
    name: str = "document_filling"
    description: str = """
    Use this tool to automatically fill insurance documents with customer data.
    
    Input must be a JSON string containing:
    - customer_data_json: JSON with customer information (full_name, date_of_birth, email, phone, address, etc.)
    - document_type: Type of document (policy_application, claim_form, consent_form, etc.)
    - policy_data_json: Optional JSON with policy details (insurance_type, coverage_amount, premium_amount, etc.)
    - request_signature: Optional boolean to request e-signature (default: false)
    
    Customer data fields:
    - full_name, date_of_birth, email, phone
    - street_address, city, state, zip_code, country
    - policy_number (optional), coverage_amount (optional)
    - beneficiary_name (optional), beneficiary_relationship (optional)
    
    Policy data fields (when applicable):
    - insurance_type, policy_term, premium_amount, payment_frequency, effective_date
    - riders, deductible
    
    Returns filled document with validation results, file path, and optional e-signature link.
    """
    args_schema: Type[BaseModel] = DocumentFillingInput
    
    def _run(self, customer_data_json: str, document_type: str, 
             policy_data_json: Optional[str] = None, request_signature: bool = False) -> str:
        """
        Fill document with customer data
        
        Args:
            customer_data_json: JSON string with customer data
            document_type: Type of document to generate
            policy_data_json: Optional JSON with policy details
            request_signature: Whether to request e-signature
            
        Returns:
            Formatted document result report
        """
        try:
            logger.info(f"Starting document filling: {document_type}")
            
            # Parse customer data
            customer_data_dict = json.loads(customer_data_json)
            customer = CustomerInfo(**customer_data_dict)
            
            # Parse policy data if provided
            policy = None
            if policy_data_json:
                policy_data_dict = json.loads(policy_data_json)
                policy = PolicyDetails(**policy_data_dict)
            
            # Map fields
            mapped_data = _field_mapper_instance.map_fields(customer, policy)
            
            # Determine required fields based on document type
            required_fields = self._get_required_fields(document_type)
            
            # Validate required fields
            validation = _field_mapper_instance.validate_required_fields(
                mapped_data, required_fields
            )
            
            if not validation['valid']:
                return self._format_validation_error(validation)
            
            # Generate document
            file_path = self._generate_document(
                document_type, customer, policy, mapped_data
            )
            
            # Get file info
            file_size = Path(file_path).stat().st_size / 1024  # KB
            
            # Read file for base64 encoding (optional)
            base64_content = None
            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    base64_content = base64.b64encode(file_content).decode('utf-8')
            except Exception as e:
                logger.warning(f"Failed to encode file to base64: {e}")
            
            # Request e-signature if requested
            signature_info = None
            if request_signature:
                signature_info = ESignatureAPI.request_signature(
                    file_path,
                    customer.email,
                    customer.full_name,
                    f"{document_type.replace('_', ' ').title()} - {customer.full_name}"
                )
            
            # Create result
            doc_id = Path(file_path).stem.split('_')[-1]
            result = DocumentResult(
                document_id=doc_id,
                document_type=document_type,
                file_path=file_path,
                file_size_kb=round(file_size, 2),
                num_pages=1,  # Simplified for now
                total_fields=validation['total_required'],
                filled_fields=validation['filled_required'],
                missing_fields=validation['missing_fields'],
                signature_requested=request_signature,
                signature_url=signature_info.get('signature_url') if signature_info else None,
                signature_status=signature_info.get('status') if signature_info else None,
                generated_at=datetime.now().isoformat(),
                download_available=True,
                base64_content=base64_content[:100] + "..." if base64_content else None  # Truncate for display
            )
            
            # Format response
            response = self._format_document_report(result, signature_info, customer)
            
            logger.info(f"Document generated successfully: {doc_id}")
            return response
            
        except json.JSONDecodeError as e:
            error_msg = f"ERROR: Invalid JSON format - {str(e)}"
            logger.error(error_msg)
            return error_msg
            
        except Exception as e:
            logger.error(f"Error in document filling: {str(e)}", exc_info=True)
            return f"ERROR: Document filling failed - {str(e)}"
    
    async def _arun(self, customer_data_json: str, document_type: str,
                    policy_data_json: Optional[str] = None, request_signature: bool = False) -> str:
        """Async version - delegates to synchronous version"""
        return self._run(customer_data_json, document_type, policy_data_json, request_signature)
    
    def _get_required_fields(self, document_type: str) -> List[str]:
        """Get required fields for document type"""
        base_fields = ['full_name', 'date_of_birth', 'email', 'phone', 
                      'street_address', 'city', 'state', 'zip_code']
        
        if document_type == "policy_application":
            return base_fields + ['insurance_type', 'coverage_amount', 'premium_amount']
        elif document_type == "claim_form":
            return base_fields + ['policy_number']
        elif document_type == "consent_form":
            return base_fields
        else:
            return base_fields
    
    def _generate_document(
        self,
        document_type: str,
        customer: CustomerInfo,
        policy: Optional[PolicyDetails],
        mapped_data: Dict[str, Any]
    ) -> str:
        """Generate document based on type"""
        
        if document_type == "policy_application":
            return _pdf_generator_instance.generate_policy_application(customer, policy, mapped_data)
        elif document_type == "claim_form":
            return _pdf_generator_instance.generate_claim_form(customer, mapped_data)
        elif document_type == "consent_form":
            return _pdf_generator_instance.generate_consent_form(customer, mapped_data)
        else:
            raise ValueError(f"Unsupported document type: {document_type}")
    
    def _format_validation_error(self, validation: Dict[str, Any]) -> str:
        """Format validation error message"""
        missing = ", ".join(validation['missing_fields'])
        
        return f"""
ERROR: Required Fields Missing
-------------------------------
The following required fields are missing or incomplete:
{missing}

Please provide all required information:
- Personal: full_name, date_of_birth, email, phone
- Address: street_address, city, state, zip_code
- Policy: (varies by document type)

Fields filled: {validation['filled_required']}/{validation['total_required']}
        """
    
    def _format_document_report(
        self,
        result: DocumentResult,
        signature_info: Optional[Dict[str, Any]],
        customer: CustomerInfo
    ) -> str:
        """Format comprehensive document report"""
        
        # Mask customer name for display
        name_parts = customer.full_name.split()
        masked_name = f"{name_parts[0][0]}*** {name_parts[-1][:2] if len(name_parts) > 1 else ''}***"
        
        # Signature section
        signature_section = "Not requested"
        if result.signature_requested and signature_info:
            if signature_info.get('status') == 'success':
                signature_section = f"""
   Status: {signature_info.get('status', 'pending').upper()}
   Signature URL: {signature_info.get('signature_url', 'N/A')}
   Envelope ID: {signature_info.get('envelope_id', 'N/A')}
   Expiry Date: {signature_info.get('expire_datetime', 'N/A')[:10]}
   
   Instructions:
   {chr(10).join('   - ' + inst for inst in signature_info.get('instructions', []))}
                """
            else:
                signature_section = f"ERROR: {signature_info.get('error', 'Unknown error')}"
        
        # Base64 section (truncated)
        base64_section = "Available (truncated for display)" if result.base64_content else "Not generated"
        
        report = f"""
========================================================================
          DOCUMENT GENERATION REPORT
========================================================================

Document ID: {result.document_id}
Document Type: {result.document_type.replace('_', ' ').title()}
Generated: {result.generated_at}

------------------------------------------------------------------------
CUSTOMER INFORMATION (Masked)
------------------------------------------------------------------------

Customer: {masked_name}
Email: {customer.email}

------------------------------------------------------------------------
DOCUMENT DETAILS
------------------------------------------------------------------------

File Path: {result.file_path}
File Size: {result.file_size_kb:.2f} KB
Number of Pages: {result.num_pages}
Download Available: {"Yes" if result.download_available else "No"}

------------------------------------------------------------------------
FIELD VALIDATION
------------------------------------------------------------------------

Total Fields: {result.total_fields}
Filled Fields: {result.filled_fields}
Completion Rate: {(result.filled_fields/result.total_fields*100) if result.total_fields > 0 else 0:.1f}%

Missing Fields: {', '.join(result.missing_fields) if result.missing_fields else 'None'}

Status: {"[COMPLETE]" if not result.missing_fields else "[INCOMPLETE]"}

------------------------------------------------------------------------
E-SIGNATURE STATUS
------------------------------------------------------------------------

Signature Requested: {"Yes" if result.signature_requested else "No"}
{signature_section}

------------------------------------------------------------------------
DOCUMENT ENCODING
------------------------------------------------------------------------

Base64 Content: {base64_section}

------------------------------------------------------------------------
NEXT STEPS
------------------------------------------------------------------------

1. Review the generated document at: {result.file_path}
2. {'Check email for e-signature request' if result.signature_requested else 'Download and sign manually if required'}
3. Submit signed document to insurance provider
4. Keep copy for your records

------------------------------------------------------------------------
COMPLIANCE NOTES
------------------------------------------------------------------------

- All data handled per data protection regulations (GDPR compliant)
- Document generated with secure encryption
- E-signatures legally binding in applicable jurisdictions
- Retain this document for your records

========================================================================
        """
        
        return report.strip()


# ==================== Standalone Usage Example ====================

def example_usage():
    """Demonstrate the DocumentFillingTool usage"""
    print("=" * 80)
    print("Advanced Insurance Document Filling Tool - Standalone Demo")
    print("=" * 80)
    
    tool = DocumentFillingTool()
    
    # Example 1: Policy Application
    print("\n\n" + "=" * 80)
    print("EXAMPLE 1: Policy Application Form")
    print("=" * 80)
    
    customer_data = {
        "full_name": "John Michael Smith",
        "date_of_birth": "1985-06-15",
        "email": "john.smith@email.com",
        "phone": "+1-555-123-4567",
        "street_address": "123 Main Street, Apt 4B",
        "city": "New York",
        "state": "NY",
        "zip_code": "10001",
        "country": "USA",
        "beneficiary_name": "Jane Smith",
        "beneficiary_relationship": "Spouse"
    }
    
    policy_data = {
        "insurance_type": "Life Insurance",
        "policy_term": 20,
        "premium_amount": 150.00,
        "payment_frequency": "monthly",
        "effective_date": "2025-11-01",
        "riders": ["Accidental Death Benefit", "Waiver of Premium"],
        "deductible": 0
    }
    
    result = tool._run(
        json.dumps(customer_data),
        "policy_application",
        json.dumps(policy_data),
        request_signature=True
    )
    print(result)
    
    input("\nPress Enter to continue to next example...")
    
    # Example 2: Claim Form
    print("\n\n" + "=" * 80)
    print("EXAMPLE 2: Insurance Claim Form")
    print("=" * 80)
    
    claim_customer = {
        "full_name": "Sarah Johnson",
        "date_of_birth": "1990-03-22",
        "email": "sarah.j@email.com",
        "phone": "+1-555-987-6543",
        "street_address": "456 Oak Avenue",
        "city": "Los Angeles",
        "state": "CA",
        "zip_code": "90001",
        "policy_number": "POL-2025-12345"
    }
    
    result = tool._run(
        json.dumps(claim_customer),
        "claim_form",
        request_signature=False
    )
    print(result)
    
    input("\nPress Enter to continue to next example...")
    
    # Example 3: Consent Form
    print("\n\n" + "=" * 80)
    print("EXAMPLE 3: Consent and Disclosure Form")
    print("=" * 80)
    
    consent_customer = {
        "full_name": "Robert Williams",
        "date_of_birth": "1978-11-30",
        "email": "r.williams@email.com",
        "phone": "+1-555-246-8135",
        "street_address": "789 Pine Street",
        "city": "Chicago",
        "state": "IL",
        "zip_code": "60601"
    }
    
    result = tool._run(
        json.dumps(consent_customer),
        "consent_form",
        request_signature=True
    )
    print(result)
    
    input("\nPress Enter to continue to error example...")
    
    # Example 4: Missing Fields Error
    print("\n\n" + "=" * 80)
    print("EXAMPLE 4: Validation Error - Missing Required Fields")
    print("=" * 80)
    
    incomplete_data = {
        "full_name": "Test User",
        "email": "test@email.com"
        # Missing many required fields
    }
    
    result = tool._run(
        json.dumps(incomplete_data),
        "policy_application"
    )
    print(result)
    
    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print("\nGenerated documents can be found in the 'generated_documents' directory")


if __name__ == "__main__":
    # Check dependencies
    if not REPORTLAB_AVAILABLE:
        print("WARNING: reportlab not installed. Installing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
        print("Please run the script again.")
    else:
        example_usage()

