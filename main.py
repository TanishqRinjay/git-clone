from __future__ import annotations
import argparse
from Repository import Repository

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

    # checkout command
    checkout_parser = subparsers.add_parser("checkout", help="Move/create a new branch")
    checkout_parser.add_argument("-b", "--create-branch", action="store_true", help="Create a new branch")
    checkout_parser.add_argument("branch", help="Branch to checkout")

    # list branches command
    branch_parser = subparsers.add_parser("branch", help="List or manage the branches")
    branch_parser.add_argument("name", nargs="?")
    branch_parser.add_argument("-d", "--delete-branch", action="store_true", help="Delete a branch")

    # log command
    log_parser = subparsers.add_parser("log", help="Show commit history")
    log_parser.add_argument("-n", "--max-count", type=int, default=10, help="Maximum number of commits to show")

    # status command
    status_parser = subparsers.add_parser("status", help="Shows repository status")


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
        elif args.command == "checkout":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            repo.checkout(args.branch, args.create_branch)
        elif args.command == "branch":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            repo.branch(args.name, args.delete_branch)
        elif args.command == "log":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            repo.log(args.max_count)
        elif args.command == "status":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            repo.status()

    except Exception as e:
        print(f"Error in parsing args: {e}")
        sys.exit(1)

main()