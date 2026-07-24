```mermaid
stateDiagram-v2
    state Sistema {
        
        state Routine {
            [*] --> IDLE
            IDLE --> WORKING : Start Pomodoro
            WORKING --> IDLE : Stop Pomodoro
            WORKING --> BREAK : Tempo esgotado
            BREAK --> WORKING : Tempo esgotado
            IDLE --> FUN : Jogar
            FUN --> IDLE : Fechar Jogo
        }

        state Audio {
            [*] --> SILENT
            SILENT --> MUSIC : Play Spotify
            MUSIC --> SILENT : Pause Spotify
        }

        state UI {
            [*] --> REST
            REST --> SHOWING : Clique no Buddy
            REST --> SHOWING : Tool show_message
            REST --> THINKING : Enter / IA Rodando
            SHOWING --> REST : Clique / Enter
            SHOWING --> REST : Clique
            THINKING --> REST : Fim da Thread IA
        }
    }
```