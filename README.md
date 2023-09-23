# Interstitial_API
Interstitial_API is a tiny relay API script powered by FastAPI designed for use with open source large language models, with a few nifty use cases and features already:

## Features & Functions 
🤖 &nbsp; **Prompt Formatting**: Add custom prefixes and suffixes to messages, or inject altogether new messages.<br>

🌐 &nbsp; **Remote API Access**: Accept encrypted API calls from anywhere over platforms like Cloudflare.<br>

🔌 &nbsp; **Extendable your API**: Add webhooks, connect multiple models to a single API domain, etc.<br>

🧹 &nbsp; **Clean up model names:** Don't let a paragraph-long folder path readout ruin your a e s t h e t i c chat UI.<br>

🦋 &nbsp; **Lightweight**: Minimal impact on CPU and memory.<br>

🥷🏾 &nbsp; **Asynchronous Backbone**: Nimble handling of whatever you send. <br>

🛠️ &nbsp; **Customizable**: Easily adapt to different models or requirements.<br>

&nbsp;

## I. Installation
### A. Prerequisites
- Python 3.7 or higher.
- [Official Python Download Link](https://www.python.org/downloads/)
- Or: `brew install python`.

### B. Create your folder and a virtual Python3 environment
Create a new folder for the interstitial_API relay server.
Download, e.g., `git clone`, the files.
Confirm your folder contains: 
	* `interstitial_API.py`
	* `start.sh`
	* `stop.sh`
	* `.env`  [⌘]+[shift]+[.] if hidden on Mac
	* `requirements.txt`
	* `this README.md`

```bash
python3 -m venv pick_a_name_any_name
source [name]/bin/activate # MacOS/Linux
[name]\Scripts\activate    # Windows
```

*Note: Creating a virtual environment isn’t strictly speaking necessary but is recommended. It helps stave off future headaches when two or more Python apps have mutually exclusive dependencies.*

### C. Install Dependencies
```bash
pip install -r requirements.txt
# or
pip install fastapi uvicorn httpx
```

### D. Prepare Files and Scripts
In the folder you've made, run:
```bash
chmod +x interstitial_API.py && chmod +x start.sh && chmod +x stop.sh
```

&nbsp;


## II. Validation
### A. Launch the Relay 🚀
Run: `./start.sh`

Without specifying command line arguments or defining environment variables in the .env file (more on that below), running start.sh will start an asynchronous API server at http://localhost:3456 that relays any queries (except GET /) to the corresponding endpoints at http://localhost:6789 (i.e. the default configuration on LM Studio).

*Note: The server will stop when the terminal window in which it is running is closed (or when you terminate it manually, e.g. by pressing [ctrl]+[c])*

### B. Test Endpoints
- Test the root endpoint: `curl http://localhost:3456/`
- Test chat completions: 
```
curl http://localhost:3456/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is 1 divided by 0?"}],
    "temperature": 0.7,
    "max_tokens": -1
  }'
```

&nbsp;


## III. Server Configuration 🖥️
### A. `nohup` keeps the llamas frolicking. 🦙
Without the command line argument `--nohup`, the server will stop when you close the terminal window in which the script is running. Thus, --nohup allows running the server headlessly.

Just remember to disable `--nohup` when you're troubleshooting or debugging. 🛠️

*Note: for compatibility and user experience, the script is not designed to allow enabling `nohup` by a durable variable i.e. in `.env.` It must be toggled via command line argument on each run.*

### B. custom local ports, destination APIs, and WAN access. 🔌
By default the relay server:
* runs on internal port 3456, 
* relays to and from http://localhost:6789, and 
* does not accept queries from outside of http://localhost

#### To specify a different local port… 🏡
`./start.sh  --port 3030`
.env: LOCAL_PORT=6789` (default)

#### To specify a different destination API… 🧳
 `./start.sh  --api-url "https://api.openai.com"`
 .env: `DESTINATION_API=http://localhost` (default)

#### To accept queries from outside http://localhost… ☣️
… don’t even think about doing it with a command line argument through uvicorn.‼️ 

Try Cloudflare Zero Trust, where a free account lets you accept API queries from anywhere via encrypted tunnels (e.g. https://api.yourdomain.com), with state-of-the-art DDoS protection and robust access control. Tailscale, Zerotier, and Netmaker are great for more insular . or reverse proxies like Nginx great alternative options from Tailscale, Zerotier, Netmaker, and Yggdrasil. None require you to open a port on your system to WAN.

<details><summary>‼️ ***Danger Zone*** ‼️</summary>
For those who need the open a relay server directly to external/WAN traffic and understand the risks, you can open the relay server directly to external/WAN traffic by launching the server with the following command rather than through `start.sh`:<pre>
        
        uvicorn interstitial_API:app --port 3456 --host 0.0.0.0
        
<i>Note: uvicorn accepts the —port argument but other server configurations must be made to .env file`</i></pre></details>


#### C. (Optional) Automatic Server Restart on MacOS. 🍎
Want the server to start every time you log into your Mac? Here's how:
a. Open "System Preferences" ➡️ "Login Items."
b. Click '+' ➡️ add `start.sh`.


&nbsp;


## IV. API Configuration. 📡
### --prompter 💉
- `./start.sh --prompter "user"`
- `./start.sh --prompter "system"`
- .env: `PROMPT_INJECTOR=""` (default/off)

The main purpose of the prompter is to demarcate user inputs and model outputs in the messages history, to help out those models that struggle to differentiate themselves from you. This is a common problem with LLMs and shows up in models autocompleting user inputs instead of responding, and carrying on a back-and-forth conversation with the “user,” but like, *not with the user* 👀

That's where this function comes in: whenever the client posts a chat completions request, this function jumps in the request JSON and inserts specific prefix tokens before the new user and suffix tokens after. It works with some models better than others (in my experience Chronos Beluga and Vicuna2 respond especially well). The default prefix and suffix are the most common, but check your model on huggingface to be sure.

#### --prompter “system”
When set to “system”, this will add the prefix and suffix as two separate message entries within the messages JSON, before and after the most recent user message, respectively.

<pre><details><summary>Example JSON after system prefix/suffix injection:</summary><pre>
{
    {
      "content": “<last assistant message>",
      "role": "assistant"
    },
    {
      "content": "\n\n### Instructions:\n",
      "role": "system"
    },
    {
      "content": “<last user message>”,
      "role": "user"
    },
    {
      "content": "\n\n### Response:\n",
      "role": "system"
    }
}</details></pre>


#### --prompter “user”
When set to “user”, this will add the prefix and suffix to the beginning and end, respectively, of the most recent user message.

<pre><details><summary>Example JSON after user prefix/suffix injection:</summary><pre>
{
    {
      "content": “<last assistant message>",
      "role": "assistant"
    },
    {
      "content": “\n\n### Instructions:\n<last user message>\n\n### Response:\n”,
      "role": "user"
    },
}</details></pre>
              

### --message-prefix
`./start.sh --message-prefix "\n# User:\n"` <br>
.env: `MESSAGE_PREFIX="\n\n### Instruction:\n"` (default)

This defines the prefix to be inserted before the user message on its way into the model, provided the prompter is enabled.


### --message-suffix
`./start.sh --message-suffix "\n\n### AI:\n"` <br>
.env: `MESSAGE_SUFFIX="\n\n### Assistant:\n"` (default)

This defines the suffix to be inserted after the user message on its way into the model, provided the prompter is enabled.



## V. Miscellaneous Functions 🧩

### Model name reducer

The API automatically reduces model names received from the /v1/models/ and /v1/chat/completions/ endpoints names to their UNIX basenames and removes their extensions, for better compatibility and aesthetics with ChatGPT UIs that aren’t designed to handle long model names.

Example model name before the reduction: “/Users/stevejobs/AIPlayground/Models/TheBloke/Wizard-Vicuna-30B-Uncensored-GGML/Wizard-Vicuna-30B-Uncensored.ggmlv3.q5_K_M.bin"

Example model name after the reduction: “Wizard-Vicuna-30B-Uncensored.ggmlv3.q5_K_M”

### Model name override

To patch compatibility between client and server apps that insist on different models, defining the MODEL_OVERRIDE variable will always tell the server that the client is requesting that model.

### Missing favicon patcher

If the destination API doesn’t serve up a favicon, have no fear 🤠

### ENDPOINT_COMPLETIONS and ENDPOINT_MODELS
These environment variables are set to /v1/chat/completions and /v1/models by default, respectively. 

If dealing with a destination API that uses different endpoints, change the .env file accordingly.
