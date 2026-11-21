# Import argparse so we can read command-line flags like --mock
import argparse
# Import os to read the VOICE_URL setting
import os
# Import time so we can measure how long each translation takes
import time
# Import requests so we can send HTTP requests to the backend
import requests

# The address of Dev 2's translation endpoint (change it to the real one)
# Nour's voice bridge (uvicorn voice.server:app --port 8001) serves POST /translate
API_URL = os.getenv("VOICE_URL", "http://localhost:8001") + "/translate"
# If one turn takes longer than this many seconds, we print a warning
SLOW_LIMIT_SECONDS = 3.0

# The demo scenario: one dictionary per spoken sentence, in the order of the demo
DEMO_TURNS = [
    # Turn 1: the patient (English) explains the problem
    {
        # Who is speaking
        "speaker": "Patient",
        # What they say
        "text": "Hello, I'd like to book an appointment. I've had a fever and a headache for three days.",
        # The language they speak
        "source": "en",
        # The language the receptionist needs
        "target": "hu",
        # Words that must appear in the translation (lowercase, adjust to taste)
        "must_contain": ["láz", "fejfájás"],
        # Should the AI ask for clarification here? No
        "expect_clarify": False,
    },
    # Turn 2: the receptionist (Hungarian) asks for the name and medication
    {
        # Who is speaking
        "speaker": "Receptionist",
        # What they say
        "text": "Milyen névre kérhetem az időpontot? Szed valamilyen gyógyszert?",
        # The receptionist speaks Hungarian
        "source": "hu",
        # The patient needs English
        "target": "en",
        # Key words that must survive the translation
        "must_contain": ["name", "medication"],
        # No clarification expected
        "expect_clarify": False,
    },
    # Turn 3: the patient gives dosage and allergy (the critical safety turn)
    {
        # Who is speaking
        "speaker": "Patient",
        # The dosage and the allergy: these must never change
        "text": "I take 500 mg of paracetamol twice a day. I'm allergic to penicillin.",
        # The patient speaks English
        "source": "en",
        # Translate into Hungarian
        "target": "hu",
        # The number and both drug names must be preserved
        "must_contain": ["500", "paracetamol", "penicillin"],
        # No clarification expected
        "expect_clarify": False,
    },
    # Turn 4: the receptionist offers an appointment time
    {
        # Who is speaking
        "speaker": "Receptionist",
        # What they say: "We can see you on Tuesday at 14:30"
        "text": "Kedden tizennégy óra harminckor tudjuk fogadni.",
        # The receptionist speaks Hungarian
        "source": "hu",
        # The patient needs English
        "target": "en",
        # The day must survive (the time may be written as 2:30 or 14:30)
        "must_contain": ["tuesday"],
        # No clarification expected
        "expect_clarify": False,
    },
    # Turn 5: the safety moment, a vague sentence
    {
        # Who is speaking
        "speaker": "Patient",
        # A vague statement the AI should NOT guess about
        "text": "It hurts over there, you know.",
        # The patient speaks English
        "source": "en",
        # Translate into Hungarian
        "target": "hu",
        # Nothing specific must appear
        "must_contain": [],
        # The AI SHOULD ask for clarification here
        "expect_clarify": True,
    },
]

# Fake answers used in --mock mode, so the script works before the backend exists
MOCK_ANSWERS = {
    # Fake answer for turn 1
    DEMO_TURNS[0]["text"]: {
        "translated_text": "Jó napot, időpontot szeretnék foglalni. Három napja lázas vagyok és fejfájásom van; láz és fejfájás.",
        "needs_clarification": False,
    },
    # Fake answer for turn 2
    DEMO_TURNS[1]["text"]: {
        "translated_text": "What name can I put the appointment under? Do you take any medication?",
        "needs_clarification": False,
    },
    # Fake answer for turn 3
    DEMO_TURNS[2]["text"]: {
        "translated_text": "Naponta kétszer 500 mg paracetamolt szedek. Allergiás vagyok a penicillinre.",
        "needs_clarification": False,
    },
    # Fake answer for turn 4
    DEMO_TURNS[3]["text"]: {
        "translated_text": "We can see you on Tuesday at 14:30.",
        "needs_clarification": False,
    },
    # Fake answer for turn 5 (asks for clarification)
    DEMO_TURNS[4]["text"]: {
        "translated_text": "",
        "needs_clarification": True,
    },
}


