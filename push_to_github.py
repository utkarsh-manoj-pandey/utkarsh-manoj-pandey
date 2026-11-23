#!/usr/bin/env python3
"""
push_to_github.py - Fast & Reliable Interactive Git Automation Script

Automates staging, committing, and pushing updates to GitHub.
Interactively asks whether to push directly or test beforehand with a dry-run,
and prompts for a custom commit message.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ANSI terminal colors
class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"


def log_info(msg: str):
    print(f"{Colors.CYAN}[*]{Colors.RESET} {msg}")


def log_success(msg: str):
    print(f"{Colors.GREEN}[✓]{Colors.RESET} {msg}")


def log_warn(msg: str):
    print(f"{Colors.YELLOW}[!]{Colors.RESET} {msg}")


def log_error(msg: str):
    print(f"{Colors.RED}[✗]{Colors.RESET} {msg}")


def run_cmd(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command safely using subprocess."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=check,
        )
        return result
    except subprocess.CalledProcessError as err:
        log_error(f"Command failed: {' '.join(cmd)}")
        if err.stdout:
            print(f"{Colors.DIM}{err.stdout.strip()}{Colors.RESET}")
        if err.stderr:
            print(f"{Colors.RED}{err.stderr.strip()}{Colors.RESET}")
        raise


def get_git_root() -> Path:
    """Locate the top-level directory of the current git repository."""
    res = run_cmd(["git", "rev-parse", "--show-toplevel"], check=False)
    if res.returncode != 0:
        log_error("Current directory is not inside a Git repository.")
        sys.exit(1)
    return Path(res.stdout.strip())


def get_current_branch(repo_root: Path) -> str:
    """Get name of current checked out branch."""
    res = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, check=False)
    if res.returncode != 0:
        return "main"
    branch = res.stdout.strip()
    return branch if branch != "HEAD" else "main"


def check_working_tree(repo_root: Path) -> tuple[bool, str]:
    """Check if there are uncommitted changes (unstaged, staged, untracked)."""
    res = run_cmd(["git", "status", "--porcelain"], cwd=repo_root, check=False)
    output = res.stdout.strip()
    has_changes = len(output) > 0
    return has_changes, output


def check_unpushed_commits(repo_root: Path, remote: str, branch: str) -> bool:
    """Check if local branch has commits ahead of remote."""
    res = run_cmd(["git", "log", f"{remote}/{branch}..HEAD", "--oneline"], cwd=repo_root, check=False)
    if res.returncode == 0 and res.stdout.strip():
        return True
    return False


def prompt_action_mode() -> str:
    """Ask user whether to push directly, run a dry-run test, or exit."""
    print(f"{Colors.BOLD}{Colors.MAGENTA}How would you like to proceed?{Colors.RESET}")
    print(f"  {Colors.BOLD}[1]{Colors.RESET} Push updates directly to GitHub")
    print(f"  {Colors.BOLD}[2]{Colors.RESET} Test beforehand using Dry Run mode (simulate without pushing)")
    print(f"  {Colors.BOLD}[3]{Colors.RESET} Cancel / Exit\n")

    while True:
        try:
            choice = input(f"{Colors.CYAN}Select option [1/2/3] (default: 1): {Colors.RESET}").strip()
            if not choice or choice in ("1", "push", "p"):
                return "push"
            elif choice in ("2", "dry-run", "dryrun", "d", "test", "t"):
                return "dry_run"
            elif choice in ("3", "exit", "quit", "cancel", "c", "q"):
                return "exit"
            else:
                log_warn("Invalid option. Please enter 1, 2, or 3.")
        except (KeyboardInterrupt, EOFError):
            print()
            log_warn("Aborted by user.")
            sys.exit(0)


def prompt_commit_message(default_prefix: str = "chore: update repository") -> str:
    """Ask user what commit message they want to pass."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    default_msg = f"{default_prefix} [{timestamp}]"

    if sys.stdin.isatty():
        try:
            print(f"\n{Colors.BOLD}Commit Message Configuration:{Colors.RESET}")
            msg = input(f"{Colors.CYAN}Enter your commit message (Press Enter for default '{default_msg}'): {Colors.RESET}").strip()
            return msg if msg else default_msg
        except (KeyboardInterrupt, EOFError):
            print()
            log_warn("Aborted by user.")
            sys.exit(0)
    return default_msg


