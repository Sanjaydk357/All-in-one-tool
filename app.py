import yt_dlp
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from pdf2docx import Converter
from docx2pdf import convert
import zipfile
import io
from flask import Flask, request, send_file, render_template,flash,redirect, url_for,session
from moviepy import VideoFileClip, AudioFileClip,AudioArrayClip, concatenate_videoclips,concatenate_audioclips
import os
from pydub import AudioSegment
import tempfile

app = Flask(__name__)
upload_folder = 'upload'
os.makedirs(upload_folder, exist_ok=True)
app.secret_key = 'supersecret'  # Needed for flashing messages

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/merge', methods=["GET"])
def merge_page():
    return render_template("merge.html")

@app.route("/merge-videos", methods=["GET", "POST"])
def merge_videos():
    if request.method == "GET":
        return render_template("merge.html")  # Show upload form if someone visits the route directly
    
    video1 = request.files["video1"]
    video2 = request.files["video2"]

    with tempfile.NamedTemporaryFile(delete=False,suffix='.mp4') as temp1, \
        tempfile.NamedTemporaryFile(delete=False,suffix='.mp4') as temp2:

        temp1.write(video1.read())
        temp2.write(video2.read())
        temp1_path = temp1.name
        temp2_path = temp2.name

    clip1 = VideoFileClip(temp1_path)
    clip2 = VideoFileClip(temp2_path)
    
    target_width, target_height = clip1.size
    target_fps = clip1.fps
    
    clip2 = clip2.resized(width=target_width, height=target_height).with_fps(target_fps)
    clip1 = clip1.with_fps(target_fps)

    final_clip = concatenate_videoclips([clip1, clip2])
    output_path = os.path.join(upload_folder, "merged_video.mp4")
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    return send_file(output_path, as_attachment=True)

@app.route('/video-to-audio', methods=["GET", "POST"])
def video_to_audio():
    if request.method == "GET":
        return render_template("video_to_audio.html")

    video = request.files.get("video")
    if not video:
        flash("No video file uploaded.")
        return render_template("video_to_audio.html")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
        temp_video.write(video.read())
        video_path = temp_video.name

    try:
        clip = VideoFileClip(video_path)

        # Debugging: Log to console if audio is found
        if clip.audio is None:
            print("No audio track found in video.")
            clip.close()
            os.remove(video_path)
            flash("No audio track found in the uploaded video.")
            return render_template("video_to_audio.html")
        else:
            print("Audio track found in video.")

        # Proceed to extract audio if present
        output_audio_path = os.path.join(upload_folder, "extracted_audio.mp3")
        clip.audio.write_audiofile(output_audio_path)
        clip.close()
        os.remove(video_path)

        return send_file(output_audio_path, as_attachment=True, mimetype='audio/mpeg')

    except Exception as e:
        flash(f"An error occurred: {str(e)}")
        if os.path.exists(video_path):
            os.remove(video_path)
        return render_template("video_to_audio.html")
    
@app.route('/screen-recorder', methods=["GET", "POST"])
def screen_recorder():
    if request.method == "GET":
        return render_template("screen_recorder.html")

    recorded_file = request.files.get("recording")
    if not recorded_file:
        flash("No recording received.")
        return render_template("screen_recorder.html")

    output_path = os.path.join(upload_folder, "screen_recording.webm")
    recorded_file.save(output_path)

    return send_file(output_path, as_attachment=True)

@app.route('/trim-audio', methods=["GET", "POST"])
def trim_audio():
    if request.method == "GET":
        return render_template("trim_audio.html")

    audio_file = request.files.get("audio")
    start_time = float(request.form.get("start", 0))
    end_time = float(request.form.get("end", 0))

    if not audio_file:
        flash("No audio file uploaded.")
        return render_template("trim_audio.html")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
        temp_audio.write(audio_file.read())
        temp_audio_path = temp_audio.name

    try:
        # Load the audio file
        audio_clip = AudioFileClip(temp_audio_path)
        
        # Trim the audio by slicing it
        trimmed_audio = audio_clip.subclip(start_time, end_time)

        # Save the trimmed audio file
        output_path = os.path.join(upload_folder, "trimmed_audio.mp3")
        trimmed_audio.write_audiofile(output_path)
        audio_clip.close()
        trimmed_audio.close()

        return send_file(output_path, as_attachment=True)

    except Exception as e:
        flash(f"An error occurred: {str(e)}")
        return render_template("trim_audio.html")

    finally:
        # Ensure the temporary file is removed only after the clip is closed and sent
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except PermissionError:
                print(f"Failed to delete the temporary file: {temp_audio_path}")

