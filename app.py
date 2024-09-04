from shiny import App, ui, render, reactive
import urllib3
import json
from openai import OpenAI
import html
import os
import http
from shiny.types import FileInfo

try:
    from setup import api_key1
except ImportError:
    api_key1 = os.getenv("OPENAI_API_KEY")
    
example_repo_url = "https://github.com/parmsam/yt-dl-pipeline"

app_info = """
This app creates a code architecture diagram in Mermaid based on an uploaded 
file or GitHub repository using OpenAI's GPT-4o-mini model.
"""
mermaid_chart_options = [
    "graph", "flowchart", "sequenceDiagram",
    "erDiagram",  "classDiagram", "mindmap",
    "stateDiagram",
]

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.script(
            src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"
        ),
        ui.tags.script("""
            function renderMermaid() {
                mermaid.initialize({startOnLoad: false});
                mermaid.run();
            }
        """)
    ),
    ui.h1("Code Architecture Diagram Generator"),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_radio_buttons("source", None, ["file upload", "repo url"], inline=True),
            ui.panel_conditional(
                "input.source === 'repo url'", 
                ui.input_text(
                    "repo_url", 
                    "GitHub Repository URL", 
                    placeholder="https://github.com/username/repo",
                    value=example_repo_url
                )
            ),
            ui.panel_conditional(
                "input.source === 'file upload'", 
                ui.input_file("file1", "Upload Code File", multiple=False),
            ),
            ui.input_password("api_key", "OpenAI API Key", value=api_key1),
            ui.input_select(
                "mermaid_chart_type", 
                "Mermaid Chart Type", 
                choices=mermaid_chart_options,
                selected="graph",
                ),
            ui.input_action_button("generate", "Generate Diagram"),
            open="always",
        ),
        ui.markdown(app_info),
        ui.output_ui("mermaid_output"),
        ui.output_code("diagram"),
    ),
)

def server(input, output, session):
    mermaid_code = reactive.Value("")
    http = urllib3.PoolManager()
    
    @reactive.calc
    def parsed_file():
        file: list[FileInfo] | None = input.file1()
        if file is None:
            return None
        with open(file[0]["datapath"], "r") as f:
            content = f.read()
        return content

    @reactive.Effect
    @reactive.event(input.generate)
    def _():
        if not input.api_key():
            ui.notification_show("Please enter your OpenAI API key.", type="error")
        if not input.repo_url():
            ui.notification_show("Please enter a GitHub repository URL.", type="error") 
        repo_url = input.repo_url()
        api_key = input.api_key()
        mermaid_chart_type = input.mermaid_chart_type()
        owner_repo = repo_url.replace("https://github.com/", "")
        # Fetch repository structure and files using GitHub API
        if input.source() == "repo url":
            try:
                # headers = {'User-Agent': 'Mozilla/5.0'}
                # repo_response = http.request('GET', f"https://api.github.com/repos/{owner_repo}/git/trees/main?recursive=1", headers=headers)
                repo_response = http.request('GET', f"https://api.github.com/repos/{owner_repo}/git/trees/main?recursive=1")
                if repo_response.status != 200:
                    ui.notification_show(f"Error: Unable to fetch repository structure. Status code: {repo_response.status}")
                try:
                    repo_data_decoded = repo_response.data.decode('utf-8')
                except AttributeError:
                    repo_data_decoded = repo_response.data
                repo_data = json.loads(repo_data_decoded)
                files_info = []
                for file in repo_data.get('tree', []):
                    if file['type'] == 'blob':
                        file_content_response = http.request('GET', f"https://raw.githubusercontent.com/{owner_repo}/main/{file['path']}")
                        if file_content_response.status == 200:
                            try:
                                file_content_response_decoded = file_content_response.data.decode('utf-8')
                            except AttributeError:
                                file_content_response_decoded = file_content_response.data
                            files_info.append({
                                'path': file['path'],
                                'content': file_content_response_decoded
                            })
                            source_code = json.dumps(files_info, indent=2)
            except Exception as e:
                ui.notification_show(f"Error: {str(e)}", type="error")
        elif input.source() == "file upload":
            source_code = parsed_file()
        # Generate diagram using OpenAI API
        client = OpenAI(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an AI that generates Mermaid diagrams based on GitHub repository structures."},
                    {"role": "user", "content": f"""Generate a Mermaid diagram for the architecture of a code repository or individual code file. 
                     - Focus on the main components and their relationships. 
                     - Just include the mermaid chart code. 
                     - Don't include the triple backticks (like ```mermaid ```). Just give me the code. 
                     - Ensure it is compliant with mermaid syntax rules and is a {mermaid_chart_type} mermaid chart.""",},
                    {"role": "user", "content": f"Code:\n{source_code}"}
                ]
            )
            response_data = response.choices[0].message.content
            mermaid_code.set(response_data)
        except Exception as e:
            ui.notification_show(f"Error: {str(e)}", type="error")
        
    @output
    @render.ui
    @reactive.event(input.generate)
    def mermaid_output():
        response = mermaid_code()
        if not response:
            return ""
        mermaid_html = ui.HTML(f"""
            <div class="mermaid">
                {response}
            </div>
            <script>
                renderMermaid();
            </script>
        """)
        return mermaid_html
    
    @output
    @render.code
    def diagram():
        result = mermaid_code()
        return result if result else "No diagram generated."

app = App(app_ui, server)