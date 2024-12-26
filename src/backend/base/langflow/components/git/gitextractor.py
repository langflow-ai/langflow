
from langflow.custom import Component
from langflow.schema import Data
from langflow.schema.message import Message
from langflow.io import MessageTextInput, Output
import git
import os
import tempfile
import shutil

class GitExtractorComponent(Component):
    display_name = "GitExtractor"
    description = "Analyzes a Git repository and returns file contents and complete repository information"
    icon = "GitLoader"

    inputs = [
        MessageTextInput(
            name="repository_url",
            display_name="Repository URL",
            info="URL of the Git repository (e.g., https://github.com/username/repo)",
            value="",
        ),
    ]

    outputs = [
        Output(display_name="Text-Based File Contents", name="text_based_file_contents", method="get_text_based_file_contents"),
        Output(display_name="Directory Structure", name="directory_structure", method="get_directory_structure"),
        Output(display_name="Repository Info", name="repository_info", method="get_repository_info"),
        Output(display_name="Statistics", name="statistics", method="get_statistics"),
        Output(display_name="Files Content", name="files_content", method="get_files_content"),
        
    ]

    def get_repository_info(self) -> list[Data]:
        try:
            temp_dir = tempfile.mkdtemp()
            try:
                repo = git.Repo.clone_from(self.repository_url, temp_dir)
                repo_info = {
                    "name": self.repository_url.split('/')[-1],
                    "url": self.repository_url,
                    "default_branch": repo.active_branch.name,
                    "remote_urls": [remote.url for remote in repo.remotes],
                    "last_commit": {
                        "hash": repo.head.commit.hexsha,
                        "author": str(repo.head.commit.author),
                        "message": repo.head.commit.message.strip(),
                        "date": str(repo.head.commit.committed_datetime)
                    },
                    "branches": [str(branch) for branch in repo.branches]
                }
                result = [Data(data=repo_info)]
                self.status = result
                return result
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            error_result = [Data(data={"error": f"Error getting repository info: {str(e)}"})]
            self.status = error_result
            return error_result

    def get_statistics(self) -> list[Data]:
        try:
            temp_dir = tempfile.mkdtemp()
            try:
                git.Repo.clone_from(self.repository_url, temp_dir)
                total_files = 0
                total_size = 0
                total_lines = 0
                binary_files = 0
                directories = 0
                for root, dirs, files in os.walk(temp_dir):
                    total_files += len(files)
                    directories += len(dirs)
                    for file in files:
                        file_path = os.path.join(root, file)
                        total_size += os.path.getsize(file_path)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                total_lines += sum(1 for _ in f)
                        except UnicodeDecodeError:
                            binary_files += 1
                statistics = {
                    "total_files": total_files,
                    "total_size_bytes": total_size,
                    "total_size_kb": round(total_size / 1024, 2),
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "total_lines": total_lines,
                    "binary_files": binary_files,
                    "directories": directories
                }
                result = [Data(data=statistics)]
                self.status = result
                return result
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            error_result = [Data(data={"error": f"Error calculating statistics: {str(e)}"})]
            self.status = error_result
            return error_result

    def get_directory_structure(self) -> Message:
        try:
            temp_dir = tempfile.mkdtemp()
            try:
                git.Repo.clone_from(self.repository_url, temp_dir)
                tree = ["Directory structure:"]
                for root, dirs, files in os.walk(temp_dir):
                    level = root.replace(temp_dir, '').count(os.sep)
                    indent = '    ' * level
                    if level == 0:
                        tree.append(f"└── {os.path.basename(root)}")
                    else:
                        tree.append(f"{indent}├── {os.path.basename(root)}")
                    subindent = '    ' * (level + 1)
                    for f in files:
                        tree.append(f"{subindent}├── {f}")
                directory_structure = '\n'.join(tree)
                self.status = directory_structure
                return Message(text=directory_structure)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            error_message = f"Error getting directory structure: {str(e)}"
            self.status = error_message
            return Message(text=error_message)

    def get_files_content(self) -> list[Data]:
        try:
            temp_dir = tempfile.mkdtemp()
            try:
                git.Repo.clone_from(self.repository_url, temp_dir)
                content_list = []
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, temp_dir)
                        file_size = os.path.getsize(file_path)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_content = f.read()
                        except UnicodeDecodeError:
                            file_content = "[BINARY FILE]"
                        content_list.append(Data(data={
                            "path": relative_path,
                            "size": file_size,
                            "content": file_content
                        }))
                self.status = content_list
                return content_list
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            error_result = [Data(data={"error": f"Error getting files content: {str(e)}"})]
            self.status = error_result
            return error_result

    def get_text_based_file_contents(self) -> Message:
        try:
            temp_dir = tempfile.mkdtemp()
            try:
                git.Repo.clone_from(self.repository_url, temp_dir)
                content_list = ["(Files content cropped to 300k characters, download full ingest to see more)"]
                total_chars = 0
                char_limit = 300000

                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, temp_dir)
                        content_list.append("=" * 50)
                        content_list.append(f"File: /{relative_path}")
                        content_list.append("=" * 50)
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_content = f.read()
                                if total_chars + len(file_content) > char_limit:
                                    remaining_chars = char_limit - total_chars
                                    file_content = file_content[:remaining_chars] + "\n... (content truncated)"
                                content_list.append(file_content)
                                total_chars += len(file_content)
                        except UnicodeDecodeError:
                            content_list.append("[BINARY FILE]")
                        
                        content_list.append("")  # Add an empty line between files
                        
                        if total_chars >= char_limit:
                            break
                    
                    if total_chars >= char_limit:
                        break

                text_content = "\n".join(content_list)
                self.status = text_content
                return Message(text=text_content)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            error_message = f"Error getting text-based file contents: {str(e)}"
            self.status = error_message
            return Message(text=error_message)
