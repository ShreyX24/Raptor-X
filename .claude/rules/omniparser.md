# OmniParser Server

Computer Vision service for screen parsing and UI element detection.

## Architecture

- **Entry Point**: `Omniparser server/omnitool/omniparserserver/omniparserserver.py`
- **Port**: 8000-8004 (configurable, use 8100 to avoid conflicts)
- **Framework**: FastAPI with Uvicorn
- **GPU**: CUDA support for faster inference

## Key Files

| File | Purpose |
|------|---------|
| `omnitool/omniparserserver/omniparserserver.py` | FastAPI server |
| `util/omniparser.py` | Core parsing logic |
| `weights/` | Pre-trained model weights |
| `start_omni_server.bat` | Windows startup script |

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/parse/` | Parse screenshot for UI elements |
| GET | `/probe/` | Health check |

## Parse Request

```json
{
  "base64_image": "...",
  "box_threshold": 0.05,
  "iou_threshold": 0.1,
  "use_paddleocr": true,
  "text_threshold": null,
  "use_local_semantics": null,
  "scale_img": null,
  "imgsz": null
}
```

## Parse Response

```json
{
  "som_image_base64": "...",
  "parsed_content_list": [
    {
      "type": "text",
      "content": "Play",
      "bbox": [100, 200, 150, 230]
    }
  ],
  "latency": 1.234,
  "config_used": {"BOX_TRESHOLD": 0.05}
}
```

## Features

### UI Element Detection
- YOLO-based icon/button detection
- Florence2 caption model for labeling
- Bounding box extraction

### OCR
- PaddleOCR (recommended) or EasyOCR
- Text extraction from screenshots
- Configurable confidence thresholds

### Semantic Understanding
- Optional caption model for icon labeling
- Useful for unlabeled UI elements

## Startup Options

```bash
python omniparserserver.py \
  --host 0.0.0.0 \
  --port 8100 \
  --device cuda \
  --use_paddleocr \
  --no-reload \
  --BOX_TRESHOLD 0.05 \
  --IOU_THRESHOLD 0.1
```

| Option | Default | Purpose |
|--------|---------|---------|
| `--host` | 0.0.0.0 | Bind address |
| `--port` | 8000 | Service port |
| `--device` | cpu | Device (cpu/cuda) |
| `--use_paddleocr` | false | Use PaddleOCR |
| `--no-reload` | false | Disable uvicorn auto-reload (required for Service Manager) |
| `--BOX_TRESHOLD` | 0.05 | Detection confidence |
| `--IOU_THRESHOLD` | 0.1 | NMS overlap threshold |

### Important: --no-reload Flag
When running via Service Manager, always use `--no-reload`:
- **With reload (default)**: Uvicorn spawns a reloader process (parent) and server process (child). Request logs go to the child's stdout, which isn't captured by Service Manager.
- **With --no-reload**: Single process handles everything, all logs visible in Service Manager.

## Model Weights

Located in `weights/` directory:
- `icon_detect/model.pt` - YOLO icon detection
- `icon_caption_florence/` - Florence2 captioning

## Performance

- Model loading: ~30 seconds on first request
- Parse time: 1-3 seconds per image (GPU)
- Parse time: 5-10 seconds per image (CPU)

## Integration

### Via Queue Service (Recommended)
```python
response = requests.post("http://localhost:9000/parse", json={
    "base64_image": screenshot_b64
})
```

### Direct (Not Recommended)
```python
response = requests.post("http://localhost:8100/parse/", json={
    "base64_image": screenshot_b64
})
```

## Dependencies

- **Depends on**: None (standalone)
- **Depended by**: Queue Service, Gemma Backend

## Common Issues

### Port 8000 Occupied
Use alternative port: `--port 8100`

### Model Not Found
Run from correct directory:
```bash
cd "Omniparser server/omnitool/omniparserserver"
python omniparserserver.py --use_paddleocr
```

### Reload Mode Issues
Don't use `reload=True` in production - causes import problems.
Instead: `uvicorn.run(app, host='0.0.0.0', port=8100)`

## Common Modifications

### Adjust detection sensitivity
1. Modify `--BOX_TRESHOLD` (lower = more detections)
2. Modify `--IOU_THRESHOLD` (higher = less overlap removal)

### Add new parse options
1. Add to `ParseRequest` model in `omniparserserver.py`
2. Pass to `omniparser.parse()` method

## Recent Changes

| Date | Change |
|------|--------|
| 2026-01-05 | Added --no-reload CLI flag for Service Manager compatibility |
| 2024-12-31 | Added per-request config overrides |
| 2024-12-31 | Added Steam dialog detection support |
