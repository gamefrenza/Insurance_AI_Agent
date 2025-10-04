"""
Example usage of Insurance AI Agent
Demonstrates different ways to use the agent programmatically
"""

import os
from insurance_agent import InsuranceAgent


def example_1_basic_quote():
    """Example 1: Basic insurance quote"""
    print("\n" + "="*70)
    print("Example 1: Basic Insurance Quote")
    print("="*70)
    
    # Set your API key (or use environment variable)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  Please set OPENAI_API_KEY environment variable")
        return
    
    # Initialize agent
    agent = InsuranceAgent(openai_api_key=api_key)
    
    # Request a quote
    query = "I need auto insurance. I'm 28 years old, drive a Honda Accord 2020, and live in San Francisco."
    result = agent.run(query)
    
    if result["success"]:
        print(f"\n✓ Success!\n{result['response']}")
    else:
        print(f"\n✗ Error: {result['error']}")


def example_2_full_workflow():
    """Example 2: Complete workflow - Quote, Underwriting, Document"""
    print("\n" + "="*70)
    print("Example 2: Complete Insurance Workflow")
    print("="*70)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  Please set OPENAI_API_KEY environment variable")
        return
    
    agent = InsuranceAgent(openai_api_key=api_key)
    
    # Step 1: Get Quote
    print("\n📊 Step 1: Getting Quote...")
    quote_query = "Calculate home insurance for a 45-year-old, property value $350,000, located in Seattle"
    quote_result = agent.run(quote_query)
    if quote_result["success"]:
        print(quote_result["response"][:200] + "...")
    
    # Step 2: Underwriting
    print("\n📋 Step 2: Underwriting Assessment...")
    uw_query = "Perform underwriting assessment for the above quote"
    uw_result = agent.run(uw_query)
    if uw_result["success"]:
        print(uw_result["response"][:200] + "...")
    
    # Step 3: Document Generation
    print("\n📄 Step 3: Generating Documents...")
    doc_query = "Generate the insurance application document"
    doc_result = agent.run(doc_query)
    if doc_result["success"]:
        print(doc_result["response"][:200] + "...")
    
    print("\n✓ Complete workflow executed!")


def example_3_multiple_customers():
    """Example 3: Process multiple customers"""
    print("\n" + "="*70)
    print("Example 3: Multiple Customer Quotes")
    print("="*70)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  Please set OPENAI_API_KEY environment variable")
        return
    
    customers = [
        "25-year-old with Tesla Model 3 in New York",
        "35-year-old with BMW X5 in Los Angeles",
        "50-year-old with Toyota Camry in Chicago"
    ]
    
    for i, customer in enumerate(customers, 1):
        # Create new agent for each customer (fresh memory)
        agent = InsuranceAgent(openai_api_key=api_key)
        
        print(f"\n--- Customer {i}: {customer} ---")
        query = f"Calculate auto insurance quote for {customer}"
        result = agent.run(query)
        
        if result["success"]:
            # Extract just the premium from response
            response = result["response"]
            if "Base Premium:" in response:
                premium_line = [line for line in response.split('\n') if 'Base Premium:' in line][0]
                print(f"✓ {premium_line.strip()}")
        else:
            print(f"✗ Error: {result['error']}")


def example_4_memory_demo():
    """Example 4: Demonstrate conversation memory"""
    print("\n" + "="*70)
    print("Example 4: Conversation Memory")
    print("="*70)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  Please set OPENAI_API_KEY environment variable")
        return
    
    agent = InsuranceAgent(openai_api_key=api_key)
    
    # First query
    print("\n💬 Query 1: Initial request")
    result1 = agent.run("I need auto insurance for my Tesla Model 3. I'm 30 years old.")
    print("✓ Response received")
    
    # Second query - agent should remember context
    print("\n💬 Query 2: Follow-up (using memory)")
    result2 = agent.run("Can you perform underwriting for that quote?")
    print("✓ Response received (agent remembered the Tesla Model 3 context)")
    
    # Third query - continue conversation
    print("\n💬 Query 3: Another follow-up")
    result3 = agent.run("Now generate the application document")
    print("✓ Response received (full context maintained)")
    
    print("\n✓ Memory allows natural conversation flow!")


def example_5_chinese_query():
    """Example 5: Chinese language support"""
    print("\n" + "="*70)
    print("Example 5: Chinese Language Query")
    print("="*70)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  Please set OPENAI_API_KEY environment variable")
        return
    
    agent = InsuranceAgent(openai_api_key=api_key)
    
    # Chinese query
    query = "计算汽车保险报价：年龄25，车辆型号Tesla Model 3，地址北京"
    print(f"\n💬 查询: {query}")
    
    result = agent.run(query)
    
    if result["success"]:
        print(f"\n✓ 成功!\n{result['response']}")
    else:
        print(f"\n✗ 错误: {result['error']}")


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("Insurance AI Agent - Example Usage")
    print("="*70)
    
    examples = [
        ("Basic Quote", example_1_basic_quote),
        ("Full Workflow", example_2_full_workflow),
        ("Multiple Customers", example_3_multiple_customers),
        ("Memory Demo", example_4_memory_demo),
        ("Chinese Query", example_5_chinese_query)
    ]
    
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"{i}. {name}")
    print("0. Run all examples")
    
    choice = input("\nSelect example (0-5): ").strip()
    
    if choice == "0":
        for name, func in examples:
            func()
            input("\nPress Enter to continue to next example...")
    elif choice.isdigit() and 1 <= int(choice) <= len(examples):
        examples[int(choice)-1][1]()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()


