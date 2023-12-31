import sys
import time

import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash
from dash.dependencies import Input, Output, State
from transformers import AutoModelWithLMHead, AutoTokenizer, GPT2Tokenizer
import torch

# device = "cuda" if torch.cuda.is_available() else "cpu"
device = "cpu"
print(f"Device: {device}")

name = "microsoft/DialoGPT-medium"
name = 'https://huggingface.co/microsoft/phi-1_5'
name = "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/raw/main/tokenizer_2/tokenizer_config.json"
name = "openai-gpt"
print(f"loading tokenizer [{name}] ...")
# tokenizer = AutoTokenizer.from_pretrained(
#   name,
#   cache_dir="cached",
#   force_download=True
# )
tokenizer = GPT2Tokenizer.from_pretrained(
  name,
  trust_remote_code=True,
  resume_download=True
)

print("loading model ...")
model = AutoModelWithLMHead.from_pretrained(name)

# Switch to cuda, eval mode, and FP16 for faster inference
if device == "cuda":
    model = model.half()
model.to(device)
model.eval()

print("model done.")


def textbox(text, box="other"):
    style = {
      "max-width"    : "55%",
      "width"        : "max-content",
      "padding"      : "10px 15px",
      "border-radius": "25px",
    }

    if box == "self":
        style["margin-left"] = "auto"
        style["margin-right"] = 0

        color = "primary"
        inverse = True

    elif box == "other":
        style["margin-left"] = 0
        style["margin-right"] = "auto"

        color = "light"
        inverse = False

    else:
        raise ValueError("Incorrect option for `box`.")

    return dbc.Card(text, style=style, body=True, color=color, inverse=inverse)


conversation = html.Div(
  style={
    "width"     : "80%",
    "max-width" : "800px",
    "height"    : "70vh",
    "margin"    : "auto",
    "overflow-y": "auto",
  },
  id="display-conversation",
)

controls = dbc.InputGroup(
  style={"width": "80%", "max-width": "800px", "margin": "auto"},
  children=[
    dbc.Input(id="user-input", placeholder="Write to the chatbot...", type="text"),
    dbc.InputGroupAddon(dbc.Button("Submit", id="submit", n_clicks=1), addon_type="append", ),
  ],
)

print("Dash setup ...")

# Define app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

# Define Layout
app.layout = dbc.Container(
  fluid=True,
  children=[
    html.H1("Dash Chatbot (with DialoGPT)"),
    html.Hr(),
    dcc.Store(id="store-conversation", data=""),
    conversation,
    controls,
  ],
)


@app.callback(
  Output("display-conversation", "children"), [Input("store-conversation", "data")]
)
def update_display(chat_history):
    return [
      textbox(x, box="self") if i % 2 == 0 else textbox(x, box="other")
      for i, x in enumerate(chat_history.split(tokenizer.eos_token)[:-1])
    ]


@app.callback(
  [Output("store-conversation", "data"), Output("user-input", "value")],
  [Input("submit", "n_clicks"), Input("user-input", "n_submit")],
  [State("user-input", "value"), State("store-conversation", "data")],
)
def run_chatbot(n_clicks, n_submit, user_input, chat_history):
    if n_clicks == 0:
        return "", ""

    print(f'n_submit: {n_submit} n_clicks: {n_clicks} user_input: {user_input} chat_history: {chat_history}')

    if user_input is None or chat_history is None:
        return chat_history, ""

    print(f'tokenizer.eos_token: {tokenizer.eos_token} tokenizer.eos_token_id: {tokenizer.eos_token_id}')
    # # temporary
    # return chat_history + user_input + "<|endoftext|>" + user_input + "<|endoftext|>", ""

    try:
        # encode the new user input, add the eos_token and return a tensor in Pytorch
        bot_input_ids = tokenizer.encode(
          chat_history + user_input + tokenizer.eos_token,
          return_tensors="pt"
        ).to(device)

        print(f'bot_input_ids: {bot_input_ids}')

        # generated a response while limiting the total chat history to 1000 tokens,
        chat_history_ids = model.generate(
          bot_input_ids,
          max_length=1024,
          pad_token_id=0  # tokenizer.eos_token_id
        )
    except Exception as e:
        import traceback
        print(f'EXCEPTION: {e}')
        traceback.print_exc()

    chat_history = tokenizer.decode(chat_history_ids[0])

    return chat_history, ""


if __name__ == "__main__":
    print(f"Started model {name}.")
    app.run_server(debug=True)
