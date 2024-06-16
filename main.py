
from typing import Annotated,Optional
from pdfparser.bearparsepdf import BearParsePDF
import math
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
import io
from pdfminer.converter import TextConverter
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
import requests
from PyPDF2 import PdfReader
import tempfile
import os
import json
import re

app = FastAPI()

#LOCAL VARIABLES
languages = [
    "English", "Spanish", "French", "German", "Chinese",
    "Russian", "Japanese", "Korean", "Italian", "Dutch",
    "Portuguese", "Turkish", "Arabic", "Hindi", "Bengali",
    "Indonesian", "Polish", "Romanian", "Swedish", "Danish",
    "Norwegian", "Finnish", "Czech", "Hungarian", "Thai",
    "Vietnamese", "Greek", "Hebrew", "Ukrainian", "Catalan"
]


#UTILITY FUNCTIONS

def get_chapter_numbers(chapter_title):
    match = re.match(r'(\d+)(\.(\d+))?(\.(\d+))?', chapter_title)
    if match:
        num1, _, num2, _, num3 = match.groups()
        return int(num1) if num1 else None, int(num2) if num2 else None, int(num3) if num3 else None
    else:
        return None, None, None

def is_before(version1, version2):
    # Split the versions by '.' and convert each part to int
    v1 = list(map(int, version1))
    v2 = list(map(int, version2))

    # Append 0s to the end of the shorter version
    len_diff = len(v1) - len(v2)
    if len_diff < 0:
        v1 += [0] * abs(len_diff)
    elif len_diff > 0:
        v2 += [0] * len_diff




    # Compare versions
    return v1 < v2

def is_same(version1, version2):
    v1 = list(map(int, version1))
    v2 = list(map(int, version2))
    return v1 ==v2

def parse(PDF_url,PDF_id):
    from supabase import create_client, Client

    url: str = 'https://tdklrrxdggwsbfdvtlws.supabase.co'
    key: str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRka2xycnhkZ2d3c2JmZHZ0bHdzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcwOTc1MzA3MSwiZXhwIjoyMDI1MzI5MDcxfQ.a8mYI-pyEnmHqj7S30uEpOdIyjKhEbGPu62yTq961eE'
    supabase: Client = create_client(url, key)

    response = requests.get(PDF_url)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:

    # Create a temporary file and write the content
        with os.fdopen(fd, 'wb') as tmp:
            # Write data to file
            tmp.write(response.content)


    # At this point, 'temp_filename' is the path of your saved pdf file
    # It's saved in a temporary directory and exists as a regular file as far as the OS is concerned
        def convert_size(size_bytes):
            if size_bytes == 0:
                return "0B"
            size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
            l = int(math.floor(math.log(size_bytes, 1024)))
            p = math.pow(1024, l)
            s = round(size_bytes / p, 2)
            return "%s %s" % (s, size_name[l])

        file_size = os.path.getsize(path)
        print('The size of the file is: ', convert_size(file_size))
        # Use it in your function

        pdf_parser = BearParsePDF(path)

    # Clean up the temporary file when you're done

        print(pdf_parser.parsePDFMetaInfo())
        text = pdf_parser.parsePDFOutlineAndSplit()

        temp = json.loads(text)
        table = "PDFInfo"
        for i in temp:
            if i[0]==1:
                data, count = supabase.table(table).insert({"PDF_ID": PDF_id,"Chunk": i[3], "SectionName": i[1], "CharCount": int(i[2])}).execute()
                print({"PDF_ID": "test", "Chunk": i[3], "SectionName": i[1], "CharCount": int(i[2])})

            elif i[0] == 2:
                level1,b,c = get_chapter_numbers(i[1])
                data, count = supabase.table(table).insert({"PDF_ID": PDF_id,"Chunk": i[3], "SectionName": i[1], "CharCount": int(i[2]),"Level1": level1}).execute()
                print(
                    {"PDF_ID": "PDF_id", "Chunk": i[3], "SectionName": i[1], "CharCount": int(i[2]), "Level1": level1})

            elif i[0] == 3:
                level1, level2, c = get_chapter_numbers(i[1])
                data, count = supabase.table(table).insert({"PDF_ID": PDF_id,"Chunk": i[3], "SectionName": i[1], "CharCount": int(i[2]),"Level1": level1,"Level2": level2}).execute()
                print(
                    {"PDF_ID": 'PDF_id', "Chunk": i[3], "SectionName": i[1], "CharCount": int(i[2]), "Level1": level1,
                     "Level2": level2})

            elif i[0] == 4:
                level1, level2, level3 = get_chapter_numbers(i[1])
                data, count = supabase.table(table).insert({"PDF_ID": PDF_id,"Chunk": i[3], "SectionName": i[1], "CharCount": int(i[2]),"Level1": level1,"Level2": level2,"Level3": level3}).execute()
                print(
                    {"PDF_ID": 'PDF_id', "Chunk": i[3], "SectionName": i[1], "CharCount": int(i[2]), "Level1": level1,
                     "Level2": level2, "Level3": level3})

    finally:
        os.unlink(path)


