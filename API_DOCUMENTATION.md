# Insurance AI Agent - API Documentation

Complete API reference for the Insurance AI Agent service.

## Base URL

```
http://localhost:8000
```

## Authentication

All API endpoints (except `/health` and `/`) require authentication using an API key.

**Header:**
```
X-API-Key: your-api-key-here
```

**Example:**
```bash
curl -H "X-API-Key: test-key-12345" \
     http://localhost:8000/api/v1/quote
```

---

## Endpoints

### 1. Health Check

**GET** `/health`

Check API health status.

**Authentication:** Not required

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-03T20:00:00",
  "agent_available": true,
  "tools": {
    "quoting": "available",
    "underwriting": "available",
    "document_filling": "available"
  }
}
```

---

### 2. Generate Quote

**POST** `/api/v1/quote`

Generate insurance quote based on customer data.

**Authentication:** Required

**Request Body:**
```json
{
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
      "value": 45000,
      "usage": "personal"
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Quote generated successfully",
  "data": {
    "result": "... detailed quote report ..."
  },
  "timestamp": "2025-10-03T20:00:00",
  "request_id": "QT-20251003200000"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/quote \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "customer_data": {
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
  }'
```

---

### 3. Perform Underwriting

**POST** `/api/v1/underwriting`

Perform underwriting assessment on applicant.

**Authentication:** Required

**Request Body:**
```json
{
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
      "fraud_indicators": false
    },
    "driving_record": {
      "years_licensed": 15,
      "accidents_last_5_years": 0,
      "violations_last_3_years": 1,
      "dui_history": false,
      "license_suspended": false
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Underwriting completed successfully",
  "data": {
    "result": "... underwriting decision report ..."
  },
  "timestamp": "2025-10-03T20:00:00",
  "request_id": "UW-20251003200000"
}
```

---

### 4. Fill Document

**POST** `/api/v1/document`

Fill insurance document with customer data.

**Authentication:** Required

**Request Body:**
```json
{
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
  "request_signature": false
}
```

**Document Types:**
- `policy_application`
- `claim_form`
- `consent_form`

**Response:**
```json
{
  "success": true,
  "message": "Document generated successfully",
  "data": {
    "result": "... document generation report ..."
  },
  "timestamp": "2025-10-03T20:00:00",
  "request_id": "DOC-20251003200000"
}
```

---

### 5. Run AI Agent

**POST** `/api/v1/agent`

Run AI agent with natural language query.

**Authentication:** Required

**Request Body:**
```json
{
  "query": "Generate a quote for auto insurance for a 30-year-old with a Tesla Model 3 in New York",
  "context": {}
}
```

**Response:**
```json
{
  "success": true,
  "message": "Agent completed successfully",
  "data": {
    "success": true,
    "output": "... agent response ...",
    "intermediate_steps": []
  },
  "timestamp": "2025-10-03T20:00:00",
  "request_id": "AG-20251003200000"
}
```

---

### 6. Clear Agent Memory

**POST** `/api/v1/agent/clear-memory`

Clear agent conversation memory.

**Authentication:** Required

**Response:**
```json
{
  "success": true,
  "message": "Memory cleared successfully",
  "timestamp": "2025-10-03T20:00:00"
}
```

---

### 7. Download Document

**GET** `/api/v1/documents/{document_id}`

Download generated document by ID.

**Authentication:** Required

**Parameters:**
- `document_id` (path): Document identifier

**Response:** PDF file download

**Example:**
```bash
curl -H "X-API-Key: your-key" \
     http://localhost:8000/api/v1/documents/abc123def456 \
     --output document.pdf
```

---

## Error Responses

### 401 Unauthorized

```json
{
  "detail": "API Key required"
}
```

### 403 Forbidden

```json
{
  "detail": "Invalid API Key"
}
```

### 500 Internal Server Error

```json
{
  "success": false,
  "message": "Internal server error",
  "detail": "Error description",
  "timestamp": "2025-10-03T20:00:00"
}
```

---

## Rate Limiting

Default rate limits (configurable):
- 100 requests per minute per API key
- 1000 requests per hour per API key

Exceeded rate limit response:
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

---

## Interactive API Documentation

Visit `/docs` for interactive Swagger UI documentation:
```
http://localhost:8000/docs
```

Visit `/redoc` for ReDoc documentation:
```
http://localhost:8000/redoc
```

---

## Python Client Example

```python
import requests
import json

API_BASE_URL = "http://localhost:8000"
API_KEY = "your-api-key-here"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Generate quote
quote_data = {
    "customer_data": {
        "age": 30,
        "gender": "male",
        "address": "123 Main St",
        "location_type": "urban",
        "insurance_type": "auto",
        "vehicle_details": {
            "make": "Honda",
            "model": "Accord",
            "year": 2020,
            "value": 28000
        }
    }
}

response = requests.post(
    f"{API_BASE_URL}/api/v1/quote",
    headers=headers,
    json=quote_data
)

if response.status_code == 200:
    result = response.json()
    print(result['data']['result'])
else:
    print(f"Error: {response.status_code}")
    print(response.json())
```

---

## JavaScript Client Example

```javascript
const API_BASE_URL = 'http://localhost:8000';
const API_KEY = 'your-api-key-here';

async function generateQuote(customerData) {
    const response = await fetch(`${API_BASE_URL}/api/v1/quote`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Key': API_KEY
        },
        body: JSON.stringify({ customer_data: customerData })
    });
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
}

// Usage
const customerData = {
    age: 30,
    gender: 'male',
    address: '123 Main St',
    location_type: 'urban',
    insurance_type: 'auto',
    vehicle_details: {
        make: 'Honda',
        model: 'Accord',
        year: 2020,
        value: 28000
    }
};

generateQuote(customerData)
    .then(result => console.log(result))
    .catch(error => console.error('Error:', error));
```

---

## WebSocket Support (Future)

Real-time updates for long-running operations:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Update:', data);
};
```

---

## Versioning

API versioning is done via URL path:
- Current: `/api/v1/`
- Future: `/api/v2/`

---

## Support

For API questions and issues:
- Documentation: `/docs`
- GitHub: https://github.com/yourusername/Insurance_AI_Agent
- Email: api-support@yourcompany.com

