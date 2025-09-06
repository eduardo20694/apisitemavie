import os, uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import psycopg2

load_dotenv()

app = Flask(__name__)
CORS(app)  # ou limitar origins

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 100))
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'webm'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS arquivos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Arquivo sem nome"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": f"Arquivo não permitido. Permitidos: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    filename = f"{uuid.uuid4().hex}_{file.filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    cursor.execute("INSERT INTO arquivos (nome, tipo) VALUES (%s, %s)", (filename, file.content_type))
    conn.commit()

    return jsonify({"message": "Arquivo enviado com sucesso!", "filename": filename})

@app.route("/galeria", methods=["GET"])
def listar_arquivos():
    tipo = request.args.get("tipo")
    if tipo:
        cursor.execute("SELECT * FROM arquivos WHERE tipo LIKE %s ORDER BY id ASC", (f"{tipo}%",))
    else:
        cursor.execute("SELECT * FROM arquivos ORDER BY id ASC")
    arquivos = cursor.fetchall()
    return jsonify(arquivos)

@app.route("/uploads/<path:filename>", methods=["GET"])
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/delete/<int:id>", methods=["DELETE"])
def deletar_arquivo(id):
    cursor.execute("SELECT nome FROM arquivos WHERE id=%s", (id,))
    arquivo = cursor.fetchone()
    if not arquivo:
        return jsonify({"error": "Arquivo não encontrado"}), 404

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], arquivo[0])
    if os.path.exists(filepath):
        os.remove(filepath)

    cursor.execute("DELETE FROM arquivos WHERE id=%s", (id,))
    conn.commit()
    return jsonify({"message": "Arquivo removido com sucesso!"})

@app.route("/delete_all", methods=["DELETE"])
def deletar_todos():
    cursor.execute("SELECT nome FROM arquivos")
    arquivos = cursor.fetchall()
    for arquivo in arquivos:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], arquivo[0])
        if os.path.exists(filepath):
            os.remove(filepath)

    cursor.execute("DELETE FROM arquivos")
    conn.commit()
    return jsonify({"message": "Todos os arquivos foram removidos!"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
