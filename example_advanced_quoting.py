"""
Example: Using Advanced QuotingTool with Insurance Agent
Demonstrates how to integrate the advanced quoting tool into the main agent
"""

import os
import json
from langchain.agents import AgentType, initialize_agent
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI

# Import the advanced quoting tool
from quoting_tool import QuotingTool


def example_1_direct_tool_usage():
    """Example 1: Using the QuotingTool directly without agent"""
    print("\n" + "=" * 80)
    print("Example 1: Direct Tool Usage")
    print("=" * 80)
    
    tool = QuotingTool()
    
    # Prepare customer data
    customer_data = {
        "age": 28,
        "gender": "female",
        "address": "123 Main Street, San Francisco, CA 94102",
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
    
    # Call the tool
    result = tool._run(json.dumps(customer_data))
    print(result)


def example_2_agent_integration():
    """Example 2: Using QuotingTool with LangChain Agent"""
    print("\n" + "=" * 80)
    print("Example 2: Agent Integration")
    print("=" * 80)
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY not found. Skipping agent integration example.")
        print("Set your API key to run this example:")
        print("  export OPENAI_API_KEY='your-api-key-here'")
        return
    
    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.2,
        openai_api_key=api_key
    )
    
    # Initialize tools
    tools = [QuotingTool()]
    
    # Initialize memory
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key="output"
    )
    
    # Initialize agent
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        memory=memory,
        verbose=True,
        handle_parsing_errors=True
    )
    
    # Test queries
    queries = [
        """Generate an auto insurance quote for:
        - 30 year old male
        - Living in Chicago (urban area)
        - Drives a 2021 BMW X5 worth $60,000
        - Personal use""",
        
        """Generate a health insurance quote for:
        - 45 year old female
        - Living in suburban Seattle
        - Non-smoker
        - No pre-existing conditions
        - BMI: 23.5
        - Regular exercise"""
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n--- Query {i} ---")
        print(query)
        print("\n--- Agent Response ---")
        
        try:
            response = agent.invoke({"input": query})
            print(response.get("output", ""))
        except Exception as e:
            print(f"Error: {str(e)}")


def example_3_structured_input():
    """Example 3: Building structured input programmatically"""
    print("\n" + "=" * 80)
    print("Example 3: Structured Input Builder")
    print("=" * 80)
    
    tool = QuotingTool()
    
    # Example: Health insurance with comprehensive details
    health_quote_data = {
        "age": 52,
        "gender": "male",
        "address": "456 Oak Avenue, Boston, MA 02101",
        "location_type": "urban",
        "insurance_type": "health",
        "health_details": {
            "smoker": False,
            "pre_existing_conditions": True,
            "bmi": 28.5,
            "exercise_frequency": "occasional"
        }
    }
    
    print("\nInput Data:")
    print(json.dumps(health_quote_data, indent=2))
    
    print("\n\nGenerated Quote:")
    result = tool._run(json.dumps(health_quote_data))
    print(result)


def example_4_batch_quotes():
    """Example 4: Generate multiple quotes in batch"""
    print("\n" + "=" * 80)
    print("Example 4: Batch Quote Generation")
    print("=" * 80)
    
    tool = QuotingTool()
    
    # Multiple customers
    customers = [
        {
            "name": "John Doe",
            "data": {
                "age": 25,
                "gender": "male",
                "address": "789 Pine St, Los Angeles, CA",
                "location_type": "urban",
                "insurance_type": "auto",
                "vehicle_details": {
                    "make": "Toyota",
                    "model": "Camry",
                    "year": 2019,
                    "value": 22000,
                    "usage": "personal"
                }
            }
        },
        {
            "name": "Jane Smith",
            "data": {
                "age": 35,
                "gender": "female",
                "address": "321 Elm St, Austin, TX",
                "location_type": "suburban",
                "insurance_type": "auto",
                "vehicle_details": {
                    "make": "Ford",
                    "model": "Explorer",
                    "year": 2021,
                    "value": 38000,
                    "usage": "personal"
                }
            }
        },
        {
            "name": "Bob Johnson",
            "data": {
                "age": 42,
                "gender": "male",
                "address": "555 Maple Dr, Rural Route 1, Montana",
                "location_type": "rural",
                "insurance_type": "auto",
                "vehicle_details": {
                    "make": "Chevrolet",
                    "model": "Silverado",
                    "year": 2022,
                    "value": 45000,
                    "usage": "commercial"
                }
            }
        }
    ]
    
    quotes_summary = []
    
    for customer in customers:
        print(f"\nGenerating quote for: {customer['name']}")
        print("-" * 60)
        
        result = tool._run(json.dumps(customer['data']))
        
        # Extract premium from result (simplified parsing)
        if "TOTAL MONTHLY PREMIUM:" in result:
            premium_line = [line for line in result.split('\n') 
                          if 'TOTAL MONTHLY PREMIUM:' in line][0]
            premium = premium_line.split('$')[1].strip()
            quotes_summary.append({
                "name": customer['name'],
                "premium": premium,
                "insurance_type": customer['data']['insurance_type']
            })
    
    # Print summary
    print("\n" + "=" * 80)
    print("BATCH QUOTES SUMMARY")
    print("=" * 80)
    for quote in quotes_summary:
        print(f"{quote['name']:20s} | {quote['insurance_type']:10s} | ${quote['premium']}/month")


def example_5_error_scenarios():
    """Example 5: Demonstrating error handling"""
    print("\n" + "=" * 80)
    print("Example 5: Error Handling Scenarios")
    print("=" * 80)
    
    tool = QuotingTool()
    
    # Scenario 1: Missing vehicle details for auto insurance
    print("\nScenario 1: Missing vehicle details for auto insurance")
    print("-" * 60)
    incomplete_data = {
        "age": 30,
        "gender": "male",
        "address": "123 Test St",
        "location_type": "urban",
        "insurance_type": "auto"
        # Missing vehicle_details
    }
    result = tool._run(json.dumps(incomplete_data))
    print(result)
    
    # Scenario 2: Invalid age
    print("\n\nScenario 2: Invalid age (out of range)")
    print("-" * 60)
    invalid_age = {
        "age": 150,  # Invalid age
        "gender": "male",
        "address": "123 Test St",
        "location_type": "urban",
        "insurance_type": "auto",
        "vehicle_details": {
            "make": "Tesla",
            "model": "Model 3",
            "year": 2023,
            "value": 45000
        }
    }
    result = tool._run(json.dumps(invalid_age))
    print(result)
    
    # Scenario 3: Invalid JSON
    print("\n\nScenario 3: Invalid JSON format")
    print("-" * 60)
    result = tool._run("This is not JSON")
    print(result)


def example_6_async_usage():
    """Example 6: Async quote generation"""
    print("\n" + "=" * 80)
    print("Example 6: Async Quote Generation")
    print("=" * 80)
    
    import asyncio
    
    tool = QuotingTool()
    
    async def generate_multiple_quotes():
        """Generate multiple quotes concurrently"""
        
        customers = [
            {
                "age": 25,
                "gender": "male",
                "address": "123 First St, City A",
                "location_type": "urban",
                "insurance_type": "auto",
                "vehicle_details": {
                    "make": "Honda",
                    "model": "Civic",
                    "year": 2020,
                    "value": 24000,
                    "usage": "personal"
                }
            },
            {
                "age": 40,
                "gender": "female",
                "address": "456 Second St, City B",
                "location_type": "suburban",
                "insurance_type": "health",
                "health_details": {
                    "smoker": False,
                    "pre_existing_conditions": False,
                    "bmi": 22.0,
                    "exercise_frequency": "frequent"
                }
            }
        ]
        
        # Generate quotes concurrently
        tasks = [tool._arun(json.dumps(customer)) for customer in customers]
        results = await asyncio.gather(*tasks)
        
        for i, result in enumerate(results, 1):
            print(f"\n--- Async Quote {i} ---")
            print(result)
    
    # Run async function
    asyncio.run(generate_multiple_quotes())


def main():
    """Run all examples"""
    print("=" * 80)
    print("Advanced QuotingTool - Integration Examples")
    print("=" * 80)
    
    examples = [
        ("Direct Tool Usage", example_1_direct_tool_usage),
        ("Agent Integration", example_2_agent_integration),
        ("Structured Input", example_3_structured_input),
        ("Batch Quotes", example_4_batch_quotes),
        ("Error Scenarios", example_5_error_scenarios),
        ("Async Usage", example_6_async_usage)
    ]
    
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"{i}. {name}")
    print("0. Run all examples (except Agent Integration)")
    
    choice = input("\nSelect example (0-6, or press Enter for all): ").strip()
    
    if not choice or choice == "0":
        # Run all examples except agent integration (requires API key)
        for name, func in examples:
            if name != "Agent Integration":
                try:
                    func()
                    input("\nPress Enter to continue to next example...")
                except Exception as e:
                    print(f"Error in {name}: {str(e)}")
    elif choice.isdigit() and 1 <= int(choice) <= len(examples):
        try:
            examples[int(choice)-1][1]()
        except Exception as e:
            print(f"Error: {str(e)}")
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()

