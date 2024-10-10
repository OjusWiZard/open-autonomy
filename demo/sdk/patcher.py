from demo.sdk.mechs import ChatGPTMech
from demo import langchain


# A mapping from the original langchain tools classes to our patched versions
# Note: the input and output interface of each mapping should be exactly same
MECH_REPLACEMENT = {
    langchain.ChatGPT: ChatGPTMech,
}


def monkey_patch(patch_chat_gpt: bool = True):
    """Monkey patch the agent to use the patched SDK version of the API."""
    if patch_chat_gpt:
        langchain.ChatGPT = MECH_REPLACEMENT[langchain.ChatGPT]
