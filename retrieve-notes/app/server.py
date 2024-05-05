from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from langserve import add_routes
from langchain_google_firestore import FirestoreVectorStore
from langchain_google_vertexai import VertexAI, ChatVertexAI, VertexAIEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain import hub
from langchain_core.runnables import RunnablePassthrough
from pydantic import BaseModel
from typing import Any
import os


project_id = os.environ['PROJECT_ID']
collection = os.environ['COLLECTION']
embedding_field =os.environ['EMBEDDING_FIELD']



app = FastAPI()

class Input(BaseModel):
    input: str  
    
    def get_input_text(self):
        return self.input
        
class Output(BaseModel):
    output: Any

embedding = VertexAIEmbeddings(
    model_name="textembedding-gecko@003",
    project=project_id,
)
vector_store = FirestoreVectorStore(
    collection=collection,
    embedding_service=embedding,
    embedding_field=embedding_field,
)

def format_docs(docs):
    return "\n\n-".join(doc.page_content for doc in docs)

def retrieve_notes_attr():
    NUMBER_OF_RESULTS = 5
    SEARCH_DISTANCE_THRESHOLD = 0.3
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": NUMBER_OF_RESULTS,
            "search_distance": SEARCH_DISTANCE_THRESHOLD,
        },
        filters=None,
    )

    prompt = hub.pull("gpalacin/retrieval_prompt")
    llm = ChatVertexAI(model_name="gemini-1.0-pro", temperature=0.5)
    return retriever, prompt, llm

retriever, prompt, llm = retrieve_notes_attr()


rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
    
add_routes(app, rag_chain, path="/retrieve-notes")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
