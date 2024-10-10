

class Mech:

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
    
    def call(self, prompt: str) -> str:
        return "Response from Mech"


class ChatGPTMech:

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.mech = Mech(api_key)
    
    def ask(self, prompt: str) -> str:
        return self.mech.call(prompt)
