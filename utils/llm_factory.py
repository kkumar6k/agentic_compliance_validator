"""
LLM Factory - Create LLM instances with proper configuration
Supports OpenAI, Groq, and xAI (Grok)
"""

import os
from langchain_openai import ChatOpenAI


def get_llm(model: str = "llama-3.3-70b-versatile", temperature: float = 0) -> ChatOpenAI:
    """
    Get configured LLM instance

    Supports OpenAI, Groq, and xAI (Grok) APIs

    Args:
        model: Model name
        temperature: Temperature setting

    Returns:
        Configured ChatOpenAI instance
    """

    # Check which API to use
    groq_key = os.getenv("GROQ_API_KEY")
    xai_key = os.getenv("XAI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    # Priority: Groq > xAI > OpenAI
    if groq_key:
        print(f"⚡ Using Groq API with model: {model}")
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key
        )
    elif xai_key:
        print(f"🤖 Using Grok API with model: {model}")
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            base_url="https://api.x.ai/v1",
            api_key=xai_key
        )
    elif openai_key:
        # Auto-detect which service based on key prefix
        if openai_key.startswith("gsk_"):
            print(f"⚡ Using Groq API (via OPENAI_API_KEY) with model: {model}")
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                base_url="https://api.groq.com/openai/v1",
                api_key=openai_key
            )
        elif openai_key.startswith("xai-"):
            print(f"🤖 Using Grok API (via OPENAI_API_KEY) with model: {model}")
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                base_url="https://api.x.ai/v1",
                api_key=openai_key
            )
        else:
            print(f"🤖 Using OpenAI API with model: {model}")
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=openai_key
            )
    else:
        raise ValueError("No API key found. Set GROQ_API_KEY, XAI_API_KEY, or OPENAI_API_KEY in .env")


# Groq model names (RECOMMENDED - Fast & Free!)
LLAMA_70B = "llama-3.3-70b-versatile"      # Latest Llama 3.3 (Best!)
LLAMA_8B = "llama-3.1-8b-instant"          # Fastest
MIXTRAL = "mixtral-8x7b-32768"             # Good for reasoning

# xAI/Grok model names
GROK_BETA = "grok-beta"
GROK_2 = "grok-2-1212"

# OpenAI model names
GPT4O = "gpt-4o"
GPT4O_MINI = "gpt-4o-mini"