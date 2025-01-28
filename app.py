from flask import Flask, render_template, request, jsonify
import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
import gdown
from PyPDF2 import PdfMerger

# Load environment variables
load_dotenv()

FOLDER_ID = os.getenv('FOLDER_ID')
SCOPES = ['https://www.googleapis.com/auth/drive']

app = Flask(__name__)

# Google Drive authentication
def authenticate_services():
    credentials = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
    return drive_service

# Create a local folder for downloads
def create_folder():
    folder_path = "downloads"
    os.makedirs(folder_path, exist_ok=True)
    os.chmod(folder_path, 0o777)
    return folder_path

# Download files from Google Drive
def download_files(links, output_path):
    file_counter = 1
    for link in links:
        if link.strip():
            if "drive.google.com" in link:
                file_id = link.split("/d/")[1].split("/")[0]
                download_url = f"https://drive.google.com/uc?id={file_id}"
                gdown.download(download_url, f"./{output_path}/{file_counter}.pdf", quiet=False)
                file_counter += 1
            else:
                raise ValueError("Invalid Google Drive link.")

# Merge downloaded PDF files
def merge_pdfs_in_folder(folder_path):
    merger = PdfMerger()
    for file in sorted(os.listdir(folder_path)):
        if file.endswith('.pdf'):
            pdf_path = os.path.join(folder_path, file)
            merger.append(pdf_path)
    merged_pdf_path = os.path.join(folder_path, 'merged_document.pdf')
    merger.write(merged_pdf_path)
    merger.close()
    return merged_pdf_path

# Upload the merged file to Google Drive
def upload_file_to_drive(drive_service, file_path, file_name, folder_id):
    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]
    media = MediaFileUpload(file_path, resumable=True)
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = uploaded_file.get('id')
    drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
    shareable_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
    return shareable_link

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Get the links from the form
        links = [
            request.form.get(f'link{i}') for i in range(1, 8)
        ]
        links = [link for link in links if link.strip()]  # Remove empty links
        
        # Process the links
        try:
            drive_service = authenticate_services()
            folder_path = create_folder()
            download_files(links, folder_path)
            merged_pdf_path = merge_pdfs_in_folder(folder_path)
            shareable_link = upload_file_to_drive(drive_service, merged_pdf_path, "combinedDoc.pdf", FOLDER_ID)
            return jsonify({'link': shareable_link})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=8001)