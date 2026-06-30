import psutil
import os
import subprocess
import time
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from smolagents import ToolCallingAgent, LiteLLMModel
import pygetwindow as gw
from pathlib import Path

from src.DesktopBuddy import DesktopBuddy
from src.DesktopAgent import DesktopAgent
from src.utils import start_ollama, start_spotify_silent
from src.tools import ResumeSpotify, PauseSpotify, AnalyseActiveWindow, WorkModeManager, PlaySpotify, ShowMessage, VerifySpotify, TrelloCardList, TrelloGetCardDescription, TrelloTaskViewer, TrelloTaskLauncher

if __name__ == "__main__":
    start_ollama()
    start_spotify_silent()
    buddy_instance = DesktopBuddy()  

    local_model = LiteLLMModel(
        model_id="ollama/gemma4:e2b",
        api_base="http://localhost:11434",
        temperature=0.1,
        max_tokens=512
    )

    api_model = LiteLLMModel(
        model_id="gemini/gemini-2.5-flash",
        temperature=0.1,
        max_tokens=512
    )

    tools = [PlaySpotify(buddy_instance), PauseSpotify(buddy_instance), ResumeSpotify(buddy_instance), AnalyseActiveWindow(), ShowMessage(buddy_instance), WorkModeManager(buddy_instance), TrelloTaskViewer(buddy_instance), VerifySpotify(buddy_instance), TrelloTaskLauncher(buddy_instance), TrelloCardList(buddy_instance), TrelloGetCardDescription(buddy_instance)]

    agent = DesktopAgent(local_model, tools)

    buddy_instance.agent = agent

    buddy_instance.run()