from enum import Enum, auto
import threading
import tkinter as tk
from PIL import Image, ImageTk
import queue
import json
import os

class BuddyStates(Enum):
    IDLE = auto()
    MUSIC = auto()
    WORKING = auto()
    SHOWING = auto()
    BREAK = auto()
    FUN = auto()
    THINKING = auto()

def load_sprites_config():
    caminho_config = "sprites.json"
    if os.path.exists(caminho_config):
        with open(caminho_config, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print("Erro: arquivo sprites.json não encontrado!")
        # Fallback seguro para evitar que o programa quebre imediatamente
        return {state.name: "idle.gif" for state in BuddyStates}

class DesktopBuddy:
    def __init__(self):
        # State management
        self.state = BuddyStates.IDLE
        self.last_state = self.state
        self.base_state = BuddyStates.IDLE
        self.state_changed_by_tool = False
        self.SPRITES = load_sprites_config()

        # Tkinter attributes
        self.window = tk.Tk()
        self.window.overrideredirect(True)  # Remove window decorations
        self.window.attributes("-topmost", True)  # Keep on top

        # Size and position of the window
        self.window_width = 260
        self.window_height = 260
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # Posicionamento inicial (Canto inferior direito)
        self.curr_x = screen_width - self.window_width - 20
        self.curr_y = screen_height - self.window_height - 50
        self.window.geometry(f"{self.window_width}x{self.window_height}+{self.curr_x}+{self.curr_y}")

        # Set transparency
        self.transparency_color = '#00ff00'  # Green color for transparency
        self.window.config(bg=self.transparency_color)
        self.window.attributes("-transparentcolor", self.transparency_color)

        # Cache de animação para evitar Garbage Collection
        self.current_frames = []
        self.current_frame_index = 0
        self.load_gif(self.SPRITES.get("IDLE", "idle.gif"))

        # Label principal que renderiza o Sprite
        self.label = tk.Label(
            self.window,
            fg="white",                  
            bg=self.transparency_color,
            font=("Arial", 16, "bold")
        )
        self.label.pack(expand=True, fill="both")

        # Widget de comando ÚNICO (reutilizado via place/place_forget)
        self.command_entry = tk.Entry(self.window, font=("Arial", 10))
        self.command_entry.bind("<Return>", lambda event: self.send_command(self.command_entry.get()))

        self.msg_label = tk.Label(
            self.window, 
            font=("Arial", 10, "italic"), 
            bg="#f0f0f0",          # Fundo cinza claro para o balão
            fg="#333333",          # Texto escuro
            bd=1,                  
            relief="solid",        # Borda simples para parecer um balão de fala
            wraplength=240,        # Quebra o texto automaticamente
            justify="center"
        )

        # Inicializa o loop de animação
        self.update_animation()

        # Enable dragging the window
        self.is_dragging = False
        self.drag_x = 0
        self.drag_y = 0
        
        self.label.bind("<ButtonPress-1>", self.start_drag)
        self.label.bind("<B1-Motion>", self.do_drag)
        self.label.bind("<ButtonRelease-1>", self.release_click)

        # Agent and threading attributes
        self.agent = None  # Deve ser injetado externamente
        self.sprite_queue = queue.Queue()
        self.check_sprite_queue()

        # Pomodoro timer attributes (Reservados para expansão futura)
        self.is_pomodoro_active = False
        self.pomodoro_loops = 0
        self.time_left = 0
        self.work_duration = 0
        self.break_duration = 0
    
    def run(self):
        self.window.mainloop()
    
    def check_sprite_queue(self):
        try:
            state_name = self.sprite_queue.get_nowait()
            
            if state_name == "last":
                state_name = self.base_state.name
            else:
                # Se veio qualquer outra coisa (ex: "MUSIC"), foi a tool que pediu!
                self.state_changed_by_tool = True
            
            if state_name in self.SPRITES:
                self.change_state(state_name)
            else:
                print(f"Estado desconhecido na fila: {state_name}. Usando o último estado {self.last_state.name}")
                self.change_state(self.last_state.name)
                
            self.sprite_queue.task_done()
        except queue.Empty:
            pass
            
        self.window.after(100, self.check_sprite_queue)
    
    def start_drag(self, event):
        self.drag_x = event.x
        self.drag_y = event.y
        self.is_dragging = False

    def do_drag(self, event):
        # Define um limiar pequeno para diferenciar clique de arrasto real
        if abs(event.x - self.drag_x) > 3 or abs(event.y - self.drag_y) > 3:
            self.is_dragging = True
            
        if self.is_dragging:
            self.curr_x = self.window.winfo_x() + (event.x - self.drag_x)
            self.curr_y = self.window.winfo_y() + (event.y - self.drag_y)
            self.window.geometry(f"+{self.curr_x}+{self.curr_y}")

    def release_click(self, event):
        if not self.is_dragging:
            # Atualiza as coordenadas atuais antes de redimensionar
            self.curr_x = self.window.winfo_x()
            self.curr_y = self.window.winfo_y()

            if self.state == BuddyStates.SHOWING:
                # E se o balão de mensagem do agente estiver ativo na tela
                if self.msg_label.winfo_manager() == "place":
                    self.msg_label.place_forget() # Esconde o balão
                    self.change_state(self.last_state.name) # Volta para o estado base real
                    self.window.geometry(f"{self.window_width}x{self.window_height}+{self.curr_x}+{self.curr_y}")
                else:
                    # Se não era o balão, era a caixinha de comandos aberta pelo usuário. Fecha ela.
                    self.change_state(self.last_state.name)
                    self.window.geometry(f"{self.window_width}x{self.window_height}+{self.curr_x}+{self.curr_y}")
                    self.command_entry.place_forget()
            else:
                # Se o pet não estava em SHOWING, o clique abre a caixinha de comandos normal
                self.change_state("SHOWING")
                self.window.geometry(f"{self.window_width}x{self.window_height + 30}+{self.curr_x}+{self.curr_y}")
                self.on_pure_click()
        
        self.is_dragging = False

    def on_pure_click(self):
        self.command_entry.place(x=0, y=0, relwidth=1, height=25)
        self.command_entry.delete(0, tk.END)
        self.command_entry.focus_set()

    def display_agent_message(self, text: str):
        # 1. Força o estado para SHOWING para carregar os sprites corretos
        self.change_state("SHOWING")
        
        # 2. Configura o texto e exibe o label no topo (y=0)
        self.msg_label.config(text=text)
        self.msg_label.place(x=10, y=0, width=240, height=40)
        
        # 3. Atualiza as coordenadas e aumenta a janela (+45px para o balão)
        self.curr_x = self.window.winfo_x()
        self.curr_y = self.window.winfo_y()
        self.window.geometry(f"{self.window_width}x{self.window_height + 45}+{self.curr_x}+{self.curr_y}")
    
    def send_command(self, command: str):
        if not command.strip():
            return
        
        self.change_state(BuddyStates.THINKING.name)
            
        self.command_entry.place_forget()
        
        self.curr_x = self.window.winfo_x()
        self.curr_y = self.window.winfo_y()
        self.window.geometry(f"{self.window_width}x{self.window_height}+{self.curr_x}+{self.curr_y}")

        if self.agent:
            self.state_changed_by_tool = False
            ai_thread = threading.Thread(
                target=self.process_ai_response, 
                args=(command,)
            )
            ai_thread.daemon = True
            ai_thread.start()
        else:
            print(f"[Simulação] Agente não configurado. Comando recebido: {command}")
            # Se não houver agente, volta para o estado base na hora
            self.change_state(self.base_state.name)
    
    def process_ai_response(self, comando: str):
        try:
            resposta = self.agent.run(comando)
            print(f"\n[AI Response]: {resposta}")

        except Exception as e:
            print(f"Erro no processamento da IA: {e}")
        finally:
            if not self.state_changed_by_tool:
                self.sprite_queue.put("last")
            
    def change_state(self, state_name: str):
        try:
            new_state = BuddyStates[state_name.upper()]
        except KeyError:
            print(f"Erro: Estado '{state_name}' não mapeado no Enum BuddyStates.")
            return

        if self.state == new_state:
            return

        print(f"Modificando Estado -> Atual: {self.state.name}, Solicitado: {new_state.name}")

        # Atualiza estados base apenas se forem estados estáveis de rotina
        if new_state in [BuddyStates.IDLE, BuddyStates.WORKING, BuddyStates.FUN, BuddyStates.BREAK]:
            self.base_state = new_state
            self.last_state = self.state

        if self.state != BuddyStates.SHOWING:
            self.last_state = self.state

        self.state = new_state
        
        gif_path = self.SPRITES.get(new_state.name, self.SPRITES.get("IDLE", "idle.gif"))
        self.load_gif(gif_path)

    def load_gif(self, gif_path):
        if not os.path.exists(gif_path):
            print(f"Arquivo de imagem não encontrado: {gif_path}")
            return
            
        frames_list = []
        try:
            with Image.open(gif_path) as img:
                num_frames = getattr(img, 'n_frames', 1)
                for i in range(num_frames):
                    img.seek(i)
                    # O segredo do Tkinter: manter uma cópia explícita do PhotoImage
                    frame = ImageTk.PhotoImage(img.copy())
                    frames_list.append(frame)
            
            self.current_frames = frames_list
            self.current_frame_index = 0
        except Exception as e:
            print(f"Erro ao carregar o GIF {gif_path}: {e}")
    
    def update_animation(self):
        if self.current_frames:
            frame = self.current_frames[self.current_frame_index]
            self.label.config(image=frame)
            # Evita que o garbage collector limpe a imagem em runtime
            self.label.image = frame 
            
            self.current_frame_index = (self.current_frame_index + 1) % len(self.current_frames)
        
        self.window.after(500, self.update_animation)