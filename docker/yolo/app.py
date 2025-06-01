from ultralytics import YOLO
from flask import Flask, request, Response, jsonify, render_template
import io
from PIL import Image
import urllib.request
import cv2
import numpy as np
from paddleocr import PaddleOCR
import re
import os

# Initialize models
model = YOLO("./models/best.pt")


# Initialize Flask
app = Flask(__name__)

def encode_image_pil(image):
    """Converts a NumPy array to JPEG bytes using PIL."""
    if image.shape[2] == 3:  # If image has 3 channels (RGB/BGR)
        image = image[..., ::-1]  # Invert channels to convert BGR to RGB
    
    pil_img = Image.fromarray(image)
    img_byte_arr = io.BytesIO()  # Create a bytes buffer in memory
    pil_img.save(img_byte_arr, format="JPEG")  # Save as JPEG
    return img_byte_arr.getvalue()

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
    """
    if isinstance(image, bytes):
        nparr = np.frombuffer(image, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif isinstance(image, Image.Image):
        image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    
    original_image = image.copy()
    detected_text = "No plate detected"
    confidence_score = 0.0

    # YOLO detection
    detections = []
    try:
        results = model.predict(source=image, save=False)
        if not results or len(results) == 0 or len(results[0].boxes.data) == 0:
            return original_image, detected_text, confidence_score
        detections = results[0].boxes.data
    except Exception as e:
        print(f"Error during YOLO detection: {e}")
        return original_image, detected_text, confidence_score

    if len(detections) == 0:
        return original_image, detected_text, confidence_score

    for detection in detections[:1]:  # Only process the first detection
        x1, y1, x2, y2, conf, cls = detection[:6]
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

        # Extract plate region
        plate_image = image[y1:y2, x1:x2]
        if plate_image.size == 0:
            continue

        # OCR on plate region
        try:
            ocr = PaddleOCR(use_angle_cls=True, lang="en")
            ocr_result = ocr.ocr(plate_image, cls=True)
            detected_text, confidence_score = extract_license_plate(ocr_result)
        except Exception as e:
            print(f"Error during OCR: {e}")
            continue


        if detected_text != "No plate detected":
            # Draw bounding box and text
            cv2.rectangle(original_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(original_image, detected_text, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return original_image, detected_text, confidence_score

@app.route('/api/anpr', methods=['POST'])
def anpr_detect():
    """
    API endpoint for license plate detection and recognition.
    Accepts an image file and returns both the processed image and the detected plate text.
    """
    try:
        if 'image' not in request.files:
            return jsonify({
                'error': 'No image file provided'
            }), 400

        img = request.files['image'].read()
        processed_image, plate_text, confidence = detect_and_recognize(img)
        
        # Encode the processed image
        # img_encoded = encode_image_pil(processed_image)
        
        # return Response(response=img_encoded, status=200, mimetype="image/jpeg")
        return jsonify({
            'plate_text': plate_text,
            'confidence': float(confidence),
            # 'image': img_encoded.decode('latin1')
        })

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/anpr/url', methods=['GET'])
def anpr_detect_from_url():
    """
    API endpoint for license plate detection from a URL.
    Accepts an image URL and returns both the processed image and the detected plate text.
    """
    image_url = request.args.get('image')
    print(f"Received image URL: {image_url}")
    if not image_url:
        return jsonify({"error": "URL image not provided"}), 400

    try:
        resp = urllib.request.urlopen(image_url)
        pil_img = Image.open(io.BytesIO(resp.read())).convert("RGB")
        processed_image, plate_text, confidence = detect_and_recognize(pil_img)
        
        # Encode the processed image
        # img_encoded = encode_image_pil(processed_image)
        
        # return Response(response=img_encoded, status=200, mimetype="image/jpeg")

        return jsonify({
            'plate_text': plate_text,
            'confidence': float(confidence),
            # 'image': img_encoded.decode('latin1')
        })

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000, debug=True)
