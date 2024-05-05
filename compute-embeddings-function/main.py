import os
import logging
from google.cloud import firestore as fstore
from google.events.cloud import firestore as event_firestore
from google.cloud.firestore_v1.vector import Vector

import functions_framework
from vertexai import init
from vertexai.language_models import TextGenerationModel, TextEmbeddingInput, TextEmbeddingModel


logging.basicConfig(level=logging.INFO)

def fetch_categories(db):
    categories_ref = db.collection('categories')
    categories_docs = categories_ref.stream()
    return [doc.to_dict()['name'] for doc in categories_docs]

def classify_text(text, categories, project_id):
    region = os.getenv('REGION')
    init(project=project_id, location=region)
    parameters = {
        "candidate_count": 1,
        "max_output_tokens": 70,
        "temperature": 0.1,
        "top_p": 1
    }
    model = TextGenerationModel.from_pretrained("text-bison")

    response = model.predict(
        f"Classify the following text into these categories {categories}, if the text does not correspond to any category classify it as random. Respond only with the word/words of the category only. Only one category available, in case of a note blonging to different ones you must pick the closet one but only one. text: {text}, category:",
        **parameters
    )
    logging.info(f"Response from Model: {response.text}")
    return response.text.strip()

def calculate_embedding(text):
    model_name = "textembedding-gecko@003"
    task = "RETRIEVAL_DOCUMENT"
    model = TextEmbeddingModel.from_pretrained(model_name)
    inputs = TextEmbeddingInput(text, task)
    embeddings = model.get_embeddings([inputs])
    return embeddings[0].values

@functions_framework.cloud_event
def main(cloud_event):
    if cloud_event.data:
        try:
            firestore_payload = event_firestore.DocumentEventData()
            firestore_payload._pb.ParseFromString(cloud_event.data)
            text = firestore_payload.value.fields['content'].string_value
            doc_id = firestore_payload.value.name.split("/")[-1]
            collection = firestore_payload.value.name.split("/")[-2]


            project_id = os.getenv('PROJECT_ID')
            db = fstore.Client(project=project_id)
            categories = fetch_categories(db)
            category = classify_text(text, categories, project_id)
            embeddings = calculate_embedding(text)

            notes_ref = db.collection(collection).document(doc_id)
            notes_ref.update({'category': category, 'embeddings': Vector(embeddings)})
        except Exception as e:
            logging.error(f'An error occurred: {str(e)}', exc_info=True)
    else:
        logging.error('No data in cloud event')
