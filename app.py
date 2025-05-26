import uuid
from fastapi import FastAPI, Request
import json
import os
from openai import OpenAI
import re
from users import UserManager
from utils import (
    RAG,
    extract_text,
    save_text_to_file,
    send_text_message
)
from embedding import default_vectorstore
client = OpenAI()
app = FastAPI()
user_manager = UserManager()

def clean_id(sender_id):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', sender_id)

@app.get("/user_stats/{user_id}")
async def get_user_stats_api(user_id: str):
    """API endpoint to get user statistics - for Node.js service"""
    try:
        sender_id = clean_id(user_id)
        stats = user_manager.get_user_stats(sender_id)

        daily_used, daily_total = map(int, stats['daily_usage'].split('/'))
        monthly_used, monthly_total = map(int, stats['monthly_usage'].split('/'))
        
        daily_remaining = max(0, daily_total - daily_used)
        monthly_remaining = max(0, monthly_total - monthly_used)
        
        return {
            "status": "success",
             "data": {
                "user_id": user_id,
                "daily_remaining": daily_remaining,
                "monthly_remaining": monthly_remaining,
                "daily_used": daily_used,
                "daily_total": daily_total,
                "monthly_used": monthly_used,
                "monthly_total": monthly_total,
                "is_premium": stats['is_premium'],
                "created_at": stats['created_at'],
                "last_activity": stats['last_activity']
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

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

            can_send, limit_msg = user_manager.can_user_send_message(sender_id)

            if msg_type == "chat":
                text_content = message.get("text", "").lower().strip()
                stats = user_manager.get_user_stats(sender_id)
                daily_used, daily_total = map(int, stats['daily_usage'].split('/'))
                monthly_used, monthly_total = map(int, stats['monthly_usage'].split('/'))
                daily_remaining = max(0, daily_total - daily_used)
                monthly_remaining = max(0, monthly_total - monthly_used)
                
                return {
                    "status": "text_received",
                    "user_id": id_user,
                    "command": text_content,
                    "user_stats": {
                        "daily_remaining": daily_remaining,
                        "monthly_remaining": monthly_remaining,
                        "daily_used": daily_used,
                        "daily_total": daily_total,
                        "monthly_used": monthly_used,
                        "monthly_total": monthly_total,
                        "is_premium": stats['is_premium'],
                        "created_at": stats['created_at']
                    }
                }
            elif msg_type == "document":
                can_send, limit_msg = user_manager.can_user_send_message(sender_id)
                if not can_send:
                    send_text_message(sender_id, limit_msg)
                    return({"status": "rate limited", "message": limit_msg})
                print("document")
                rag = RAG(sender_id)
                document = message.get("document", {})
                file_path = document.get("filePath")
                file_name = os.path.basename(file_path).lower()

                if not file_path or not os.path.exists(file_path):
                    return {"status": "error", "detail": "Arquivo não encontrado."}

                print(f"Arquivo recebido em: {file_path}")
                extracted_text = extract_text(file_path)
                save_text_to_file(extracted_text)

                is_script = any(
                    keyword in file_name.lower()
                    for keyword in ["script", "roteiro", "screenplay"]
                )

                if is_script:
                    await rag.store_user_script(extracted_text, file_path)
                    return {
                        "status": "script_received",
                        "user_id": id_user,
                        "message": "context received"
                        }
                else:
                    user_manager.increment_usage(sender_id)
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

@app.post("/admin/set_user_limits")
async def set_user_limits(user_id: str, daily_limit: int = None, monthly_limit: int = None):
    user_manager.set_user_limits(user_id, daily_limit, monthly_limit)
    return {"status": "success", "message": f"Limits updated for user {user_id}"}

@app.post("/admin/set_premium")
async def set_premium_user(user_id: str, is_premium: bool = True):
    user_manager.set_premium_user(user_id, is_premium)
    return {"status": "success", "message": f"Premium status updated for user {user_id}"}


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
