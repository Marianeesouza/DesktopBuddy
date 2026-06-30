
from asyncio import subprocess
from smolagents import tool
import os
import re
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
import webbrowser

load_dotenv()

class AnalyseActiveWindow(Tool):
    name = "analyse_active_window"
    description = """Obtém o título da janela atualmente em foco no computador do usuário.
    Use esta ferramenta somente quando precisar saber qual aplicação ou documento o usuário está utilizando.
    Não utilize esta ferramenta para adivinhar atividades do usuário.
    Entrada obrigatória: {}.
    
    Exemplos:
    - "O que estou fazendo?"
    - "Analise minha janela atual."
    - "Qual programa está aberto?"""
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
    description = """Exibe uma mensagem textual ao usuário. Utilize esta ferramenta apenas quando for realmente necessário enviar uma mensagem.

    Exemplos:
    - responder perguntas;
    - solicitar informações;
    - informar erros;
    - emitir avisos;
    - fornecer orientações.

    Não utilize esta ferramenta apenas para confirmar que outra ferramenta foi executada. Se outra ferramenta já apresentou a informação ao usuário (por exemplo, abriu um painel, uma janela ou uma interface), não utilize show_message."""
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
        
        return "done"

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

    def forward(self, playlist_or_track_id: str, call_type: int) -> str:
        if not playlist_or_track_id or len(playlist_or_track_id.strip()) == 0:
            return "Error: playlist_or_track_id cannot be empty. You must provide a valid Spotify Link ID string. If you don't know the ID, tell the user you don't have it."
        
        subprocess.Popen(['spotify'])

        sp = self.buddy.spotify_client

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
        already_playing = False
        if current_play and current_play.get('is_playing'):
            context = current_play.get('context')

            if call_type == 0 and context:
                # Verificando se a playlist desejada já está tocando
                already_playing = context.get('uri') == f"spotify:playlist:{playlist_or_track_id}"
            elif call_type == 1:
                # Verificando se a faixa (item) atual é a mesma desejada
                item = current_play.get('item')
                already_playing = item and item.get('id') == playlist_or_track_id
                
        if not already_playing:
            try:
                match call_type:
                    case 0:
                        if is_track:
                            return "Error: This ID belongs to a track, not a playlist."
                        sp.start_playback(device_id=device_id, context_uri=f"spotify:playlist:{playlist_or_track_id}")
                    case 1:
                        if not is_track:
                            return "Error: This ID belongs to a playlist, not a track."
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
    output_type = "string"

    def __init__(self, buddy: DesktopBuddy):
        super().__init__()
        self.buddy = buddy

    def forward(self) -> str:
        sp = self.buddy.spotify_client
        try:
            sp.pause_playback()
            self.buddy.sprite_queue.put(AudioState.SILENT)
            print("Spotify playback paused.")
            return "Success: Spotify playback paused."
        except spotipy.exceptions.SpotifyException as e:
            if "Restriction violated" in str(e) or e.http_status == 403:
                return "Success: Spotify is already paused."
            return f"Error pausing Spotify: {str(e)}"

class ResumeSpotify(Tool):
    name = "resume_spotify"
    description = "Retoma a reprodução do Spotify de onde ela foi pausada."
    inputs = {}
    output_type = "string"

    def __init__(self, buddy: DesktopBuddy):
        super().__init__()
        self.buddy = buddy

    def forward(self) -> str:
        sp = self.buddy.spotify_client
        try:
            sp.start_playback()
            self.buddy.sprite_queue.put(AudioState.MUSIC)
            print("Spotify playback resumed.")
            return "Success: Spotify playback resumed."
        except spotipy.exceptions.SpotifyException as e:
            if "Restriction violated" in str(e) or e.http_status == 403:
                self.buddy.sprite_queue.put(AudioState.MUSIC)
                return "Success: Spotify playback is already active and playing."
            return f"Error resuming Spotify: {str(e)}"
        
class VerifySpotify(Tool):
    name = "verify_spotify"
    description = """Verifica o estado atual do Spotify.
    Retorna:
    1 → reproduzindo
    0 → pausado
    -1 → Spotify indisponível ou fechado

    Utilize esta ferramenta somente quando precisar decidir entre pausar, retomar ou iniciar uma reprodução."""
    inputs = {}
    output_type = "integer"

    def __init__(self, buddy: DesktopBuddy):
        super().__init__()
        self.buddy = buddy

    def forward(self) -> int:
        sp = self.buddy.spotify_client

        try:
            playback = sp.current_playback()

            if playback is None:
                return -1

            is_playing = playback.get('is_playing', False)
            return 1 if is_playing else 0

        except Exception as e:
            print(f"[VerifySpotify Tool Error]: {str(e)}")
            return -1        