@app.route('/merge-audio', methods=["GET", "POST"])
def merge_audio():
    if request.method == "GET":
        return render_template("merge_audio.html")

    audio1 = request.files.get("audio1")
    audio2 = request.files.get("audio2")

    if not audio1 or not audio2:
        flash("Please upload both audio files.")
        return render_template("merge_audio.html")

    temp1 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp2 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp1.write(audio1.read())
    temp2.write(audio2.read())
    temp1.close()
    temp2.close()

    try:
        clip1 = AudioFileClip(temp1.name)
        clip2 = AudioFileClip(temp2.name)

        final_audio = concatenate_audioclips([clip1, clip2])
        output_path = os.path.join(upload_folder, "merged_audio.mp3")
        final_audio.write_audiofile(output_path)

        clip1.close()
        clip2.close()
        os.remove(temp1.name)
        os.remove(temp2.name)

        return send_file(output_path, as_attachment=True)

    except Exception as e:
        flash(f"An error occurred: {str(e)}")
        return render_template("merge_audio.html")

@app.route('/record-audio', methods=["GET", "POST"])
def record_audio():
    if request.method == "GET":
        return render_template("record_audio.html")

    audio_file = request.files.get("audio")
    if not audio_file:
        flash("No audio file uploaded.")
        return render_template("record_audio.html")

    # Save as .webm first
    temp_webm_path = os.path.join(upload_folder, "temp_audio.webm")
    audio_file.save(temp_webm_path)

    # Convert to .mp3 using pydub
    mp3_path = os.path.join(upload_folder, "recorded_audio.mp3")
    audio = AudioSegment.from_file(temp_webm_path, format="webm")
    audio.export(mp3_path, format="mp3")

    os.remove(temp_webm_path)

    return send_file(mp3_path, as_attachment=True)

@app.route('/reverse-audio', methods=["GET", "POST"])
def reverse_audio():
    if request.method == "GET":
        return render_template("reverse_audio.html")

    audio_file = request.files.get("audio")
    if not audio_file:
        flash("Please upload an audio file.")
        return render_template("reverse_audio.html")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
        temp_audio.write(audio_file.read())
        temp_audio_path = temp_audio.name

    try:
        clip = AudioFileClip(temp_audio_path)
        audio_array = clip.to_soundarray()
        reversed_array = audio_array[::-1]  # Reverse the array
        reversed_clip = AudioArrayClip(reversed_array, fps=clip.fps)

        output_path = os.path.join(upload_folder, "reversed_audio.mp3")
        reversed_clip.write_audiofile(output_path)

        clip.close()
        reversed_clip.close()
        os.remove(temp_audio_path)

        return send_file(output_path, as_attachment=True)

    except Exception as e:
        flash(f"Error reversing audio: {str(e)}")
        return render_template("reverse_audio.html")

@app.route('/split-pages', methods=["GET", "POST"])
def split_pages():
    if request.method == "GET":
        return render_template("split_pages.html")

    pdf_file = request.files.get("pdf")
    if not pdf_file:
        flash("No PDF file uploaded.")
        return render_template("split_pages.html")

    try:
        reader = PdfReader(pdf_file)
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for i, page in enumerate(reader.pages):
                writer = PdfWriter()
                writer.add_page(page)
                page_io = io.BytesIO()
                writer.write(page_io)
                zipf.writestr(f"page_{i + 1}.pdf", page_io.getvalue())

        zip_buffer.seek(0)
        return send_file(zip_buffer, as_attachment=True, download_name="split_pages.zip", mimetype='application/zip')

    except Exception as e:
        flash(f"Error splitting pages: {str(e)}")
        return render_template("split_pages.html")
    
@app.route('/merge-pdf', methods=["GET", "POST"])
def merge_pdf():
    if request.method == "GET":
        return render_template("merge_pdf.html")

    uploaded_files = request.files.getlist("pdfs")
    if not uploaded_files or len(uploaded_files) < 2:
        flash("Please upload at least two PDF files.")
        return render_template("merge_pdf.html")

    merger = PdfMerger()

    try:
        for file in uploaded_files:
            merger.append(file)

        output_path = os.path.join(upload_folder, "merged.pdf")
        with open(output_path, "wb") as f:
            merger.write(f)

        merger.close()
        return send_file(output_path, as_attachment=True)

    except Exception as e:
        flash(f"Error merging PDFs: {str(e)}")
        return render_template("merge_pdf.html")

