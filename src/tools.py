
from asyncio import subprocess
from smolagents import tool
import os
from time import sleep
from dotenv import load_dotenv
from smolagents import Tool
import psutil
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import subprocess
from src.DesktopBuddy import DesktopBuddy
from src.StateManager import BuddyStateManager, AudioState, RoutineState, UIState
import pygetwindow as gw

load_dotenv()

class AnalyseActiveWindow(Tool):
    name = "analyse_active_window"
    description = """Captura o título da janela que está ativa na tela do usuário e retorna seu título. Esta ferramenta NÃO aceita nenhum argumento ou parâmetro. Chame com arguments {}. 
    Returns:
        str | None: O título da janela ativa ou None se nenhuma janela ativa for encontrada."""
    inputs = {}
    output_type = "string"

    def forward(self) -> str | None:
        sleep(0.5)
        active_window = gw.getActiveWindow()
        if active_window is not None:
            title = active_window.title
            print(f"Active window title: {title}")
            return title
        else:
            print("No active window found.")
            return None

class ShowMessage(Tool):
    name = "show_message"
    description = "Exibe na tela alguma mensagem para o usuário. Use isso sempre que precisar comunicar algo para o usuário."
    inputs = {"message":{"type": "string", "description": "Mensagem a ser passada para o usuário."}}
    output_type = "null"

    def __init__(self, buddy: DesktopBuddy):
        super().__init__()
        self.buddy = buddy

    def forward(self, message: str) -> None:
        print(f"[Tool ShowMessage]: Exibindo mensagem -> {message}")
        
        # Dispara a renderização na thread principal com segurança
        self.buddy.window.after(0, lambda: self.buddy.display_agent_message(message))
        self.buddy.sprite_queue.put(UIState.SHOWING)
        
        return "Success: Message displayed to the user."

@tool
def list_processes() -> list[str]:
    """
    Lista os processos em execução no sistema,
    para que possa tomar a decisão de quais processos
    poderiam ser desconectados.
    """
    processes = []
    seen_names = set()
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] not in seen_names:
            seen_names.add(proc.info['name'])
            processes.append(f"{proc.info['pid']}: {proc.info['name']}")
    return processes

@tool
def kill_process(pid: int) -> bool:
    """
    Deve sempre ser solicitada a confirmação do usuário antes de chamar esta função.
    Mata um processo com base no seu PID.
    Args:
        pid (int): O ID do processo a ser morto.
    Returns:
        bool: True se o processo foi morto com sucesso, False caso contrário.
    """
    import psutil
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=3)
        print(f"Process {pid} terminated successfully.")
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
        print(f"Failed to terminate process {pid}: {e}")
        return False

class PlaySpotify(Tool):
    name = "play_spotify_playlist_or_track"
    description = "Abre o Spotify e inicia a reprodução de uma playlist ou música específica. Args: playlist_or_track_id (str): O ID da playlist do Spotify; call_type (integer): Identificador de o que será tocado. Envie 0 para tocar playlists e 1 para tocar músicas."
    inputs = {
        "playlist_or_track_id": {"type": "string", "description": "O ID da playlist do Spotify."},
        "call_type": {"type": "integer", "description": "Identificador de o que será tocado. Envie 0 para tocar playlists e 1 para tocar músicas."}
    }
    output_type = "string"

    def __init__(self, buddy: DesktopBuddy):
        super().__init__()
        self.buddy = buddy

    def forward(self, playlist_or_track_id: str, call_type: int) -> None:
        if not playlist_or_track_id or len(playlist_or_track_id.strip()) == 0:
            return "Error: playlist_or_track_id cannot be empty. You must provide a valid Spotify Link ID string. If you don't know the ID, tell the user you don't have it."
        
        # Força a abertura do Spotify
        subprocess.Popen(['spotify'])

        # Configurações de autenticação do Spotify
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.getenv('SPOTIPY_CLIENT_ID'),
            client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
            redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI'),
            scope='user-modify-playback-state, user-read-playback-state'
        ))

        tries = 0
        device_id = None
        while True:
            try:
                device_id = [d['id'] for d in sp.devices()['devices'] if d['type'] == 'Computer'][0]
                sp.transfer_playback(device_id, force_play=True)
                while True:
                    print("Waiting for Spotify to start playing...")
                    sleep(1)
                    if sp.current_playback() is not None and sp.current_playback()['is_playing']:
                        break
                break
            except (KeyError, IndexError):
                if tries >= 5:
                    print("Error: Failed to connect to Spotify after multiple attempts.")
                    return
                print("Spotify not ready yet, retrying...")
                tries += 1
                sleep(5)
                continue

        is_track = False
        try:
            sp.track(playlist_or_track_id)
            is_track = True
        except Exception:
            is_track = False

        # Abre a playlist
        current_play = sp.current_playback()
        if current_play['context'] is None or current_play['context']['uri'] != f"spotify:playlist:{playlist_or_track_id}" or current_play['context']['uris'][0] != f"spotify:track:{playlist_or_track_id}":
            try:
                match call_type:
                    case 0:
                        if is_track == True:
                            return "This id is a track not a playlist"
                        sp.start_playback(device_id=device_id, context_uri=f"spotify:playlist:{playlist_or_track_id}")
                    case 1:
                        if is_track == False:
                            return "This id is a playlist not a track"
                        sp.start_playback(device_id=device_id, uris=[f"spotify:track:{playlist_or_track_id}"])
                    case _:
                        return "Error: call_type provided is invalid. Use 0 for playlists and 1 for single tracks."
                    
                sleep(1.5)
                playback = sp.current_playback()
                
                if playback is None or not playback.get('is_playing', False):
                    return "Error: Playback command sent, but music is not active. Spotify may be paused or stuck. Please try again."
                
                self.buddy.sprite_queue.put(AudioState.MUSIC)
                print(f"Started playing Spotify: {playlist_or_track_id}")
                return f"Success: The {'playlist' if call_type == 0 else 'track'} is now actively playing on Spotify."
            except Exception as e:
                return f"Error controlling Spotify playback: {str(e)}. Check if your account has Premium active (required for SDK integration)."
        else:
            self.buddy.sprite_queue.put(AudioState.MUSIC)
            print("Spotify is already playing the desired playlist or track.")
            return "Success: The playlist is now playing on Spotify."

