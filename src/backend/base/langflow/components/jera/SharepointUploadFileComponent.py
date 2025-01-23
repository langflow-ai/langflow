from langflow.custom import Component
from langflow.io import BoolInput, FileInput, MessageTextInput, Output
from langflow.schema import Data
import json
 
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")
 
 
class SharepointUploadFileComponent(Component):
    display_name = "Sharepoint Upload File"
    description = "Use this component to Upload file from sharepoint."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "cloud-upload"
    name = "SharepointUploadFileComponent"

    '''
    source_file_path: Annotated[UploadFile, File(..., description="The file to upload"),],
    destination_file_path: Annotated[str, Form(..., description="The file path in SharePoint where the file will be uploaded")],
    sharepoint_site_url: Annotated[str, Form(..., description="The SharePoint site url")],
    access_token: Annotated[str, Form(..., description="user sharepoint access token")],
    drive_name: Annotated[str, Form(..., description="The name of the shared document drive. Defaults to 'ドキュメント' if not provided.")] = 'ドキュメント',
    is_overwrite: bool = Query(False, description="If true, it always upload file no matter if it already exists or not."),
    '''

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
        "prettierrc", "eslint", "tf"
    ]

 
    inputs = [
        FileInput(name="source_file_path", fileTypes=file_extensions, display_name="Source File path", required=True, info="The file to upload."),
        MessageTextInput(name="destination_file_path", display_name="Destination File path", required=True, info="The file path in SharePoint where the file will be uploaded."),
        MessageTextInput(name="sharepoint_site_url", display_name="The SharePoint site url", required=True, info="The SharePoint site url."),
        MessageTextInput(name="access_token", display_name="Access token", required=True, info="User's sharepoint access token."),
        MessageTextInput(name="drive_name", display_name="Drive name", placeholder='ドキュメント', required=True, info="The name of the shared document drive. Defaults to 'ドキュメント' if not provided."),
        BoolInput(name="is_overwrite", display_name="is_overwrite", required=True, info="If true, it always upload file no matter if it already exists or not."),
    ]
 
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
   
    def build_output_data(self) -> Data:
        with open(self.source_file_path, 'rb') as file:
            file_content = file.read()
            http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

            url = f"{SDCP_ROOT_URL}sharepoint/upload_file/"
            
            headers = {
                'accept': 'application/json',
                'Content-Type': 'application/json'  # Set the content type to JSON
            }
            if SDCP_TOKEN:
                headers['apikey'] = SDCP_TOKEN

            # Prepare the data as a JSON-encoded string
            fields = {
                # 'source_file_path': ('self.source_file_path', file_content),
                'source_file_path': (self.source_file_path, file_content, 'application/octet-stream'),
                'destination_file_path': self.destination_file_path,
                'sharepoint_site_url': self.sharepoint_site_url,
                'access_token': self.access_token,
                'drive_name': self.drive_name,
                'is_overwrite': self.is_overwrite
            }

            encoded_data, content_type = urllib3.encode_multipart_formdata(fields)
            headers['Content-Type'] = content_type

            # Make the PUT request with the JSON body
            response = http.request('PUT', url, body=encoded_data, headers=headers)

            response_data = json.loads(response.data.decode('utf-8'))

            # Extract the translated text
            response_message = response_data["message"]

            data_obj = Data(value=response_message)
            return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
