from fastapi import FastAPI
import fitz
import httpx
from dotenv import load_dotenv
import os
from openai import OpenAI
from langchain_core.documents import Document
import uuid
from datetime import datetime
from embedding import *

load_dotenv()
client = OpenAI()
app = FastAPI()
prompt_briefing = os.getenv("PROMPT_BRIEFING")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
GRAPH_URL = os.getenv("GRAPH_URL")
base_prompt = os.getenv("PROMPT_BASE")

tom = "Meme"


async def store_document(text, title):
    """Split and store a document in the vector database"""
    # Generate a unique document ID
    doc_id = str(uuid.uuid4())
    date = datetime.now().isoformat()

    # Split text into chunks
    texts = text_splitter.split_text(text)

    # Create documents with metadata
    documents = [
        Document(
            page_content=chunk,
            metadata={"doc_id": doc_id, "title": title, "date": date, "chunk": i},
        )
        for i, chunk in enumerate(texts)
    ]

    # Add documents to vector store
    default_vectorstore.add_documents(documents)
    default_vectorstore.persist()

    print(f"Stored document: {title} with ID: {doc_id}")
    return doc_id


async def store_user_script(user_id, text, title):
    """Split and store a script in the user's vector database"""
    # Generate a unique document ID
    doc_id = str(uuid.uuid4())
    date = datetime.now().isoformat()

    # Split text into chunks
    texts = text_splitter.split_text(text)

    # Create documents with metadata
    documents = [
        Document(
            page_content=chunk,
            metadata={
                "doc_id": doc_id,
                "title": title,
                "date": date,
                "chunk": i,
                "user_id": user_id,
                "type": "user_script",
            },
        )
        for i, chunk in enumerate(texts)
    ]

    user_vectorstore = get_user_collection(user_id)
    user_vectorstore.add_documents(documents)
    user_vectorstore.persist()

    print(f"Stored user script: {title} with ID: {doc_id} for user: {user_id}")
    return doc_id


async def search_similar_documents(query, k=3, threshold=0.7):
    results = default_vectorstore.similarity_search_with_score(query, k=k * 2)

    filtered_results = [doc for doc, score in results if score >= threshold][:k]

    return filtered_results


async def search_user_scripts(user_id, query, k=3, threshold=0.7):
    user_vectorstore = get_user_collection(user_id)

    results = user_vectorstore.similarity_search_with_score(query, k=k * 2)

    filtered_results = [doc for doc, score in results if score >= threshold][:k]

    return filtered_results


async def get_user_scripts_context(user_id, max_scripts=4):
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


def prepare_context_from_docs(docs):
    if not docs:
        return ""

    context_text = "Inspiração de roteiros anteriores do usuário:\n\n"
    for i, doc in enumerate(docs, 1):
        title = doc.metadata.get("title", f"Script {i}")
        context_text += f"--- {title} ---\n{doc.page_content}\n\n"

    return context_text


