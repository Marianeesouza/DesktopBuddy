from src.DesktopBuddy import DesktopBuddy
from src.tools import ResumeSpotify, PauseSpotify, AnalyseActiveWindow, list_processes, WorkModeManager, PlaySpotify, ShowMessage, TrelloTaskViewer
from smolagents import ToolCallingAgent, LiteLLMModel
import psutil
import os
import subprocess
import time
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pygetwindow as gw

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
    
    # 1. Abre o Spotify normalmente
    try:
        subprocess.Popen(["cmd", "/c", "start", "spotify:"], shell=True)
    except Exception as e:
        print(f"Erro ao tentar abrir o Spotify: {e}")
        return

    # 2. Instancia a API do Spotipy para a rotina de ativação
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

    # 3. Executa a rotina da API primeiro (o que costumava forçar a janela a abrir)
    try:
        current_playback = sp.current_playback()
        old_volume = current_playback['device']['volume_percent'] if current_playback else 50
        
        sp.transfer_playback(device_id, force_play=False)
        sp.volume(0, device_id=device_id)
        
        # Toca e pausa logo em seguida
        sp.start_playback(device_id=device_id, uris=["spotify:track:5aiw148eh0xYAI1S1vS9Wj"])
        time.sleep(0.6) # Um pequeno fôlego para o comando processar nos servidores
        sp.pause_playback(device_id=device_id)
        sp.volume(old_volume, device_id=device_id)
        
        print("Música tratada via API.")
    except Exception as e:
        print(f"Não foi possível registrar o play silencioso: {e}")

    # 4. --- GOLPE FINAL: Minimiza a janela DEPOIS de todos os comandos de playback ---
    print("Minimizando a janela após os comandos de som...")
    for _ in range(6):  # Tenta por até 3 segundos garantir que ela suma
        spotify_windows = [w for w in gw.getAllTitles() if "Spotify" in w]
        if spotify_windows:
            try:
                win = gw.getWindowsWithTitle(spotify_windows[0])[0]
                if not win.isMinimized: # Só manda minimizar se ela tiver pulado na tela
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
        model_id="ollama/qwen2.5:3b",
        api_base="http://localhost:11434",
        temperature=0.1,
        max_tokens=512
    )

    agent = ToolCallingAgent(
        tools=[PlaySpotify(buddy_instance), PauseSpotify(buddy_instance), ResumeSpotify(buddy_instance), AnalyseActiveWindow(), ShowMessage(buddy_instance), list_processes, WorkModeManager(buddy_instance), TrelloTaskViewer(buddy_instance)],
        max_steps = 5,
        model=local_model
    )

    agent.prompt_templates["system_prompt"] = """Você é o Desktop Buddy, um assistente de desktop prestativo e amigável. Você pode realizar várias tarefas no computador do usuário utilizando as ferramentas à sua disposição. Sempre priorize as necessidades do usuário e forneça a melhor assistência possível, de forma educada e amigável.

    REGRAS OPERACIONAIS:
    1. PASSOS MÍNIMOS: Sempre conclua a tarefa solicitada com a menor quantidade de passos possível. Não chame ferramentas desnecessárias. Evite chamar a mesma ferramenta várias vezes em sequência.
    2. EXECUÇÃO SEQUENCIAL: Se uma tarefa exigir várias etapas, divida-as e chame as ferramentas de forma sequencial.
    3. LIMITE MÁXIMO DE PASSOS: Se o limite máximo de passos for atingido antes da conclusão, simplesmente diga que não pode responder a essa solicitação.
    4. HONESTIDADE: Se você não souber como fazer algo, não há problema em dizer que não sabe, mas tente encontrar uma maneira de ajudar com as ferramentas que possui. Se precisar de mais informações, pergunte ao usuário de forma clara e concisa.

    REGRAS CRÍTICAS DE SINTAXE E FERRAMENTAS:
    - JSON ESTRITO: Ao chamar ferramentas, você DEVE fornecer APENAS parâmetros JSON válidos que correspondam ao esquema (schema) da ferramenta. NÃO gere texto, chaves extras, trechos de código, tokens ou espaços em branco dentro dos argumentos da ferramenta. Seja extremamente conciso. Toda chamada de ferramenta PRECISA conter a chave 'name' e a chave 'arguments'.
    - NÃO INVENTE ARGUMENTOS: Se uma ferramenta possui um esquema de entrada vazio (como 'analyse_active_window'), seu campo de argumentos DEVE ser estritamente {}. Nunca injete o retorno/saída de uma ferramenta de volta em seus próprios parâmetros.
    - COMUNICAÇÃO COM O USUÁRIO: CRÍTICO! Para falar ou comunicar qualquer coisa ao usuário (incluindo sua resposta final, respostas, pensamentos ou comentários), você DEVE sempre usar a ferramenta 'show_message'. Não use saídas de texto comum para respostas finais.

    EXEMPLO DE UM FLUXO CORRETO:
    Usuário: "analise a minha janela ativa e me diga se ela é útil"
    Thought: Eu preciso capturar o título da janela ativa primeiro.
    Action: analyse_active_window com os argumentos {}
    Observation: "Vídeo de Gameplay - YouTube - Google Chrome"
    Thought: Eu tenho a informação. Agora preciso dizer ao usuário o que encontrei usando a ferramenta correta.
    Action: show_message com os argumentos {"message": "Você está vendo um vídeo de gameplay no Youtube. Isso não parece produtivo! Vamos voltar ao trabalho!"}
    Observation: "Success: Message displayed to the user."
    Thought: Tarefa concluída.
    Action: final_answer com os argumentos {"answer": "Task completed successfully."}
    """

    buddy_instance.agent = agent

    buddy_instance.run()