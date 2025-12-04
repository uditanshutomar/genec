import os
import sys
print("DEBUG: Starting imports")
from genec.llm.anthropic_client import AnthropicClientWrapper
print("DEBUG: Imports done")

# Set API key explicitly or rely on env var
# os.environ["ANTHROPIC_API_KEY"] = "..." 

def main():
    print("Initializing Anthropic Client...")
    try:
        client = AnthropicClientWrapper()
        if not client.enabled:
            print("Client disabled (no API key).")
            return

        print("Sending test message...")
        response = client.send_message("Hello, are you working?")
        print(f"Response: {response}")
        
    except Exception as e:
        print(f"Error: {e}")
    except BaseException as e:
        print(f"Fatal Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