class PauseSpotify(Tool):
    name = "pause_spotify"
    description = "Pausa a reprodução do Spotify."
    inputs = {}
    output_type = "null"

    def __init__(self, buddy: DesktopBuddy):
        super().__init__()
        self.buddy = buddy

    def forward(self) -> None:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.getenv('SPOTIPY_CLIENT_ID'), client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'), redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI'), scope='user-modify-playback-state, user-read-playback-state'))
        sp.pause_playback()
        self.buddy.sprite_queue.put(AudioState.SILENT)
        print("Spotify playback paused.")
        return "Success: Spotify playback paused."

class ResumeSpotify(Tool):
    name = "resume_spotify"
    description = "Retoma a reprodução do Spotify."
    inputs = {}
    output_type = "null"

    def __init__(self, buddy: DesktopBuddy):
        super().__init__()
        self.buddy = buddy

    def forward(self) -> None:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.getenv('SPOTIPY_CLIENT_ID'), client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'), redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI'), scope='user-modify-playback-state, user-read-playback-state'))
        sp.start_playback()
        self.buddy.sprite_queue.put(AudioState.MUSIC)
        print("Spotify playback resumed.")
        return "Success: Spotify playback resumed."


class PomodoroTimer(Tool):
    name = "start_pomodoro_timer"
    description = """
    Inicia um timer de Pomodoro.
    Args:
        work_duration (int): Duração do período de trabalho em minutos.
        break_duration (int): Duração do período de descanso em minutos.
        loops (int): Número de ciclos do Pomodoro.
    """
    inputs = {
        "work_duration": {"type": "integer", "description": "Duração do período de trabalho em minutos.", "nullable": True},
        "break_duration": {"type": "integer", "description": "Duração do período de descanso em minutos.", "nullable": True},
        "loops": {"type": "integer", "description": "Número de ciclos do Pomodoro.", "nullable": True}
    }
    
    output_type = "null"

    def __init__(self, buddy: DesktopBuddy):
        super().__init__()
        self.buddy = buddy

    def forward(self, work_duration: int = 25, break_duration: int = 5, loops: int = 4) -> None:
        print(f"Starting Pomodoro timer: {work_duration} minutes of work followed by {break_duration} minutes of break.")
        self.buddy.is_pomodoro_active = True
        self.buddy.pomodoro_loops = loops
        self.buddy.time_left = work_duration * 60
        self.buddy.work_duration = work_duration
        self.buddy.break_duration = break_duration

        self.buddy.sprite_queue.put(RoutineState.WORKING)

class ChangeState(Tool):
    name = "change_buddy_state"
    description = """
    Muda o estado de rotina do Buddy, podendo ser 'IDLE'(0) ou 'WORKING'(1).
    Args:
        id_state (int): Identificação do estado.
    """
    inputs = {"id_state" : {"type": "integer", "description": "Identificação do estado. 'IDLE'(0) ou 'WORKING'(1)"}} 
    output_type = "string"

    def __init__(self, buddy: DesktopBuddy):
        super().__init__()
        self.buddy = buddy
    
    def forward(self, id_state: int):
        match id_state:
            case 0:
                self.buddy.sprite_queue.put(RoutineState.IDLE)
                return "Estado alterado para 'IDLE' (0)"
            case 1:
                self.buddy.sprite_queue.put(RoutineState.WORKING)
                return "Estado alterado para 'WORKING' (1)"
            case _:
                return "ID inválido"