# Define a function that translates one turn, either with the mock or the real backend
def translate(turn, use_mock):
    # If mock mode is on, return the fake answer instead of calling the network
    if use_mock:
        # Look up the fake answer using the sentence as the key
        return MOCK_ANSWERS[turn["text"]]
    # Otherwise send the sentence to the real backend and wait up to 15 seconds
    response = requests.post(
        # The translation endpoint address
        API_URL,
        # The JSON body: text, source language and target language
        json={"text": turn["text"], "source": turn["source"], "target": turn["target"]},
        # Give up if the backend takes longer than 15 seconds
        timeout=15,
    )
    # Raise an error if the backend answered with a failure status code
    response.raise_for_status()
    # Convert the JSON reply into a Python dictionary and return it
    return response.json()


# Define the main function that runs the whole demo
def main():
    # Create a parser for command-line flags
    parser = argparse.ArgumentParser(description="Run the COSMO demo scenario.")
    # Add a --mock flag that switches to fake answers
    parser.add_argument("--mock", action="store_true", help="use fake answers, no backend needed")
    # Read the flags the user typed
    args = parser.parse_args()

    # Counter for turns that passed all checks
    passed = 0
    # List that stores how long each turn took
    timings = []

    # Print a title so the output is easy to read
    print("=== COSMO demo run ===")
    # Say which mode we are running in
    print("Mode:", "MOCK" if args.mock else "REAL BACKEND", "\n")

    # Loop over each turn, numbering from 1
    for number, turn in enumerate(DEMO_TURNS, start=1):
        # Remember the time just before the request starts
        start = time.time()
        # Start a try block so one failing turn does not stop the whole run
        try:
            # Translate this turn (mock or real)
            result = translate(turn, args.mock)
        # If the request failed (backend off, timeout, bad status)
        except requests.RequestException as error:
            # Print the failure and move on to the next turn
            print(f"Turn {number} [{turn['speaker']}] FAIL: request error: {error}\n")
            # Skip the rest of this loop iteration
            continue
        # Calculate how many seconds the turn took
        elapsed = time.time() - start
        # Save the timing for the summary at the end
        timings.append(elapsed)

        # Get the translation text, using an empty string if it is missing, in lowercase
        translation = (result.get("translated_text") or "").lower()
        # Check that every required word appears in the translation
        facts_ok = all(word.lower() in translation for word in turn["must_contain"])
        # Check that the clarification flag matches what we expected
        clarify_ok = bool(result.get("needs_clarification")) == turn["expect_clarify"]
        # The turn passes only if both checks pass
        ok = facts_ok and clarify_ok
        # Add 1 to the counter if the turn passed (True counts as 1)
        passed += ok

        # Print the turn number, speaker and PASS or FAIL
        print(f"Turn {number} [{turn['speaker']}] {'PASS' if ok else 'FAIL'}")
        # Print the original sentence
        print("  Original:   ", turn["text"])
        # Print the translation we received
        print("  Translation:", result.get("translated_text"))
        # Print whether the AI asked for clarification
        print("  Clarify?    ", result.get("needs_clarification"))
        # Print how long it took, in seconds with one decimal
        print(f"  Time:        {elapsed:.1f}s")
        # If the check failed because of missing facts, say so clearly
        if not facts_ok:
            # Explain that a required word is missing
            print("  !! A required word is missing from the translation")
        # If the clarification flag was wrong, say so clearly
        if not clarify_ok:
            # Explain the mismatch
            print("  !! Clarification flag was not what we expected")
        # If this turn was slower than the limit, warn about latency
        if elapsed > SLOW_LIMIT_SECONDS:
            # Print the latency warning
            print("  !! Slow turn: check latency")
        # Print an empty line to separate turns
        print()

    # Print the final score
    print(f"=== {passed}/{len(DEMO_TURNS)} turns passed ===")
    # Only print timing stats if at least one turn finished
    if timings:
        # Calculate the average time per turn
        average = sum(timings) / len(timings)
        # Print the average and the slowest turn
        print(f"Average: {average:.1f}s | Slowest: {max(timings):.1f}s")


# Run main() only when this file is executed directly (not imported)
if __name__ == "__main__":
    # Start the program
    main()