import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from PyPDF2 import PdfMerger
import re

load_dotenv()

FOLDER_ID = os.getenv('FOLDER_ID')
SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate_services():
    credentials = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
    return drive_service

def enter_links():
    links = []
    for i in range(7):
        input_link = input(f"Enter Link {i+1}: ").strip()
        if input_link:
            links.append(input_link)
    return links

def create_folder():
    folder_path = "downloads"
    os.makedirs(folder_path, exist_ok=True)
    os.chmod(folder_path, 0o777)
    return folder_path

def extract_file_id(drive_link):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', drive_link)
    if match:
        return match.group(1)
    else:
        raise ValueError("Invalid Google Drive link format. Ensure it follows 'https://drive.google.com/file/d/FILE_ID/view'.")

def download_pdf_from_drive(drive_service, file_id, output_path, file_counter):
    try:
        request = drive_service.files().get_media(fileId=file_id)
        file_name = f"{output_path}/{file_counter}.pdf"
        with open(file_name, 'wb') as pdf_file:
            downloader = MediaIoBaseDownload(pdf_file, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"Download Progress: {int(status.progress() * 100)}%")
        print(f"File downloaded successfully: {file_name}")
        return file_name
    except Exception as e:
        print(f"Error downloading file: {e}")
        return None

def download_files(drive_service, links, output_path):
    file_counter = 1
    for link in links:
        if "drive.google.com" in link:
            file_id = extract_file_id(link)
            download_pdf_from_drive(drive_service, file_id, output_path, file_counter)
        else:
            raise ValueError("Invalid Google Drive link.")
        file_counter += 1

def merge_pdfs_in_folder(folder_path):
    merger = PdfMerger()
    pdf_order = ['1', '2', '3', '4', '5', '6', '7']
    for pdf_type in pdf_order:
        for item in os.listdir(folder_path):
            if item.endswith('.pdf') and pdf_type in item:
                pdf_path = os.path.join(folder_path, item)
                merger.append(pdf_path)
    merged_pdf_path = os.path.join(folder_path, 'merged_document.pdf')
    merger.write(merged_pdf_path)
    merger.close()
    return merged_pdf_path

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

def main():
    links = enter_links()
    drive_service = authenticate_services()
    folder_path = create_folder()
    download_files(drive_service, links, folder_path)
    merged_pdf_path = merge_pdfs_in_folder(folder_path)
    shareable_link = upload_file_to_drive(drive_service, merged_pdf_path, "combinedDoc.pdf", FOLDER_ID)
    print(f"Final Shareable Link: {shareable_link}")

if __name__ == '__main__':
    main()