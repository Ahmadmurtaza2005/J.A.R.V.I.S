from difflib import get_close_matches
import json

from helpers import speak, takeCommand

data = json.load(open("data.json"))


def translate(word):
    word = word.lower()
    if word in data:
        speak(data[word])
    elif len(get_close_matches(word, data.keys())) > 0:
        x = get_close_matches(word, data.keys())[0]
        speak('Did you mean ' + x +
              ' instead,  respond with Yes or No.')
        ans = takeCommand().lower()
        if 'yes' in ans:
            speak(data[x])
        elif 'no' in ans:
            speak("Word doesn't exist. Please make sure you spelled it correctly.")
        else:
            #changed from we to I
            speak("I did not understand your entry.")

    else:
        speak("Word doesn't exist. Please double check it.")


if __name__ == '__main__':
    translate()
