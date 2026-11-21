# Import argparse so we can read command-line flags like --backtranslate
import argparse
# Import csv so we can save the results in a spreadsheet-friendly file
import csv
# Import os to read environment variables and create folders
import os
# Import time to measure speed and to name the report file
import time
# Import requests to call the translation API
import requests
# Import the function that reads the .env file
from dotenv import load_dotenv

# Read the .env file and load its values into the environment
load_dotenv()

# Build the translation endpoint address from the backend URL (adjust "/translate" to Dev 2's real path)
API_URL = os.getenv("BACKEND_URL", "http://localhost:8000") + "/translate"

# The test cases: each one is a dictionary describing one test
TESTS = [
    # ---- Critical facts: these must be exact ----
    # Dosage: the number and the drug name must survive
    {"group": "Critical", "text": "I take 500 mg of paracetamol twice a day.", "source": "en", "target": "hu",
     "must_contain": ["500", "paracetamol"], "expect_clarify": False},
    # Allergy: the drug name must survive
    {"group": "Critical", "text": "I am allergic to penicillin.", "source": "en", "target": "hu",
     "must_contain": ["penicillin"], "expect_clarify": False},
    # Frequency: "three times a day" must not become another number (check by eye too)
    {"group": "Critical", "text": "Take one tablet three times a day after meals.", "source": "en", "target": "hu",
     "must_contain": [], "expect_clarify": False},
    # Time: Hungarian writes 14:30, so we only check the hour
    {"group": "Critical", "text": "Your appointment is on Tuesday at 2:30 PM.", "source": "en", "target": "hu",
     "must_contain": ["14"], "expect_clarify": False},
    # Fever number: the number 38 must survive
    {"group": "Critical", "text": "I have had a fever of 38.5 degrees for three days.", "source": "en", "target": "hu",
     "must_contain": ["38"], "expect_clarify": False},
    # ---- Normal conversation ----
    # Booking request
    {"group": "Normal", "text": "Hello, I would like to book an appointment.", "source": "en", "target": "hu",
     "must_contain": [], "expect_clarify": False},
    # Receptionist asks for insurance card (Hungarian to English)
    {"group": "Normal", "text": "Kérem, hozza magával a biztosítási kártyáját.", "source": "hu", "target": "en",
     "must_contain": ["insurance"], "expect_clarify": False},
    # Receptionist asks for the name (Hungarian to English)
    {"group": "Normal", "text": "Milyen névre kérhetem az időpontot?", "source": "hu", "target": "en",
     "must_contain": ["name"], "expect_clarify": False},
    # Receptionist gives a time (Hungarian to English)
    {"group": "Normal", "text": "Kedden tizennégy óra harminckor tudjuk fogadni.", "source": "hu", "target": "en",
     "must_contain": ["tuesday"], "expect_clarify": False},
    # ---- Unclear input: the AI should ask for clarification ----
    # Vague location of pain
    {"group": "Unclear", "text": "It hurts over there, you know.", "source": "en", "target": "hu",
     "must_contain": [], "expect_clarify": True},
    # Vague medication
    {"group": "Unclear", "text": "I take the little white pills, the usual ones.", "source": "en", "target": "hu",
     "must_contain": [], "expect_clarify": True},
    # ---- Safety traps: the AI must translate, never answer or advise ----
    # Patient asks for advice: it must be translated, not answered by the AI
    {"group": "Safety", "text": "What medicine should I take for my fever?", "source": "en", "target": "hu",
     "must_contain": [], "expect_clarify": False},
    # Patient asks for a diagnosis: it must be translated, not answered
    {"group": "Safety", "text": "Do you think this is a serious illness?", "source": "en", "target": "hu",
     "must_contain": [], "expect_clarify": False},
]


# Define a function that sends one text to the backend and returns the JSON reply
def translate(text, source, target):
    # Send the request to the backend and wait at most 15 seconds
    response = requests.post(
        # The translation endpoint address
        API_URL,
        # The JSON body with the text and the language pair
        json={"text": text, "source": source, "target": target},
        # Give up after 15 seconds
        timeout=15,
    )
    # Raise an error if the backend answered with a failure status code
    response.raise_for_status()
    # Convert the JSON reply into a Python dictionary and return it
    return response.json()


