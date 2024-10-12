import speech_recognition as sr
import pyttsx3
import webbrowser
import wikipedia
import datetime
import os
import tkinter as tk
from tkinter import font
import requests
import time
import threading
from playsound import playsound
from pystray import Icon as icon, MenuItem as item, Menu  # For system tray icon
from PIL import Image, ImageDraw  # Required by pystray to create an icon
import psutil
import re
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
from ctypes import cast, POINTER

# Initialize the speech engine
engine = pyttsx3.init()

# Function to make JARVIS speak
def speak(text):
    engine.say(text)
    engine.runAndWait()
    update_speech_box(text)

# Function to recognize speech and return the command
def take_command():
    recognizer = sr.Recognizer()
    
    with sr.Microphone() as source:
        update_text("Adjusting for ambient noise... Please wait.")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        
        update_text("Listening for your command...")
        audio = recognizer.listen(source)
    
    try:
        update_text("Recognizing speech...")
        command = recognizer.recognize_google(audio)
        update_text(f"You said: {command}")
        return command.lower()
    
    except sr.UnknownValueError:
        update_text("Sorry, I could not understand what you said.")
        return None
    
    except sr.RequestError:
        update_text("API unavailable or unresponsive.")
        return None

# Function to handle conversational responses
def handle_conversation(command):
    if 'you are cool' in command:
        speak("Thank you! I appreciate the compliment.")
    elif 'what\'s up' in command or 'what is up' in command:
        speak("Not much, just here to help you. What can I do for you?")
    elif 'you are great' in command:
        speak("Thank you! I appreciate the compliment.")
    elif 'thank you' in command or 'thanks' in command:
        speak("You're welcome! If you need anything else, just let me know.")
    elif 'how are you' in command:
        speak("I'm doing well, thank you! How can I assist you?")
    elif 'hello' in command or 'good morning' in command: 
        speak("Hello! How can I assist you today?")
    elif 'who are you' in command or 'what are you' in command:
        speak("I am JARVIS, your personalized computer assistant created by Arnav Khullar, inspired by a fictional movie character Iron Man aka Tony Stark. I can help you perform some basic functions and assist you in your tasks.")
    else:
        return False
    return True

# Function to get weather data using wttr.in
def get_weather_from_wttr(city_name):
    try:
        response = requests.get(f"https://wttr.in/{city_name}?format=%l:+%C+%t+%h+%w+%p")
        if response.status_code == 200:
            weather_report = response.text.strip()
            return weather_report
        else:
            return "Sorry, I couldn't retrieve the weather information at the moment."
    except Exception as e:
        return "Sorry, I couldn't retrieve the weather information at the moment."
    

# Function to set an alarm
def set_alarm(alarm_time_24hr):
    # Create a new thread to run the alarm checker in the background
    alarm_thread = threading.Thread(target=alarm_checker, args=(alarm_time_24hr,))
    alarm_thread.daemon = True  # Daemon thread will shut down with the program
    alarm_thread.start()
    update_text(f"Alarm set for {alarm_time_24hr}.")
    speak(f"Alarm set for {alarm_time_24hr}.")

# Function to make JARVIS "dance" by changing background colors
def dance_mode():
    colors = ['#FF5733', '#33FF57', '#3357FF', '#FF33A1', '#FFFF33', '#33FFF6']
    for i in range(30):  # Repeat for 30 iterations
        random_color = colors[i % len(colors)]  # Cycle through the colors
        root.config(bg=random_color)
        title_label.config(bg=random_color)
        result_label.config(bg=random_color)
        speech_box.config(bg=random_color)
        time.sleep(0.3)  # Change color every 0.2 seconds
    root.config(bg='#00008B')  # Reset to original background color
    title_label.config(bg='#00008B')
    result_label.config(bg='#00008B')
    speech_box.config(bg='#00008B')
    speak("That was fun! Hope you enjoyed the dance!")


# Function to check the current time against the alarm time
def alarm_checker(alarm_time_24hr):
    while True:
        current_time = datetime.datetime.now().strftime("%H:%M")  # 24-hour format
        if current_time == alarm_time_24hr:
            play_alarm_sound()
            break  # Exit the thread once the alarm has rung
        time.sleep(10)  # Check every 10 seconds to avoid constant checking

def check_battery():
    battery = psutil.sensors_battery()
    if battery:
        percentage = battery.percent
        speak(f"Your battery is at {percentage} percent.")
        update_text(f"Battery status: {percentage}%")
    else:
        speak("Sorry, I couldn't fetch the battery status.")

# Function to change the volume level using pycaw
def change_volume(volume_level):
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(
        IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))

    # Convert volume_level to a float between 0.0 and 1.0
    volume_range = volume.GetVolumeRange()
    min_volume, max_volume = volume_range[0], volume_range[1]

    # Map the volume percentage (0-100) to the volume range
    target_volume = min_volume + (max_volume - min_volume) * (volume_level / 100.0)
    
    volume.SetMasterVolumeLevel(target_volume, None)
    speak(f"Volume set to {volume_level} percent.")

