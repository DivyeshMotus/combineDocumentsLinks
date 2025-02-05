from flask import Flask, render_template, request, jsonify
import os
import re
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.discovery import build
from PyPDF2 import PdfMerger

# Load environment variables
load_dotenv()

FOLDER_ID = os.getenv('FOLDER_ID')
SCOPES = ['https://www.googleapis.com/auth/drive']

app = Flask(__name__)

# Google Drive Authentication
def authenticate_drive():
    credentials = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)

# Function to extract Google Drive file ID from link
def extract_file_id(drive_link):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', drive_link)
    if match:
        return match.group(1)
    else:
        return None

# Function to download PDF file from Google Drive
def download_pdf_from_drive(drive_service, file_id, output_folder, file_counter):
    try:
        request = drive_service.files().get_media(fileId=file_id)
        file_name = f"{output_folder}/{file_counter}.pdf"
        with open(file_name, 'wb') as pdf_file:
            downloader = MediaIoBaseDownload(pdf_file, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"Download Progress: {int(status.progress() * 100)}%")
        return file_name
    except Exception as e:
        return None

# Function to merge downloaded PDFs
def merge_pdfs(folder_path):
    merger = PdfMerger()
    for file in sorted(os.listdir(folder_path)):
        if file.endswith('.pdf'):
            merger.append(os.path.join(folder_path, file))
    merged_pdf_path = os.path.join(folder_path, 'merged_document.pdf')
    merger.write(merged_pdf_path)
    merger.close()
    return merged_pdf_path

# Function to upload merged PDF to Google Drive
def upload_to_drive(drive_service, file_path, file_name):
    try:
        file_metadata = {'name': file_name}
        if FOLDER_ID:
            file_metadata['parents'] = [FOLDER_ID]
        media = MediaFileUpload(file_path, resumable=True)
        uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = uploaded_file.get('id')
        drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
        return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
    except Exception as e:
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # Get links from the form
            links = [request.form.get(f'link{i}') for i in range(1, 8)]
            links = [link.strip() for link in links if link]  # Remove empty links

            if not links:
                return jsonify({'error': 'No valid links provided'}), 400  # Return JSON error

            # Create a folder for downloads
            output_folder = "downloads"
            os.makedirs(output_folder, exist_ok=True)

            drive_service = authenticate_drive()

            # Download PDFs
            file_counter = 1
            for link in links:
                file_id = extract_file_id(link)
                if file_id:
                    result = download_pdf_from_drive(drive_service, file_id, output_folder, file_counter)
                    if not result:
                        return jsonify({'error': f'Failed to download file {file_id}'}), 500
                    file_counter += 1

            # Merge PDFs
            merged_pdf_path = merge_pdfs(output_folder)

            # Upload merged file to Google Drive
            shareable_link = upload_to_drive(drive_service, merged_pdf_path, "combinedDoc.pdf")

            if shareable_link:
                return jsonify({'link': shareable_link})  # Valid JSON response
            else:
                return jsonify({'error': 'Upload failed'}), 500  # Error response if upload fails

        except Exception as e:
            return jsonify({'error': str(e)}), 500  # Catch all errors

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)