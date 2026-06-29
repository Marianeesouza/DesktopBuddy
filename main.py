from src.DesktopBuddy import DesktopBuddy
from src.tools import ResumeSpotify, PauseSpotify, AnalyseActiveWindow, list_processes, WorkModeManager, PlaySpotify, ShowMessage, VerifySpotify, TrelloCardList, TrelloGetCardDescription, TrelloTaskViewer, TrelloTaskLauncher
from smolagents import ToolCallingAgent, LiteLLMModel
import psutil
import os
import subprocess
import time
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pygetwindow as gw
from pathlib import Path

def start_ollama():
    print("Verificando se o Ollama está ativo...")
    try:
        # Tenta fazer uma requisição simples para o servidor do Ollama
        response = requests.get("http://localhost:11434/", timeout=2)
        if response.status_code == 200:
            print("Ollama já está rodando!")
            return
    except requests.exceptions.ConnectionError:
        print("Ollama não encontrado. Iniciando o serviço em segundo plano (Oculto)...")
        
        caminho_ollama_cli = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
        
        if os.path.exists(caminho_ollama_cli):
            CREATE_NO_WINDOW = 0x08000000
            
            # Passamos o argumento "serve" para ele agir apenas como servidor de API
            subprocess.Popen(
                [caminho_ollama_cli, "serve"], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW
            )
            
            print("Aguardando o Ollama inicializar...")
            for i in range(15):
                try:
                    if requests.get("http://localhost:11434/", timeout=2).status_code == 200:
                        print("Ollama inicializado com sucesso!")
                        return
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                    time.sleep(1)
            
            print("Aviso: O comando de abertura foi enviado, mas o servidor está demorando a responder.")
        else:
            print(f"Erro: Executável CLI do Ollama não encontrado em: {caminho_ollama_cli}")

def start_spotify_silent():
    print("Preparando o ambiente do Spotify...")
    
    try:
        subprocess.Popen(["cmd", "/c", "start", "spotify:"], shell=True)
    except Exception as e:
        print(f"Erro ao tentar abrir o Spotify: {e}")
        return

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv('SPOTIPY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
        redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI'),
        scope='user-modify-playback-state, user-read-playback-state'
    ))

    print("Aguardando comunicação com o player do Spotify...")
    device_id = None
    for _ in range(15):
        try:
            devices = sp.devices()['devices']
            computer_devices = [d['id'] for d in devices if d['type'] == 'Computer']
            if computer_devices:
                device_id = computer_devices[0]
                break
        except Exception:
            pass
        time.sleep(1)

    if not device_id:
        print("Aviso: Dispositivo de computador não encontrado.")
        return

    try:
        current_playback = sp.current_playback()
        old_volume = current_playback['device']['volume_percent'] if current_playback else 50
        
        sp.transfer_playback(device_id, force_play=False)
        sp.volume(0, device_id=device_id)
        
        sp.start_playback(device_id=device_id, uris=["spotify:track:5aiw148eh0xYAI1S1vS9Wj"])
        time.sleep(0.6)
        sp.pause_playback(device_id=device_id)
        sp.volume(old_volume, device_id=device_id)
        
        print("Música tratada via API.")
    except Exception as e:
        print(f"Não foi possível registrar o play silencioso: {e}")

    print("Minimizando a janela após os comandos de som...")
    for _ in range(6):
        spotify_windows = [w for w in gw.getAllTitles() if "Spotify" in w]
        if spotify_windows:
            try:
                win = gw.getWindowsWithTitle(spotify_windows[0])[0]
                if not win.isMinimized:
                    win.minimize()
                    print("Janela do Spotify minimizada em definitivo!")
                    break
            except Exception:
                pass
        time.sleep(0.5)

    print("Spotify ativo e guardado na barra de tarefas!")

if __name__ == "__main__":
    start_ollama()
    start_spotify_silent()
    buddy_instance = DesktopBuddy()  

    local_model = LiteLLMModel(
        model_id="ollama/gemma4:e2b",
        api_base="http://localhost:11434",
        temperature=1.0,
        max_tokens=512
    )

    api_model = LiteLLMModel(
        model_id="gemini/gemini-1.5-flash",
        temperature=1.0,
        max_tokens=512
    )

    agent = ToolCallingAgent(
        tools=[PlaySpotify(buddy_instance), PauseSpotify(buddy_instance), ResumeSpotify(buddy_instance), AnalyseActiveWindow(), ShowMessage(buddy_instance), list_processes, WorkModeManager(buddy_instance), TrelloTaskViewer(buddy_instance), VerifySpotify(), TrelloTaskLauncher(), TrelloCardList(buddy_instance), TrelloGetCardDescription(buddy_instance)],
        max_steps = 5,
        model=local_model
    )

    PROMPT_PATH = Path("src/prompts") / "system_prompt.txt"

    SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

    agent.prompt_templates["system_prompt"] = SYSTEM_PROMPT

    buddy_instance.agent = agent

    buddy_instance.run()