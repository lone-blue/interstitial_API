import asyncio
import os
import httpx
import re, json
import logging
import tempfile
import re
import elevenlabs
import time
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, Header, Request
from fastapi.responses import Response, StreamingResponse, FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from uuid import uuid4
from pydantic import BaseModel
from dotenv import load_dotenv
from httpx import HTTPStatusError, Timeout
from datetime import datetime
from subprocess import run, PIPE
from pydub import AudioSegment
from elevenlabs import voices, generate, stream, set_api_key, play

import shutil

load_dotenv()

# define our environment variables, which can be set in .env 
api_url = os.getenv("DESTINATION_API", "http://localhost:6789") # the API URL we're relaying to. This should generally remain localhost except if using docker, etc.
endpoint_completions = os.getenv("ENDPOINT_COMPLETIONS", "/v1/chat/completions") # these generally aren't changed from their defaults, but can be if necessary.
endpoint_models = os.getenv("ENDPOINT_MODELS", "/v1/models") # these generally aren't changed from their defaults, but can be if necessary.
message_prefix = os.getenv("MESSAGE_PREFIX", "\n\n### Instruction:\n") # the message we inject before the user's last message. The default, "### Instruction:\n", is common but not universal among current models, so check the hugging face page
message_suffix = os.getenv("MESSAGE_SUFFIX", "\n\n### Response:\n") # the message we inject after the user's last message (i.e. the last message before the model's response and effectively its prompt). The default, "### Response:\n", is common but not universal among current models, so check the hugging face page
message_prefix = os.getenv("MESSAGE_PREFIX").replace("\\n", "\n")
message_suffix = os.getenv("MESSAGE_SUFFIX").replace("\\n", "\n")
prompter = os.getenv("PROMPT_INJECTOR", "") # which role the prefix and suffix injections are attributed to
model_override = os.getenv("MODEL_OVERRIDE") # if for whatever reason we need to override the model specified by client for chat completions.

timeout = Timeout(connect=30, read=600, write=120, pool=5)

app = FastAPI()

class CompletionsRequest(BaseModel):
    prompt: str
    max_tokens: int

