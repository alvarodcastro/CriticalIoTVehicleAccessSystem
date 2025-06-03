from ultralytics import YOLO
from flask import Flask, request, Response, jsonify, render_template
import io
from PIL import Image
import urllib.request

# Cargar modelo YOLO
model = YOLO("yolov8m.pt")

# Inicializar Flask
app = Flask(__name__)

def encode_image_pil(image):
    """Convierte un array NumPy a una imagen JPEG en bytes usando PIL."""

    if image.shape[2] == 3:  # Si la imagen tiene 3 canales (RGB/BGR)
        image = image[..., ::-1]  # Invierte los canales para convertir de BGR a RGB
    
    pil_img = Image.fromarray(image)
    img_byte_arr = io.BytesIO() # Creamos un buffer de bytes en memoria
    pil_img.save(img_byte_arr, format="JPEG")  # Guardamos como JPEG
    return img_byte_arr.getvalue()

@app.route('/api/test', methods=['POST'])
def detect():
    img = request.files["image"].read()
    pil_img = Image.open(io.BytesIO(img)).convert("RGB")  # Convertir a PIL RGB
    results = model(pil_img)
    
    res_img = results[0].plot()  # Imagen con detecciones
    img_encoded = encode_image_pil(res_img)  # Convertir a JPEG con PIL

    return Response(response=img_encoded, status=200, mimetype="image/jpeg")

@app.route('/api/test2', methods=['GET'])
def detect_from_url():
    image_url = request.args.get('image')
    if not image_url:
        return jsonify({"error": "URL image not provided"}), 400

    try:
        resp = urllib.request.urlopen(image_url)  # Descargar imagen
        pil_img = Image.open(io.BytesIO(resp.read())).convert("RGB")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    results = model(pil_img)
    res_img = results[0].plot()
    img_encoded = encode_image_pil(res_img)

    return Response(response=img_encoded, status=200, mimetype="image/jpeg")

@app.route('/api/test3', methods=['POST'])
def detect_from_binary():
    try:
        img = request.get_data()
        pil_img = Image.open(io.BytesIO(img)).convert("RGB")
    except Exception as e:
        return jsonify({"error": f"No se pudo leer la imagen: {str(e)}"}), 400

    results = model(pil_img)
    res_img = results[0].plot()
    img_encoded = encode_image_pil(res_img)

    return Response(response=img_encoded, status=200, mimetype="image/jpeg")

@app.route("/upload", methods=["GET", "POST"])
def upload_image():
    return render_template("public/upload.html")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000)
