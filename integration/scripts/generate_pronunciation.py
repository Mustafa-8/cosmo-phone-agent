# Import os to read environment variables and create folders
import os
# Import requests to call the ElevenLabs API
import requests
# Import the function that reads the .env file
from dotenv import load_dotenv

# Read the .env file and load its values into the environment
load_dotenv()

# Read the ElevenLabs API key (empty string if missing)
API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
# Use the SAME Hungarian voice and model as the live demo (voice/config.py), so the review
# checks what the audience will hear: Andris + eleven_flash_v2_5 by default.
VOICE_ID = os.getenv("VOICE_ID_HU", "rlxsbADLInnFyRAXDQLB")
# The TTS model used by the voice bridge
MODEL_ID = os.getenv("TTS_MODEL_ID", "eleven_flash_v2_5")
# The folder where the MP3 files will be saved
AUDIO_FOLDER = "output/pronunciation"
# The file where the review table for the Hungarian speaker will be saved
REVIEW_FILE = "output/reports/pronunciation_review.md"

# The phrases to test: (category, Hungarian text, English meaning)
PHRASES = [
    # Numbers with units
    ("Dosage", "Napi kétszer ötszáz milligramm paracetamolt szedek.", "I take 500 mg of paracetamol twice a day."),
    # Drug name in a sentence
    ("Allergy", "Allergiás vagyok a penicillinre.", "I am allergic to penicillin."),
    # Another drug name
    ("Drug name", "Ibuprofent szedek fejfájásra.", "I take ibuprofen for headaches."),
    # Time and day
    ("Time", "Kedden tizennégy óra harminckor tudjuk fogadni.", "We can see you on Tuesday at 14:30."),
    # Decimal number written in words (important for fever)
    ("Decimal", "A láza harminchét egész nyolc tized fok.", "Your temperature is 37.8 degrees."),
    # Decimal number written with digits (to see how the voice reads it)
    ("Decimal digits", "A láza 37,8 fok.", "Your temperature is 37.8 degrees."),
    # Long compound words
    ("Long words", "Kérem, hozza magával a biztosítási kártyáját.", "Please bring your insurance card."),
    # Date
    ("Date", "Az időpontja november huszonharmadikán van.", "Your appointment is on November 23rd."),
    # Name question
    ("Question", "Milyen névre kérhetem az időpontot?", "What name can I put the appointment under?"),
    # Clarification request
    ("Clarification", "Elnézést, nem értettem. Meg tudja ismételni?", "Sorry, I did not understand. Can you repeat that?"),
]


# Define a function that picks a voice ID if none was set in .env
def pick_voice():
    # If a voice ID was set in .env, use it
    if VOICE_ID:
        # Return the voice ID from .env
        return VOICE_ID
    # Otherwise ask ElevenLabs for the list of available voices
    response = requests.get(
        # The endpoint that lists voices (verify in the docs)
        "https://api.elevenlabs.io/v1/voices",
        # The header with the API key
        headers={"xi-api-key": API_KEY},
        # Wait at most 15 seconds
        timeout=15,
    )
    # Stop with an error if the request failed
    response.raise_for_status()
    # Get the list of voices from the JSON reply
    voices = response.json().get("voices", [])
    # If there are no voices, we cannot continue
    if not voices:
        # Raise a clear error message
        raise RuntimeError("No voices found in your ElevenLabs account")
    # Print which voice we are using so you can note it down
    print("Using voice:", voices[0].get("name"), voices[0].get("voice_id"))
    # Return the ID of the first voice in the list
    return voices[0]["voice_id"]


# Define the main function
def main():
    # Stop early if the API key is missing
    if not API_KEY:
        # Print a clear message and leave the function
        print("ELEVENLABS_API_KEY is missing. Add it to your .env file.")
        # Exit main()
        return
    # Create the audio folder (no error if it already exists)
    os.makedirs(AUDIO_FOLDER, exist_ok=True)
    # Create the reports folder (no error if it already exists)
    os.makedirs("output/reports", exist_ok=True)
    # Choose the voice to test
    voice_id = pick_voice()

    # Start the review table with a title and the table header row
    review_lines = [
        # Title of the review document
        "# Hungarian pronunciation review\n",
        # Short instruction for the reviewer
        "Listen to each file and mark each column with OK or the problem you hear.\n",
        # Table header
        "| # | File | Category | Hungarian text | Meaning | Numbers OK? | Words OK? | Natural? | Notes |",
        # Table separator row
        "|---|------|----------|----------------|---------|-------------|-----------|----------|-------|",
    ]

    # Loop over all phrases, numbering them from 1
    for number, (category, text, meaning) in enumerate(PHRASES, start=1):
        # Start a try block so one failure doesn't stop the rest
        try:
            # Send the text to ElevenLabs and ask for audio back
            response = requests.post(
                # The text-to-speech endpoint for this voice (verify in the docs)
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                # The header with the API key
                headers={"xi-api-key": API_KEY},
                # The body: the text to speak and the model to use
                json={"text": text, "model_id": MODEL_ID, "language_code": "hu"},
                # Wait at most 30 seconds for the audio
                timeout=30,
            )
            # Raise an error if the request failed
            response.raise_for_status()
        # If the request failed
        except requests.RequestException as error:
            # Print the error and continue with the next phrase
            print(f"Phrase {number} FAILED: {error}")
            # Skip to the next phrase
            continue
        # Build the file name, for example output/pronunciation/phrase_01.mp3
        filename = f"phrase_{number:02d}.mp3"
        # Build the full path of the file
        path = os.path.join(AUDIO_FOLDER, filename)
        # Open the file in binary write mode
        with open(path, "wb") as audio_file:
            # Write the audio bytes into the file
            audio_file.write(response.content)
        # Tell the user which file was saved
        print(f"Saved {path} [{category}]")
        # Add a row to the review table for this phrase
        review_lines.append(f"| {number} | {filename} | {category} | {text} | {meaning} |  |  |  |  |")

    # Open the review file in write mode using UTF-8 so Hungarian letters are saved correctly
    with open(REVIEW_FILE, "w", encoding="utf-8") as review_file:
        # Write all the lines, separated by new lines
        review_file.write("\n".join(review_lines) + "\n")
    # Tell the user where the review table is
    print(f"\nReview table saved to {REVIEW_FILE}")
    # Remind the user of the next step
    print("Next: give the MP3 files and this table to a Hungarian speaker.")


# Run main() only when this file is executed directly
if __name__ == "__main__":
    # Start the program
    main()