import pygetwindow as gw
import time
from trello import TrelloClient
import os
from dotenv import load_dotenv

load_dotenv()

def test_get_window_title():
    # Get the title of the currently active window
    while True:
        last_title = ""
        active_window = gw.getActiveWindow()
        if active_window is not None:
            title = active_window.title
            if title != last_title:
                print(f"Active window title: {title}")
                last_title = title
        else:
            print("No active window found.")
        # Wait for a short period before checking again
        time.sleep(1)

def test_py_trello():
    client = TrelloClient(
        api_key=os.getenv('TRELLO_API_KEY'),
        api_secret=os.getenv('TRELLO_API_SECRET'),
        token=os.getenv('TRELLO_TOKEN')
    )

    board = client.get_board(os.getenv('TRELLO_BOARD_ID'))
    cards = board.get_cards()
    lists = board.all_lists()
    
    for list in lists:
        print(f"\n--- Lista: {list.name} ---")
        cards = list.list_cards(card_filter='open')
        
        for card in cards:
            # Filtro: Só exibe se o card NÃO estiver concluído (due_complete == False)
            if not card.is_due_complete:
                print(f"[Incompleto] {card.name}")
                print(card.description)

    #for card in cards:
    #    print(card)
    #    print(card.get_list())
    #    print(card.description)

if __name__ == "__main__":
    test_py_trello()