def generate_script(briefing):
    prompt = f"""
Você é um redator criativo especializado em roteiros audiovisuais para campanhas publicitárias em redes sociais (Instagram/TikTok). Seu trabalho é criar roteiros dinâmicos e emocionais para vídeos curtos de campanhas, baseados em briefings fornecidos. O roteiro deve ser impactante e otimizado para performance, com uma narrativa clara e envolvente.

Com base no briefing a seguir, crie um roteiro completo, estruturado da seguinte forma:

Título (curto e criativo, de até 6 palavras)

Duração sugerida (ex: 30s ou 45s)

Estrutura narrativa:

Abertura impactante (Hook): Descrição das primeiras imagens impactantes que devem capturar a atenção do público logo nos primeiros 3 segundos.

Desenvolvimento emocional ou divertido: Discurso envolvente que explora o conceito da campanha, destacando produtos ou serviços oferecidos. O desenvolvimento deve criar uma conexão emocional com o público-alvo.

Chamada para ação clara (CTA): Um convite direto ao público, estimulando a ação desejada (como visitar a loja ou comprar).

Linguagem e estilo de edição alinhados à plataforma (Instagram/TikTok) e ao público-alvo (decisores de compra, como filhos e netos).

Tom e ritmo do vídeo: o tom é de {tom} e ajuste o ritmo da narrativa para garantir fluidez e engajamento.

Observações importantes:

Não mencionar preços, promoções ou concorrentes.

Usar apenas os produtos da marca (exceto no caso de eletrodomésticos e eletrônicos destacados).

A edição deve ser dinâmica, com cortes rápidos e visuais atraentes.

Evitar tons negativos ou desrespeitosos.

Gere o roteiro com 250 palavras ou mais, respeitando os seguintes critérios:

Objetividade e clareza na apresentação do conceito da campanha.

Uso de linguagem envolvente para criar uma experiência emocional.

Ritmo e transições dinâmicas otimizadas para a duração curta de vídeos em plataformas como Instagram e TikTok.

Baseie o roteiro nas diretrizes abaixo:
{briefing}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "system",
                    "content": "Você é um redator criativo especialista em roteiros audiovisuais.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=1,
            max_tokens=2048,
            top_p=1,
        )

        roteiro = response.choices[0].message.content
        return roteiro
    except Exception as e:
        print("Erro ao gerar o roteiro:", e)
        return str(e)


def generate_script_with_inspiration(briefing, context=""):
    prompt = f"""
Você é um redator criativo especializado em roteiros audiovisuais para campanhas publicitárias em redes sociais (Instagram/TikTok). Seu trabalho é criar roteiros dinâmicos e emocionais para vídeos curtos de campanhas, baseados em briefings fornecidos. O roteiro deve ser impactante e otimizado para performance, com uma narrativa clara e envolvente.

Com base no briefing a seguir, crie um roteiro completo, estruturado da seguinte forma:

Título (curto e criativo, de até 6 palavras)

Duração sugerida (ex: 30s ou 45s)

Estrutura narrativa:

Abertura impactante (Hook): Descrição das primeiras imagens impactantes que devem capturar a atenção do público logo nos primeiros 3 segundos.

Desenvolvimento emocional ou divertido: Discurso envolvente que explora o conceito da campanha, destacando produtos ou serviços oferecidos. O desenvolvimento deve criar uma conexão emocional com o público-alvo.

Chamada para ação clara (CTA): Um convite direto ao público, estimulando a ação desejada (como visitar a loja ou comprar).

Linguagem e estilo de edição alinhados à plataforma (Instagram/TikTok) e ao público-alvo (decisores de compra, como filhos e netos).

Tom e ritmo do vídeo: o tom é de {tom} e ajuste o ritmo da narrativa para garantir fluidez e engajamento.

Observações importantes:

Não mencionar preços, promoções ou concorrentes.

Usar apenas os produtos da marca (exceto no caso de eletrodomésticos e eletrônicos destacados).

A edição deve ser dinâmica, com cortes rápidos e visuais atraentes.

Evitar tons negativos ou desrespeitosos.

Gere o roteiro com 250 palavras ou mais, respeitando os seguintes critérios:

Objetividade e clareza na apresentação do conceito da campanha.

Uso de linguagem envolvente para criar uma experiência emocional.

Ritmo e transições dinâmicas otimizadas para a duração curta de vídeos em plataformas como Instagram e TikTok.

{context}

Baseie o roteiro nas diretrizes abaixo:
{briefing}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "system",
                    "content": "Você é um redator criativo especialista em roteiros audiovisuais que se inspira em exemplos anteriores para criar conteúdo único e impactante.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=1,
            max_tokens=2048,
            top_p=1,
        )

        roteiro = response.choices[0].message.content
        return roteiro
    except Exception as e:
        print("Erro ao gerar o roteiro com inspiração:", e)
        return str(e)


async def get_media_url(media_id):
    headers = {"authorization": f"bearer {WHATSAPP_TOKEN}"}
    url = f"{GRAPH_URL}/{media_id}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        return resp.json().get("url")


async def download_media(url):
    headers = {"authorization": f"bearer {WHATSAPP_TOKEN}"}
    filename = "archive.pdf"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        with open(filename, "wb") as f:
            f.write(response.content)
    return filename


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
