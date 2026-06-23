
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
        
        subprocess.Popen(['spotify'])

        # Spotify auth config
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

class WorkModeManager(Tool):
    name = "work_mode_manager"
    description = """
    Muda o estado de rotina do Buddy para WORKING ou volta para o modo IDLE. Para iniciar essa ferramenta sem o uso do pomodoro, passe os parâmetros "pomodoro_work_time", "pomodoro_break_time" e "pomodoro_loops" como 0.
    Args:
        id_state (int): Envie 1 para ativar o modo de trabalho (WORKING) ou 0 para desativar (IDLE).
        pomodoro_work_time (int): Tempo de trabalho do pomodoro em segundos.
        pomodoro_break_time (int): Tempo de intervalo do pomodoro em segundos.
        pomodoro_loops (int): Quantidade de ciclos completos. Envie 0 para modo de foco infinito.
    """
    inputs = {
        "id_state": {"type": "integer", "description": "Identificação do estado. 0 para IDLE, 1 para WORKING."},
        "pomodoro_work_time": {"type": "integer", "description": "Tempo em minutos que durará o tempo de trabalho do ciclo pomodoro.", "nullable": True},
        "pomodoro_break_time": {"type": "integer", "description": "Tempo em minutos que durará o tempo de intervalo do ciclo pomodoro.", "nullable": True},
        "pomodoro_loops": {"type": "integer", "description": "Quantidade de loops (Work+Break) que vai durar o pomodoro. Envie 0 para não ativar o ciclo.", "nullable": True}
    } 
    output_type = "string"

    def __init__(self, buddy: DesktopBuddy):
        super().__init__()
        self.buddy = buddy
    
    def forward(self, id_state: int, pomodoro_work_time: int = None, pomodoro_break_time: int = None, pomodoro_loops: int = None):
        match id_state:
            case 0:
                self.buddy.stop_work_mode()
                return "Modo de trabalho encerrado com sucesso."
            case 1:
                if pomodoro_loops is None or pomodoro_break_time is None or pomodoro_work_time is None:
                    return "AVISO: Você está chamando esta ferramenta 'work_mode_manager' com os parâmetros do pomodoro nulos. Você DEVE usar a ferramenta 'show_message' para perguntar ao usuário se o pomodoro deve ou não ser ativo. Em caso positivo, pergunte quais os tempos dos períodos de trabalho e intervalo em minutos."
                self.buddy.work_duration = (pomodoro_work_time if pomodoro_work_time is not None else 0)*60
                self.buddy.break_duration = (pomodoro_break_time if pomodoro_break_time is not None else 0)*60
                self.buddy.pomodoro_loops = pomodoro_loops if pomodoro_loops is not None else 0
                self.buddy.start_work_mode()
                if pomodoro_loops == 0:
                    return f"Modo de trabalho contínuo iniciado com sucesso."
                else:
                    return f"Modo Pomodoro iniciado com sucesso!"
            case _:
                return "Error: ID inválido. Use 0 para parar ou 1 para iniciar o modo de trabalho."
            
class TrelloTaskViewer(Tool):
    name = "trello_task_viewer"
    description = "Abre uma interface visual integrada no Buddy para exibir os cards de tasks incompletas organizados por listas do Trello."
    inputs = {
        "message": {
            "type": "string",
            "description": "A mensagem ou introdução que o Buddy vai falar no topo do painel (ex: 'Aqui estão suas tarefas de hoje!').",
            "nullable": True
        }
    }
    output_type = "string"

    def __init__(self, buddy):
        super().__init__()
        self.buddy = buddy
    
    def forward(self, message="Aqui estão suas atividades pendentes:"):
        self.buddy.window.after(0, lambda: self.buddy.open_trello_dashboard(message))
        return "Painel do Trello aberto com a mensagem do agente."