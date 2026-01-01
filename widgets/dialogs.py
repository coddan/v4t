from textual import on
from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.widgets import Label, Input, Button, SelectionList
from textual.widgets.selection_list import Selection
from textual.containers import Horizontal, Vertical

class PathDialog(ModalScreen):
    def __init__(self, current_path, action_name):
        super().__init__()
        self.current_path = current_path
        self.action_name = action_name

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(f"{self.action_name}: {self.current_path}", id="modal-title")
            yield Input(value=self.current_path, id="new-path-input")
            with Horizontal(id="modal-buttons"):
                yield Button("Ok", variant="success", id="save") 
                yield Button("Abort", variant="error", id="cancel")

    @on(Button.Pressed, "#save")
    def confirm(self):
        new_path = self.query_one("#new-path-input").value
        self.dismiss(new_path)

    @on(Button.Pressed, "#cancel")
    def cancel(self):
        self.dismiss(None)

class PolicySelectModal(ModalScreen):
    def __init__(self, all_policies, current_policies, title="Choose Policies"):
        super().__init__()
        self.all_policies = sorted(all_policies)
        self.current_policies = set(current_policies or [])
        self.title_text = title

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(self.title_text, id="modal-title")
            yield Input(placeholder="Search policy...", id="policy-search")
            yield SelectionList[str](
                *[Selection(p, p, p in self.current_policies) for p in self.all_policies],
                id="policy-selection"
            )
            with Horizontal(id="modal-buttons"):
                yield Button("Save", variant="success", id="save")
                yield Button("Abort", variant="error", id="cancel")

    @on(Input.Changed, "#policy-search")
    def filter_list(self, event):
        search_term = event.value.lower()
        selection_list = self.query_one("#policy-selection", SelectionList)
        current_selected = set(selection_list.selected)
        selection_list.clear()
        for p in self.all_policies:
            if search_term in p.lower():
                is_selected = p in current_selected
                selection_list.add_option(Selection(p, p, is_selected))

    @on(Button.Pressed, "#save")
    def save(self):
        self.dismiss(self.query_one("#policy-selection").selected)

    @on(Button.Pressed, "#cancel")
    def cancel(self):
        self.dismiss(None)