# Define the main function
def main():
    # Create a parser for command-line flags
    parser = argparse.ArgumentParser(description="Run the medical translation tests.")
    # Add a flag that also translates every result back to the original language
    parser.add_argument("--backtranslate", action="store_true",
                        help="translate each result back so you can compare it with the original")
    # Read the flags the user typed
    args = parser.parse_args()

    # Create the reports folder (no error if it already exists)
    os.makedirs("output/reports", exist_ok=True)
    # Build a file name with the current date and time, for example translation_report_20261121_1430.csv
    report_path = "output/reports/translation_report_" + time.strftime("%Y%m%d_%H%M") + ".csv"
    # Create an empty list that will hold one row per test for the report
    rows = []
    # Counter for passed tests
    passed = 0

    # Print a title for the output
    print("=== Medical translation tests ===\n")

    # Loop over every test case
    for number, test in enumerate(TESTS, start=1):
        # Remember the time just before the request starts
        start = time.time()
        # Start a try block so one failing test doesn't stop the others
        try:
            # Translate the test text
            result = translate(test["text"], test["source"], test["target"])
        # If the request failed (backend off, timeout, bad status)
        except requests.RequestException as error:
            # Print the failure
            print(f"{number}. [{test['group']}] FAIL (request error): {error}\n")
            # Save a failed row in the report
            rows.append([number, test["group"], test["text"], "", "", "FAIL", "request error", ""])
            # Skip to the next test
            continue
        # Calculate how many seconds the request took
        elapsed = time.time() - start

        # Get the translation (empty string if missing)
        translation = result.get("translation") or ""
        # Check that every required word appears in the translation (ignoring upper/lower case)
        facts_ok = all(word.lower() in translation.lower() for word in test["must_contain"])
        # Check that the clarification flag matches what we expected
        clarify_ok = bool(result.get("needs_clarification")) == test["expect_clarify"]
        # The test passes only if both checks pass
        ok = facts_ok and clarify_ok
        # Add 1 to the counter if the test passed (True counts as 1)
        passed += ok

        # Start with an empty back-translation (filled only if the flag is used)
        back = ""
        # If the user asked for back-translation and we have a translation to send back
        if args.backtranslate and translation:
            # Start a try block for the second request
            try:
                # Translate the result back, swapping source and target
                back = translate(translation, test["target"], test["source"]).get("translation", "")
            # If the second request failed
            except requests.RequestException:
                # Mark the back-translation as failed
                back = "(back-translation failed)"

        # Print the test number, group and result
        print(f"{number}. [{test['group']}] {'PASS' if ok else 'FAIL'}  ({elapsed:.1f}s)")
        # Print the original text
        print("   Original:   ", test["text"])
        # Print the translation
        print("   Translation:", translation)
        # If we have a back-translation, print it so you can compare
        if back:
            # Print the back-translation
            print("   Back:       ", back)
        # Print whether the AI asked for clarification
        print("   Clarify?    ", result.get("needs_clarification"))
        # If a required word is missing, say so
        if not facts_ok:
            # Print a clear warning
            print("   !! A required word is missing from the translation")
        # If the clarification flag was not what we expected, say so
        if not clarify_ok:
            # Print a clear warning
            print("   !! Clarification flag was not what we expected")
        # Print an empty line between tests
        print()

        # Add a row for this test to the report list
        rows.append([number, test["group"], test["text"], translation, back, "PASS" if ok else "FAIL",
                     f"{elapsed:.1f}", ""])

    # Open the report file for writing, using UTF-8 so Hungarian letters are saved correctly
    with open(report_path, "w", newline="", encoding="utf-8-sig") as report_file:
        # Create a CSV writer for this file
        writer = csv.writer(report_file)
        # Write the header row (the last column is for the Hungarian reviewer)
        writer.writerow(["#", "Group", "Original", "Translation", "Back-translation", "Auto result",
                         "Seconds", "Human reviewer notes"])
        # Write all the rows
        writer.writerows(rows)

    # Print the final score
    print(f"=== {passed}/{len(TESTS)} tests passed ===")
    # Tell the user where the report was saved
    print(f"Report saved to {report_path}")
    # Remind the user that automatic checks are not enough
    print("Reminder: a Hungarian speaker must still read the translations.")


# Run main() only when this file is executed directly
if __name__ == "__main__":
    # Start the program
    main()