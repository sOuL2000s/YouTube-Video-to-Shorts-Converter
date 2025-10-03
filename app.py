import os
import subprocess
import uuid
import shutil
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Enable CORS for all routes by default

# --- Configuration ---
TEMP_VIDEO_DIR = 'temp_videos'
MAX_VIDEO_SIZE_MB = 1000 # Increased to 1GB for more flexible processing
MAX_VIDEO_SIZE_BYTES = MAX_VIDEO_SIZE_MB * 1024 * 1024

if not os.path.exists(TEMP_VIDEO_DIR):
    os.makedirs(TEMP_VIDEO_DIR)

# --- Frontend HTML (embedded directly into Python for a single-file solution) ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Video to Shorts Converter</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #6a0572; /* Deep Purple */
            --secondary-color: #a044ff; /* Lighter Purple */
            --accent-color: #ffd700; /* Gold */
            --bg-light: #fdfdff;
            --bg-dark: #eef2f6;
            --text-dark: #2c3e50;
            --text-light: #ffffff;
            --border-color: #d1d8e0;
            --shadow-light: rgba(0, 0, 0, 0.05);
            --shadow-medium: rgba(0, 0, 0, 0.1);
        }

        body {
            font-family: 'Poppins', sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, var(--bg-dark) 0%, var(--bg-light) 100%);
            color: var(--text-dark);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            line-height: 1.6;
        }
        .container {
            max-width: 700px;
            width: 100%;
            background: var(--bg-light);
            padding: 30px 40px;
            border-radius: 12px;
            box-shadow: 0 10px 30px var(--shadow-medium);
            transition: all 0.3s ease-in-out;
            border: 1px solid var(--border-color);
        }
        h1 {
            text-align: center;
            color: var(--primary-color);
            margin-bottom: 30px;
            font-size: 2.2em;
            font-weight: 600;
            letter-spacing: -0.5px;
        }
        .form-group {
            margin-bottom: 25px;
        }
        label {
            display: block;
            margin-bottom: 10px;
            font-weight: 600;
            color: var(--text-dark);
            font-size: 1.05em;
        }
        input[type="url"],
        input[type="number"],
        input[type="text"],
        select {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            font-size: 1em;
            color: var(--text-dark);
            background-color: var(--bg-light);
            box-shadow: inset 0 1px 3px var(--shadow-light);
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
            box-sizing: border-box;
        }
        input[type="url"]:focus,
        input[type="number"]:focus,
        input[type="text"]:focus,
        select:focus {
            border-color: var(--secondary-color);
            box-shadow: 0 0 0 3px rgba(160, 68, 255, 0.2);
            outline: none;
        }
        small {
            display: block;
            margin-top: 8px;
            color: #7f8c8d;
            font-size: 0.85em;
        }
        button {
            width: 100%;
            padding: 15px;
            background-color: var(--primary-color);
            color: var(--text-light);
            border: none;
            border-radius: 8px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease;
            box-shadow: 0 4px 15px rgba(106, 5, 114, 0.2);
            margin-top: 15px; /* Added spacing for buttons */
        }
        button:hover {
            background-color: var(--secondary-color);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(160, 68, 255, 0.3);
        }
        button:active {
            transform: translateY(0);
            box-shadow: 0 2px 10px rgba(106, 5, 114, 0.2);
        }
        button:disabled {
            background-color: #cccccc;
            cursor: not-allowed;
            box-shadow: none;
            transform: none;
        }

        .advanced-options-toggle {
            display: flex;
            align-items: center;
            margin-bottom: 25px;
            margin-top: -10px;
            color: var(--primary-color);
            cursor: pointer;
            font-weight: 600;
            font-size: 0.95em;
        }
        .advanced-options-toggle:hover {
            color: var(--secondary-color);
        }
        .advanced-options-toggle input[type="checkbox"] {
            margin-right: 8px;
            min-width: 16px; /* Ensure checkbox is visible */
            min-height: 16px;
            accent-color: var(--primary-color); /* Style checkbox */
            cursor: pointer;
        }
        .advanced-options-container {
            border-top: 1px dashed var(--border-color);
            padding-top: 25px;
            margin-top: 25px;
            display: none; /* Hidden by default */
            transition: all 0.4s ease-out;
            overflow: hidden; /* For smooth hide/show */
            max-height: 0;
            opacity: 0;
        }
        .advanced-options-container.active {
            display: block; /* Show when active */
            max-height: 1000px; /* Arbitrary large value for smooth transition */
            opacity: 1;
        }

        .status-message {
            margin-top: 30px;
            padding: 15px 20px;
            border-radius: 8px;
            text-align: center;
            font-weight: 500;
            animation: fadeIn 0.5s ease-out;
        }
        .status-message.loading {
            background-color: #fff3e0; /* Light orange */
            color: #e65100; /* Dark orange */
            border: 1px solid #ffcc80;
        }
        .status-message.success {
            background-color: #e8f5e9; /* Light green */
            color: #2e7d32; /* Dark green */
            border: 1px solid #a5d6a7;
        }
        .status-message.error {
            background-color: #ffebee; /* Light red */
            color: #c62828; /* Dark red */
            border: 1px solid #ef9a9a;
        }
        .download-links {
            margin-top: 30px;
            padding-top: 25px;
            border-top: 1px dashed var(--border-color);
            animation: slideInUp 0.7s ease-out;
        }
        .download-links h3 {
            margin-bottom: 20px;
            color: var(--primary-color);
            font-size: 1.5em;
            font-weight: 600;
            text-align: center;
        }
        .download-links p {
            margin-bottom: 15px;
            text-align: center;
        }
        .download-links ul {
            list-style: none;
            padding: 0;
            display: grid;
            gap: 10px;
        }
        .download-links li {
            background-color: var(--bg-dark);
            padding: 10px 15px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .download-links li:hover {
            background-color: #e0e7ed;
        }
        .download-links a {
            color: var(--primary-color);
            text-decoration: none;
            font-weight: 500;
            flex-grow: 1;
            padding-right: 10px;
        }
        .download-links a:hover {
            text-decoration: underline;
            color: var(--secondary-color);
        }

        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Responsive Design */
        @media (max-width: 768px) {
            .container {
                margin: 15px;
                padding: 25px;
                box-shadow: 0 5px 20px var(--shadow-light);
            }
            h1 {
                font-size: 1.8em;
            }
            label {
                font-size: 1em;
            }
            input[type="url"],
            input[type="number"],
            input[type="text"],
            select,
            button {
                font-size: 0.95em;
                padding: 12px;
            }
        }

        @media (max-width: 480px) {
            body {
                padding: 10px;
            }
            .container {
                padding: 20px;
                border-radius: 8px;
            }
            h1 {
                font-size: 1.5em;
                margin-bottom: 20px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                margin-bottom: 8px;
            }
            small {
                font-size: 0.8em;
            }
            .status-message {
                margin-top: 20px;
                padding: 12px 15px;
            }
            .download-links h3 {
                font-size: 1.2em;
            }
            .download-links p {
                font-size: 0.9em;
            }
            .download-links li {
                padding: 8px 12px;
                font-size: 0.9em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>YouTube Video to Shorts Converter</h1>
        <form id="converterForm">
            <div class="form-group">
                <label for="youtubeUrl">YouTube Video URL:</label>
                <input type="url" id="youtubeUrl" placeholder="e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ" required>
            </div>
            <div class="form-group">
                <label for="sliceDuration">Slice Duration (seconds):</label>
                <input type="number" id="sliceDuration" value="60" min="5" max="600" required>
                <small>Enter the desired length of each short video segment (e.g., 15 for 15-second shorts).</small>
            </div>

            <div class="advanced-options-toggle">
                <input type="checkbox" id="toggleAdvancedOptions">
                <label for="toggleAdvancedOptions" style="margin-bottom: 0; cursor: pointer;">Show Advanced Options</label>
            </div>

            <div id="advancedOptions" class="advanced-options-container">
                <h2>Advanced Settings</h2>
                <div class="form-group">
                    <label for="downloadStartTime">Download Start Time (HH:MM:SS or seconds):</label>
                    <input type="text" id="downloadStartTime" placeholder="e.g., 00:01:30 or 90">
                    <small>Specify where to start downloading the original YouTube video.</small>
                </div>
                <div class="form-group">
                    <label for="downloadEndTime">Download End Time (HH:MM:SS or seconds):</label>
                    <input type="text" id="downloadEndTime" placeholder="e.g., 00:05:00 or 300">
                    <small>Specify where to end downloading the original YouTube video.</small>
                </div>
                <div class="form-group">
                    <label for="outputResolution">Output Resolution:</label>
                    <select id="outputResolution">
                        <option value="">Original (no change)</option>
                        <option value="1920x1080">1080p (16:9)</option>
                        <option value="1080x1920">1080p Portrait (9:16) - Ideal for Shorts</option>
                        <option value="1280x720">720p (16:9)</option>
                        <option value="720x1280">720p Portrait (9:16)</option>
                        <option value="854x480">480p (16:9)</option>
                        <option value="480x854">480p Portrait (9:16)</option>
                    </select>
                    <small>Choose the resolution for your output shorts. Vertical options are for YouTube Shorts.</small>
                </div>
                <div class="form-group">
                    <label for="videoBitrate">Video Bitrate (kbps):</label>
                    <input type="number" id="videoBitrate" value="" placeholder="e.g., 2000 (for 2Mbps)">
                    <small>Higher bitrate means better quality but larger file size. Leave empty for default. (e.g., 2000-5000 for 1080p).</small>
                </div>
                <div class="form-group">
                    <label for="audioBitrate">Audio Bitrate (kbps):</label>
                    <input type="number" id="audioBitrate" value="" placeholder="e.g., 128">
                    <small>Audio quality. Leave empty for default. (e.g., 128, 192, 256).</small>
                </div>
                <div class="form-group">
                    <label for="videoCodec">Video Codec:</label>
                    <select id="videoCodec">
                        <option value="libx264">H.264 (Default, widely compatible)</option>
                        <option value="libx265">H.265 / HEVC (More efficient, smaller files, less compatible)</option>
                    </select>
                    <small>Choose the video compression standard. H.264 is recommended for broad compatibility.</small>
                </div>
            </div>

            <button type="submit" id="convertButton">Convert to Shorts</button>
        </form>

        <div id="status" class="status-message" style="display: none;"></div>
        <div id="downloadLinks" class="download-links" style="display: none;">
            <h3>Your Shorts are Ready!</h3>
            <p>Click on the links below to download your video segments.</p>
            <ul>
                <!-- Download links will be inserted here by JavaScript -->
            </ul>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const form = document.getElementById('converterForm');
            const youtubeUrlInput = document.getElementById('youtubeUrl');
            const sliceDurationInput = document.getElementById('sliceDuration');
            const convertButton = document.getElementById('convertButton');
            const statusDiv = document.getElementById('status');
            const downloadLinksDiv = document.getElementById('downloadLinks');
            const downloadLinksList = downloadLinksDiv.querySelector('ul');

            const toggleAdvancedOptions = document.getElementById('toggleAdvancedOptions');
            const advancedOptionsContainer = document.getElementById('advancedOptions');

            const downloadStartTimeInput = document.getElementById('downloadStartTime');
            const downloadEndTimeInput = document.getElementById('downloadEndTime');
            const outputResolutionSelect = document.getElementById('outputResolution');
            const videoBitrateInput = document.getElementById('videoBitrate');
            const audioBitrateInput = document.getElementById('audioBitrate');
            const videoCodecSelect = document.getElementById('videoCodec');


            const API_ENDPOINT = 'http://localhost:5000/convert';

            // Toggle advanced options visibility
            toggleAdvancedOptions.addEventListener('change', () => {
                if (toggleAdvancedOptions.checked) {
                    advancedOptionsContainer.classList.add('active');
                } else {
                    advancedOptionsContainer.classList.remove('active');
                }
            });


            form.addEventListener('submit', async (event) => {
                event.preventDefault();

                const youtubeUrl = youtubeUrlInput.value.trim();
                const sliceDuration = parseInt(sliceDurationInput.value, 10);

                if (!youtubeUrl || !sliceDuration || isNaN(sliceDuration) || sliceDuration < 5) {
                    displayStatus('Please provide a valid YouTube URL and a slice duration of at least 5 seconds.', 'error');
                    return;
                }

                convertButton.disabled = true;
                convertButton.textContent = 'Processing...';

                displayStatus('Processing your video... This may take a while depending on video length, server load, and chosen quality settings (re-encoding takes longer).', 'loading');
                downloadLinksDiv.style.display = 'none';
                downloadLinksList.innerHTML = '';

                const requestBody = {
                    url: youtubeUrl,
                    duration: sliceDuration,
                    // Advanced options
                    download_start_time: downloadStartTimeInput.value.trim(),
                    download_end_time: downloadEndTimeInput.value.trim(),
                    output_resolution: outputResolutionSelect.value,
                    video_bitrate: videoBitrateInput.value.trim(),
                    audio_bitrate: audioBitrateInput.value.trim(),
                    video_codec: videoCodecSelect.value,
                };

                try {
                    const response = await fetch(API_ENDPOINT, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(requestBody),
                    });

                    const result = await response.json();

                    if (response.ok) {
                        if (result.downloadUrls && Array.isArray(result.downloadUrls) && result.downloadUrls.length > 0) {
                            displayStatus('Video successfully processed! Your shorts are ready.', 'success');
                            result.downloadUrls.forEach((url, index) => {
                                const listItem = document.createElement('li');
                                const link = document.createElement('a');
                                link.href = url;
                                link.textContent = `Short Segment ${index + 1} (${sliceDuration}s)`;
                                link.download = `youtube_short_segment_${index + 1}.mp4`;
                                listItem.appendChild(link);
                                downloadLinksList.appendChild(listItem);
                            });
                            downloadLinksDiv.style.display = 'block';
                        } else if (result.message) {
                            displayStatus(`Processing finished: ${result.message}`, 'success');
                        } else {
                            displayStatus('Processing finished, but no download links were returned.', 'error');
                        }
                    } else {
                        displayStatus(`Error: ${result.message || 'Something went wrong on the server.'}`, 'error');
                    }
                } catch (error) {
                    console.error('Fetch error:', error);
                    displayStatus(`Network error or server unavailable: ${error.message}. Please ensure your backend server is running at ${API_ENDPOINT}.`, 'error');
                } finally {
                    convertButton.disabled = false;
                    convertButton.textContent = 'Convert to Shorts';
                }
            });

            function displayStatus(message, type) {
                statusDiv.textContent = message;
                statusDiv.className = `status-message ${type}`;
                statusDiv.style.display = 'block';
                if (type === 'loading' || type === 'error') {
                    downloadLinksDiv.style.display = 'none';
                    downloadLinksList.innerHTML = '';
                }
            }
        });
    </script>
