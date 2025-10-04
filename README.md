# Insurance AI Agent

## 🚀 AI-Powered Insurance Automation Platform

An advanced, production-ready insurance automation system built with LangChain and OpenAI GPT-4. This intelligent platform automates the complete insurance workflow including quote generation, underwriting assessment, and document filling through natural language interaction and REST API.

## 🌟 Key Features

### Core Capabilities
- **🤖 AI-Powered Agent**: Natural language processing with LangChain and GPT-4
- **💰 Intelligent Quoting**: Automated insurance quote generation with comprehensive rate tables
- **📊 Smart Underwriting**: ML-based risk assessment with rule engine and decision tree classifier
- **📄 Document Automation**: PDF generation and electronic signature integration
- **🔐 Secure API**: FastAPI-based REST API with key authentication
- **🐳 Production Ready**: Docker containerization and cloud deployment support

### Insurance Types Supported
- Auto Insurance
- Health Insurance  
- Life Insurance
- Home Insurance

## 🛠️ Technology Stack

- **Framework**: LangChain, FastAPI
- **AI/ML**: OpenAI GPT-4, scikit-learn
- **PDF Processing**: ReportLab, PyPDF2
- **API**: FastAPI, Uvicorn
- **Testing**: Pytest
- **Deployment**: Docker, Docker Compose
- **Cloud**: AWS, Heroku, Azure support

## 📋 Features

- **Insurance Quoting**: Automatically calculates insurance premiums based on customer information
- **Underwriting Assessment**: Performs risk evaluation and provides approval decisions
- **Document Filling**: Generates insurance application forms and policy documents
- **ReAct Agent**: Uses reasoning and action framework for intelligent decision making
- **Conversation Memory**: Maintains context across multiple interactions
- **GDPR Compliance**: Built with data privacy and security best practices
- **Structured Output**: Returns JSON-formatted responses for easy integration

## 🏗️ Architecture

The agent uses LangChain's ReAct (Reasoning + Acting) framework with three custom tools:

1. **QuotingTool**: Calculates insurance premiums based on customer profile
2. **UnderwritingTool**: Assesses risk and determines approval status
3. **DocumentFillingTool**: Generates policy documents with collected information

```
User Query → ReAct Agent → Tool Selection → Tool Execution → Response
                ↓
         [Conversation Memory]
```

## 📋 Requirements

- Python 3.8 or higher
- OpenAI API key (GPT-4 access)
- See `requirements.txt` for package dependencies

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Insurance_AI_Agent
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up OpenAI API key**
   ```bash
   # Windows PowerShell
   $env:OPENAI_API_KEY="your-api-key-here"

   # Windows Command Prompt
   set OPENAI_API_KEY=your-api-key-here

   # Linux/Mac
   export OPENAI_API_KEY="your-api-key-here"
   ```

   Alternatively, create a `.env` file in the project root:
   ```
   OPENAI_API_KEY=your-api-key-here
   ```

## 💻 Usage

### Basic Usage

Run the agent with example queries:
```bash
python insurance_agent.py
```

### Interactive Mode

After running the script, you can interact with the agent in interactive mode:

```
💬 Your query: Calculate auto insurance for a 30-year-old with a Honda Civic in New York

🤖 Agent Response: [Insurance quote details...]
```

### Example Queries

**English:**
- "Calculate auto insurance quote for a 25-year-old with Tesla Model 3 in Beijing"
- "Perform underwriting assessment for a 35-year-old applying for life insurance"
- "Generate insurance application document for home insurance"

**中文:**
- "计算汽车保险报价：年龄25，车辆型号Tesla Model 3，地址北京"
- "评估一个35岁客户的人寿保险承保风险"
- "生成家庭保险申请文件"

### Programmatic Usage

```python
from insurance_agent import InsuranceAgent

# Initialize the agent
agent = InsuranceAgent(openai_api_key="your-api-key")

# Run a query
result = agent.run("Calculate auto insurance for age 25, Tesla Model 3, Beijing")

# Access the response
if result["success"]:
    print(result["response"])
else:
    print(f"Error: {result['error']}")

# Clear memory for new conversation
agent.clear_memory()
```

## 🛠️ Custom Tools

### QuotingTool
Calculates insurance premiums based on:
- Customer age
- Insurance type (auto, home, life, health)
- Asset details (vehicle model, property value, etc.)
- Location

**Output:** Quote ID, premium amount, coverage details, deductible

### UnderwritingTool
Performs risk assessment considering:
- Age demographics
- Location risk factors
- Asset value and type
- Historical risk patterns

**Output:** Approval status, risk rating, conditions, assessment ID

### DocumentFillingTool
Generates insurance documents including:
- Applicant information
- Policy details
- Legal declarations
- GDPR compliance notices

**Output:** Formatted document with all sections

## 🔒 Security & Compliance

- **Data Privacy**: Sensitive information is not stored permanently
- **GDPR Compliance**: All data handling follows GDPR regulations
- **Audit Trail**: All transactions are logged with timestamps
- **Encryption**: Secure data handling practices
- **Compliance Notices**: Built-in privacy notices in documents

## 📊 Output Format

All responses are structured with:
```json
{
  "success": true/false,
  "query": "Original user query",
  "response": "Agent's response text",
  "timestamp": "ISO 8601 timestamp",
  "compliance_note": "Privacy compliance message"
}
```

## 🧪 Demo Mode

If you don't have an OpenAI API key, you can still test the tools:
```bash
python insurance_agent.py
# Press Enter when prompted for API key to enter demo mode
```

Demo mode shows the capabilities of each tool without requiring LLM access.

## 🎯 Use Cases

1. **Insurance Companies**: Automate initial quote generation and assessment
2. **Insurance Brokers**: Quick quotes for multiple insurance types
3. **Customer Service**: 24/7 automated insurance information
4. **Compliance Teams**: Standardized document generation

## ⚙️ Configuration

### Model Selection
Change the LLM model in `insurance_agent.py`:
```python
self.llm = ChatOpenAI(
    model="gpt-4",  # or "gpt-3.5-turbo" for faster/cheaper responses
    temperature=0.2,
    openai_api_key=self.api_key
)
```

### Memory Settings
Adjust conversation memory:
```python
from langchain.memory import ConversationBufferWindowMemory

self.memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    k=5,  # Keep last 5 interactions
    return_messages=True
)
```

## 🐛 Troubleshooting

**Issue: "OpenAI API key not found"**
- Solution: Set the OPENAI_API_KEY environment variable or pass it to the agent

**Issue: "Rate limit exceeded"**
- Solution: Wait a moment and retry, or upgrade your OpenAI plan

**Issue: "Tool execution error"**
- Solution: Check the logs for detailed error messages and ensure input format is correct

## 📝 Logging

The agent uses Python's logging module. Adjust log level in `insurance_agent.py`:
```python
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for more details
```

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

See LICENSE file for details.

## 🔮 Future Enhancements

- [ ] Integration with real insurance APIs
- [ ] Multi-language support
- [ ] Web interface (FastAPI/Streamlit)
- [ ] Database integration for persistent storage
- [ ] Advanced risk models with ML
- [ ] Claims processing automation
- [ ] Policy renewal automation

## 📧 Support

For questions or issues, please open an issue on GitHub.

---

**Note**: This is a demonstration project. For production use, additional security measures, comprehensive testing, and regulatory compliance reviews are required.
An AI Agent for Insurance Agent fully automates insurance quoting/underwriting/document completion
