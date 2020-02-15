# QLive-Bot
A proof-of-concept Q&amp;A bot for the QLive Trivia app (now defunct).

## Mode of operation
Broadly speaking the core program flow is as follows:
1. Connect to QLive API to recieve question and possible answers.
2. Use Google to search for possible answers by scoring the returned titles, descriptions and content of webpages.
3. Display scores along with a "best" sentence from results containing the answer in context (good for manual filtering of false positives).
4. Recieve user input to respond to the question using multiple "virtual player" accounts.

### Additional features
The program provides a number of additional features including:
1. Google Vision API interfacing to identify picture questions. Useful for identifying celebrities and logos for example.
2. Android Debug Bridge (ADB) for taking a screenshot rapidly from an Android device. This was originally part of the core functionality
before the QLive API was reverse-engineered, allowing questions and answers to be extracted using computer vision and the Tesseract OCR.
Now its use is limited to capturing images for the vision API.
3. Rudimentary implementation of some natural language processing to improve scoring of answers.

### Disclaimer
This program is provided to demonstrate the inherent vulnerability of live trivia apps to botting.

The program was never deployed in a live scenario and no profit was ever made as a result.
