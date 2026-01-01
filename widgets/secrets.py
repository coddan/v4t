import json
from textual import on
from textual.app import ComposeResult
from textual.widgets import ListView, ListItem, Label, TextArea, Input, Static
from textual.containers import Horizontal, Vertical

from widgets.dialogs import PathDialog

class SecretsWidget(Static):
    BINDINGS = [
        ("n", "create_secret", "New Secret"),
        ("x", "confirm_delete", "Remove"),
        ("c", "copy_secret", "Copy"),
        ("m", "move_secret", "Move"),
        ("ctrl+s", "save_secret", "Save"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_mount = ""
        self.current_path = ""

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="mount-container"):
                yield Label("MOUNTS", classes="header-label")
                yield ListView(id="mount-list")
            with Vertical(id="key-container"):
                yield Label("SECRETS", classes="header-label")
                yield ListView(id="key-list")
            with Vertical(id="editor-container"):
                yield Label("EDITOR", classes="header-label")
                yield Input(placeholder="Path (ex. my-app/config)", id="secret-path")
                yield TextArea(language="json", id="secret-editor")

    def on_mount(self) -> None:
        self.refresh_mounts()

    def refresh_mounts(self):
        try:
            mounts = self.app.vault.list_mounts()
            lst = self.query_one("#mount-list", ListView)
            lst.clear()
            for path in sorted(mounts.keys()):
                safe_id = path.replace("/", "_").strip("_")
                item = ListItem(Label(f"󰆧 {path}"), id=f"mnt_{safe_id}")
                item.vault_path = path
                lst.append(item)
        except Exception as e:
            self.notify(f"Error loading mounts: {e}", severity="error")

    @on(ListView.Selected, "#mount-list")
    async def handle_mount_selected(self, event):
        self.current_mount = event.item.vault_path
        self.current_path = ""
        await self.refresh_keys()

    async def refresh_keys(self):
        try:
            lst = self.query_one("#key-list", ListView)
            await lst.query("ListItem").remove() 
            
            if not self.current_mount:
                return

            keys = self.app.vault.list_keys(self.current_mount, self.current_path)
            
            if self.current_path:
                back_item = ListItem(Label("󰉖 .. (Back)"), id="key_back")
                back_item.is_dir = True
                back_item.is_back = True
                lst.append(back_item)

            for key in keys:
                is_dir = key.endswith("/")
                icon = "󰉋" if is_dir else "󰏓"
                
                safe_key = key.replace("/", "_").replace(".", "_")
                unique_id = f"key_{safe_key}"
                
                item = ListItem(Label(f"{icon} {key}"))
                item.vault_key = key
                item.is_dir = is_dir
                item.is_back = False
                lst.append(item)
                
        except Exception as e:
            self.notify(f"Could not load keys: {e}", severity="error")

    @on(ListView.Selected, "#key-list")
    async def handle_key_selected(self, event):
        item = event.item
        
        if hasattr(item, "is_back") and item.is_back:
            parts = self.current_path.strip("/").split("/")
            self.current_path = "/".join(parts[:-1])
            if self.current_path: 
                self.current_path += "/"
            await self.refresh_keys()
            return

        if item.is_dir:
            self.current_path += item.vault_key 
            await self.refresh_keys()
            return

        full_key_path = f"{self.current_path}{item.vault_key}"
        self.query_one("#secret-path").value = full_key_path
        
        try:
            data = self.app.vault.read_secret(self.current_mount, full_key_path)
            self.query_one("#secret-editor").load_text(json.dumps(data, indent=2))
        except Exception as e:
            self.notify(f"Read failed: {e}", severity="error")

    def action_create_secret(self):
        if not hasattr(self, 'current_mount'):
            self.notify("Choose mount path first!", severity="warning")
            return
        self.query_one("#secret-path").value = ""
        self.query_one("#secret-path").focus()
        self.query_one("#secret-editor").load_text('{\n  "key": "value"\n}')

    def action_save_secret(self):
        path = self.query_one("#secret-path").value
        raw_content = self.query_one("#secret-editor").text
        
        if not path:
            self.notify("Path is missing!", severity="error")
            return
        try:
            data = json.loads(raw_content)
            self.app.vault.save_secret(self.current_mount, path, data)
            self.notify(f"Saved '{path}'")
            self.run_worker(self.refresh_keys())
        except json.JSONDecodeError:
            self.notify("Invalid JSON format!", severity="error")
        except Exception as e:
            self.notify(f"Save failed: {e}", severity="error")

    def action_confirm_delete(self):
        lst = self.query_one("#key-list", ListView)
        if lst.highlighted_child:
            item = lst.highlighted_child
            try:
                self.app.vault.delete_secret(item.vault_mount, item.vault_key)
                self.notify(f"Removed {item.vault_key}")
                self.refresh_keys()
                self.query_one("#secret-editor").load_text("")
                self.query_one("#secret-path").value = ""
            except Exception as e:
                self.notify(f"Remove failed: {e}", severity="error")

    def action_copy_secret(self):
        source = self.query_one("#secret-path").value        
        def handle_copy(new_path):
            if new_path and new_path != source:
                try:
                    source_item = self.query_one("#key-list").highlighted_child
                    data = self.app.vault.read_secret(source_item.vault_mount, source_item.vault_key)
                    
                    parts = new_path.strip("/").split("/", 1)
                    new_mount = parts[0]
                    new_secret_path = parts[1] if len(parts) > 1 else ""
                
                    self.app.vault.save_secret(new_mount, new_secret_path, data)
                    self.notify(f"Copied to {new_path}")
                    self.current_mount = new_mount
                    self.refresh_keys()
                except Exception as e:
                    self.notify(f"Copy failed: {e}", severity="error")

        self.app.push_screen(PathDialog(source, "Copy"), handle_copy)

    def action_move_secret(self):
        source = self.query_one("#secret-path").value        
        def handle_move(new_path):
            if new_path and new_path != source:
                try:
                    source_item = self.query_one("#key-list").highlighted_child
                    data = self.app.vault.read_secret(source_item.vault_mount, source_item.vault_key)
                
                    parts = new_path.strip("/").split("/", 1)
                    new_mount = parts[0]
                    new_secret_path = parts[1] if len(parts) > 1 else ""
                
                    self.app.vault.save_secret(new_mount, new_secret_path, data)
                    self.app.vault.delete_secret(source_item.vault_mount, source_item.vault_key)
                    
                    self.notify(f"Moved to {new_path}")
                    self.current_mount = new_mount
                    self.query_one("#secret-path").value = ""
                    self.query_one("#secret-editor").load_text("")
                    self.refresh_keys()
                except Exception as e:
                    self.notify(f"Move failed: {e}", severity="error")

        self.app.push_screen(PathDialog(source, "Move"), handle_move)
