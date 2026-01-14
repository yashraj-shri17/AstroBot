import os
import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
from PyPDF2 import PdfReader

# Load environment variables
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY") or "gsk_dummy_key_for_startup_prevent_crash"

# Step 1: Extract text from PDFs in output/media
pdf_text = ""
pdf_folder = "output/media"

# Ensure directories exist
if not os.path.exists(pdf_folder):
    os.makedirs(pdf_folder, exist_ok=True)

for file in os.listdir(pdf_folder):
    if file.endswith(".pdf"):
        try:
            reader = PdfReader(os.path.join(pdf_folder, file))
            for page in reader.pages:
                pdf_text += page.extract_text() + "\n"
        except Exception as e:
            print(f"⚠️ Could not read {file}: {e}")

# Step 2: Load JSON text
json_text = ""
json_path = "output/output.json"
if os.path.exists(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        try:
            json_data = json.load(f)
            json_text = json.dumps(json_data, indent=2)
        except:
            pass # json_text remains empty if load fails

all_text = pdf_text + "\n" + json_text

# Step 3: Split into documents
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    length_function=len,
)

split_docs = text_splitter.split_text(all_text)
if not split_docs:
    # Fallback to avoid FAISS error on empty documents
    split_docs = ["Welcome to AstroBot! I am ready to help you with ISRO and MOSDAC information once data is loaded."]

documents = [Document(page_content=chunk) for chunk in split_docs]

# Step 4: Create embeddings and vector store
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = FAISS.from_documents(documents=documents, embedding=embeddings)
retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})

# Step 5: Initialize the ChatGroq model
model = ChatGroq(model="llama-3.1-8b-instant", groq_api_key=groq_api_key, temperature=0.7)

# Step 6: Function to check if question is relevant
def is_relevant_question(question, context):
    relevant_keywords = [
        "mosdac", "isro", "satellite", "space", "data", "archive", "mission", "payload",
        "observation", "remote sensing", "ocean", "atmosphere", "climate", "weather", "gis",
        "geospatial", "satellite data", "earth observation", "insat", "meteorological",
        "oceanographic", "atmospheric", "payload data", "satellite imagery", "data products",
        "data dissemination"
    ]

    question_lower = question.lower()
    for keyword in relevant_keywords:
        if keyword in question_lower:
            return True

    if len(context.strip()) > 100:
        return True
    return False

# Step 7: Format documents
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# Step 8: Response function with chat history
def get_response(question, chat_history=[]):
    if question.lower() in ["/new", "/reset", "new chat", "reset chat"]:
        return "Starting a new chat session. Previous context has been cleared.", []

    docs = retriever.invoke(question)
    context = format_docs(docs)

    if not is_relevant_question(question, context):
        return ("I'm sorry, but I can only answer questions related to MOSDAC, ISRO, "
                "and satellite data topics based on the provided documents. "
                "Your question seems to be outside my knowledge domain."), chat_history

    history_prompt = ""
    if chat_history:
        history_prompt = "\nPrevious conversation context:\n"
        for chat in chat_history[-3:]:
            history_prompt += f"User: {chat['user']}\nAssistant: {chat['assistant']}\n\n"

    prompt = f"""
You are an expert AI assistant specialized in MOSDAC, ISRO, and satellite data topics.
Always provide detailed, comprehensive explanations based on the provided context.
If the context doesn't fully answer the question, you can use your knowledge
but stay strictly within MOSDAC/ISRO domain.

{history_prompt}
Context from MOSDAC/ISRO documents:
{context}

Question: {question}
Provide a detailed and accurate answer:
"""

    response = model.invoke(prompt)
    new_chat_history = chat_history + [{"user": question, "assistant": response.content}]
    return response.content, new_chat_history

# Step 9: Interactive chat loop
if __name__ == "__main__":
    print("🤖 MOSDAC/ISRO Specialist Assistant is ready!")
    print("I can answer questions about MOSDAC website and ISRO related topics.")
    print("Type '/new' to start a new chat session (clear previous context)")
    print("Type 'exit' to end the conversation.")
    print("=" * 70)

    chat_history = []
    while True:
        try:
            query = input("\n🙋 You: ")
            if query.lower() == 'exit':
                break

            response, chat_history = get_response(query, chat_history)

            if query.lower() in ["/new", "/reset", "new chat", "reset chat"]:
                chat_history = []

            print(f"\n🤖 Assistant: {response}")
            print("=" * 70)

        except Exception as e:
            print(f"An error occurred: {e}")
            print("Please try again with a different question.")