import os, sys
from textual.app import App, ComposeResult
from textual import on
from textual.widgets import Header, Footer, Button, ContentSwitcher, Static
from textual.containers import Horizontal, Vertical
from utils.vault_client import VaultManager

from widgets.secrets import SecretsWidget
from widgets.identity import IdentityWidget
from widgets.policies import PoliciesWidget

class VaultTUI(App):
    CSS_PATH = "app.tcss"

    BINDINGS = [
        ("1", "switch_tab('secrets')", "Secrets"),
        ("2", "switch_tab('identity')", "Identity"),
        ("3", "switch_tab('policies')", "Policies"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.vault = VaultManager(
            url=os.getenv("VAULT_ADDR", "http://127.0.0.1:8200"),
            token=os.getenv("VAULT_TOKEN", "vault-root-token")
        )

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="nav-bar"):
            yield Button("Secrets", id="nav-secrets", variant="primary")
            yield Button("Identity", id="nav-identity")
            yield Button("Policies", id="nav-policies")
        
        with ContentSwitcher(initial="secrets"):
            yield SecretsWidget(id="secrets")
            yield IdentityWidget(id="identity")
            yield PoliciesWidget(id="policies")
            
        yield Footer()


    def action_switch_view(self, view_id: str) -> None:
        valid_views = ["secrets", "identity", "policies"]
        
        if view_id not in valid_views:
            return

        self.query_one(ContentSwitcher).current = view_id
        
        for btn in self.query("#nav-bar Button"):
            btn.variant = "primary" if btn.id == f"nav-{view_id}" else "default"

    @on(Button.Pressed)
    def handle_nav(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("nav-"):
            view_id = event.button.id.replace("nav-", "")
            self.action_switch_view(view_id)

if __name__ == "__main__":
    VaultTUI().run()