origins = [
    "http://localhost:3456",  
    "http://localhost:6789",  
    "http://localhost:12345", 
    "http://127.0.0.1:12345",
    ## specify other origins here, or uncomment the next line to allow all origins
    # origins = ["*"]
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

class UnexpectedEndpointError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

@app.exception_handler(UnexpectedEndpointError)
async def unexpected_endpoint_error_handler(request: Request, exc: UnexpectedEndpointError):
    return Response(
        content=json.dumps({
            'error': {
                'message': exc.detail,
                'type': 'invalid_request_error',
                'param': None,
                'code': None
            }
        }),
        media_type="application/json",
        status_code=exc.status_code
    )

async def send_request(client: httpx.AsyncClient, method: str, url: str, **kwargs):
    response = await client.request(method, url, **kwargs)
    content = response.json()

    if 'error' in content and 'Unexpected endpoint' in content['error']:
        raise UnexpectedEndpointError(content['error'])

    return Response(content=json.dumps(content), media_type=response.headers.get('content-type'), status_code=response.status_code)


@app.get("/v1/chat/completions")
async def get_completions (data: dict, request: Request):
    return request 

@app.post("/v1/chat/completions")
async def chat_completions(data: dict, request: Request):

    headers_to_forward = {key: value for key, value in request.headers.items() if key.lower() in ['content-type', 'authorization']}
    modified_data = data
    is_streaming = data.get("stream", False)

   # if prompter is set to system, add system messages with prefix/suffix as new messages separating user and assistant messages, and prompting assistant
    if prompter == "system":
        modified_data = add_system_messages(data)

   # if prompter is set to user, modify the last user message to begin and and with the prefix/suffix. Some models respond better to this approach.
    elif prompter == "user":
        modified_data = add_user_prompts(data)

   # Apply model override if set
    if model_override:
        modified_data = apply_model_override(modified_data)
    
   # Create an HTTP client
    client = httpx.AsyncClient()
    logger.info(f"Sending data to destination API: {modified_data}")
    try:
        if is_streaming:
           # Define a generator function to stream content from the destination API
            async def content_generator():
               # Send the POST request to the destination API and stream the response
                async with client.stream('POST', f'{api_url}{endpoint_completions}', json=modified_data, headers=headers_to_forward, timeout=timeout) as response:
                    logger.info(f"Received response from destination API: {response.status_code}")
                   # Handle non-200 status codes
                    if response.status_code != 200:
                        await response.aread()  # read the response before accessing content
                        yield f"Error: {response.content}".encode()
                        return
                   # Asynchronously iterate over the response text in chunks
                    async for chunk in response.aiter_text():
                        try:
                           # Check for special 'data: [DONE]' chunk
                            if chunk.strip() == 'data: [DONE]':
                                logger.info("Chunk stream completed.")
                                yield chunk.encode()
                                return

                            json_data = json.loads(chunk.split('data: ', 1)[1])
                            content_value = json_data.get('choices', [{}])[0].get('delta', {}).get('content', None)
                            if content_value is not None:
                            #   print(f"{json.dumps(json_data)}\n\n")
                                print(f"Received chunk from destination API, with this choices:delta:content: {content_value}")
                            else:
                                print("Content key not found in the chunk.")

                           
                            # Extract the JSON part from the chunk, assuming "data: " prefix is present
                            json_str = chunk.split("data: ", 1)[1]
                            # Parse the JSON string into a Python object
                            chunk_dict = json.loads(json_str)
                            # Remove folder paths and .bin from the "model" field
                            chunk_dict['model'] = re.sub(r'.*\/([^/]+)\.bin$', r'\1', chunk_dict['model'])
                            # Combine the "data: " prefix with the transformed JSON string
                            transformed_chunk = "data: " + json.dumps(chunk_dict)

                           # Yield each chunk to stream it to the client
                            yield transformed_chunk.encode()

                        except GeneratorExit:
                           # Handle client disconnection
                            logger.info("Client disconnected, closing stream.")
                            return

           # Return a StreamingResponse to stream the content to the client in real-time
            return StreamingResponse(content_generator(), media_type="text/plain")

        else:
           # Use client.post if streaming is false
            response = await client.post(f'{api_url}{endpoint_completions}', json=modified_data, headers=headers_to_forward, timeout=timeout)

           # Check for an error within the response content
            response_json = response.json()
            if 'error' in response_json:
                return {"error": response_json['error']}
            
           # Return the JSON response directly
            return response_json

    except asyncio.TimeoutError:
       # Handle request timeouts
        logger.error("The request to the destination API timed out.")
        return {"error": "The request timed out."}
        
    except Exception as e:
       # Handle other exceptions
        logger.error(f"Exception occurred: {e}")
        return {"error": str(e)}

# This function inserts the prefixes and suffixes as separate system messages between user and assistant text
def add_system_messages(data: dict) -> dict:
    messages = data.get('messages', [])
    if messages:
        last_user_msg_index = next(
            (i for i, msg in reversed(list(enumerate(messages))) if msg.get('role') == 'user'),
            None
        )
        if last_user_msg_index is not None:
            messages.insert(last_user_msg_index, {"content": message_prefix, "role": prompter})
            messages.insert(last_user_msg_index + 2, {"content": message_suffix, "role": prompter})
    return data

# This function inserts the prefixes and suffixes at the beginning and end of the latest user message
def add_user_prompts(data: dict) -> dict:
    messages = data.get('messages', [])
    if messages:
        last_user_msg_index = next(
            (i for i, msg in reversed(list(enumerate(messages))) if msg.get('role') == 'user'),
            None
        )
        if last_user_msg_index is not None:
            user_message_content = messages[last_user_msg_index]['content']
            modified_content = f"{message_prefix}{user_message_content}\n{message_suffix}"
            messages[last_user_msg_index]['content'] = modified_content
    return data

# This function overrides the model specified in the original request
def apply_model_override(data: dict) -> dict:
    if model_override and model_override.strip() != "":
        data["model"] = model_override
    return data


@app.post("/v1/completions")
async def completions(request_model: CompletionsRequest, request: Request):
    print(request_model)
   # Reformatting the request payload to match the /v1/chat/completions endpoint
    chat_completions_payload = {
        "messages": [
            {
                "role": "user",
                "content": request_model.prompt
            }
        ],
        "max_tokens": request_model.max_tokens if request_model.max_tokens > 0 else -1,
        "stream": False
    }##

   # Directly call the existing /v1/chat/completions endpoint function
    chat_response = await chat_completions(chat_completions_payload, request)#

   # Extracting and reformatting the relevant data
    formatted_response = {
        "id": chat_response['id'].replace('chatcmpl', 'cmpl'),
        "object": "text_completion",
        "created": chat_response['created'],
        "model": chat_response['model'].split('/')[-1].split('.')[0], # Extract model name from path
        "choices": [
            {
                "text": chat_response['choices'][0]['message']['content'],
                "index": chat_response['choices'][0]['index'],
                "logprobs": None,
                "finish_reason": chat_response['choices'][0]['finish_reason']
            }
        ],
        "usage": chat_response['usage']
    }##

   # Returning the response to the requester
    return formatted_response


# Queries the available models on the destination API
@app.get("/v1/models")
async def models():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f'{api_url}{endpoint_models}', timeout=30.0)
           # Print the response content to debug the issue
            print("Response content:", response.content)
            
           # Update the "id" value in the response
            data = json.loads(response.content)
            data["data"][0]["id"] = re.sub(r'.*\/([^/]+)\.bin$', r'\1', data["data"][0]["id"])
            
           # Convert the updated data back to a JSON string
            modified_data = json.dumps(data)

            logger.debug(f"api_url: {api_url}")
            logger.debug(f"endpoint_models: {endpoint_models}")
            return json.loads(modified_data)

        except httpx.HTTPError:
            logger.error("Error retrieving models from destination API.")
            return {"error": "Failed to retrieve models from the destination API."}

        except Exception as e:
           # Handle exceptions or errors that may occur during the request
            print("Request error:", str(e))
            return {"error": f"Request error: {str(e)}"}

# Attempts to pull the favicon from the destination API, otherwise returns :cowboy:
@app.get("/favicon.ico")
async def favicon():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f'{api_url}/favicon.ico', timeout=30.0)
           # Check if the response is not empty (you may need to adjust the condition depending on the API)
            if response.status_code == 200 and response.content:
                return Response(response.content, media_type=response.headers.get('content-type'), status_code=response.status_code)
        except httpx.HTTPError:
            logger.error("Error retrieving favicon from destination API. Using local fallback.")
    
    return FileResponse("favicon.ico")

@app.head("/")
async def read_root():
    return {}

@app.get("/")
async def root():
    return {"message": "This relay is powered by interstitial_API"}
