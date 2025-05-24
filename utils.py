import fitz
import requests
from dotenv import load_dotenv
import os
from langchain_core.documents import Document
import uuid
from langchain.chains import RetrievalQA
from langchain_community.chat_models import ChatOpenAI
from datetime import datetime
from template import prompt_template
from embedding import (
    get_user_collection,
    text_splitter,
)

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
GRAPH_URL = os.getenv("GRAPH_URL")


class RAG:
    def __init__(self, user_id):
        self.user_id = user_id
        self.user_vectorstore = get_user_collection(user_id)
        self.retriever = self.user_vectorstore.as_retriever(search_kwargs={"k": 4})
        self.llm = ChatOpenAI(model="gpt-4.1", temperature=1)
        self.chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            retriever=self.retriever,
            chain_type="stuff",
            return_source_documents=True,
        )

    async def store_user_script(self, text, title):
        """Split and store a script in the user's vector database"""
        doc_id = str(uuid.uuid4())
        date = datetime.now().isoformat()

        texts = text_splitter.split_text(text)
        metadata_base = {
            "doc_id": doc_id,
            "title": title,
            "date": date,
            "user_id": self.user_id
        }
        documents = [
            Document(
                page_content=chunk,
                metadata={**metadata_base, "chunk": i}
            )
            for i, chunk in enumerate(texts)
        ]

        self.user_vectorstore.add_documents(documents)
        self.user_vectorstore.persist()

        print(f"Stored user script: {title} with ID: {doc_id} for user: {self.user_id}")
        return doc_id


    async def search_user_scripts(self, user_id, query, k=3, threshold=0.7):
        user_vectorstore = get_user_collection(user_id)

        results = user_vectorstore.similarity_search_with_score(query, k=k * 2)

        filtered_results = [doc for doc, score in results if score >= threshold][:k]

        return filtered_results


    async def get_user_scripts_context(self, user_id, max_scripts=4):
        """Get user scripts to use as context, even without a specific query"""
        try:
            user_vectorstore = get_user_collection(user_id)
            results = user_vectorstore.similarity_search("", k=max_scripts * 2)

            doc_groups = {}
            for doc in results:
                doc_id = doc.metadata.get("doc_id", "unknown")
                if doc_id not in doc_groups:
                    doc_groups[doc_id] = []
                doc_groups[doc_id].append(doc)

            context_docs = []
            for doc_id, chunks in list(doc_groups.items())[:max_scripts]:
                sorted_chunks = sorted(chunks, key=lambda x: x.metadata.get("chunk", 0))
                if sorted_chunks:
                    context_docs.append(sorted_chunks[0])

            return context_docs
        except Exception as e:
            print(f"Error getting user scripts: {e}")
            return []


    def prepare_context_from_docs(self, docs):
        if not docs:
            return ""

        context_text = "Inspiração de roteiros anteriores do usuário:\n\n"
        for i, doc in enumerate(docs, 1):
            title = doc.metadata.get("title", f"Script {i}")
            context_text += f"--- {title} ---\n{doc.page_content}\n\n"

        return context_text


    def generate_script(self ,user_id, briefing, context=""):
        prompt = prompt_template.format(context_str=context, briefing_str=briefing)

        try:
            result = self.chain({"query": prompt})
            roteiro = result["result"]
            return roteiro
        except Exception as e:
            print("error generate inspo", e)
            return str(e)

def extract_text_from_pdf(file_path):
    text = ""
    try:
        doc = fitz.open(file_path)
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text += page.get_text("text")
            text += "\n"
    except Exception as e:
        print("error extracting text:", e)
    return text


def save_text_to_file(text, filename="extracted_text.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)

def send_text_message(sender_id: str, message_text: str):
    url = "http://localhost:3000/send-message" 
    payload = {
        "to": sender_id,
        "message": message_text
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"error send to api node {e}")
        return None