def execute_dry_run(repo_root: Path, remote: str, branch: str, commit_msg: str | None, has_changes: bool):
    """Simulate the staging, commit, and push steps."""
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.YELLOW}  DRY RUN SIMULATION MODE (NO ACTUAL CHANGES WILL BE PUSHED)  {Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")

    if has_changes:
        log_info(f"Target commit message: \"{Colors.BOLD}{commit_msg}{Colors.RESET}\"")
        log_warn("[DRY RUN] Would execute: git add -A")
        log_warn(f"[DRY RUN] Would execute: git commit -m \"{commit_msg}\"")
    else:
        log_info("Working tree clean; no commit needed.")

    push_cmd = f"git push -u {remote} {branch}"
    log_warn(f"[DRY RUN] Would execute: {push_cmd}")
    print(f"\n{Colors.GREEN}[✓] Dry run preview completed successfully.{Colors.RESET}")


def execute_actual_push(repo_root: Path, remote: str, branch: str, commit_msg: str | None, has_changes: bool):
    """Perform real staging, committing, and pushing to remote."""
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}  EXECUTING ACTUAL DEPLOYMENT TO GITHUB  {Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}\n")

    if has_changes:
        log_info(f"Commit Message: \"{Colors.BOLD}{commit_msg}{Colors.RESET}\"")

        # Stage
        log_info("Staging all changes (git add -A)...")
        run_cmd(["git", "add", "-A"], cwd=repo_root)
        log_success("All changes staged.")

        # Commit
        log_info("Committing changes...")
        run_cmd(["git", "commit", "-m", commit_msg], cwd=repo_root)
        log_success("Changes committed successfully.")

    # Push
    push_cmd = ["git", "push", "-u", remote, branch]
    log_info(f"Pushing updates to {remote}/{branch}...")
    try:
        result = subprocess.run(push_cmd, cwd=repo_root)
        if result.returncode == 0:
            print()
            log_success(f"Successfully pushed all updates to GitHub ({remote}/{branch})!")
            print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
            print(f"{Colors.GREEN}{Colors.BOLD}  ALL UPDATES DEPLOYED TO GITHUB SUCCESSFULLY  {Colors.RESET}")
            print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}\n")
        else:
            print()
            log_error(f"Push exited with status code {result.returncode}")
            sys.exit(result.returncode)
    except Exception as e:
        log_error(f"Error executing git push: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Automate staging, committing, and pushing updates to GitHub with interactive mode selection.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 push_to_github.py
  python3 push_to_github.py -m "chore: remove portfolio and update repository"
  python3 push_to_github.py --dry-run
""",
    )
    parser.add_argument(
        "-m", "--message",
        dest="commit_message",
        help="Commit message. If omitted, the script asks you interactively.",
    )
    parser.add_argument(
        "positional_message",
        nargs="?",
        default=None,
        help="Optional shorthand commit message.",
    )
    parser.add_argument(
        "-b", "--branch",
        default=None,
        help="Target branch (defaults to current branch).",
    )
    parser.add_argument(
        "-r", "--remote",
        default="origin",
        help="Target Git remote (default: origin).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Directly run in dry-run mode without prompting.",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Non-interactive mode: push directly without prompting for mode.",
    )

    args = parser.parse_args()

    # Step 1: Detect repository root & branch
    repo_root = get_git_root()
    branch = args.branch or get_current_branch(repo_root)
    remote = args.remote

    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  GITHUB PUSH AUTOMATION SYSTEM  {Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    log_info(f"Repository Root : {repo_root}")
    log_info(f"Target Branch   : {Colors.BOLD}{branch}{Colors.RESET}")
    log_info(f"Target Remote   : {Colors.BOLD}{remote}{Colors.RESET}\n")

    # Step 2: Check status of working tree
    has_changes, porcelain_output = check_working_tree(repo_root)
    has_unpushed = check_unpushed_commits(repo_root, remote, branch)

    if not has_changes and not has_unpushed:
        log_success("Working directory is clean and up to date with remote. Nothing to commit or push!")
        print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}\n")
        return

    # Display pending changes
    if has_changes:
        log_info("Detected changes in working tree:")
        for line in porcelain_output.splitlines():
            status_code = line[:2]
            filepath = line[3:]
            color = Colors.GREEN if "A" in status_code or "M" in status_code else Colors.YELLOW
            if "D" in status_code:
                color = Colors.RED
            print(f"  {color}{status_code}{Colors.RESET} {filepath}")
        print()
    elif has_unpushed:
        log_info("Working tree is clean, but local unpushed commits exist.\n")

    # Step 3: Determine execution mode (Direct Push vs Dry Run)
    if args.dry_run:
        mode = "dry_run"
    elif args.yes or not sys.stdin.isatty():
        mode = "push"
    else:
        mode = prompt_action_mode()

    if mode == "exit":
        log_warn("Operation cancelled by user.")
        print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}\n")
        return

    # Step 4: Determine commit message if there are changes to commit
    commit_msg = args.commit_message or args.positional_message
    if has_changes and not commit_msg:
        if sys.stdin.isatty():
            commit_msg = prompt_commit_message()
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_msg = f"chore: update repository [{timestamp}]"

    # Step 5: Execute chosen mode
    if mode == "dry_run":
        execute_dry_run(repo_root, remote, branch, commit_msg, has_changes)

        # After dry run, offer to push right away if in an interactive terminal
        if sys.stdin.isatty() and not args.dry_run:
            try:
                proceed = input(f"\n{Colors.CYAN}Would you like to proceed with the actual push now? [y/N]: {Colors.RESET}").strip().lower()
                if proceed in ("y", "yes"):
                    execute_actual_push(repo_root, remote, branch, commit_msg, has_changes)
                else:
                    log_info("Push cancelled. No remote changes were made.")
                    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}\n")
            except (KeyboardInterrupt, EOFError):
                print()
                log_warn("Aborted by user.")
                sys.exit(0)
    else:
        execute_actual_push(repo_root, remote, branch, commit_msg, has_changes)


if __name__ == "__main__":
    main()
