import os
from pathlib import Path
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# ---------------- Config ---------------- #
INPUT_FILE = Path("data/weather_context.txt")

# Set your Groq API key
from dotenv import load_dotenv
load_dotenv()
# API Key is loaded from environment variables

def load_weather_file(path):
    """Load weather context file"""
    if not path.exists():
        return "No weather data available. Please set a region first."
    
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

def get_weather_response(question):
    """Get response for weather-related questions"""
    weather_data = load_weather_file(INPUT_FILE)
    
    template = """
You are a helpful weather assistant that answers based on the provided weather data.
Be concise but informative. If the data doesn't contain the answer, say so.

Weather Data:
{context}

Question: {question}

Provide a helpful and accurate answer:
"""
    
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=template
    )
    
    api_key = os.getenv("GROQ_API_KEY") or "gsk_dummy_key_for_startup_prevent_crash"
    llm = ChatGroq(temperature=0, model_name="llama-3.1-8b-instant", groq_api_key=api_key)
    chain = LLMChain(llm=llm, prompt=prompt)
    
    return chain.run({"context": weather_data, "question": question})