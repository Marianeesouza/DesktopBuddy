from pathlib import Path
from smolagents import ToolCallingAgent
from threading import Lock

class DesktopAgent:

    def __init__(self, model, tools):
        self.agent = ToolCallingAgent(
            tools=tools,
            model=model,
            max_steps=5
        )

        prompt = (
            Path(__file__).parent
            / "prompts"
            / "system_prompt.txt"
        ).read_text(encoding="utf-8")

        self.agent.prompt_templates["system_prompt"] = prompt
        self._lock = Lock()

    def process_user_message(self, message: str):
        with self._lock:
            return self.agent.run(message, reset=False)
    
    def process_system_event(self, event: str, **context):
        context_text = "\n".join(
        f"{key}: {value}"
        for key, value in context.items()
        )

        prompt = f""" Você recebeu um evento interno do Desktop Buddy. Este evento NÃO foi enviado pelo usuário.

        Evento:
        {event}

        Contexto:
        {context_text}

        Decida quais ferramentas utilizar.
        Caso nenhuma ação seja necessária, não faça nada.
        """
        with self._lock:
            return self.agent.run(prompt, reset=False)
    
    def evaluate_productivity(self):

        prompt ="""
        Você recebeu uma verificação automática de produtividade.

        Primeiro obtenha a janela atualmente ativa utilizando a ferramenta apropriada.

        Em seguida, analise se ela parece compatível com trabalho ou estudo.

        Caso considere que ela representa uma distração, utilize show_message para incentivar o usuário a voltar ao trabalho.

        Caso contrário, não realize nenhuma ação.
        """
        with self._lock:
            return self.agent.run(prompt, reset=False)