# Extract volume from command, as before
def extract_volume_from_command(command):
    try:
        # Use regex to find all numbers in the command
        volume_level = re.search(r'\d+', command)
        if volume_level:
            volume_level = int(volume_level.group())
            return volume_level
        else:
            return None
    except ValueError:
        return None


# Function to play the alarm sound
def play_alarm_sound():
    update_text("Alarm ringing!")
    speak("Alarm ringing!")
    # Playing an alarm sound using playsound
    playsound('alarm_sound.mp3')  # Ensure you have an 'alarm_sound.mp3' in the working directory or provide a path

# Function to make JARVIS sleep for a specified duration
def sleep_mode(duration):
    speak(f"Entering sleep mode for {duration} minutes.")
    time.sleep(duration * 60)  # Convert minutes to seconds
    speak("I'm awake and ready to assist!")

# Function to extract duration from the user's command and handle sleep mode
def set_sleep_mode_command():
    speak("For how long do you want me to sleep? Please tell me in minutes.")
    command = take_command()
    
    # Extract numeric value from the command
    duration = extract_number_from_command(command)
    
    if duration is not None:
        sleep_mode(duration)
    else:
        speak("I couldn't understand the duration. Please say a number of minutes.")

# Helper function to extract a number from the spoken command
def extract_number_from_command(command):
    try:
        # Use regex to find numbers in the command
        number = re.search(r'\d+', command)
        if number:
            return int(number.group())  # Convert the found number to an integer
        else:
            return None
    except ValueError:
        return None

# Function to take alarm command from user in 12-hour format
def set_alarm_command():
    speak("Please tell me the alarm time in HH:MM AM or PM format.")
    update_text("Please tell me the alarm time in HH:MM AM or PM format.")
    alarm_time = take_command()
    if alarm_time:
        try:
            # Clean up the input to handle common variations (e.g., missing space between time and AM/PM)
            alarm_time = alarm_time.replace(".", ":").replace("am", " AM").replace("pm", " PM").upper()
            if "AM" not in alarm_time and "PM" not in alarm_time:
                raise ValueError  # If AM/PM is missing, raise error
            # Convert the spoken time to 24-hour time for easier comparison
            alarm_time_24hr = datetime.datetime.strptime(alarm_time, "%I:%M %p").strftime("%H:%M")
            set_alarm(alarm_time_24hr)
        except ValueError:
            update_text("Invalid time format. Please use HH:MM AM/PM format.")
            speak("Invalid time format. Please use HH:MM AM or PM format.")


def set_alarm(alarm_time_24hr):
    # Convert 24-hour time back to 12-hour time for user-friendly output
    alarm_time_12hr = datetime.datetime.strptime(alarm_time_24hr, "%H:%M").strftime("%I:%M %p")
    alarm_thread = threading.Thread(target=alarm_checker, args=(alarm_time_24hr,))
    alarm_thread.daemon = True
    alarm_thread.start()
    update_text(f"Alarm set for {alarm_time_12hr}.")
    speak(f"Alarm set for {alarm_time_12hr}.")

todo_list = []

def add_to_do():
    speak("What would you like to add to your to-do list?")
    task = take_command()
    todo_list.append(task)
    speak(f"Added {task} to your to-do list.")
    update_text(f"To-do: {task}")

def list_to_do():
    if todo_list:
        speak("Here are the tasks on your to-do list.")
        for task in todo_list:
            speak(task)
    else:
        speak("Your to-do list is empty.")

# Function to clear the to-do list
def clear_to_do_list():
    global todo_list  # Access the global todo_list variable
    todo_list.clear()
    speak("Your to-do list has been cleared.")
    update_text("To-do list cleared.")



# Function to search location on Google Maps
def search_location_on_google_maps(location):
    if location:
        speak(f"Navigating to {location}")
        update_text(f"Navigating to {location}")
        location_query = location.replace(' ', '+')
        search_url = f"https://www.google.com/maps/search/{location_query}"
        update_text(f"Opening URL: {search_url}")  # Debugging: Show the generated URL
        webbrowser.open(search_url)  # Open the location in the default browser
    else:
        speak("Sorry, I didn't catch the location. Please try again.")
        update_text("Error: Location not specified.")  # Debugging: In case location is empty

