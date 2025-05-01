import os
import asyncio
from dotenv import load_dotenv
from agents.agent_manager import AgentManager  # Add this line to import AgentManager

async def main():
    """Command-line interface for testing the multi-agent system."""
    print("CuraTrak OSHA Compliance Assistant")
    print("----------------------------------")
    print("Initializing agents...")
    
    # Initialize agent manager
    manager = AgentManager()
    await manager.initialize()
    
    print("Agents initialized successfully!")
    print("Enter 'exit' to quit")
    print("Enter 'report' to generate a report")
    print()
    
    last_response = None
    last_query = None
    
    while True:
        # Get user query
        user_query = input("Enter your question about OSHA compliance (or 'report'/'exit'): ")
        
        if user_query.lower() == 'exit':
            break
            
        elif user_query.lower() == 'report':
            if not last_response:
                print("\nYou need to run a query first before generating a report.")
                continue
                
            topic = input("Enter the topic for this report: ")
            email_to = input("Email the report to (leave blank to skip): ")
            
            email_to = email_to if email_to.strip() else None
            
            print("\nGenerating report...")
            report_result = await manager.generate_report(topic, last_query, last_response, email_to)
            
            print(f"\nReport generated successfully!")
            print(f"HTML Report: {report_result['report']['html_path']}")
            
            if 'pdf_path' in report_result['report']:
                print(f"PDF Report: {report_result['report']['pdf_path']}")
            
            if report_result['report']['email_preview']:
                print(f"Email Preview: {report_result['report']['email_preview']}")
            
            print("\nYou can open these files in a browser to view them.")
            continue
        
        print("\nProcessing your query...")
        
        try:
            # Process query - results will be displayed incrementally by the manager
            response = await manager.process_query(user_query)
            last_response = response
            last_query = user_query
            
            # No need to print full response again since we've already shown incremental results
            print("\nQuery processing complete! You can now generate a report based on these results.")
        except Exception as e:
            print(f"Error: {str(e)}")
    
    # Clean up resources
    print("Cleaning up resources...")
    await manager.cleanup()
    print("Done!")

if __name__ == "__main__":
    # This is critical - it makes your script actually run!
    asyncio.run(main())