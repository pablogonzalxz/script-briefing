import uuid
from fastapi import FastAPI, Request, UploadFile, File, Form
import json
from dotenv import load_dotenv
import os
from openai import OpenAI
import re
from utils import (
    RAG,
    extract_text_from_pdf,
    save_text_to_file,
    send_text_message
)
from embedding import default_vectorstore
load_dotenv()
client = OpenAI()
app = FastAPI()
prompt_briefing = os.getenv("PROMPT_BRIEFING")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
GRAPH_URL = os.getenv("GRAPH_URL")

def clean_id(sender_id):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', sender_id)

@app.post("/receive_webhook")
async def receive_webhook(request: Request):
    body = await request.json()
    print("message received:")
    print(json.dumps(body, indent=2))

    try:
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")
        if messages:
            print("if messages")
            message = messages[0]
            id_user = message["from"]
            msg_type = message.get("type")
            sender_id = clean_id(id_user)
            rag = RAG(sender_id)
            if msg_type == "document":
                print("document")
                document = message.get("document", {})
                file_path = document.get("file_path")
                file_name = os.path.basename(file_path).lower()

                if not file_path or not os.path.exists(file_path):
                    return {"status": "error", "detail": "Arquivo não encontrado."}

                print(f"Arquivo recebido em: {file_path}")
                extracted_text = extract_text_from_pdf(file_path)
                save_text_to_file(extracted_text)

                is_script = any(
                    keyword in file_name.lower()
                    for keyword in ["script", "roteiro", "screenplay"]
                )

                if is_script:
                    await rag.store_user_script(extracted_text, file_path)
                    return {"status": "script received"}
                else:
                    similar_docs = await rag.search_user_scripts(sender_id, extracted_text)
                    
                    if not similar_docs:
                        similar_docs = await rag.get_user_scripts_context(sender_id)

                    if similar_docs:
                        context_text = rag.prepare_context_from_docs(similar_docs)
                        roteiro = rag.generate_script(
                            sender_id, extracted_text, context_text
                        )
                    else:
                        roteiro = rag.generate_script(sender_id, extracted_text)

                unique_id = str(uuid.uuid4())
                user_folder = os.path.join("roteiros", sender_id)
                os.makedirs(user_folder, exist_ok=True)
                script_file_path = os.path.join(user_folder, f"roteiro_{unique_id}.txt")
                with open(script_file_path, "w", encoding="utf-8") as f:
                    f.write(roteiro)
                send_text_message(id_user, roteiro)
                return {"status": "doc received"}
    except Exception as e:
        print("Error webhook:", e)

    return {"status": "ignored"}


@app.post("/teste/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    title: str = Form(None),
    user_id: str = Form(...),
    is_script: bool = Form(False),
):
    file_path = f"temp_{file.file_path}"
    with open(file_path, "wb") as f:
        f.write(await file.read())

    extracted_text = extract_text_from_pdf(file_path)
    save_text_to_file(extracted_text)

    doc_title = title if title else file.file_path

    is_script = any(
        keyword in file_path.lower() for keyword in ["script", "roteiro", "screenplay"]
    )
    rag = RAG("teste")
    if is_script:
        await rag.store_user_script(user_id, extracted_text, doc_title)
        return {"status": "ok", "message": "Script stored for user inspiration"}
    else:
        await rag.store_user_script(extracted_text, doc_title)
        try:
            context_docs = await rag.get_user_scripts_context(user_id)

            if context_docs:
                context_text = rag.prepare_context_from_docs(context_docs)
                roteiro = rag.generate_script(extracted_text, context_text)
                used_context = [
                    {
                        "title": doc.metadata.get("title", "untitled"),
                        "doc_id": doc.metadata.get("doc_id"),
                        "preview": doc.page_content[:200],
                    }
                    for doc in context_docs
                ]
            else:
                roteiro = rag.generate_script(extracted_text)
                used_context = []

            with open("roteiro_gerado.txt", "w", encoding="utf-8") as f:
                f.write(roteiro)
            return {
                "status": "ok",
                "script": roteiro,
                "used_context_documents": used_context,
            }
        except Exception as e:
            return {"error": str(e)}


@app.get("/list-documents")
async def list_documents():
    try:
        results = default_vectorstore.similarity_search("", k=100)
        docs = []
        seen_ids = set()

        for doc in results:
            doc_id = doc.metadata.get("doc_id", "unknown")
            if doc_id not in seen_ids:
                docs.append(
                    {
                        "id": doc_id,
                        "title": doc.metadata.get("title", "Untitled"),
                        "date": doc.metadata.get("date", "Unknown date"),
                        "preview": doc.page_content[:100] + "..."
                        if len(doc.page_content) > 100
                        else doc.page_content,
                    }
                )
                seen_ids.add(doc_id)

        return {"documents": docs}
    except Exception as e:
        return {"error": str(e)}
