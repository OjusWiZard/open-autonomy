

class OpenAI:

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
    
    def call(self, prompt: str) -> str:
        return "Response from OpenAI"


class ChatGPT:

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.openai = OpenAI(api_key)
    
    def ask(self, prompt: str) -> str:
        return self.openai.call(prompt)
