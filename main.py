
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
import hashlib
from ppts import markdown_to_json,create_ppt_from_json

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



def generate_file_hash(file_content):
    """Generate a SHA-256 hash for the given file content."""
    sha256_hash = hashlib.sha256()

    # Assuming the file_content is in bytes
    # If it's not the case, you should convert it to bytes
    sha256_hash.update(file_content)

    return sha256_hash.hexdigest()

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

@app.post("/makePPT/")
async def makePPT(text: str):
    from ppts import MarkdownToPPTXConverter
    converter = MarkdownToPPTXConverter(text, ppttemplate_path=".//templates//template-en.pptx")
    # 提取图片建议
    image_descriptions = converter.extract_image_suggestions_with_page_numbers(text)
    # 解析Markdown并生成PPTX
    converter.parse_markdown()
    # 创建PPTX
    converter.create_pptx(image_descriptions=image_descriptions)
    # 保存PPTX
    url = converter.save_pptx("output.pptx")
    return url

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
        filename = generate_file_hash(contents)

        data = supabase.storage.from_(bucket_name).upload('user/' + filename, contents,file_options={"content-type": "application/pdf"})

        res = supabase.storage.from_(bucket_name).get_public_url('user/' + filename)
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

@app.get("/privacypolicy/")
async def privacypolicy():
    content = """
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Privacy Policy</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f4f4f4;
        }
        .container {
            max-width: 800px;
            margin: auto;
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        }
        h1 {
            text-align: center;
            color: #333;
        }
        h2 {
            color: #555;
        }
        p {
            margin-bottom: 15px;
        }
    </style>
</head>
<body>

<div class="container">
    <h1>Privacy Policy</h1>
    <p>Welcome to the GPT Store! We value your privacy and are committed to protecting your personal data. This Privacy Policy outlines how we handle the information you provide when using our services, including generating PPTX files based on your input data.</p>

    <h2>1. Information We Collect</h2>
    <p>When you use our service, we may collect the following types of data:</p>
    <ul>
        <li><strong>Personal Information:</strong> This includes any personal details you provide, such as your name or email address, when creating an account or communicating with us.</li>
        <li><strong>Input Data:</strong> The content you provide (e.g., text, images, or documents) to generate PPTX files.</li>
        <li><strong>Usage Data:</strong> Information about how you use the platform, such as interaction with features, time spent, etc.</li>
    </ul>

    <h2>2. How We Use Your Data</h2>
    <p>We use your data in the following ways:</p>
    <ul>
        <li><strong>Generate PPTX Files:</strong> Your input data is processed to create personalized PowerPoint presentations based on the information you submit.</li>
        <li><strong>Improving Services:</strong> Usage data helps us enhance the platform, optimize performance, and introduce new features.</li>
        <li><strong>Customer Support:</strong> We may use your contact information to respond to inquiries or resolve issues with the service.</li>
    </ul>

    <h2>3. Data Sharing</h2>
    <p>We do not sell or share your personal data with third parties, except in the following situations:</p>
    <ul>
        <li>With your explicit consent.</li>
        <li>When required by law or to comply with legal obligations.</li>
        <li>To protect the security and integrity of our platform.</li>
    </ul>

    <h2>4. Data Security</h2>
    <p>We implement strong security measures to protect your personal and input data. However, no system is entirely secure, and we cannot guarantee the absolute security of your information. Please ensure you use strong passwords and protect your account credentials.</p>

    <h2>5. Your Rights</h2>
    <p>You have the right to:</p>
    <ul>
        <li>Access the personal data we hold about you.</li>
        <li>Request corrections or deletions of your data.</li>
        <li>Withdraw consent to data processing at any time.</li>
    </ul>

    <h2>6. Changes to This Policy</h2>
    <p>We may update this privacy policy from time to time to reflect changes in our practices or legal obligations. Please review this page periodically for updates.</p>

    <h2>7. Contact Us</h2>
    <p>If you have any questions about this privacy policy or how we handle your data, feel free to contact us at <strong>support@gptstore.com</strong>.</p>
</div>

</body>
</html>
    """
    return HTMLResponse(content=content)