class WorkModeManager(Tool):
    name = "work_mode_manager"
    description = """Ativa ou desativa o modo de trabalho do Buddy.
    Use esta ferramenta quando o usuário quiser:
    - começar a trabalhar
    - entrar em modo de foco
    - ativar modo de trabalho
    - iniciar um pomodoro
    - encerrar o modo de trabalho

    NÃO utilize esta ferramenta para abrir tarefas do Trello.

    Se o usuário NÃO mencionar pomodoro, utilize:

    id_state = 1
    pomodoro_work_time = 0
    pomodoro_break_time = 0
    pomodoro_loops = 0

    Somente pergunte sobre tempos do pomodoro quando o usuário demonstrar intenção explícita de utilizar essa técnica.
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
    description = """Abre o painel visual das tarefas do Trello. Esta ferramenta já apresenta a interface ao usuário. Depois de utilizá-la normalmente nenhuma outra ferramenta precisa ser chamada. Não utilize show_message após esta ferramenta apenas para informar que o painel foi aberto."""
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
        return "done"
    
class TrelloCardList(Tool):
    name = "trello_card_list"
    description = """Lista todos os cards pendentes do Trello e retorna seus nomes e respectivos IDs.Utilize esta ferramenta quando precisar descobrir qual card corresponde à tarefa que o usuário deseja abrir. Sempre obtenha o ID por meio desta ferramenta. Nunca invente IDs de cards.

    Exemplos:
    - "vamos trabalhar na tarefa"
    - "abra minha tarefa"
    - "continuar projeto"
    - "preparar tarefa"

    """
    inputs = {}
    output_type = "string"

    def __init__(self, buddy):
        super().__init__()
        self.buddy = buddy
    
    def forward(self):
        try:
            board = self.buddy.trello_board 
            lines = []
            for lst in board.all_lists():
                cards = lst.list_cards(card_filter='open')
                incomplete = [c for c in cards if not c.is_due_complete]
                
                for card in incomplete:
                    lines.append(f"ID: {card.id} | Nome: {card.name}")
            
            return "\n".join(lines) if lines else "Nenhum card pendente encontrado."
        except Exception as e:
            return f"Erro ao listar cards: {str(e)}"
    
class TrelloTaskLauncher(Tool):
    name = "task_launcher"
    description = """Abre automaticamente todos os recursos associados a um card do Trello.
    A descrição do card pode conter:
    - URLs
    - pastas
    - arquivos
    - projetos do VS Code
    - projetos do IntelliJ
    - comandos
    Forneça apenas o ID do card. Nunca invente um ID. Sempre utilize um ID obtido anteriormente pelo trello_card_list. Use esta ferramenta somente quando o usuário realmente desejar abrir ou preparar uma tarefa."""
    inputs = {
        "card_id": {
            "type": "string",
            "description": "O ID único do card que você deseja ler a descrição."
        }
    }
    output_type = "string"

    def __init__(self, buddy):
        super().__init__()
        self.buddy = buddy

    def forward(self, card_id: str) -> str:
        try:
            card = self.buddy.trello_client.get_card(card_id)
            
            if not card:
                return f"Card com ID {card_id} não foi encontrado no Trello."
                
            if card.description:
                opened = []
                
                for item in card.description.splitlines():
                    item = item.strip()
                    
                    if not item:
                        continue

                    if item.startswith("-"):
                        item = item[1:].strip()

                    url_match = re.search(r'https?://[^\s\)"]+', item)

                    if url_match:
                        print("url_match")
                        url = url_match.group(0)
                        webbrowser.open(url)
                        opened.append(url)
                        continue
                        
                    elif item.upper().startswith("VSCODE:"):
                        path = item[7:].strip()
                        subprocess.Popen(f'code "{path}"', shell=True)
                        opened.append(f"VS Code ({path})")
                        
                    elif item.upper().startswith("INTELLIJ:"):
                        path = item[9:].strip()
                        subprocess.Popen(f'idea "{path}"', shell=True)
                        opened.append(f"IntelliJ ({path})")
                        
                    elif item.startswith("http://") or item.startswith("https://"):
                        print("webbrowser")
                        webbrowser.open(item)
                        opened.append(item)

                    elif item.upper().startswith("CMD:"):
                        cmd = item[4:].strip()
                        subprocess.Popen(cmd, shell=True)
                        
                    elif os.path.exists(item):
                        if hasattr(os, 'startfile'):
                            os.startfile(item)
                
                if not opened:
                    return f"A descrição do card '{card.name}' foi lida, mas nenhum alvo válido foi encontrado."
                    
                return f"Sucesso ao abrir os seguintes alvos do card '{card.name}': {', '.join(opened)}"
                
            return f"O card '{card.name}' não possui nenhuma descrição informada."
            
        except Exception as e:
            return f"Erro ao buscar detalhes do card {card_id}: {str(e)}"
        

class TrelloGetCardDescription(Tool):
    name = "trello_get_card_description"
    description = """
    Obtém a descrição completa de um card do Trello utilizando seu ID. Utilize esta ferramenta quando precisar ler o conteúdo de um card antes de decidir a próxima ação. Não invente IDs. O ID deve vir do trello_card_list.
    """
    inputs = {
        "card_id": {
            "type": "string",
            "description": "O ID único do card que você deseja ler a descrição."
        }
    }
    output_type = "string"

    def __init__(self, buddy):
        super().__init__()
        self.buddy = buddy

    def forward(self, card_id: str) -> str:
        try:
            card = self.buddy.trello_client.get_card(card_id)
            if card and card.description:
                return f"Descrição do Card '{card.name}':\n{card.description}"
            return f"O card '{card.name}' não possui nenhuma descrição informada."
        except Exception as e:
            return f"Erro ao buscar detalhes do card {card_id}: {str(e)}"
        

@tool
def list_processes() -> list[str]:
    """
    Lista todos os processos atualmente em execução. Utilize esta ferramenta apenas quando precisar descobrir o PID de algum programa. Não utilize esta ferramenta se o usuário já informou o PID.

    Returns:
        Lista dos processos abertos no momento.
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
    Encerra um processo do sistema.

    PERIGOSO. Antes de utilizar esta ferramenta você DEVE confirmar
    explicitamente com o usuário. Nunca encerre processos sem confirmação.

    Args:
        pid: PID do processo a ser encerrado. Deve ser obtido pela ferramenta
            list_processes ou informado explicitamente pelo usuário.

    Returns:
        True se o processo foi encerrado com sucesso, False caso contrário.
    """

    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=3)
        print(f"Process {pid} terminated successfully.")
        return True

    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
        print(f"Failed to terminate process {pid}: {e}")
        return False