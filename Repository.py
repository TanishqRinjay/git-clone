
from GitObject import GitObject, Blob, Tree, Commit
from pathlib import Path
from typing import Dict
import json

class Repository:
    def __init__(self, path="."): 
        self.path = Path(path).resolve()
        self.git_dir = self.path / ".gitpy"

        # .git/objects
        self.objects_dir = self.git_dir / "objects"

        # .git/refs
        self.ref_dir = self.git_dir / "refs"
        self.heads_dir = self.ref_dir / "heads"

        # HEAD file
        self.head_file = self.git_dir / "HEAD"

        # .git/index
        self.index_file = self.git_dir / "index"
        
    def init(self) -> bool:
        if self.git_dir.exists():
            return False

        # Creating directories
        self.git_dir.mkdir()
        self.objects_dir.mkdir()
        self.ref_dir.mkdir()
        self.heads_dir.mkdir()

        # Create initial head pointing to a branch
        self.head_file.write_text("ref: refs/heads/master\n")
        self.index_file.write_text(json.dumps({}, indent=2))

        print(f"Initialize empty git repository in {self.git_dir}")
        return True

    def store_object(self, obj: GitObject):
        obj_hash = obj.hash()
        obj_dir = self.objects_dir / obj_hash[:2]
        obj_file = obj_dir / obj_hash[2:]

        if not obj_file.exists():
            obj_dir.mkdir(exist_ok=True)
            obj_file.write_bytes(obj.serialize())
        return obj_hash

    def load_index(self) -> Dict[str, str]:
        if not self.index_file.exists():
            return {}

        try:
            return json.loads(self.index_file.read_text())
        except:
            return {}

    def save_index(self, index: Dict[str, str]):
        self.index_file.write_text(json.dumps(index, indent=2))

    def add_directory(self, path: str):
        full_path = self.path / path
        if not full_path.exists():
            raise FileNotFoundError(f"Path {path} not found")
        if not full_path.is_dir():
            raise ValueError(f"{path} is not a directory")
        index = self.load_index()
        added_count = 0
        for file_path in full_path.rglob("*"):
            if file_path.is_file():
                if ".gitpy" in file_path.parts or ".git" in file_path.parts:
                    continue
                content = file_path.read_bytes()
                blob = Blob(content)
                blob_hash = self.store_object(blob)
                rel_path = str(file_path.relative_to(self.path))
                index[rel_path] = blob_hash
                added_count += 1
        self.save_index(index)
        if added_count > 0:
            print(f"Added {added_count} files to the staging area")
        else:
            print("Directory path already up to date")

    def add_file(self, path: str):
        full_path = self.path / path
        if not full_path.exists():
            raise FileNotFoundError(f"Path {path} not found")
        content = full_path.read_bytes()
        blob = Blob(content)
        blob_hash = self.store_object(blob)
        index = self.load_index()
        index[path] = blob_hash
        self.save_index(index)
        print(f"Added {path} to the staging area")

    def add_path(self, path: str):
        full_path = self.path / path
        if not full_path.exists():
            raise FileNotFoundError(f"Path {path} does not exist")
        if full_path.is_file():
            self.add_file(path)
        elif full_path.is_dir():
            self.add_directory(path)
        else:
            raise ValueError(f"Path {path} is not a file or directory")

    def load_object(self, obj_hash: str) -> GitObject:
        obj_dir = self.objects_dir / obj_hash[:2]
        obj_file = obj_dir / obj_hash[2:]
        if not obj_file.exists():
            raise FileNotFoundError(f"Object {obj_hash} not found")
        
        return GitObject.deserialize(obj_file.read_bytes())
        
    def create_tree_from_index(self):
        index = self.load_index()
        if not index:
            tree = Tree()
            return self.store_object(tree)

        dirs = {}
        files = {}
        
        for file_path, blob_hash in index.items():
            parts = file_path.split("/")
            if len(parts) == 1:
                files[parts[0]] = blob_hash
            else:
                dir_name = parts[0]
                if dir_name not in dirs:
                    dirs[dir_name] = {}
                current = dirs[dir_name]
                for part in parts[1:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

                current[parts[-1]] = blob_hash

        def create_tree_recursive(entries_dict: Dict):
            tree = Tree()

            # Here i just named the value in key-value pair as blob_hash, but it can be nested dict with key-value pair
            for name, blob_hash in entries_dict.items():
                if isinstance(blob_hash, str):
                    tree.add_entry("100644", name, blob_hash)
                if isinstance(blob_hash, dict):
                    subtree_hash = create_tree_recursive(blob_hash)
                    tree.add_entry("40000", name, subtree_hash)

            return self.store_object(tree)

        root_entries = dict(files)
        for dir_name, dir_content in dirs.items():
            root_entries[dir_name] = dir_content

        return create_tree_recursive(root_entries)

    def get_current_branch(self) -> str:
        if not self.head_file.exists():
            return "master"
        head_content = self.head_file.read_text().strip()
        if head_content.startswith("ref: refs/heads/"):
            return head_content[16:]
        
        return "HEAD"

    def get_branch_commit(self, current_branch: str):
        branch_file = self.heads_dir / current_branch
        if not branch_file.exists():
            return None
        return branch_file.read_text().strip()

    def set_branch_commit(self, current_branch: str, commit_hash: str):
        branch_file = self.heads_dir / current_branch
        branch_file.write_text(commit_hash + "\n")

    def commit(self, message: str, author: str = "GitPy user <user@gitpy.com>"):
        tree_hash = self.create_tree_from_index()

        current_branch = self.get_current_branch()
        parent_commit = self.get_branch_commit(current_branch)
        index = self.load_index()

        if not index:
            print("Nothing to commit, working tree clean")
            return None

        if parent_commit:
            parent_git_commit_obj = self.load_object(parent_commit)
            parent_commit_data = Commit.from_content(parent_git_commit_obj.content)
            if tree_hash == parent_commit_data.tree_hash:
                print("Nothing to commit, working tree clean")
                return None

        commit = Commit(
            tree_hash=tree_hash,
            parent_hashes=[parent_commit] if parent_commit else [],
            author=author,
            commiter=author,
            message=message,
        )
        commit_hash = self.store_object(commit)
        self.set_branch_commit(current_branch, commit_hash)
        self.save_index({})
        print(f"Created commit {commit_hash} on branch {current_branch}")
        return commit_hash

    def get_files_from_tree_recursive(self, tree_hash: str, prefix: str = ""):
        files = set()
        try:
            tree_obj = self.load_object(tree_hash)
            tree = Tree.from_content(tree_obj.content)
            # List <tuple<str, str, str>>
            # (mode, path, hash)
            for mode, name, obj_hash in tree.entries:
                full_name = f"{prefix}{name}"
                if mode.startswith("100"):
                    files.add(full_name)
                elif mode.startswith("400"):
                    subtree_files = self.get_files_from_tree_recursive(obj_hash, f"{full_name}/")
                    files.update(subtree_files)
            
        except Exception as e: 
            print(f"Warning: could not read tree {tree_hash}: {e}")
        return files

    def checkout(self, branch: str, create_branch: bool = False):
        if self.load_index():
            print("Please commit your changes before checking out a different branch")
            return
        previous_branch = self.get_current_branch()
        files_to_clear = set()
        try:
            previous_commit_hash = self.get_branch_commit(previous_branch) 
            if previous_commit_hash:
                prev_commit_object = self.load_object(previous_commit_hash)
                prev_commit = Commit.from_content(prev_commit_object.content)
                if prev_commit.tree_hash:
                    files_to_clear = self.get_files_from_tree_recursive(prev_commit.tree_hash)

        except Exception:
            files_to_clear = set()

        branch_file = self.heads_dir / branch
        if not branch_file.exists():
            if create_branch:
                if previous_commit_hash:
                    self.set_branch_commit(branch, previous_commit_hash)
                    print(f"Created new branch '{branch}'")
                else:
                    print("No commits yet, cannot create a new branch")
            else:
                print(f"Branch '{branch}' does not exist")
                print(f"Use 'python main.py checkout -b {branch} to create and switch to new branch'")
                return
        self.head_file.write_text(f"ref: refs/heads/{branch}\n")

        self.restore_working_directory(branch, files_to_clear)
        print(f"Switched to branch '{branch}'")

    def restore_tree(self, tree_hash: str, path: Path):
        try:
            tree_obj = self.load_object(tree_hash)
            tree = Tree.from_content(tree_obj.content)
            # List <tuple<str, str, str>>
            # (mode, path, hash)
            for mode, name, obj_hash in tree.entries:
                file_path = path / name
                if mode.startswith("100"):
                    blob_obj = self.load_object(obj_hash)
                    blob = Blob(blob_obj.content)
                    file_path.write_bytes(blob.content)
                elif mode.startswith("400"):
                    file_path.mkdir(exist_ok=True)
                    self.restore_tree(obj_hash, file_path)
            
        except Exception as e: 
            print(f"Warning: could not read tree {tree_hash}: {e}")
        return

    def restore_working_directory(self, branch: str, files_to_clear: set[str]):
        target_commit_hash = self.get_branch_commit(branch)
        if not target_commit_hash:
            return

        # remove files tracked by previous branch
        for rel_path in sorted(files_to_clear):
            file_path = self.path / rel_path
            try:
                if file_path.is_file():
                    file_path.unlink()
                elif file_path.is_dir():
                    if not any(file_path.iterdir()):
                        file_path.rmdir()
            except Exception as e:
                print(f"Warning: could not remove file {file_path}: {e}")
                pass
        target_commit_obj = self.load_object(target_commit_hash)
        target_commit = Commit.from_content(target_commit_obj.content)
        if target_commit.tree_hash:
            self.restore_tree(target_commit.tree_hash, self.path)
        self.save_index({})

    def branch(self, branch_name: str, delete: bool = False):
        if delete and branch_name:
            branch_file = self.heads_dir / branch_name
            if branch_file.exists():
                branch_file.unlink()
                print(f"Deleted branch '{branch_name}'")
            else:
                print(f"Branch {branch_name} does not exists")
            return
        
        current_branch = self.get_current_branch()
        if branch_name:
            current_commit = self.get_branch_commit(current_branch)
            if current_commit:
                self.set_branch_commit(branch_name, current_commit)
                print(f"Created branch {branch_name}")
            else:
                print(f"No commits yet, cannot create a new branch")
        else:
            branches = []
            for branch_file in self.heads_dir.iterdir():
                if branch_file.is_file() and not branch_file.name.startswith("."):
                    branches.append(branch_file.name)
            for branch in sorted(branches):
                if branch != current_branch:
                    print(f"  {branch}")
                else:
                    print(f"* {branch}")
            
    def log(self, max_count: int):
        current_branch = self.get_current_branch()
        commit_hash = self.get_branch_commit(current_branch)
        if not commit_hash:
            return
        count = 0
        while commit_hash and count < max_count:
            commit_obj = self.load_object(commit_hash)
            commit = Commit.from_content(commit_obj.content)
            print(f"commit {commit_hash}")
            print(f"Author: {commit.author}")
            print(f"Date: {time.ctime(commit.timestamp)}")
            print(f"\n    {commit.message}\n")
            commit_hash = commit.parent_hashes[0] if commit.parent_hashes else None
            count += 1

    def build_index_from_tree(self, tree_hash: str, prefix: str = ""):
        index = {}
        try:
            tree_obj = self.load_object(tree_hash)
            tree = Tree.from_content(tree_obj.content)
            # List <tuple<str, str, str>>
            # (mode, path, hash)
            for mode, name, obj_hash in tree.entries:
                full_name = f"{prefix}{name}"
                if mode.startswith("100"):
                    index[full_name] = obj_hash
                elif mode.startswith("400"):
                    sub_index = self.build_index_from_tree(obj_hash, f"{full_name}/")
                    index.update(sub_index)
            
        except Exception as e: 
            print(f"Warning: could not read tree {tree_hash}: {e}")
        return index

    def get_all_files(self) -> list[Path]:
        files = []
        for item in self.path.rglob("*"):
            if ".gitpy" in item.parts or ".git" in item.parts:
                continue
            if item.is_file():
                files.append(item)
        return files

    def status(self):
        current_branch = self.get_current_branch()
        print(f"On branch {current_branch}")
        index = self.load_index()
        current_commit_hash = self.get_branch_commit(current_branch)

        last_index_files = {}
        if current_commit_hash:
            try:
                commit_obj = self.load_object(current_commit_hash)
                commit = Commit.from_content(commit_obj.content)
                if commit.tree_hash:
                    last_index_files = self.build_index_from_tree(commit.tree_hash)
            except:
                last_index_files = {}

        working_files = {}
        for item in self.get_all_files():
            rel_path = str(item.relative_to(self.path))
            try:
                content = item.read_bytes()
                blob = Blob(content)
                working_files[rel_path] = blob.hash()
            except:
                continue

        unstaged_files = []
        staged_files = []
        untracked_files = []
        deleted_files = []

        # Storing what files are in staging area
        for file_path in set(index.keys()) | set(last_index_files.keys()):
            index_hash = index.get(file_path)
            last_index_hash = last_index_files.get(file_path)
            if index_hash and not last_index_hash:
                staged_files.append(("new file", file_path))
            elif index_hash and last_index_hash and index_hash != last_index_hash:
                staged_files.append(("modified file", file_path))

        # Printing files are in staging area
        if staged_files:
            print("\n Changes to be committed:")
            for file_type, file_path in sorted(staged_files):
                print(f"  {file_type}: {file_path}")

        # Storing what files are modified but not staged
        for file_path in working_files:
            if file_path in index:
                if working_files[file_path] != index[file_path]:
                    unstaged_files.append(("modified file", file_path))

        # Storing what files are deleted
        for file_path in index:
            if file_path not in working_files:
                unstaged_files.append(("deleted file", file_path))

        # Printing files are modified but not staged
        if unstaged_files:
            print("\n Changes not staged for commit:")
            for file_type, file_path in sorted(unstaged_files):
                print(f"  {file_type}: {file_path}")

        # Storing what files are untracked
        for file_path in working_files:
            if file_path not in index and file_path not in last_index_files:
                untracked_files.append(file_path)

        # Printing files are untracked
        if untracked_files:
            print("\n Untracked files:")
            for file_path in sorted(untracked_files):
                print(f"  {file_path}")