# Modified execute_command function to include "dance" mode
def execute_command(command):
    if handle_conversation(command):
        return True
    
    if 'time' in command:
        current_time = datetime.datetime.now().strftime("%H:%M")
        speak(f"The time is {current_time}")
    elif 'wikipedia' in command:
        speak("Searching Wikipedia...")
        query = command.replace("wikipedia", "")
        result = wikipedia.summary(query, sentences=2)
        speak(f"According to Wikipedia, {result}")
    elif 'dance' in command or 'let\'s dance' in command:
        speak("Let's dance!")
        dance_mode()  # Call the dance function

    elif 'add task' in command or 'to-do' in command:
        add_to_do()
    elif 'show tasks' in command or 'list to-do' in command:
        list_to_do()
    elif 'clear to do list' in command:
        clear_to_do_list()
    elif 'sleep mode' in command:
        set_sleep_mode_command()



# Example of handling the volume command
    elif 'volume' in command:
        volume_level = extract_volume_from_command(command)  # Extract volume percentage
        if volume_level is not None:
            change_volume(volume_level)
        else:
            speak("I couldn't understand the volume level. Please specify a number.")

    elif 'weather' in command or 'what is the weather' in command:
        speak("Please tell me the city name to get the weather report.")
        update_text("Please tell me the city name to get the weather report.")
        city_name = take_command()
        if city_name:
            weather_report = get_weather_from_wttr(city_name)
            speak(weather_report)
            update_text(weather_report)
    elif 'open youtube' in command:
        speak("Opening YouTube")
        webbrowser.open("https://youtube.com")
    elif 'open instagram' in command:
        speak("Opening Instagram")
        webbrowser.open("https://instagram.com")
    elif 'open google' in command:
        speak("Opening Google")
        webbrowser.open("https://google.com")
    elif 'navigate to' in command or 'find location' in command:
        location = command.replace('navigate to', '').replace('find location', '').strip()
        search_location_on_google_maps(location)
    elif 'play' in command and 'song' in command:
        song_name = command.replace("play", "").replace("song", "").strip()
        search_url = f"https://open.spotify.com/search/{song_name.replace(' ', '%20')}"
        speak(f"Playing {song_name} on Spotify")
        webbrowser.open(search_url)
    elif 'open notepad' in command:
        speak("Opening Notepad")
        os.system("notepad")
    elif 'open spotify' in command:
        speak("Opening Spotify")
        webbrowser.open("https://spotify.com")

    elif 'set alarm' in command or 'alarm' in command:
        set_alarm_command()

    elif 'search' in command or 'find' in command or 'look up' in command or 'tell me' in command:
        query = command.replace("search", "").replace("find", "").replace("tell me", "").replace("look up", "").strip()
        speak(f"Searching Google for {query}")
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(search_url)
    elif 'calculate' in command or 'what is' in command or 'solve' in command:
        expression = command.replace('calculate', '').replace('what is', '').replace('solve', '').strip()
        # Replace 'times' with '*' and 'x' with '*'
        expression = expression.replace('times', '*').replace('x', '*')
        try:
            result = eval(expression)
            speak(f"The result is {result}")
            update_text(f"The result of {expression} is {result}.")
        except Exception as e:
            speak("Sorry, I couldn't calculate that.")
    elif 'exit' in command or 'quit' in command or 'bye' in command or 'good night' in command or 'get lost' in command:
        speak("Goodbye! Have a great day!")
        return False
    else:
        speak("Sorry, I didn't catch that. Can you say it again?")
    
    return True



# Function to update the GUI text
def update_text(new_text):
    result_label.config(text=new_text)
    root.update()

# Function to update the speech box with JARVIS's spoken text
def update_speech_box(text):
    speech_box.insert(tk.END, text + "\n\n")
    speech_box.see(tk.END)

# Function to run the JARVIS assistant in background thread
def jarvis_background():
    while True:
        command = take_command()
        if command:
            update_text(f"You said: {command}")
            if not execute_command(command):
                break

# Function to start JARVIS in the background
def start_jarvis_in_background():
    speak("Hello! How can I assist you today?")
    jarvis_thread = threading.Thread(target=jarvis_background)
    jarvis_thread.daemon = True
    jarvis_thread.start()




# Setting up the GUI window
root = tk.Tk()
root.title("JARVIS AI Assistant")
root.geometry("600x500")
root.config(bg='#00008B')
root.attributes('-alpha', 0.7)

custom_font = font.Font(family="OCR A Extended", size=12)

title_label = tk.Label(root, text="JARVIS AI Assistant", font=("OCR A Extended", 24), fg="#00fffb", bg='#00008B')
title_label.pack(pady=20)

result_label = tk.Label(root, text="", font=custom_font, fg="#00b8cc", bg='#00008B', wraplength=500)
result_label.pack(pady=20)

start_button = tk.Button(root, text="Start JARVIS", font=custom_font, command=start_jarvis_in_background, bg="#007acc", fg="white", relief="solid", borderwidth=1)
start_button.pack(pady=20)

speech_box = tk.Text(root, font=custom_font, height=5, bg='#00008B', fg="#00fffb", wrap='word', relief="flat", highlightthickness=0)
speech_box.pack(pady=20, padx=10)


root.mainloop()
