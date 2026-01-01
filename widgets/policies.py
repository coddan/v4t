from textual import on
from textual.app import ComposeResult
from textual.widgets import ListView, ListItem, Label, TextArea, Input, Static
from textual.containers import Horizontal, Vertical

class PoliciesWidget(Static):
    BINDINGS = [
        ("n", "new_policy", "New Policy"),
        ("ctrl+s", "save_policy", "Save"),
        ("x", "delete_policy", "Remove"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="policy-sidebar"):
                yield Label("POLICIES", classes="header-label")
                yield ListView(id="policy-list")
            
            with Vertical(id="policy-editor-area"):
                yield Label("EDITOR", classes="header-label")
                yield Input(placeholder="Policy-name (ex. my-policy)", id="policy-name")
                yield TextArea(language="yaml", id="policy-text")

    def on_mount(self) -> None:
        self.refresh_policies()

    def refresh_policies(self):
        try:
            policies = self.app.vault.list_policies()
            lst = self.query_one("#policy-list", ListView)
            lst.clear()
            for p in sorted(policies):
                lst.append(ListItem(Label(p), id=p))
        except Exception as e:
            self.notify(f"Could not load policies: {e}", severity="error")

    @on(ListView.Selected, "#policy-list")
    def handle_policy_selected(self, event):
        name = event.item.id
        self.query_one("#policy-name").value = name
        try:
            content = self.app.vault.get_policy(name)
            self.query_one("#policy-text").load_text(content)
        except Exception as e:
            self.notify(f"Error reading policy: {e}", severity="error")


    def action_new_policy(self):
        self.query_one("#policy-name").value = ""
        self.query_one("#policy-name").focus()
        template = 'path "secret/data/*" {\n  capabilities = ["read"]\n}'
        self.query_one("#policy-text").load_text(template)
        self.notify("Enter policy name and define rules")

    def action_save_policy(self):
        name = self.query_one("#policy-name").value
        rules = self.query_one("#policy-text").text

        if not name:
            self.notify("Name missing!", severity="error")
            self.query_one("#policy-name").focus()
            return

        try:
            self.app.vault.save_policy(name, rules)
            self.notify(f"Policy '{name}' Saved")
            self.refresh_policies()
        except Exception as e:
            self.notify(f"Could not save: {e}", severity="error")

    def action_delete_policy(self):
        name = self.query_one("#policy-name").value
        if not name or name in ["root", "default"]:
            self.notify("Cannot remove system policies", severity="error")
            return

        try:
            self.app.vault.delete_policy(name)
            self.notify(f"Policy '{name}' removed")
            self.refresh_policies()
            self.query_one("#policy-name").value = ""
            self.query_one("#policy-text").load_text("")
        except Exception as e:
            self.notify(f"Error during deletion: {e}", severity="error")