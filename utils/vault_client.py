import hvac

class VaultManager:
    def __init__(self, url="http://127.0.0.1:8200", token=None):
        self.url = url.rstrip('/')
        self.token = token
        self.client = hvac.Client(url=url, token=token)

    ### secrets
    def list_mounts(self):
        try:
            mounts = self.client.sys.list_mounted_backends()
            data = mounts.get("data", mounts) if isinstance(mounts, dict) else mounts
            
            if data and isinstance(data, dict):
                return {k: v for k, v in data.items() if isinstance(v, dict) and v.get('type') in ['kv', 'generic']}
        except Exception:
            pass

        try:
            res = self.client.read("sys/mounts")
            if res and isinstance(res, dict):
                data = res.get("data", res)
                return {k: v for k, v in data.items() if isinstance(v, dict) and v.get('type') in ['kv', 'generic']}
        except Exception:
            pass
        
        return {}

    def list_keys(self, mount_path, path=""):
        mount = mount_path.strip("/")
        p = path.strip("/")
        try:
            res = self.client.secrets.kv.v2.list_secrets(
                path=p,
                mount_point=mount
            )
            return res.get("data", {}).get("keys", [])
        except Exception:
            try:
                res = self.client.sys.list_mounted_backends()
                path_to_list = f"{mount}/{p}".rstrip("/")
                res = self.client.read(f"{path_to_list}?list=true")
                return res.get("data", {}).get("keys", []) if res else []
            except Exception:
                return []

    def read_secret(self, mount, path):
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                mount_point=mount,
                path=path
            )
            return response['data']['data']
        except Exception:
            res = self.client.read(f"{mount}/{path}")
            return res.get("data", {}) if res else {}

    def save_secret(self, mount_path, key_path, data):
        mount = mount_path.strip("/")
        key = key_path.lstrip("/")
        try:
            # KV v2
            self.client.secrets.kv.v2.create_or_update_secret(
                path=key,
                secret=data,
                mount_point=mount
            )
        except Exception:
            # KV v1
            self.client.write(f"{mount}/{key}", **data)

    def delete_secret(self, mount, path):
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                mount_point=mount,
                path=path
            )
        except Exception:
            self.client.delete(f"{mount}/{path}")

    def move_secret(self, source_path, dest_path):
        self.copy_secret(source_path, dest_path)
        return self.delete_secret(source_path)

    def copy_secret(self, source_path, dest_path):
        data = self.read_secret(source_path)
        if data:
            return self.client.write(dest_path, **data)
        raise Exception("Source path is empty or not found")


    ## identity and group
    def list_entities(self):
        try:
            res = self.client.read("identity/entity/id?list=true")
            keys = res.get("data", {}).get("keys", []) if res else []
            entities = []
            for eid in keys:
                ent = self.client.read(f"identity/entity/id/{eid}")
                if ent and "data" in ent:
                    entities.append(ent["data"])
            return entities
        except Exception:
            return []

    def list_groups(self):
        try:
            res = self.client.read("identity/group/id?list=true")
            if not res or not res.get("data"):
                return []
            
            keys = res["data"].get("keys", [])
            groups = []
            for gid in keys:
                g = self.client.read(f"identity/group/id/{gid}")
                if g and g.get("data"):
                    groups.append(g["data"])
            return groups
        except Exception as e:
            print(f"VAULT CLIENT ERROR (list_groups): {e}")
            return []

    def update_group_members(self, group_id, name, entity_ids):
        try:
            payload = {
                "name": name,
                "member_entity_ids": entity_ids
            }
            return self.client.write(f"identity/group/id/{group_id}", **payload)
        except Exception as e:
            raise Exception(f"Could not update group: {e}")

    def refresh_groups(self):
        try:
            groups = self.app.vault.list_groups()
            lst = self.query_one("#group-list", ListView)
            
            lst.clear()
            
            if not groups:
                self.notify("No groups found.", severity="warning")
                return

            for g in groups:
                safe_id = f"group_{g['id'].replace('-', '_')}"
                
                item = ListItem(Label(f"󰏓 {g['name']}"), id=safe_id)
                item.group_data = g 
                lst.append(item)
                
            self.notify("Grouplist updated")
        except Exception as e:
            self.notify(f"Could not load groups: {e}", severity="error")

    def update_entity_policies(self, entity_id, name, policies):
        payload = {"name": name, "policies": policies}
        return self.client.write(f"identity/entity/id/{entity_id}", **payload)

    def update_group_policies(self, group_id, name, policies):
        payload = {"name": name, "policies": policies}
        return self.client.write(f"identity/group/id/{group_id}", **payload)

    ### policies
    def list_policies(self) -> list:
        try:
            policies = self.client.sys.list_policies()
            return policies if isinstance(policies, list) else policies.get("policies", [])
        except Exception:
            res = self.client.read("sys/policy")
            return res.get("data", {}).get("keys", []) if res else []

    def get_policy(self, name: str) -> str:
        try:
            policy = self.client.sys.read_policy(name)
            if isinstance(policy, dict):
                return policy.get("rules", "")
            return policy
        except Exception as e:
            return f"# Could not fetch policy: {str(e)}"

    def save_policy(self, name: str, rules: str):
        return self.client.sys.create_or_update_policy(name=name, policy=rules)

    def delete_policy(self, name: str):
        return self.client.sys.delete_policy(name)

