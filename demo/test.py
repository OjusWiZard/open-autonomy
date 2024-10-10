

from demo.langchain import ChatGPT


def main() -> None:
    
    chat_gpt = ChatGPT(api_key="YOUR_API_KEY")
    response = chat_gpt.ask("What is the meaning of life?")

    print(response)

if __name__ == "__main__":
    main()