@app.route('/pdf-to-word', methods=["GET", "POST"])
def pdf_to_word():
    if request.method == "GET":
        return render_template("pdf_to_word.html")

    pdf_file = request.files.get("pdf")
    if not pdf_file:
        flash("Please upload a PDF file.")
        return render_template("pdf_to_word.html")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_pdf.write(pdf_file.read())
        pdf_path = temp_pdf.name

    output_docx = os.path.join(upload_folder, "converted.docx")

    try:
        cv = Converter(pdf_path)
        cv.convert(output_docx)
        cv.close()
        os.remove(pdf_path)
        return send_file(output_docx, as_attachment=True)

    except Exception as e:
        flash(f"Error converting PDF to Word: {str(e)}")
        return render_template("pdf_to_word.html")
    
@app.route('/word-to-pdf', methods=["GET", "POST"])
def word_to_pdf():
    if request.method == "GET":
        return render_template("word_to_pdf.html")

    docx_file = request.files.get("word")
    if not docx_file:
        flash("Please upload a Word (.docx) file.")
        return render_template("word_to_pdf.html")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_docx:
        temp_docx.write(docx_file.read())
        input_path = temp_docx.name

    output_pdf_path = os.path.join(upload_folder, "converted.pdf")

    try:
        convert(input_path, output_pdf_path)
        os.remove(input_path)
        return send_file(output_pdf_path, as_attachment=True)
    except Exception as e:
        flash(f"Conversion failed: {str(e)}")
        return render_template("word_to_pdf.html")

@app.route('/image-to-pdf', methods=["GET", "POST"])
def image_to_pdf():
    if request.method == "GET":
        return render_template("image_to_pdf.html")

    image_files = request.files.getlist("images")
    if not image_files or len(image_files) == 0:
        flash("Please upload at least one image file.")
        return render_template("image_to_pdf.html")

    images = []
    temp_files = []

    try:
        for image_file in image_files:
            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp.write(image_file.read())
            temp.close()
            temp_files.append(temp.name)

            img = Image.open(temp.name).convert("RGB")
            images.append(img)

        if not images:
            flash("No valid image files provided.")
            return render_template("image_to_pdf.html")

        output_pdf_path = os.path.join(upload_folder, "merged_images.pdf")
        images[0].save(output_pdf_path, save_all=True, append_images=images[1:], format="PDF")

        for path in temp_files:
            os.remove(path)

        return send_file(output_pdf_path, as_attachment=True)

    except Exception as e:
        for path in temp_files:
            if os.path.exists(path):
                os.remove(path)
        flash(f"Error while processing images: {str(e)}")
        return render_template("image_to_pdf.html")

@app.route('/compress-zip', methods=["GET", "POST"])
def compress_zip():
    if request.method == "GET":
        return render_template("compress_zip.html")

    files = request.files.getlist("files")  # Get all uploaded files
    if not files:
        flash("Please upload at least one file.")
        return render_template("compress_zip.html")

    # Create a temporary zip file
    zip_filename = os.path.join(upload_folder, "compressed_files.zip")
    try:
        with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file in files:
                file_path = os.path.join(upload_folder, file.filename)
                file.save(file_path)  # Save each file temporarily

                # Add to the zip file
                zipf.write(file_path, arcname=file.filename)

                # Close and delete the temporary file after adding it to the zip
                try:
                    os.remove(file_path)  # Remove the file after adding it to the zip
                except Exception as e:
                    flash(f"Error deleting file {file.filename}: {str(e)}")

        return send_file(zip_filename, as_attachment=True)

    except Exception as e:
        flash(f"Error compressing files: {str(e)}")
        return render_template("compress_zip.html")

    except Exception as e:
        flash(f"Error compressing files: {str(e)}")
        return render_template("compress_zip.html")
    

@app.route('/download-video', methods=["GET", "POST"])
def download_video():
    if request.method == "GET":
        return render_template("download_video.html")

    video_url = request.form.get("video_url")
    if not video_url:
        flash("Please provide a video URL.")
        return render_template("download_video.html")

    try:
        # Temporary directory to download video
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, "%(title)s.%(ext)s")

        ydl_opts = {
            'outtmpl': output_path,
            'format': 'mp4',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            final_path = ydl.prepare_filename(info)

        return send_file(final_path, as_attachment=True)

    except Exception as e:
        flash(f"Error downloading video: {str(e)}")
        return render_template("download_video.html")

@app.route('/download-audio', methods=["GET", "POST"])
def download_audio():
    if request.method == "GET":
        return render_template("download_audio.html")

    video_url = request.form.get("video_url")
    if not video_url:
        flash("Please provide a video URL.")
        return render_template("download_audio.html")

    try:
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, "%(title)s.%(ext)s")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            final_path = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"

        return send_file(final_path, as_attachment=True)

    except Exception as e:
        flash(f"Error downloading audio: {str(e)}")
        return render_template("download_audio.html")

if __name__ == "__main__":
    app.run(debug=True)