from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import PlainTextResponse
import json
from dotenv import load_dotenv
import os
from openai import OpenAI
from datetime import datetime
from utils import (
    store_document,
    store_user_script,
    search_similar_documents,
    search_user_scripts,
    get_user_scripts_context,
    prepare_context_from_docs,
    generate_script,
    generate_script_with_inspiration,
    get_media_url,
    download_media,
    extract_text_from_pdf,
    save_text_to_file
)
from embedding import *

load_dotenv()
client = OpenAI()
app = FastAPI()
prompt_briefing = os.getenv("PROMPT_BRIEFING")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
GRAPH_URL = os.getenv("GRAPH_URL")


@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(
            content=params.get("hub.challenge", ""), status_code=200
        )
    return PlainTextResponse(content="token invalid", status_code=403)


@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("message received:")
    print(json.dumps(data, indent=2))
    return {"status": "received"}


@app.post("/webhook/file")
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
            message = messages[0]
            # sender_id = message["from"]
            msg_type = message.get("type")

            if msg_type == "document":
                mime_type = message["document"].get("mime_type")
                media_id = message["document"].get("id")

                if mime_type in [
                    "application/pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ]:
                    print("document received")
                    media_url = await get_media_url(media_id)
                    file_path = await download_media(media_url)
                    print(f"saved in: {file_path}")
                    extracted_text = extract_text_from_pdf(file_path)
                    save_text_to_file(extracted_text)

                    is_script = any(
                        keyword in filename.lower()
                        for keyword in ["script", "roteiro", "screenplay"]
                    )

                    if is_script:
                        await store_user_script(sender_id, extracted_text, filename)
                        return {"status": "script received"}
                    else:
                        await store_document(extracted_text, filename)
                        context_docs = await get_user_scripts_context(sender_id)

                        if context_docs:
                            context_text = prepare_context_from_docs(context_docs)
                            roteiro = generate_script_with_inspiration(
                                extracted_text, context_text
                            )
                        else:
                            roteiro = generate_script(extracted_text)

                    script_filename = f"roteiro_{sender_id}.txt"
                    with open(script_filename, "w", encoding="utf-8") as f:
                        f.write(roteiro)

                    return {"status": "doc received"}
    except Exception as e:
        print("Error webhook:", e)

    return {"status": "ignored"}


@app.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    title: str = Form(None),
    user_id: str = Form(...),
    is_script: bool = Form(False),
):
    filename = f"temp_{file.filename}"
    with open(filename, "wb") as f:
        f.write(await file.read())

    extracted_text = extract_text_from_pdf(filename)
    save_text_to_file(extracted_text)

    doc_title = title if title else file.filename

    is_script = any(
        keyword in filename.lower() for keyword in ["script", "roteiro", "screenplay"]
    )

    if is_script:
        await store_user_script(user_id, extracted_text, doc_title)
        return {"status": "ok", "message": "Script stored for user inspiration"}
    else:
        await store_document(extracted_text, doc_title)
        try:
            context_docs = await get_user_scripts_context(user_id)

            if context_docs:
                context_text = prepare_context_from_docs(context_docs)
                roteiro = generate_script_with_inspiration(extracted_text, context_text)
                used_context = [
                    {
                        "title": doc.metadata.get("title", "untitled"),
                        "doc_id": doc.metadata.get("doc_id"),
                        "preview": doc.page_content[:200],
                    }
                    for doc in context_docs
                ]
            else:
                roteiro = generate_script(extracted_text)
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


@app.post("/generate-script-with-user-context")
async def generate_script_with_user_context(
    briefing: str = Form(...),
    user_id: str = Form(...),
    similarity_threshould: float = Form(0.7),
    max_sources: int = Form(3),
):
    try:
        context_docs = await search_user_scripts(
            user_id, query=briefing, k=max_sources, threshould=similarity_threshould
        )

        context_text = prepare_context_from_docs(context_docs)
        roteiro = generate_script_with_inspiration(briefing, context_text)

        script_filename = f"roteiro_context_{user_id}.txt"
        with open(script_filename, "w", encoding="utf-8") as f:
            f.write(roteiro)

        return {
            "status": "ok",
            "script": roteiro,
            "used_sources": len(context_docs),
            "user_context_applied": bool(context_docs),
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/generate-script-with-context")
async def generate_script_with_context(
    briefing: str = Form(...),
    similarity_threshold: float = Form(0.7),
    max_sources: int = Form(3),
):
    try:
        context_docs = await search_similar_documents(
            briefing, k=max_sources, threshold=similarity_threshold
        )

        context_text = prepare_context_from_docs(context_docs)

        roteiro = generate_script_with_inspiration(briefing, context_text)

        with open("roteiro_contextual.txt", "w", encoding="utf-8") as f:
            f.write(roteiro)

        return {"status": "ok", "script": roteiro, "used_sources": len(context_docs)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/store-user-script")
async def store_user_script_endpoint(
    content: str = Form(...), user_id: str = Form(...), title: str = Form(None)
):
    """Store a script directly in the user's vector database"""
    try:
        doc_title = (
            title if title else f"Script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        doc_id = await store_user_script(user_id, content, doc_title)
        return {
            "status": "script stored successfully",
            "title": doc_title,
            "user_id": user_id,
            "doc_id": doc_id,
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/store-script")
async def store_script(content: str = Form(...), title: str = Form(None)):
    """Store a script directly in the vector database"""
    try:
        doc_title = (
            title if title else f"Script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        await store_document(content, doc_title)
        return {"status": "script stored successfully", "title": doc_title}
    except Exception as e:
        return {"error": str(e)}


@app.get("/list-user-scripts/{user_id}")
async def list_user_scripts(user_id: str):
    """List all scripts for a specific user"""
    try:
        user_vectorstore = get_user_collection(user_id)

        results = user_vectorstore.similarity_search("", k=100)
        scripts = []
        seen_ids = set()

        for doc in results:
            doc_id = doc.metadata.get("doc_id", "unknown")
            if doc_id not in seen_ids:
                scripts.append(
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

        return {"user_id": user_id, "scripts": scripts}
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
