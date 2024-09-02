from shiny import App, ui, render, reactive
import urllib3
import json
from openai import OpenAI
import html

try:
    from setup import api_key1
except ImportError:
    api_key1 = ""

example_repo_url = "https://github.com/parmsam/yt-dl-pipeline"

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.script(src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"),
        ui.tags.script("""
            function renderMermaid() {
                mermaid.initialize({startOnLoad: false});
                mermaid.run();
            }
        """)
    ),
    ui.h1("GitHub Repository Architecture Diagram Generator"),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_text(
                "repo_url", 
                "GitHub Repository URL", 
                placeholder="https://github.com/username/repo",
                value=example_repo_url),
            ui.input_password("api_key", "OpenAI API Key", value=api_key1),
            ui.input_action_button("generate", "Generate Diagram"),
            open="always",
        ),
        ui.output_ui("mermaid_output"),
        ui.output_code("diagram"),
    ),
)

def server(input, output, session):
    mermaid_code = reactive.Value("")
    http = urllib3.PoolManager()

    @reactive.Effect
    @reactive.event(input.generate)
    def _():
        if not input.api_key():
            ui.notification_show("Please enter your OpenAI API key.", type="error")
        if not input.repo_url():
            ui.notification_show("Please enter a GitHub repository URL.", type="error") 
        repo_url = input.repo_url()
        api_key = input.api_key()
        owner_repo = repo_url.replace("https://github.com/", "")
        # Fetch repository structure and files using GitHub API
        try:
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
        except Exception as e:
            ui.notification_show(f"Error: {str(e)}", type="error")
        # Generate diagram using OpenAI API
        client = OpenAI(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an AI that generates Mermaid diagrams based on GitHub repository structures."},
                    {"role": "user", "content": f"""Generate a Mermaid diagram for the architecture of the repository at {repo_url}. 
                     - Focus on the main components and their relationships. 
                     - Just include the mermaid chart code. 
                     - Don't include the triple backticks (like ```mermaid ```). Just give me the code. 
                     - Ensure it is compliant with mermaid syntax rules.""",},
                    {"role": "user", "content": f"Repository structure:\n{json.dumps(files_info, indent=2)}"}
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