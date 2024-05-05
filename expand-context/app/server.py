from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from langserve import add_routes
import vertexai
from typing import Any
from langchain_google_vertexai import VertexAI
from langchain.tools import GooglePlacesTool, tool
from langchain.agents import Tool
from langchain_community.utilities import GoogleSearchAPIWrapper
from langchain_google_vertexai import VertexAI, HarmBlockThreshold, HarmCategory
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_google_vertexai import ChatVertexAI
from langchain.pydantic_v1 import BaseModel
from langchain.tools import tool
from langchain import hub
import requests
import os

app = FastAPI()

LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
GPLACES_API_KEY = os.getenv("GPLACES_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PROJECT_ID = os.getenv("PROJECT_ID")
REGION = os.getenv("REGION")

required_env_vars = ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "GPLACES_API_KEY", "GOOGLE_CSE_ID", "GOOGLE_API_KEY", "REGION", "PROJECT_ID"]
for var in required_env_vars:
    if os.getenv(var, None) is None:
        raise ValueError(f"Environment variable {var} is not set.")


class Input(BaseModel):
    input: str  
class Output(BaseModel):
    output: Any
vertexai.init(project=PROJECT_ID,location=REGION)

model_name = "gemini-1.5-pro-preview-0409"

search = GoogleSearchAPIWrapper()

search_tool = Tool(
    name="google_search",
    description="Searches in Google for up to date information, examples: information about characters, news about sports, TV shows, episodes, general topics",
    func=search.run,
)

description_places="Searches for information (address, phone numbers, opinions, details) of places like hairdresser, restaurants, monuments and their data using the Google Maps Places API"
places_tool = GooglePlacesTool(name="search_places", description= description_places)

@tool("summary-tool")
def summary_tool(url: str) -> str:
    """Use this tool when asked for summaries or content of URLs. It gets the content of URL to be further actioned by LLM
    Args: url
    """
    import requests
    r = requests.get(url)
    return {"content": r.content, "link": url}


safety_settings = {
    HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
}

llm = ChatVertexAI(model=model_name, temperature=0.9, safety_settings=safety_settings)

prompt=hub.pull("gpalacin/agent-langchain-chat")

tools = [places_tool, search_tool,  summary_tool]
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools)

add_routes(
    app,
    agent_executor.with_types(input_type=Input, output_type=Output).with_config(
        {"run_name": "agent"}
    ),
    path="/expand-context"
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
