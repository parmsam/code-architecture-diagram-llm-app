from shiny import App, ui, render, reactive
import urllib3
import json
import base64
from io import BytesIO
from PIL import Image

app_ui = ui.page_fluid(
    ui.h1("GitHub Repository Architecture Diagram Generator"),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_text("repo_url", "GitHub Repository URL", placeholder="https://github.com/username/repo"),
            ui.input_password("api_key", "OpenAI API Key"),
            ui.input_action_button("generate", "Generate Diagram"),
        ),
        ui.output_ui("diagram"),
        ui.output_text("error_message"),
    )
)

def server(input, output, session):
    http = urllib3.PoolManager()

    @reactive.Calc
    def generate_diagram():
        if not input.repo_url() or not input.api_key():
            return None

        repo_url = input.repo_url()
        api_key = input.api_key()

        # Fetch repository structure
        try:
            response = http.request('GET', f"{repo_url}/archive/refs/heads/main.zip")
            if response.status != 200:
                return f"Error: Unable to fetch repository. Status code: {response.status}"
        except Exception as e:
            return f"Error: {str(e)}"

        # Generate diagram using OpenAI API
        try:
            openai_url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are an AI that generates architecture diagrams based on GitHub repository structures."},
                    {"role": "user", "content": f"Generate a PlantUML diagram for the architecture of the repository at {repo_url}. Focus on the main components and their relationships."}
                ]
            }
            response = http.request('POST', openai_url, body=json.dumps(data).encode('utf-8'), headers=headers)
            
            if response.status != 200:
                return f"Error: OpenAI API request failed. Status code: {response.status}"
            
            response_data = json.loads(response.data.decode('utf-8'))
            plantuml_diagram = response_data['choices'][0]['message']['content']

            # Generate image from PlantUML
            plantuml_url = f"http://www.plantuml.com/plantuml/png/{base64.b64encode(plantuml_diagram.encode('utf-8')).decode('utf-8')}"
            img_response = http.request('GET', plantuml_url)
            
            if img_response.status != 200:
                return f"Error: Unable to generate diagram image. Status code: {img_response.status}"
            
            img = Image.open(BytesIO(img_response.data))
            buf = BytesIO()
            img.save(buf, format="PNG")
            img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            
            return f'<img src="data:image/png;base64,{img_base64}" alt="Architecture Diagram" style="max-width: 100%;">'
        except Exception as e:
            return f"Error: {str(e)}"

    @output
    @render.ui
    @reactive.event(input.generate)
    def diagram():
        result = generate_diagram()
        if result and result.startswith('<img'):
            return ui.HTML(result)
        return ui.HTML("")

    @output
    @render.text
    @reactive.event(input.generate)
    def error_message():
        result = generate_diagram()
        if result and not result.startswith('<img'):
            return result
        return ""

app = App(app_ui, server)
