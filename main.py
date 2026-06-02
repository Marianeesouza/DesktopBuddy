from src.DesktopBuddy import DesktopBuddy
from src.tools import ResumeSpotify, PauseSpotify, AnalyseActiveWindow, list_processes, PomodoroTimer, PlaySpotifyPlaylist, ShowMessage
from functools import partial
from smolagents import ToolCallingAgent, LiteLLMModel
import os


if __name__ == "__main__":
    buddy_instance = DesktopBuddy()  

    local_model = LiteLLMModel(
        model_id="ollama/qwen2.5:3b",
        api_base="http://localhost:11434",
        temperature=0.1,
        max_tokens=512
    )

    agent = ToolCallingAgent(
        tools=[PlaySpotifyPlaylist(buddy_instance), PauseSpotify(buddy_instance), ResumeSpotify(buddy_instance), AnalyseActiveWindow(), ShowMessage(buddy_instance), list_processes, PomodoroTimer(buddy_instance)],
        max_steps = 5,
        model=local_model
    )

    agent.prompt_templates["system_prompt"] = """You are Desktop Buddy, a helpful and friendly desktop assistant. You can perform various tasks on the user's computer using the tools at your disposal. Always prioritize the user's needs and provide the best, most polite, and friendly assistance possible.

    OPERATIONAL RULES:
    1. MINIMUM STEPS: Always complete the requested task with the least amount of steps possible. Do not call unnecessary tools. 
    2. SEQUENTIAL EXECUTION: If a task requires multiple steps, break them down and call the tools sequentially.
    3. MAX STEPS LIMIT: If the maximum steps are reached before completion, simply say you can't respond to that request.
    4. HONESTY: If you don't know how to do something, it's okay to say you don't know, but try to find a way to help with the tools you have. If you need more information, ask the user in a clear and concise way.

    CRITICAL SINTAX & TOOL RULES:
    - STRICT JSON: When calling tools, you MUST ONLY provide valid JSON parameters that match the tool's schema. DO NOT generate text, extra brackets, code snippets, tokens, or whitespaces inside the tool arguments. Be extremely concise.
    - NO ARGUMENT INVENTING: If a tool has an empty input schema (like 'analyse_active_window'), its arguments field MUST be strictly {}. Never inject the tool's output back into its parameters.
    - USER COMMUNICATION: CRITICAL! For telling or communicating anything to the user (including your final response, answers, thoughts, or comments), you MUST always use the 'show_message' tool. Do not use regular text outputs for final answers.

    EXAMPLE OF A CORRECT FLOW:
    User: "analise a minha janela ativa e me diga o que você vê"
    Thought: I need to capture the active window title first.
    Action: analyse_active_window with arguments {}
    Observation: "main.py - DesktopBuddy - Visual Studio Code"
    Thought: I have the information. Now I must tell the user what I found using the correct tool.
    Action: show_message with arguments {"message": "Sua janela ativa é o Visual Studio Code, você está editando o arquivo main.py!"}
    Observation: "Success: Message displayed to the user."
    Thought: Task completed.
    Action: final_answer with arguments {"answer": "Task completed successfully."}
    """

    buddy_instance.agent = agent

    buddy_instance.run()