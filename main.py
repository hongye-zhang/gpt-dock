
from typing import Annotated,Optional

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
import io
from pdfminer.converter import TextConverter
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage


app = FastAPI()

@app.post("/createEntry/")
async def createEntry(User: str):
    from supabase import create_client, Client

    url: str = 'https://tdklrrxdggwsbfdvtlws.supabase.co'
    key: str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRka2xycnhkZ2d3c2JmZHZ0bHdzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcwOTc1MzA3MSwiZXhwIjoyMDI1MzI5MDcxfQ.a8mYI-pyEnmHqj7S30uEpOdIyjKhEbGPu62yTq961eE'
    supabase: Client = create_client(url, key)
    data, count = supabase.table('FileInfo').insert({"User": User}).execute()


@app.post("/fillGenParams/")
async def generationParameters(newTitle : Optional[str] = None, newSubTitle : Optional[str] = None,newaAuthor : Optional[str] = None,newLanguage : Optional[str] = None):
    from supabase import create_client, Client

    url: str = 'https://tdklrrxdggwsbfdvtlws.supabase.co'
    key: str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRka2xycnhkZ2d3c2JmZHZ0bHdzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcwOTc1MzA3MSwiZXhwIjoyMDI1MzI5MDcxfQ.a8mYI-pyEnmHqj7S30uEpOdIyjKhEbGPu62yTq961eE'
    supabase: Client = create_client(url, key)
    data, count = supabase.table('FileInfo').insert({"NewTitle": newTitle, "NewSubtitle": newSubTitle}).execute()


@app.post("/generateBegin/")
async def createEntry(User: str,PDF_id:int,Level1:Optional[int] = None,Level2:Optional[int] = None,Level3:inOptional[int] = None,Level4:Optional[int] = None):
    from supabase import create_client, Client
    url: str = 'https://tdklrrxdggwsbfdvtlws.supabase.co'
    key: str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRka2xycnhkZ2d3c2JmZHZ0bHdzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcwOTc1MzA3MSwiZXhwIjoyMDI1MzI5MDcxfQ.a8mYI-pyEnmHqj7S30uEpOdIyjKhEbGPu62yTq961eE'
    supabase: Client = create_client(url, key)
    data, count = supabase.table('FileInfo').select({"PDF_ID":PDF_id}).execute()
    return data['Chunk']


@app.post("/generateEnd/")
async def createEntry(PDF_id:int, content:str):
    from supabase import create_client, Client
    url: str = 'https://tdklrrxdggwsbfdvtlws.supabase.co'
    key: str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRka2xycnhkZ2d3c2JmZHZ0bHdzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcwOTc1MzA3MSwiZXhwIjoyMDI1MzI5MDcxfQ.a8mYI-pyEnmHqj7S30uEpOdIyjKhEbGPu62yTq961eE'
    supabase: Client = create_client(url, key)
    data, count = supabase.table('PDFInfo').upsert({'id': PDF_id, 'ChunkResult': content}).execute()



@app.post("/countchars/")
async def countWords(files: list[UploadFile]):
    for file in files:
        manager = PDFResourceManager()
        file_handle = io.StringIO()
        converter = TextConverter(manager, file_handle, laparams=LAParams())
        interpreter = PDFPageInterpreter(manager, converter)

        for page in PDFPage.get_pages(file, set()):
            interpreter.process_page(page)

        text = file_handle.getvalue()

        chars_count = len(text)
    if chars_count == 0:
        return 0
    return chars_count

@app.post("/files/")
async def create_files(files: Annotated[list[bytes], File()]):
    return {"file_sizes": [len(file) for file in files]}


@app.post("/uploadfiles/")
async def create_upload_files(files: list[UploadFile]):
    import os
    from supabase import create_client, Client

    url: str = 'https://tdklrrxdggwsbfdvtlws.supabase.co'
    key: str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRka2xycnhkZ2d3c2JmZHZ0bHdzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcwOTc1MzA3MSwiZXhwIjoyMDI1MzI5MDcxfQ.a8mYI-pyEnmHqj7S30uEpOdIyjKhEbGPu62yTq961eE'
    supabase: Client = create_client(url, key)
    bucket_name: str = "PDF storage"
    for f in files:
        contents = await f.read()

        data = supabase.storage.from_(bucket_name).upload('user/' + f.filename, contents)
    return {"filenames": [file.filename for file in files]}


@app.get("/")
async def main():
    content = """
<body>
<title>Upload</title>
<h1>Please upload your file</h1>
<form action="/uploadfiles/" enctype="multipart/form-data" method="post">
<input name="files" type="file" multiple>
<input type="submit">
</form>
</body>
    """
    return HTMLResponse(content=content)