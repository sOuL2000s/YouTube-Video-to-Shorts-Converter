import os
import subprocess
import uuid
import shutil
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
# Enable CORS for all routes. This is important for local development if frontend is on a different port,
# and generally good practice if you intend to have other frontends consume this API.
CORS(app)

# --- Configuration ---
TEMP_VIDEO_DIR = 'temp_videos'
MAX_VIDEO_SIZE_MB = 1000 # Increased to 1GB for more flexible processing
MAX_VIDEO_SIZE_BYTES = MAX_VIDEO_SIZE_MB * 1024 * 1024

if not os.path.exists(TEMP_VIDEO_DIR):
    os.makedirs(TEMP_VIDEO_DIR)

# --- Frontend HTML (embedded directly into Python for a single-file solution) ---
# IMPORTANT: The JavaScript API_ENDPOINT and download_urls are now relative,
# which allows the browser to automatically use the correct domain on Render.
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VideoShaper - YouTube Shorts Converter</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&family=Roboto:wght@400;500&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" integrity="sha512-Fo3rlrZj/k7ujmOfEX3L5qT4uE5T7zIq4v+n+5i2TzQzF+Bv4M3zB9y3t5R7E/D0FzP4/7zLz6t2Rz6k5vB9t6w==" crossorigin="anonymous" referrerpolicy="no-referrer" />
    <style>
        :root {
            --primary-purple: #6c5ce7; /* Soft Purple */
            --secondary-blue: #0984e3; /* Bright Blue */
            --accent-yellow: #fdcb6e; /* Warm Yellow */
            --light-gray: #f5f6fa;
            --medium-gray: #dfe4ea;
            --dark-text: #2d3436;
            --light-text: #ffffff;
            --success-green: #2ecc71;
            --error-red: #e74c3c;
            --warning-orange: #f39c12;

            --header-height: 60px;
            --footer-height: 50px;

            --border-radius-sm: 8px;
            --border-radius-md: 12px;

            --shadow-light: rgba(0, 0, 0, 0.08);
            --shadow-medium: rgba(0, 0, 0, 0.15);
            --shadow-deep: rgba(0, 0, 0, 0.25);
        }

        /* Base Styles & Typography */
        body {
            font-family: 'Roboto', sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, var(--light-gray) 0%, var(--medium-gray) 100%);
            color: var(--dark-text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        h1, h2, h3 {
            font-family: 'Montserrat', sans-serif;
            color: var(--dark-text);
            margin-top: 0;
            margin-bottom: 1rem;
        }

        h1 { font-size: 2.8rem; font-weight: 700; margin-bottom: 2rem; }
        h2 { font-size: 1.8rem; font-weight: 600; margin-bottom: 1.5rem; }
        h3 { font-size: 1.3rem; font-weight: 600; margin-bottom: 1rem; }

        p {
            font-size: 1rem;
            line-height: 1.7;
        }

        small {
            display: block;
            margin-top: 0.5rem;
            color: #7f8c8d;
            font-size: 0.85em;
        }

        /* Layout Structure */
        .header {
            background: var(--primary-purple);
            padding: 1rem 2rem;
            color: var(--light-text);
            box-shadow: 0 2px 10px var(--shadow-deep);
            z-index: 1000;
            position: sticky;
            top: 0;
        }

        .header-content {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            font-family: 'Montserrat', sans-serif;
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--light-text);
            margin: 0;
        }

        .main-content {
            flex-grow: 1;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .footer {
            background: var(--dark-text);
            color: var(--light-text);
            padding: 1rem 2rem;
            text-align: center;
            font-size: 0.9rem;
            box-shadow: 0 -2px 10px var(--shadow-deep);
            margin-top: auto; /* Pushes footer to bottom */
        }

        /* Container Styling */
        .container {
            max-width: 800px; /* Wider container */
            width: 100%;
            background: var(--light-text);
            padding: 40px 50px; /* More generous padding */
            border-radius: var(--border-radius-md);
            box-shadow: 0 15px 40px var(--shadow-medium);
            border: 1px solid var(--medium-gray);
            transition: all 0.3s ease-in-out;
        }

        .intro-section {
            text-align: center;
            margin-bottom: 3rem;
        }

        .intro-section h1 {
            color: var(--primary-purple);
            font-size: 3.2rem;
            margin-bottom: 1rem;
        }

        .intro-section p {
            max-width: 600px;
            margin: 0 auto;
            color: #555;
            font-size: 1.1rem;
        }

        /* Form Elements */
        .form-group {
            margin-bottom: 1.5rem; /* Increased spacing */
        }

        label {
            display: block;
            margin-bottom: 0.6rem;
            font-weight: 600;
            color: var(--dark-text);
            font-size: 1.05rem;
        }

        input[type="url"],
        input[type="number"],
        input[type="text"],
        select {
            width: 100%;
            padding: 0.8rem 1rem;
            border: 1px solid var(--medium-gray);
            border-radius: var(--border-radius-sm);
            font-size: 1rem;
            color: var(--dark-text);
            background-color: var(--light-gray);
            box-shadow: inset 0 1px 3px var(--shadow-light);
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
            box-sizing: border-box;
        }

        input[type="url"]:focus,
        input[type="number"]:focus,
        input[type="text"]:focus,
        select:focus {
            border-color: var(--primary-purple);
            box-shadow: 0 0 0 3px rgba(108, 92, 231, 0.25); /* Focus ring */
            outline: none;
            background-color: var(--light-text);
        }

        /* Buttons */
        .btn-primary {
            width: 100%;
            padding: 1rem 1.5rem;
            background: linear-gradient(45deg, var(--primary-purple) 0%, var(--secondary-blue) 100%);
            color: var(--light-text);
            border: none;
            border-radius: var(--border-radius-sm);
            font-size: 1.15rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 6px 20px rgba(108, 92, 231, 0.3);
            margin-top: 1.5rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .btn-primary:hover {
            background: linear-gradient(45deg, var(--secondary-blue) 0%, var(--primary-purple) 100%);
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(108, 92, 231, 0.4);
        }

        .btn-primary:active {
            transform: translateY(0);
            box-shadow: 0 4px 15px rgba(108, 92, 231, 0.2);
        }

        .btn-primary:disabled {
            background: #cccccc;
            cursor: not-allowed;
            box-shadow: none;
            transform: none;
            opacity: 0.7;
        }

        /* Advanced Options Toggle */
        .advanced-options-toggle {
            display: flex;
            align-items: center;
            margin-top: 1rem;
            margin-bottom: 1.5rem;
            color: var(--primary-purple);
            cursor: pointer;
            font-weight: 600;
            font-size: 0.95em;
            transition: color 0.3s ease;
        }
        .advanced-options-toggle:hover {
            color: var(--secondary-blue);
        }
        .advanced-options-toggle input[type="checkbox"] {
            margin-right: 10px;
            min-width: 18px; /* Larger checkbox */
            min-height: 18px;
            accent-color: var(--primary-purple);
            cursor: pointer;
        }
        .advanced-options-toggle label {
            margin-bottom: 0;
            cursor: pointer;
            font-size: 0.95em; /* Adjust to match checkbox text */
        }
        .advanced-options-container {
            border-top: 1px dashed var(--medium-gray);
            padding-top: 1.5rem;
            margin-top: 1.5rem;
            display: grid; /* Use grid for better layout of form groups */
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); /* 2 columns on wider screens */
            gap: 1.5rem; /* Spacing between grid items */
            transition: all 0.5s ease-out;
            overflow: hidden;
            max-height: 0;
            opacity: 0;
            transform: translateY(10px);
            pointer-events: none; /* Disable interaction when hidden */
        }
        .advanced-options-container.active {
            max-height: 1000px; /* Arbitrary large value */
            opacity: 1;
            transform: translateY(0);
            pointer-events: all; /* Enable interaction when active */
        }

        /* Status Messages */
        .status-message {
            margin-top: 2rem;
            padding: 1rem 1.5rem;
            border-radius: var(--border-radius-sm);
            text-align: center;
            font-weight: 500;
            animation: fadeIn 0.5s ease-out;
            display: flex; /* For icon alignment */
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
        .status-message.loading {
            background-color: #fff8e1;
            color: var(--warning-orange);
            border: 1px solid #ffecb3;
        }
        .status-message.success {
            background-color: #e8f5e9;
            color: var(--success-green);
            border: 1px solid #c8e6c9;
        }
        .status-message.error {
            background-color: #ffebee;
            color: var(--error-red);
            border: 1px solid #ffcdd2;
        }

        /* Download Links */
        .download-links {
            margin-top: 2rem;
            padding-top: 1.5rem;
            border-top: 1px dashed var(--medium-gray);
            animation: slideInUp 0.7s ease-out;
        }
        .download-links h3 {
            color: var(--primary-purple);
            font-size: 1.6rem;
            text-align: center;
            margin-bottom: 1.5rem;
        }
        .download-links p {
            text-align: center;
            margin-bottom: 1.5rem;
            color: #555;
        }
        .download-links ul {
            list-style: none;
            padding: 0;
            display: grid;
            gap: 0.8rem;
        }
        .download-links li {
            background-color: var(--light-gray);
            padding: 0.8rem 1.2rem;
            border-radius: var(--border-radius-sm);
            border: 1px solid var(--medium-gray);
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: background-color 0.2s ease, transform 0.2s ease;
            box-shadow: 0 2px 10px var(--shadow-light);
        }
        .download-links li:hover {
            background-color: #e0e7ed;
            transform: translateY(-2px);
            box-shadow: 0 4px 15px var(--shadow-light);
        }
        .download-links a {
            color: var(--primary-purple);
            text-decoration: none;
            font-weight: 500;
            flex-grow: 1;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .download-links a:hover {
            text-decoration: underline;
            color: var(--secondary-blue);
        }
        .download-links a i {
            font-size: 1.1em;
            color: var(--secondary-blue);
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
            .header-content, .footer {
                padding: 1rem 1.5rem;
            }
            .logo {
                font-size: 1.5rem;
            }
            .main-content {
                padding: 30px 15px;
            }
            .container {
                padding: 30px;
                border-radius: 10px;
            }
            .intro-section h1 {
                font-size: 2.5rem;
            }
            .intro-section p {
                font-size: 1rem;
            }
            h1 { font-size: 2.2rem; margin-bottom: 1.5rem; }
            h2 { font-size: 1.6rem; margin-bottom: 1.2rem; }
            h3 { font-size: 1.2rem; margin-bottom: 0.8rem; }
            .form-group {
                margin-bottom: 1rem;
            }
            label {
                font-size: 1rem;
                margin-bottom: 0.5rem;
            }
            input[type="url"], input[type="number"], input[type="text"], select, .btn-primary {
                font-size: 0.95rem;
                padding: 0.7rem 1rem;
            }
            .btn-primary {
                margin-top: 1rem;
            }
            .advanced-options-container {
                grid-template-columns: 1fr; /* Single column on smaller screens */
                gap: 1rem;
            }
            .download-links h3 {
                font-size: 1.4rem;
            }
            .download-links p {
                font-size: 0.95rem;
            }
        }

        @media (max-width: 480px) {
            .header-content, .footer {
                padding: 0.8rem 1rem;
            }
            .logo {
                font-size: 1.3rem;
            }
            .main-content {
                padding: 20px 10px;
            }
            .container {
                padding: 20px;
                border-radius: 8px;
            }
            .intro-section h1 {
                font-size: 2rem;
            }
            .intro-section p {
                font-size: 0.9rem;
            }
            h1 { font-size: 1.8rem; margin-bottom: 1.2rem; }
            h2 { font-size: 1.4rem; margin-bottom: 1rem; }
            h3 { font-size: 1.1rem; margin-bottom: 0.7rem; }
            .advanced-options-toggle label {
                font-size: 0.9em;
            }
            .status-message {
                padding: 0.8rem 1rem;
                font-size: 0.9em;
            }
            .download-links li {
                padding: 0.7rem 1rem;
                font-size: 0.9em;
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1 class="logo">VideoShaper</h1>
            <!-- Navigation could go here for a multi-page site -->
        </div>
    </header>

    <main class="main-content">
        <div class="container">
            <div class="intro-section">
                <h1>Transform Your Videos into Engaging Shorts!</h1>
                <p>Easily convert any YouTube video into short, shareable clips. Download full videos or specific segments, then slice them into custom-duration shorts with advanced control over resolution, bitrate, and codec.</p>
            </div>

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
                    <label for="toggleAdvancedOptions"><i class="fas fa-sliders-h"></i> Show Advanced Options</label>
                </div>

                <div id="advancedOptions" class="advanced-options-container">
                    <h2>Customization Settings</h2>
                    <div class="form-group">
                        <label for="downloadStartTime">Download Start Time:</label>
                        <input type="text" id="downloadStartTime" placeholder="e.g., 00:01:30 or 90">
                        <small>Optional: Start download from this time (HH:MM:SS or seconds).</small>
                    </div>
                    <div class="form-group">
                        <label for="downloadEndTime">Download End Time:</label>
                        <input type="text" id="downloadEndTime" placeholder="e.g., 00:05:00 or 300">
                        <small>Optional: End download at this time (HH:MM:SS or seconds).</small>
                    </div>
                    <div class="form-group">
                        <label for="outputResolution">Output Resolution:</label>
                        <select id="outputResolution">
                            <option value="">Original (no change)</option>
                            <option value="1920x1080">1080p (16:9)</option>
                            <option value="1080x1920">1080p Portrait (9:16) - Ideal for Shorts</option>
                            <option value="1280x720">720p (16:9)</option>
                            <option value="720x1280">700p Portrait (9:16)</option>
                            <option value="854x480">480p (16:9)</option>
                            <option value="480x854">480p Portrait (9:16)</option>
                        </select>
                        <small>Choose resolution. Portrait options are optimized for Shorts. Note: May involve cropping.</small>
                    </div>
                    <div class="form-group">
                        <label for="videoBitrate">Video Bitrate (kbps):</label>
                        <input type="number" id="videoBitrate" value="" placeholder="e.g., 2000 (for 2Mbps)">
                        <small>Higher bitrate = better quality, larger file. Leave empty for default (e.g., 2000-5000 for 1080p).</small>
                    </div>
                    <div class="form-group">
                        <label for="audioBitrate">Audio Bitrate (kbps):</label>
                        <input type="number" id="audioBitrate" value="" placeholder="e.g., 128">
                        <small>Audio quality. Leave empty for default (e.g., 128, 192, 256).</small>
                    </div>
                    <div class="form-group">
                        <label for="videoCodec">Video Codec:</label>
                        <select id="videoCodec">
                            <option value="libx264">H.264 (Default, widely compatible)</option>
                            <option value="libx265">H.265 / HEVC (More efficient, smaller files, less compatible)</option>
                        </select>
                        <small>Choose video compression. H.264 for compatibility, H.265 for efficiency.</small>
                    </div>
                </div>

                <button type="submit" id="convertButton" class="btn-primary">Convert to Shorts</button>
            </form>

            <div id="status" class="status-message" style="display: none;"></div>
            <div id="downloadLinks" class="download-links" style="display: none;">
                <h3><i class="fas fa-cloud-download-alt"></i> Your Shorts are Ready!</h3>
                <p>Click on the links below to download your video segments.</p>
                <ul>
                    <!-- Download links will be inserted here by JavaScript -->
                </ul>
            </div>
        </div>
    </main>

    <footer class="footer">
        <p>&copy; 2025 VideoShaper. All rights reserved.</p>
    </footer>

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

            // IMPORTANT: API_ENDPOINT is now relative, so it will work on Render's domain.
            const API_ENDPOINT = '/convert';

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
                    displayStatus('<i class="fas fa-exclamation-circle"></i> Please provide a valid YouTube URL and a slice duration of at least 5 seconds.', 'error');
                    return;
                }

                convertButton.disabled = true;
                convertButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

                displayStatus('<i class="fas fa-hourglass-half"></i> Processing your video... This may take a while depending on video length, server load, and chosen quality settings (re-encoding takes longer).', 'loading');
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
                            displayStatus('<i class="fas fa-check-circle"></i> Video successfully processed! Your shorts are ready.', 'success');
                            result.downloadUrls.forEach((url, index) => {
                                const listItem = document.createElement('li');
                                const link = document.createElement('a');
                                link.href = url; // These URLs are now relative from the backend
                                link.innerHTML = `<i class="fas fa-film"></i> Short Segment ${index + 1} (${sliceDuration}s)`;
                                link.download = `youtube_short_segment_${index + 1}.mp4`;
                                listItem.appendChild(link);
                                downloadLinksList.appendChild(listItem);
                            });
                            downloadLinksDiv.style.display = 'block';
                        } else if (result.message) {
                            displayStatus(`<i class="fas fa-info-circle"></i> Processing finished: ${result.message}`, 'success');
                        } else {
                            displayStatus('<i class="fas fa-exclamation-circle"></i> Processing finished, but no download links were returned.', 'error');
                        }
                    } else {
                        displayStatus(`<i class="fas fa-times-circle"></i> Error: ${result.message || 'Something went wrong on the server.'}`, 'error');
                    }
                } catch (error) {
                    console.error('Fetch error:', error);
                    displayStatus(`<i class="fas fa-times-circle"></i> Network error or server unavailable: ${error.message}. Please ensure your backend service is running.`, 'error');
                } finally {
                    convertButton.disabled = false;
                    convertButton.innerHTML = 'Convert to Shorts';
                }
            });

            function displayStatus(message, type) {
                statusDiv.innerHTML = message;
                statusDiv.className = `status-message ${type}`;
                statusDiv.style.display = 'flex'; // Use flex for icon alignment
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
    video_codec = data.get('video_codec', 'libx264') # Default to libx264 if not specified

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
    if output_resolution and 'x' not in output_resolution and output_resolution not in ['original', '']:
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
                '-avoid_negative_ts', 'make_zero',
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
                if output_resolution and output_resolution not in ['original', '']:
                    width, height = map(int, output_resolution.split('x'))
                    # This filter scales to fit *within* the target dimensions while maintaining aspect ratio,
                    # then crops to exactly the target dimensions (center crop).
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
            # IMPORTANT: Return relative URLs so they work on the deployed domain
            download_urls.append(f"/download/{session_id}/{output_slice_filename}")

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

    return send_from_directory(
        directory=os.path.join(TEMP_VIDEO_DIR, session_id),
        path=filename,
        as_attachment=True
    )

if __name__ == '__main__':
    # Only run in debug mode locally. Render will use Gunicorn.
    app.run(debug=True, port=os.environ.get('PORT', 5000))
