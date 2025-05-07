import cv2
import numpy as np
from ultralytics import YOLO
from paddleocr import PaddleOCR
import re
import os

# Initialize models
model = YOLO(os.path.join(os.path.dirname(__file__), "models", "best.pt"))
ocr = PaddleOCR(use_angle_cls=True, lang="en")

def extract_license_plate(ocr_result, confidence_threshold=0.7):
    """
    Extracts and cleans the text OCR with highest confidence.
    """
    if not ocr_result or not ocr_result[0]:
        return "No plate detected", 0.0

    best_text = ""
    max_confidence = 0

    for detection in ocr_result[0]:
        text = detection[1][0]
        confidence = detection[1][1]

        if confidence > confidence_threshold and confidence > max_confidence:
            best_text = text
            max_confidence = confidence

    cleaned_text = re.sub(r'[^A-Za-z0-9]', '', best_text).upper()
    return cleaned_text if cleaned_text else "No plate detected", max_confidence

def detect_and_recognize(image):
    """
    Detects and recognizes license plates from an image using YOLO and PaddleOCR.
    
    Args:
        image: numpy array of the image
        
    Returns:
        tuple: (processed_image, plate_text, confidence_score)
    """
    if isinstance(image, bytes):
        # Convert bytes to numpy array
        nparr = np.frombuffer(image, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    original_image = image.copy()
    detected_text = "No plate detected"
    confidence_score = 0.0

    # YOLO detection
    results = model.predict(source=image, save=False)
    detections = results[0].boxes.data

    if len(detections) == 0:
        return original_image, detected_text, confidence_score

    for detection in detections[:1]:  # Only process the first detection
        x1, y1, x2, y2, conf, cls = detection[:6]
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

        # Extract plate region
        plate_image = image[y1:y2, x1:x2]

        # OCR on plate region
        ocr_result = ocr.ocr(plate_image, cls=True)
        detected_text, confidence_score = extract_license_plate(ocr_result)

        if detected_text != "No plate detected":
            # Draw bounding box and text
            cv2.rectangle(original_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(original_image, detected_text, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return original_image, detected_text, confidence_score

def save_debug_image(image, filename):
    """
    Saves a debug image with detection visualization
    """
    debug_dir = os.path.join(os.path.dirname(__file__), "static", "debug_images")
    os.makedirs(debug_dir, exist_ok=True)
    filepath = os.path.join(debug_dir, filename)
    cv2.imwrite(filepath, image)
    return os.path.join("debug_images", filename)