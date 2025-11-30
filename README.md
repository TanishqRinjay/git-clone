# 🐍 GitPy: A Pythonic Dive into Git Internals

![GitHub language count](https://img.shields.io/github/languages/count/TanishqRinjay/git-clone?style=flat-square)

A minimalist, educational implementation of the core Git version control system, built from scratch in pure Python. The goal of this project is to **demystify Git's inner workings** by replicating its essential data structures and command line interface.

---

## ✨ Features

GitPy supports the fundamental, low-level commands necessary to manage repository history:

| Command | Description | Internal Functionality |
| :--- | :--- | :--- |
| `init` | Initializes the repository, creating the custom `.gitpy` folder structure. | Sets up `HEAD`, `refs`, and the empty `index`. |
| `add` | Stages files or directories for the next commit. | Creates **Blob** objects and updates the **Index**. |
| `commit` | Records changes permanently to the history. | Creates **Tree** and **Commit** objects, updating branch **Refs**. |
| `checkout` | Switches branches or restores the working directory to a specific state. | Recursively reads **Tree** objects to restore files. |
| `branch` | Lists, creates, or deletes local branches. | Manipulates pointers in the `.gitpy/refs/heads` directory. |
| `log` | Displays the commit history of the current branch. | Follows the **parent_hashes** back through the **DAG**. |
| `status` | Shows the state of the staging area and working directory. | Compares the working area, Index, and last Commit's Tree. |

---

## 🧠 Why GitPy? (A Technical Deep Dive)

This project is a deep dive into the system design principles that underpin distributed version control. The implementation directly showcases the following concepts:

* **Content-Addressable Storage (CAS):** Implements the object database where file content is hashed using SHA-1 (`hashlib`) and the hash *is* the identifier (the key).
* **The Merkle DAG:** The Commit objects are chained via `parent_hashes`, forming a **Directed Acyclic Graph (DAG)** that ensures the history is immutable and cryptographically verifiable.
* **Object Serialization:** Files are compressed using the standard Python `zlib` library and stored with a custom header, replicating the exact storage format of real Git objects.
* **Recursive Tree Building:** Demonstrates the algorithm required to convert a flat "staging index" into a nested hierarchy of Tree objects for permanent storage.

---

## 🛠️ Setup and Usage

### Prerequisites

* Python 3.6+

### Installation

Clone the repository:

```bash
git clone https://github.com/TanishqRinjay/git-clone.git
cd gitpy