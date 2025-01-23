# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.io import MessageTextInput, Output, FileInput, DropdownInput
from langflow.schema import Data
import urllib3
from urllib3.util import Retry
from urllib3.filepost import encode_multipart_formdata
import json
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")



class UploadFileComponent(Component):
    display_name = "Upload File Component"
    description = "Use this component to upload file to blob."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "notebook-pen"
    name = "UploadFileComponent"
    
    file_extensions = [
        "doc", "docx", "pdf", "txt", "rtf", "odt", "html", "htm", "csv", 
        "xlsx", "xls", "ppt", "pptx", "jpg", "jpeg", "png", "gif", "bmp", 
        "svg", "tiff", "tif", "mp3", "wav", "aac", "flac", "ogg", "m4a", 
        "mp4", "avi", "mkv", "mov", "wmv", "flv", "zip", "rar", "tar", 
        "gz", "7z", "exe", "msi", "bat", "sh", "jar", "dll", "sys", 
        "ini", "log", "db", "sql", "mdb", "sqlite", "py", "java", "c", 
        "cpp", "js", "html", "css", "json", "xml", "yaml", "yml", "conf", 
        "env", "iso", "md", "ics", "epub", "swf", "obj", "fbx", "stl", 
        "dae", "3ds", "shp", "kml", "gpx", "geojson", "dcm", "nii", "mha", 
        "ttf", "otf", "woff", "woff2", "dwg", "dxf", "step", "stp", "bak", 
        "vdi", "vmdk", "img", "eml", "msg", "pst", "gitignore", 
        "gitattributes", "unity", "pak", "vpk", "pem", "key", "crt", "mat", 
        "h5", "csv.gz", "sav", "rdata", "arff", "php", "asp", "jsp", "ts", 
        "jsx", "scss", "jsonc", "toml", "properties", "plist", "sol", 
        "wallet", "eth", "psd", "ai", "indd", "sketch", "rb", "go", "pl", 
        "rs", "lua", "blend", "unitypackage", "efi", "tmp", "cache", "rst", 
        "adoc", "man", "dbf", "xlt", "pot", "flp", "als", "logicx", "cpr", 
        "accdb", "parquet", "feather", "orc", "sas", "stata", "gcode", 
        "3mf", "sln", "csproj", "xcodeproj", "gradle", "pfx", "p12", "asc", 
        "opj", "spv", "sim", "tex", "bib", "m4v", "webm", "srt", "mxf", 
        "cdr", "emf", "wmf", "msgpack", "bson", "bin", "hex", "xz", "lz", 
        "tar.gz", "zst", "pb", "onnx", "pkl", "bashrc", "zshrc", "profile", 
        "veg", "aep", "prproj", "qbw", "qbb", "skp", "rom", "cap", "vhd", 
        "vhdx", "dmg", "m", "nb", "wolfram", "wsdl", "wadl", "vrml", "x3d", 
        "ova", "ovf", "dockerfile", "inp", "com", "pdb", "mobi", "azw", 
        "qif", "ofx", "xlsm", "swift", "kt", "nim", "editorconfig", 
        "prettierrc", "eslint", "tf",
    ]

    inputs = [
        FileInput(name="file", display_name="File", file_types=file_extensions, info="The file to upload", required=True),
        MessageTextInput(name="to_dir", display_name="To dir", info="Directory name in which the file is going to be uploaded", required=True),
        MessageTextInput(name="conn_str", display_name="Connection string", info="Connection string", required=True),
        MessageTextInput(name="container_name", display_name="Container name", info="Container name", required=True),
        DropdownInput(name="overwrite", display_name="Overwrite", options=["true", "false"], value="false", info="Overwrite the file if exist", required=True),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Data:
        with open(self.file, 'rb') as file:
            file_content = file.read()
        
        filename = os.path.basename(self.file)

        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        
        Overwrite_file = self.overwrite
        url = f"{SDCP_ROOT_URL}blob/upload_file/?overwrite={Overwrite_file}"

        headers = {'accept': 'application/json', 'Content-Type': 'multipart/form-data'}
        
        fields = {
            "file": ( filename, file_content, 'application/octet-stream'),
            "to_dir":self.to_dir, 
            "conn_str":self.conn_str, 
            "container_name":self.container_name,
        }
        

        encoded_data, content_type = encode_multipart_formdata(fields)
        headers['Content-Type'] = content_type
 
        response = http.request('POST', url, body=encoded_data, headers=headers)
        
        result = json.loads(response.data.decode('utf-8'))
        return Data(value=result.get("message", ""))
