import json
import hashlib
from pptx import Presentation
from pptx.util import Inches, Pt


def markdown_to_json(markdown_text):
    lines = markdown_text.split("\n")
    result = {"title": "", "subtitle": "", "sections": []}
    current_section = None
    current_content = None

    for line in lines:
        if not line or line == "---":
            continue

        if line.startswith("# "):
            result["title"] = line[2:].strip("*")
        elif line.startswith("### ") and not line.startswith("### **Content Page:"):
            result["subtitle"] = line[4:].strip("*")
        elif line.startswith("## **Section Page:"):
            current_section = {"title": line[18:].strip("*"), "pages": []}
            result["sections"].append(current_section)
        elif line.startswith("### **Content Page:"):
            current_content = {
                "title": line[20:].strip("*"),
                "content": [],
                "image_suggestion": "",
                "midjourney_prompt": "",
            }
            current_section["pages"].append(current_content)
        elif line.startswith("- **"):
            current_content["content"].append(
                {"subtitle": line[3:].strip("*"), "points": []}
            )
        elif line.startswith("  - "):
            current_content["content"][-1]["points"].append(line[4:])
        elif line.startswith("**Image Suggestion**:"):
            current_content["image_suggestion"] = line.split(":", 1)[1].strip()
        elif line.startswith("**Midjourney Prompt**:"):
            current_content["midjourney_prompt"] = line.split(":", 1)[1].strip()

    return json.dumps(result, ensure_ascii=False, indent=2)


def add_title_slide(prs, title, subtitle):
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = title
    slide.placeholders[1].text = subtitle


def add_section_slide(prs, title):
    slide_layout = prs.slide_layouts[2]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = title


def add_content_slide(prs, title, content):
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = title

    tf = slide.placeholders[1].text_frame
    for item in content:
        p = tf.add_paragraph()
        p.text = item["subtitle"]
        p.level = 0
        for point in item["points"]:
            p = tf.add_paragraph()
            p.text = point
            p.level = 1


def generate_file_hash(file_content):
    """Generate a SHA-256 hash for the given file content."""
    sha256_hash = hashlib.sha256()

    # Assuming the file_content is in bytes
    # If it's not the case, you should convert it to bytes
    sha256_hash.update(file_content)

    return sha256_hash.hexdigest()


def create_ppt_from_json(json_data):
    prs = Presentation()

    data = json.loads(json_data)

    add_title_slide(prs, data["title"], data["subtitle"])

    for section in data["sections"]:
        add_section_slide(prs, section["title"])
        for page in section["pages"]:
            add_content_slide(prs, page["title"], page["content"])

    prs.save("result.pptx")
    with open('result.pptx', 'r') as file:
        contents = file.read()
    filename = generate_file_hash(contents)
    url: str = 'https://tdklrrxdggwsbfdvtlws.supabase.co'
    key: str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRka2xycnhkZ2d3c2JmZHZ0bHdzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcwOTc1MzA3MSwiZXhwIjoyMDI1MzI5MDcxfQ.a8mYI-pyEnmHqj7S30uEpOdIyjKhEbGPu62yTq961eE'
    supabase = create_client(url, key)
    bucket_name: str = "PDF storage"
    data = supabase.storage.from_(bucket_name).upload('user/' + filename, contents,
                                                      file_options={
                                                          "content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"})
    res = supabase.storage.from_(bucket_name).get_public_url('user/' + filename)
    return res