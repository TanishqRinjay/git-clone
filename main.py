from __future__ import annotations
import argparse
import hashlib
import json
import time
import zlib
from pathlib import Path
from typing import Dict, List, Tuple


class GitObject:
    def __init__(self, obj_type: str, content: bytes) -> None:
        self.type = obj_type
        self.content = content

    def hash(self) -> str:
        header = f"{self.type} {len(self.content)}\0".encode()
        return hashlib.sha1(header + self.content).hexdigest()

    def serialize(self) -> bytes:
        header = f"{self.type} {len(self.content)}\0".encode()
        return zlib.compress(header + self.content)

    @classmethod
    def deserialize(cls, data: bytes) -> GitObject:
        decompressed = zlib.decompress(data)
        null_idx = decompressed.find(b"\0")
        header = decompressed[:null_idx].decode()
        content = decompressed[null_idx + 1:]
        obj_type, _ = header.split(" ")
        return cls(obj_type, content)

class Blob(GitObject):
    def __init__(self, content: bytes):
        super().__init__("blob", content)
        
    def get_content(self) -> bytes:
        return self.content

class Tree(GitObject):
    def __init__(self, entries: List[Tuple[str, str, str]] = None):
        self.entries = entries or []
        content = self._serialize_entries()
        super().__init__("tree", content)

    def _serialize_entries(self) -> bytes:
        # <mode> <name>\0<hash>
        content = b""
        for mode, name, obj_hash in sorted(self.entries):
            content += f"{mode} {name}\0".encode()
            content += bytes.fromhex(obj_hash)
        return content
    
    def add_entry(self, mode: str, name: str, obj_hash: str):
        self.entries.append((mode, name, obj_hash))
        self.content = self._serialize_entries()

    @classmethod
    def from_content(selfcls, content: bytes) -> Tree:
        tree = cls()
        i = 0
        while i < len(content):
            null_idx = content.find(b"\0", 1)
            if null_idx == -1:
                break
            mode_name = content[i:null_idx].decode()
            mode, name = mode_name.split(" ", 1)
            obj_hash = content[null_idx + 1:  null_idx + 21].hex()
            tree.entries.append((mode, name, obj_hash))
            i = null_idx + 21
        return tree

class Commit(GitObject):
    def __init__(self, tree_hash: str, parent_hashes: List[str], author: str, commiter: str, message: str, timestamp: int = None):
        self.tree_hash = tree_hash
        self.parent_hashes = parent_hashes
        self.author = author
        self.commiter = commiter
        self.message = message
        self.timestamp = timestamp or int(time.time())
        content = self._serialize_commit()
        super().__init__("commit", content)

    def _serialize_commit(self) -> bytes:
        lines = [f"tree {self.tree_hash}"]
        for parent in self.parent_hashes:
            lines.append(f"parent {parent}")

        lines.append(f"author {self.author} {self.timestamp} +0000")
        lines.append(f"committer {self.commiter} {self.timestamp} +0000")
        lines.append("")
        lines.append(self.message)
        return "\n".join(lines).encode()

    @classmethod
    def from_content(cls, content: bytes) -> Commit:
        lines = content.decode().split("\n")
        tree_hash = None
        parent_hashes = []
        author = None
        commiter = None
        message_start = 0

        for i, line in enumerate(lines):
            if line.startswith("tree "):
                tree_hash = line.split(" ")[1]
            elif line.startswith("parent "):
                parent_hashes.append(line.split(" ")[1])
            elif line.startswith("author "):
                author_parts = line[7:].rsplit(" ", 2)
                author = author_parts[0]
                timestamp = int(author_parts[1])
            elif line.startswith("committer "):
                commiter = line.split(" ")[1]
            elif line == "":
                message_start = i + 1
                break

        message = "\n".join(lines[message_start:])
        return cls(tree_hash, parent_hashes, author, commiter, message, timestamp)


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
        self.head_file.write_text("refs: refs/heads/master\n")
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

            for name, blob_hash in entries_dict.items():
                if isinstance(blob_hash, str):
                    tree.add_entry("100644", name, blob_hash)
                if isinstance(blob_hash, dict):
                    subtree_hash = create_tree_recursive(blob_hash)
                    tree.add_entry("040000", name, subtree_hash)

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


def main():
    parser = argparse.ArgumentParser(    
        description="GitPy: A simple git clone using python"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands"
    )

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new git repository")

    # add command
    add_parser = subparsers.add_parser("add", help="Add files to the staging area")
    add_parser.add_argument("paths", nargs="+", help="Files and directories to add") 

    # commit command
    commit_parser = subparsers.add_parser("commit", help="Create a new commit")
    commit_parser.add_argument("-m", "--message", help="Commit message", required=True)
    commit_parser.add_argument("--author", help="Author name and email")


    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return
    repo = Repository()
    try:
        if args.command == "init":
            if not repo.init():
                print("Repository already exists")
                return
        elif args.command == "add":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            for path in args.paths:
                repo.add_path(path)
        elif args.command == "commit":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            author = args.author or "GitPy user <user@gitpy.com>"
            repo.commit(args.message, author)


    except Exception as e:
        print(f"Error in parsing args: {e}")
        sys.exit(1)

main()