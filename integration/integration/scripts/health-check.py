# Import os so we can read environment variables (the API keys)
import os
# Import requests so we can send HTTP requests
import requests
# Import the function that reads the .env file
from dotenv import load_dotenv

# Read the .env file and load its values into the environment
load_dotenv()

# Read the backend address, using a local default if it is missing
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
# Read the ElevenLabs key (empty string if missing)
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY", "")
# Read the Gemini key (empty string if missing)
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")


# Define a helper that prints OK or FAIL for one check and returns the result
def report(name, ok, hint=""):
    # Choose the word to print depending on the result
    status = "OK  " if ok else "FAIL"
    # Print the check name with its status
    print(f"[{status}] {name}")
    # If the check failed and we have a hint, print it to help fix the problem
    if not ok and hint:
        # Print the hint on its own line
        print(f"       -> {hint}")
    # Return the result so the caller can count successes
    return ok


# Define a helper that checks one URL and expects status code 200
def check_url(name, url, headers=None, hint=""):
    # Start a try block so a network error doesn't crash the script
    try:
        # Send a GET request and wait at most 5 seconds
        response = requests.get(url, headers=headers, timeout=5)
        # Status 200 means everything is fine
        ok = response.status_code == 200
        # Build a hint that includes the status code if the check failed
        full_hint = f"{hint} (status code {response.status_code})"
        # Report the result and return it
        return report(name, ok, full_hint)
    # If the request failed completely (server off, no internet, wrong address)
    except requests.RequestException:
        # Report the failure with the hint
        return report(name, False, hint)


# Define the main function that runs all checks
def main():
    # Print a title for the output
    print("=== Caller AI health check ===\n")
    # Create a list that will hold True or False for every check
    results = []

    # Check 1: is the backend running? (Dev 2 must add a GET /health endpoint)
    results.append(check_url(
        # Name shown in the output
        "Backend is running",
        # The health endpoint of the backend
        f"{BACKEND_URL}/health",
        # Hint shown when it fails
        hint="Is the backend started? Did Dev 2 add /health?",
    ))

    # Check 2: is the ElevenLabs key set in the .env file?
    results.append(report(
        # Name shown in the output
        "ElevenLabs key is set",
        # True if the key is not empty
        len(ELEVEN_KEY) > 0,
        # Hint shown when it fails
        "Add ELEVENLABS_API_KEY to your .env file",
    ))

    # Check 3: does the ElevenLabs key work? (verify this endpoint in their docs)
    results.append(check_url(
        # Name shown in the output
        "ElevenLabs key is valid",
        # The endpoint that lists available voices
        "https://api.elevenlabs.io/v1/voices",
        # The header with the key
        headers={"xi-api-key": ELEVEN_KEY},
        # Hint shown when it fails
        hint="Check the key, your internet and your ElevenLabs quota",
    ))

    # Check 4: is the Gemini key set in the .env file?
    results.append(report(
        # Name shown in the output
        "Gemini key is set",
        # True if the key is not empty
        len(GEMINI_KEY) > 0,
        # Hint shown when it fails
        "Add GEMINI_API_KEY to your .env file",
    ))

    # Check 5: does the Gemini key work? (verify this endpoint in the Gemini docs)
    results.append(check_url(
        # Name shown in the output
        "Gemini key is valid",
        # The endpoint that lists models, with the key as a parameter
        f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}",
        # Hint shown when it fails
        hint="Check the key and your internet connection",
    ))

    # Count how many checks passed (True counts as 1)
    passed = sum(results)
    # Print the final score
    print(f"\n=== {passed}/{len(results)} checks passed ===")


# Run main() only when this file is executed directly
if __name__ == "__main__":
    # Start the program
    main()