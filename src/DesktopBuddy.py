from src.StateManager import BuddyStateManager, RoutineState, AudioState, UIState
import threading
import time
import tkinter as tk
from PIL import Image, ImageTk
import queue
import json
import os

def load_sprites_config():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    path_config = os.path.join(current_dir, "..", "sprites.json")
    if os.path.exists(path_config):
        with open(path_config, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print("Erro: arquivo sprites.json não encontrado!")
        return {}

class DesktopBuddy:
    def __init__(self):
        # State engine and basic configs
        self.state_manager = BuddyStateManager()
        self.SPRITES = load_sprites_config()
        self.agent = None  
        self.sprite_queue = queue.Queue()

        # UI configs
        self._init_window()
        self._init_widgets()
        self._setup_bindings()
        
        # Animation loop management
        self.check_sprite_queue()
        self.update_animation()

        # Miscelenious Configs
        self._init_working_attributes()

    def _init_window(self):
        self.window = tk.Tk()
        self.window.overrideredirect(True)  
        self.window.attributes("-topmost", True)  

        self.window_width = 230
        self.window_height = 230
        
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        self.curr_x = screen_width - self.window_width - 20
        self.curr_y = screen_height - self.window_height - 50
        self.window.geometry(f"{self.window_width}x{self.window_height}+{self.curr_x}+{self.curr_y}")

        self.transparency_color = '#00ff00'  
        self.window.config(bg=self.transparency_color)
        self.window.attributes("-transparentcolor", self.transparency_color)

    def _init_widgets(self):

        self.current_frames = []
        self.current_frame_index = 0

        self.label = tk.Label(
            self.window,
            fg="white",                  
            bg=self.transparency_color,
            font=("Arial", 16, "bold")
        )
        self.label.pack(expand=True, fill="both")

        self.command_entry = tk.Entry(self.window, font=("Arial", 10))

        self.msg_label = tk.Label(
            self.window, 
            font=("Arial", 10, "italic"), 
            bg="#f0f0f0",          
            fg="#333333",          
            bd=1,                  
            relief="solid",        
            wraplength=240,        
            justify="center"
        )

        self.load_gif(self.SPRITES.get("IDLE_SILENT", "idle.gif"))

    def _setup_bindings(self):
        self.is_dragging = False
        self.drag_x = 0
        self.drag_y = 0
        
        # Mouse interations
        self.label.bind("<ButtonPress-1>", self.start_drag)
        self.label.bind("<B1-Motion>", self.do_drag)
        self.label.bind("<ButtonRelease-1>", self.release_click)
        
        self.command_entry.bind("<Return>", lambda event: self.send_command(self.command_entry.get()))

    def _init_working_attributes(self):
        self.work_thread_active = False
        self.pomodoro_loops = 0
        self.work_duration = 0
        self.break_duration = 0
    
    def run(self):
        self.window.mainloop()

    def update_sprite_visual(self):
        sprite_key = self.state_manager.get_current_state()
        gif_path = self.SPRITES.get(sprite_key, "idle.gif")
        self.load_gif(gif_path)
    
    def check_sprite_queue(self):
        try:
            state_enum = self.sprite_queue.get_nowait()

            self._handle_queue_command(state_enum)
            
            self.sprite_queue.task_done()
        except queue.Empty:
            pass
            
        self.window.after(100, self.check_sprite_queue)

    def _handle_queue_command(self, state_enum):
        if isinstance(state_enum, AudioState):
            self.state_manager.audio_state = state_enum
            
        elif isinstance(state_enum, RoutineState):
            self.state_manager.routine_state = state_enum
            
        elif isinstance(state_enum, UIState):
            self.state_manager.ui_state = state_enum
            
        self.update_sprite_visual()

    def start_drag(self, event):
        self.drag_x = event.x
        self.drag_y = event.y
        self.is_dragging = False

    def do_drag(self, event):
        if abs(event.x - self.drag_x) > 3 or abs(event.y - self.drag_y) > 3:
            self.is_dragging = True
            
        if self.is_dragging:
            self.curr_x = self.window.winfo_x() + (event.x - self.drag_x)
            self.curr_y = self.window.winfo_y() + (event.y - self.drag_y)
            self.window.geometry(f"+{self.curr_x}+{self.curr_y}")

    def release_click(self, event):
        if not self.is_dragging:
            self.curr_x = self.window.winfo_x()
            self.curr_y = self.window.winfo_y()

            if self.state_manager.ui_state == UIState.SHOWING:
                if hasattr(self, '_message_auto_close_id'):
                    self.window.after_cancel(self._message_auto_close_id)

                if self.msg_label.winfo_manager() == "place":
                    self.close_agent_message()
                else:
                    self.command_entry.place_forget()
                    self.state_manager.ui_state = UIState.REST
                    self.update_sprite_visual()
                    self.window.geometry(f"{self.window_width}x{self.window_height}+{self.curr_x}+{self.curr_y}")
            else:
                self.state_manager.ui_state = UIState.SHOWING
                self.update_sprite_visual()
                self.window.geometry(f"{self.window_width}x{self.window_height + 30}+{self.curr_x}+{self.curr_y}")
                self.on_pure_click()
        
        self.is_dragging = False
    
    def close_agent_message(self):
        self.msg_label.place_forget()
        self.state_manager.ui_state = UIState.REST
        self.update_sprite_visual()
        self.curr_x = self.window.winfo_x()
        self.curr_y = self.window.winfo_y()
        self.window.geometry(f"{self.window_width}x{self.window_height}+{self.curr_x}+{self.curr_y}")

    def on_pure_click(self):
        self.command_entry.place(x=0, y=0, relwidth=1, height=25)
        self.command_entry.delete(0, tk.END)
        self.command_entry.focus_set()

    def display_agent_message(self, text: str):
        self.state_manager.ui_state = UIState.SHOWING
        self.update_sprite_visual()
        
        self.msg_label.config(text=text, wraplength=self.window_width - 20, padx=5, pady=5, justify="center",anchor="center")
        self.msg_label.place(x=10, y=0, width=self.window_width - 10)

        self.window.update_idletasks()
        req_height = self.msg_label.winfo_reqheight() + 10
        
        self.curr_x = self.window.winfo_x()
        self.curr_y = self.window.winfo_y()

        req_height += self.window_height

        self.window.geometry(f"{self.window_width}x{req_height}+{self.curr_x}+{self.curr_y}")

        if hasattr(self, '_message_auto_close_id'):
            self.window.after_cancel(self._message_auto_close_id)
        
        self._message_auto_close_id = self.window.after(8000, self.close_agent_message)
    
    def send_command(self, command: str):
        if not command.strip():
            return
        
        self.state_manager.ui_state = UIState.THINKING
        self.update_sprite_visual()
            
        self.command_entry.place_forget()
        
        self.curr_x = self.window.winfo_x()
        self.curr_y = self.window.winfo_y()
        self.window.geometry(f"{self.window_width}x{self.window_height}+{self.curr_x}+{self.curr_y}")

        if self.agent:
            ai_thread = threading.Thread(
                target=self.process_ai_response, 
                args=(command,)
            )
            ai_thread.daemon = True
            ai_thread.start()
        else:
            print(f"Agente não configurado. Comando recebido: {command}")
            self.state_manager.ui_state = UIState.REST
            self.update_sprite_visual()
    
    def process_ai_response(self, comando: str):
        try:
            resposta = self.agent.run(comando)
            print(f"\n[AI Response]: {resposta}")

        except Exception as e:
            print(f"Erro no processamento da IA: {e}")
        finally:
            self.window.after(0, self._finalize_ai_interaction)

    def _finalize_ai_interaction(self):
        if self.state_manager.ui_state == UIState.THINKING:
            self.state_manager.ui_state = UIState.REST
            self.update_sprite_visual()

    def load_gif(self, gif_path):
        if not os.path.isabs(gif_path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_dir, ".."))
            full_path = os.path.join(project_root, gif_path)
        else:
            full_path = gif_path

        full_path = os.path.normpath(full_path)

        if not os.path.exists(full_path):
            print(f"Arquivo de imagem não encontrado: {gif_path}")
            return
            
        frames_list = []
        try:
            with Image.open(full_path) as img:
                num_frames = getattr(img, 'n_frames', 1)
                for i in range(num_frames):
                    img.seek(i)
                    
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
            self.label.image = frame 
            
            self.current_frame_index = (self.current_frame_index + 1) % len(self.current_frames)
        
        self.window.after(500, self.update_animation)

    def _work_thread_loop(self):
        seconds_counter = 0
        check_interval = 5*60
        next_check = check_interval
        loops_passed = 1

        while self.work_thread_active:
            time.sleep(1)
            seconds_counter+=1

            if (seconds_counter >= next_check and (self.pomodoro_loops == 0 or (self.pomodoro_loops != 0 and self.state_manager.routine_state == RoutineState.WORKING))):
                next_check += check_interval
                comando = "Analise a janela que está ativa no momento. Verifique o conteúdo da janela e avise o usuário caso essa janela não pareça útil para trabalho ou estudos. Use seu próprio julgamento para definir isto. Mostre uma mensagem para o usuário utilizando a ferramenta 'work_mode_manager' apenas se a janela ativa não parecer útil e peça para que ele volte ao trabalho."
                self.window.after(0, lambda: self.send_command(comando))

            if self.pomodoro_loops == 0:
                continue

            if (self.pomodoro_loops >= loops_passed):
                if (self.state_manager.routine_state == RoutineState.WORKING):
                    current_time_limit = self.work_duration * loops_passed + self.break_duration * (loops_passed - 1)

                    if (seconds_counter >= current_time_limit):
                        self.state_manager.routine_state=RoutineState.BREAK
                        self.window.after(0, self.update_sprite_visual)

                elif (self.state_manager.routine_state == RoutineState.BREAK):
                    current_time_limit = self.work_duration * loops_passed + self.break_duration * loops_passed

                    if (seconds_counter >= current_time_limit):
                        if self.pomodoro_loops > 0 and loops_passed >= self.pomodoro_loops:
                            # Stops work mode if pomodoro ends
                            self.window.after(0, self.stop_work_mode)
                            break

                        loops_passed += 1
                        self.state_manager.routine_state=RoutineState.WORKING
                        self.window.after(0, self.update_sprite_visual)


    def start_work_mode(self):
        self.work_thread_active = True
        self.state_manager.routine_state = RoutineState.WORKING
        self.update_sprite_visual()

        self.work_thread = threading.Thread(target=self._work_thread_loop, daemon=True)
        self.work_thread.start()

    def stop_work_mode(self):
        self._init_working_attributes() #Makes thread loop stop
        self.state_manager.routine_state = RoutineState.IDLE
        self.update_sprite_visual()

    