# WEB ENDPOINTS
@app.post("/createEntry/")
async def createEntry(User: str, Filename:str, Url:str):
    from supabase import create_client, Client

    url: str = 'https://tdklrrxdggwsbfdvtlws.supabase.co'
    key: str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRka2xycnhkZ2d3c2JmZHZ0bHdzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcwOTc1MzA3MSwiZXhwIjoyMDI1MzI5MDcxfQ.a8mYI-pyEnmHqj7S30uEpOdIyjKhEbGPu62yTq961eE'
    supabase: Client = create_client(url, key)
    try:
        data, count = supabase.table('FileInfo').insert({"User": User,"Filename": Filename,"Url": Url}).execute()
    except:
        return "This pdf has already been uploaded, do you wish to continue from the previous session?"
    id = data[1][0]['id']
    parse(Url,id)
    data, count = supabase.table('PDFInfo').select("*").eq('PDF_ID', id).execute()
    ret = []
    ret.append(id)
    for i in data[1]:
        ret.append(i['SectionName'])
    return json.dumps(ret)



@app.post("/fillGenParams/")
async def generationParameters(id:int,newTitle : Optional[str] = None, newSubTitle : Optional[str] = None,newaAuthor : Optional[str] = None,newLanguage : Optional[str] = None):
    from supabase import create_client, Client

    url: str = 'https://tdklrrxdggwsbfdvtlws.supabase.co'
    key: str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRka2xycnhkZ2d3c2JmZHZ0bHdzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcwOTc1MzA3MSwiZXhwIjoyMDI1MzI5MDcxfQ.a8mYI-pyEnmHqj7S30uEpOdIyjKhEbGPu62yTq961eE'
    supabase: Client = create_client(url, key)
    if newLanguage not in languages:
        newLanguage = "English"
    data, count = supabase.table('FileInfo').update({"NewTitle": newTitle, "NewSubtitle": newSubTitle, "NewAuthor": newaAuthor,"OutLanguage":newLanguage}).eq('id', id).execute()




@app.post("/generateBegin/")
async def generateStart(PDF_id:int,lv1v1:int,lv1v2: int,lv2v1:Optional[int] = 0,lv3v1:Optional[int] = 0,lv2v2:Optional[int] = 0,lv3v2:Optional[int]= 0):
    from supabase import create_client, Client
    url: str = 'https://tdklrrxdggwsbfdvtlws.supabase.co'
    key: str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRka2xycnhkZ2d3c2JmZHZ0bHdzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcwOTc1MzA3MSwiZXhwIjoyMDI1MzI5MDcxfQ.a8mYI-pyEnmHqj7S30uEpOdIyjKhEbGPu62yTq961eE'
    supabase: Client = create_client(url, key)
    ret = []
    data, count = supabase.table('PDFInfo').select("*").eq('PDF_ID', PDF_id).execute()
    if is_before([lv1v1, lv2v1, lv3v1], [lv1v2, lv2v2, lv3v2]):
        for i in data[1]:
            a = i["Level1"]
            b = 0
            if i["Level2"] is not None:
                b = i["Level2"]
            c = 0
            if i["Level3"] is not None:
                b = i["Level3"]
            if not is_before([a, b, c], [lv1v1, lv2v1, lv3v1]) and is_before([a, b, c], [lv1v2, lv2v2, lv3v2]):
                ret.append([i['SectionName'] + " " + i["Chunk"],i["id"]])
    elif is_same([lv1v1, lv2v1, lv3v1], [lv1v2, lv2v2, lv3v2]):
        for i in data[1]:
            a = i["Level1"]
            b = 0
            if i["Level2"] is not None:
                b = i["Level2"]
            c = 0
            if i["Level3"] is not None:
                b = i["Level3"]
            if a == lv1v1 and b == lv2v1 and c == lv3v1:
                ret.append([i['SectionName'] + " " + i["Chunk"]])
    return json.dumps(ret)



@app.post("/generateEnd/")
async def generateEnd(id:int, content:str):
    from supabase import create_client, Client
    url: str = 'https://tdklrrxdggwsbfdvtlws.supabase.co'
    key: str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRka2xycnhkZ2d3c2JmZHZ0bHdzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcwOTc1MzA3MSwiZXhwIjoyMDI1MzI5MDcxfQ.a8mYI-pyEnmHqj7S30uEpOdIyjKhEbGPu62yTq961eE'
    supabase: Client = create_client(url, key)
    data, count = supabase.table('PDFInfo').update({"ChunkResult": content}).eq('id', id).execute()



@app.post("/countchars/")
async def countWords(files: list[UploadFile]):
    global chars_count
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
    res = "error"
    for f in files:
        contents = await f.read()

        data = supabase.storage.from_(bucket_name).upload('user/' + f.filename, contents,file_options={"content-type": "application/pdf"})

        res = supabase.storage.from_(bucket_name).get_public_url('user/' + f.filename)
    content = f"""
<body>
<title>Upload</title>
<h1>Please copy the following Link:</h1>
<b>{res}</b>
</form>
</body>
    """
    return HTMLResponse(content=content)


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