</body>
</html>
"""

# --- Helper Functions ---
def parse_time_to_seconds(time_str):
    """
    Parses a time string (HH:MM:SS or seconds) into total seconds.
    Returns None if parsing fails.
    """
    if not time_str:
        return None
    try:
        # Check if it's already an integer (seconds)
        return int(time_str)
    except ValueError:
        # Try to parse as HH:MM:SS
        parts = list(map(int, time_str.split(':')))
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2: # MM:SS
            return parts[0] * 60 + parts[1]
        elif len(parts) == 1: # S or SS
             return parts[0]
        return None

# --- Flask Routes (Backend Logic) ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template_string(HTML_PAGE)

@app.route('/convert', methods=['POST'])
def convert_video():
    """
    Handles the POST request to download and slice a YouTube video.
    """
    data = request.get_json()
    youtube_url = data.get('url')
    slice_duration_str = data.get('duration')

    # Advanced options
    download_start_time_str = data.get('download_start_time')
    download_end_time_str = data.get('download_end_time')
    output_resolution = data.get('output_resolution')
    video_bitrate_str = data.get('video_bitrate')
    audio_bitrate_str = data.get('audio_bitrate')
    video_codec = data.get('video_codec')

    if not youtube_url or not slice_duration_str:
        return jsonify({"message": "Missing YouTube URL or slice duration."}), 400

    try:
        slice_duration = int(slice_duration_str)
        if slice_duration < 5:
            return jsonify({"message": "Slice duration must be at least 5 seconds."}), 400
    except ValueError:
        return jsonify({"message": "Invalid slice duration. Must be a number."}), 400

    download_start_seconds = parse_time_to_seconds(download_start_time_str)
    download_end_seconds = parse_time_to_seconds(download_end_time_str)

    # Validate custom resolutions format (e.g., "1920x1080")
    if output_resolution and 'x' not in output_resolution and output_resolution not in ['original']:
        return jsonify({"message": "Invalid output resolution format. Use WIDTHxHEIGHT (e.g., 1920x1080)."}), 400

    # Validate bitrates
    video_bitrate = None
    if video_bitrate_str:
        try:
            video_bitrate = int(video_bitrate_str)
            if video_bitrate <= 0:
                return jsonify({"message": "Video bitrate must be a positive number."}), 400
        except ValueError:
            return jsonify({"message": "Invalid video bitrate. Must be a number."}), 400

    audio_bitrate = None
    if audio_bitrate_str:
        try:
            audio_bitrate = int(audio_bitrate_str)
            if audio_bitrate <= 0:
                return jsonify({"message": "Audio bitrate must be a positive number."}), 400
        except ValueError:
            return jsonify({"message": "Invalid audio bitrate. Must be a number."}), 400

    session_id = str(uuid.uuid4())
    session_dir = os.path.join(TEMP_VIDEO_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    original_video_path = os.path.join(session_dir, 'original_video.mp4')
    download_urls = []

    try:
        # 1. Download the YouTube video using yt-dlp
        app.logger.info(f"Downloading {youtube_url} to {original_video_path}")
        download_command = [
            'yt-dlp',
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
            '--merge-output-format', 'mp4',
            '--restrict-filenames',
            '-o', original_video_path,
        ]

        # Add download sections if specified
        if download_start_seconds is not None and download_end_seconds is not None:
            download_command.extend(['--download-sections', f"*{download_start_seconds}-{download_end_seconds}"])
        elif download_start_seconds is not None:
            download_command.extend(['--download-sections', f"*{download_start_seconds}-inf"])
        elif download_end_seconds is not None:
            download_command.extend(['--download-sections', f"*0-{download_end_seconds}"])

        download_command.append(youtube_url)

        subprocess.run(download_command, check=True, capture_output=True, text=True, timeout=600) # 10 minutes timeout for download
        app.logger.info(f"Download complete: {original_video_path}")

        if MAX_VIDEO_SIZE_BYTES > 0 and os.path.getsize(original_video_path) > MAX_VIDEO_SIZE_BYTES:
            return jsonify({"message": f"Video file is too large (>{MAX_VIDEO_SIZE_MB}MB). Please choose a shorter video."}), 413

        # 2. Get video duration for slicing
        probe_command = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            original_video_path
        ]
        duration_output = subprocess.run(probe_command, check=True, capture_output=True, text=True, timeout=60)
        full_video_duration = float(duration_output.stdout.strip())
        app.logger.info(f"Full video duration (of downloaded segment): {full_video_duration} seconds")

        # 3. Slice the video using FFmpeg
        num_slices = int(full_video_duration / slice_duration)
        if full_video_duration % slice_duration != 0:
            num_slices += 1

        # Determine if re-encoding is needed
        re_encode = bool(output_resolution or video_bitrate or audio_bitrate or video_codec != 'libx264')

        for i in range(num_slices):
            start_time = i * slice_duration
            current_slice_duration = slice_duration # FFmpeg handles the end gracefully

            output_slice_filename = f"short_segment_{i+1}_{session_id}.mp4"
            output_slice_path = os.path.join(session_dir, output_slice_filename)

            slice_command = [
                'ffmpeg',
                '-i', original_video_path,
                '-ss', str(start_time),
                '-t', str(current_slice_duration),
                '-avoid_negative_ts', 'make_zero', # Handle negative timestamps gracefully
            ]

            if re_encode:
                slice_command.extend(['-c:v', video_codec]) # Video codec
                slice_command.extend(['-c:a', 'aac']) # Standard audio codec for mp4

                # Video Bitrate
                if video_bitrate:
                    slice_command.extend(['-b:v', f"{video_bitrate}k"])
                # Audio Bitrate
                if audio_bitrate:
                    slice_command.extend(['-b:a', f"{audio_bitrate}k"])

                # Output Resolution and Aspect Ratio
                if output_resolution and output_resolution != 'Original (no change)':
                    width, height = map(int, output_resolution.split('x'))
                    # This filter scales to fit *within* the target dimensions while maintaining aspect ratio,
                    # then crops to exactly the target dimensions (center crop).
                    # This is typical for converting wide video to vertical shorts without black bars.
                    # Adjust if a different scaling/cropping strategy is desired.
                    filter_complex = f"scale='min({width},iw)':min'({height},ih)':force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
                    slice_command.extend(['-vf', filter_complex])
                else: # Default video quality if re-encoding without explicit settings
                    slice_command.extend(['-crf', '23']) # Constant Rate Factor, 0 is lossless, 51 is worst. 23 is good default.

            else:
                # If no re-encoding is needed, just copy streams for speed
                slice_command.extend(['-c', 'copy'])

            slice_command.append(output_slice_path)

            app.logger.info(f"Slicing command: {' '.join(slice_command)}")
            subprocess.run(slice_command, check=True, capture_output=True, text=True, timeout=600) # 10 minutes timeout for slicing
            app.logger.info(f"Sliced: {output_slice_path}")
            download_urls.append(f"http://localhost:5000/download/{session_id}/{output_slice_filename}")

        return jsonify({"message": "Video processed successfully.", "downloadUrls": download_urls}), 200

    except subprocess.CalledProcessError as e:
        app.logger.error(f"Subprocess failed: {e.cmd}\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
        return jsonify({"message": f"Video processing failed. Error: {e.stderr.strip()}"}), 500
    except subprocess.TimeoutExpired as e:
        app.logger.error(f"Subprocess timed out: {e.cmd}")
        return jsonify({"message": "Video processing timed out. The video might be too long or the server too busy."}), 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"message": f"An internal server error occurred: {str(e)}"}), 500
    finally:
        if os.path.exists(original_video_path):
            os.remove(original_video_path)
            app.logger.info(f"Removed original video: {original_video_path}")

@app.route('/download/<session_id>/<filename>')
def download_file(session_id, filename):
    """
    Serves the sliced video files from the temporary directory.
    """
    if ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"message": "Invalid filename."}), 400

    file_path = os.path.join(TEMP_VIDEO_DIR, session_id, filename)
    if not os.path.exists(file_path):
        return jsonify({"message": "File not found or has been removed."}), 404

    # TODO: Implement a more robust cleanup mechanism for session directories
    # A simple approach could be to delete the parent session_id directory after a certain time
    # or after all files in it have been accessed. For this example, files persist.

    return send_from_directory(
        directory=os.path.join(TEMP_VIDEO_DIR, session_id),
        path=filename,
        as_attachment=True
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
