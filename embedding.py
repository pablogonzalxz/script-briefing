import os
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


embeddings = OpenAIEmbeddings()
PERSIST_DIRECTORY = "./chroma_db"


class UserScriptCollection:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.collection_name = f"user_{user_id}_scripts"
        self.persist_directory = os.path.join(PERSIST_DIRECTORY, self.collection_name)
        os.makedirs(self.persist_directory, exist_ok=True)

        self.vectorstore = Chroma(
            collection_name=self.collection_name,
            persist_directory=self.persist_directory,
            embedding_function=embeddings,
        )

    def get_vectorstore(self):
        return self.vectorstore


user_collection = {}


def get_user_collection(user_id: str):
    if user_id not in user_collection:
        user_collection[user_id] = UserScriptCollection(user_id)
    return user_collection[user_id].get_vectorstore()


default_vectorstore = Chroma(
    persist_directory=PERSIST_DIRECTORY, embedding_function=embeddings
)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000, chunk_overlap=200, length_function=len
)
