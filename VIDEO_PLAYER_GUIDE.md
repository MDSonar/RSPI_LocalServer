# Video Player Integration Guide

## Overview
The RSPI LocalServer now offers seamless video playback directly from USB storage via the File Manager. No manual path entry needed.

## How It Works

### Option 1: Direct Play from File Manager (Recommended)
The easiest way to watch videos:

1. Open **File Manager** from the dashboard
2. Navigate to your video file (on USB)
3. Click the **▶️ Play** button next to the video file
4. Video plays instantly in an inline modal within the File Manager
5. Click **Close** to exit the modal and continue browsing

**Supported formats:** MP4, MKV, MOV, AVI, WEBM, M4V

### Option 2: Video Player App (Standalone)
For a dedicated video player experience in fullscreen:

1. Open **Video Player** from the dashboard (or install it if not present)
2. If opened from File Manager with a video selected:
   - Video auto-loads automatically (no manual input needed)
   - Manual input form is hidden
   - Click **Close** to return to browsing
3. If opened standalone:
   - Paste a relative video path (e.g., `Movies/demo.mp4`)
   - Click **Play Video**
   - Enjoy fullscreen playback

**Note:** Using the Play button in File Manager is the most user-friendly approach.

## Technical Details

### Flow Diagram
```
File Manager (UI)
    ↓
[Video File List with ▶️ Play Button]
    ↓
playVideoInline(path) function
    ↓
/api/video/stream?path=... (HTTP Range-based streaming)
    ↓
Video Modal or Player
    ↓
HTML5 Video Element (Browser Playback)
```

### API Endpoints
- **`/api/video/stream`** – Streams video with HTTP Range support for seeking
  - Query param: `path` (relative path to video file)
  - Returns: Video stream with proper Content-Type and Range headers
  - Path validation: Prevents directory traversal attacks via PathValidator
  - Supported extensions: `.mp4, .mkv, .mov, .avi, .webm, .m4v`

### Path Handling
All paths are **relative to your USB root** (same as File Manager):
- ✅ `Movies/demo.mp4`
- ✅ `Videos/Folder/movie.mkv`
- ❌ `/absolute/path/demo.mp4` (not allowed)
- ❌ `../../etc/passwd` (blocked by PathValidator)

## Performance Tips

### For Faster Playback
1. **Network:** Use wired LAN if possible; on Wi-Fi, stay close to the AP and use 5 GHz band
2. **Video Quality:** Watch at the resolution your connection supports
3. **Server Load:** Close other apps; check System Info to see available resources
4. **Storage:** Use USB 3.0 drives (faster than USB 2.0)

### For Large Files
- First video load may take a few seconds as the Pi streams the data
- Once playback starts, seeking should be smooth (thanks to HTTP Range support)
- Consider splitting large videos into chapters

## Troubleshooting

### Video doesn't play from File Manager
- Ensure the file extension is supported (see list above)
- Check that the API endpoint is working: visit `/api/video/stream?path=test.mp4` to verify connectivity
- Check System Info to ensure available memory and CPU

### Slow playback or buffering
- Check network connection (wired vs Wi-Fi quality)
- Close other devices on the network
- Try a lower-resolution or lower-bitrate video file
- Check if the Pi is under load (see System Info app)

### "File not found" error
- Verify the file path is correct (relative to USB root)
- Check that the file still exists in the File Manager
- Ensure no special characters in the filename

## Architecture

### File Manager Integration
- **Dev mode:** `/app/static/index.html` and `/app/static/filemanager.html`
- **Installed:** `/opt/rspi-localserver/apps/optional/filemanager/filemanager.html`
- Functions: `isVideoFile(name)`, `playVideoInline(path)`, `closeVideo()`

### Video Player App (Optional)
- **Dev mode:** `/apps/optional/videoplayer/videoplayer.html`
- **Installed:** `/opt/rspi-localserver/apps/optional/videoplayer/videoplayer.html`
- **Route:** `/apps/videoplayer`
- **Query support:** `?path=` auto-loads and hides manual input

### Backend (FastAPI)
- **Route:** `GET /api/video/stream`
- **File:** `/app/main.py` (lines ~280-340)
- **Features:**
  - Path validation via `FileManager.validator.safe_path()`
  - HTTP 206 Partial Content for seeking
  - Chunked streaming (256 KB chunks)
  - Content-Type detection

## Future Improvements
- Subtitle support (SRT, ASS, VTT)
- Playlist/folder playback
- Adaptive bitrate streaming (HLS/DASH)
- Thumbnail/preview generation
- Video metadata (duration, codec, resolution) display
