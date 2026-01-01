import asyncio
from textual import on
from textual.app import ComposeResult
from textual.widgets import DataTable, ListView, ListItem, Label, Static
from textual.containers import Horizontal, Vertical

from widgets.dialogs import PolicySelectModal

class IdentityWidget(Static):
    BINDINGS = [
        ("a", "add_to_group", "Add to Group"),
        ("r", "remove_from_group", "Remove from Group"),
        ("p", "manage_policies", "Handle Policies"),
        ("g", "manage_groups", "Handle Groups"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="entity-side"):
                yield Label("󰏓 USERS (Entities)", classes="header-label")
                yield DataTable(id="entity-table")
            
            with Vertical(id="group-side"):
                yield Label("GROUPS", classes="header-label")
                yield ListView(id="group-list")

    async def on_mount(self) -> None:
        table = self.query_one("#entity-table", DataTable)
        table.add_columns("Name", "ID", "Policies", "Groups")
        table.cursor_type = "row"
        await self.refresh_all()

    async def refresh_all(self):
        await asyncio.sleep(0.1)
        self.refresh_entities()
        self.refresh_groups()

    def refresh_entities(self):
        try:
            table = self.query_one("#entity-table", DataTable)
            current_cursor = table.cursor_coordinate
            table.clear(columns=False)
            
            entities = self.app.vault.list_entities()
            groups = self.app.vault.list_groups() or []
            group_map = {g['id']: g['name'] for g in groups}
            
            for ent in entities:
                g_ids = ent.get("direct_group_ids") or []
                g_names = [group_map.get(gid, gid) for gid in g_ids]
                p_list = ", ".join(ent.get("policies", [])) or "-"
                
                table.add_row(
                    ent["name"], 
                    ent["id"], 
                    p_list,
                    ", ".join(sorted(g_names)) if g_names else "-",
                    key=ent["id"]
                )
            if current_cursor:
                try: table.move_cursor(row=current_cursor.row)
                except: pass
        except Exception as e:
            self.notify(f"Entity Refresh Error: {e}", severity="error")

    def refresh_groups(self):
        try:
            lst = self.query_one("#group-list", ListView)
            groups = self.app.vault.list_groups()
            old_index = lst.index
            lst.clear()
            
            if groups:
                for g in groups:
                    item = ListItem(Label(f"󰏓 {g['name']}"))
                    item.group_data = g 
                    lst.append(item)
                
                if old_index is not None:
                    try: lst.index = old_index
                    except: pass
        except Exception as e:
            self.notify(f"Group Refresh Error: {e}", severity="error")

    async def action_manage_policies(self):
        table = self.query_one("#entity-table", DataTable)
        group_list = self.query_one("#group-list", ListView)
        all_vault_policies = self.app.vault.list_policies()

        if self.app.focused == table:
            await self.manage_entity_policies(table, all_vault_policies)
        elif self.app.focused == group_list:
            await self.manage_group_policies(group_list, all_vault_policies)
        else:
            self.notify("Focus on a user or group first", severity="warning")

    async def manage_entity_policies(self, table, all_policies):
        if table.cursor_row is None: return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        entity_id = str(row_key.value)
        
        entities = self.app.vault.list_entities()
        entity = next((e for e in entities if e["id"] == entity_id), None)
        
        if entity:
            def handle_save(new_policies):
                if new_policies is not None:
                    self.app.vault.update_entity_policies(entity_id, entity["name"], new_policies)
                    self.notify(f"Policies updated for {entity['name']}")
                    self.run_worker(self.refresh_all())
            
            self.app.push_screen(
                PolicySelectModal(all_policies, entity.get("policies", []), f"Policies: {entity['name']}"), 
                handle_save
            )

    async def manage_user_groups(self, table):
        if table.cursor_row is None: return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        user_id = str(row_key.value)
        
        all_groups = self.app.vault.list_groups()
        entities = self.app.vault.list_entities()
        user_data = next((e for e in entities if e["id"] == user_id), None)
        
        if not user_data or not all_groups: return

        group_names = [g['name'] for g in all_groups]
        current_groups = [g['name'] for g in all_groups if user_id in (g.get('member_entity_ids') or [])]

        def handle_save(selected_names):
            if selected_names is None: return
            
            for group in all_groups:
                g_id = group['id']
                g_name = group['name']
                members = set(group.get('member_entity_ids') or [])
                
                if g_name in selected_names and user_id not in members:
                    members.add(user_id)
                    self.app.vault.update_group_members(g_id, g_name, list(members))
                
                elif g_name not in selected_names and user_id in members:
                    members.remove(user_id)
                    self.app.vault.update_group_members(g_id, g_name, list(members))
            
            self.notify(f"Group memberships synced for {user_data['name']}")
            self.run_worker(self.refresh_all())

        self.app.push_screen(
            PolicySelectModal(group_names, current_groups, f"Groups for: {user_data['name']}"),
            handle_save
        )

    async def action_manage_groups(self):
        table = self.query_one("#entity-table", DataTable)
        if self.app.focused == table:
            await self.manage_user_groups(table)
        else:
            self.notify("Focus on the User table to manage their groups", severity="warning")

    async def manage_group_policies(self, group_list, all_policies):
        item = group_list.highlighted_child
        if not item or not hasattr(item, "group_data"): return
        
        group_id = item.group_data["id"]
        group_name = item.group_data["name"]
        
        def handle_save(new_policies):
            if new_policies is not None:
                self.app.vault.update_group_policies(group_id, group_name, new_policies)
                self.notify(f"Policies updated for {group_name}")
                self.run_worker(self.refresh_all())

        self.app.push_screen(
            PolicySelectModal(all_policies, item.group_data.get("policies", []), f"Policies: {group_name}"), 
            handle_save
        )

    async def modify_membership(self, add: bool):
        table = self.query_one("#entity-table", DataTable)
        group_list = self.query_one("#group-list", ListView)

        if table.cursor_row is None or not group_list.highlighted_child:
            self.notify("Select both a user (left) and a group (right)", severity="warning")
            return

        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        entity_id = str(row_key.value)
        group_item = group_list.highlighted_child
        group_id = group_item.group_data["id"]
        group_name = group_item.group_data["name"]
        members = group_item.group_data.get("member_entity_ids", []) or []

        if add:
            if entity_id not in members: members.append(entity_id)
        else:
            if entity_id in members: members.remove(entity_id)

        try:
            self.app.vault.update_group_members(group_id, group_name, members)
            await self.refresh_all()
            self.notify(f"Updated membership in {group_name}")
        except Exception as e:
            self.notify(f"Membership Error: {e}", severity="error")

    async def action_add_to_group(self): await self.modify_membership(add=True)
    async def action_remove_from_group(self): await self.modify_membership(add=False)