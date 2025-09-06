import os, uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import psycopg2

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configurações
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

def get_conn_cursor():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    return conn, cursor

# Cria tabela se não existir (agora com descrição)
conn, cursor = get_conn_cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS arquivos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    descricao TEXT DEFAULT '',
    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()
cursor.close()
conn.close()

# -------------------- ROTAS --------------------

# Upload de arquivo (agora com descrição)
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    descricao = request.form.get("descricao", "")  # pega a descrição
    if file.filename == "":
        return jsonify({"error": "Arquivo sem nome"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": f"Arquivo não permitido. Permitidos: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    filename = f"{uuid.uuid4().hex}_{file.filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    conn, cursor = get_conn_cursor()
    cursor.execute(
        "INSERT INTO arquivos (nome, tipo, descricao) VALUES (%s, %s, %s)",
        (filename, file.content_type, descricao)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Arquivo enviado com sucesso!", "filename": filename, "descricao": descricao})

# Listar arquivos (agora retornando a descrição)
@app.route("/galeria", methods=["GET"])
def listar_arquivos():
    tipo = request.args.get("tipo")
    conn, cursor = get_conn_cursor()
    if tipo:
        cursor.execute("SELECT * FROM arquivos WHERE tipo LIKE %s ORDER BY id ASC", (f"{tipo}%",))
    else:
        cursor.execute("SELECT * FROM arquivos ORDER BY id ASC")
    arquivos = cursor.fetchall()
    cursor.close()
    conn.close()
    # Retorna lista de dicionários com id, nome, tipo, descricao e data
    return jsonify([{
        "id": a[0],
        "nome": a[1],
        "tipo": a[2],
        "descricao": a[3],
        "data": a[4].isoformat()
    } for a in arquivos])

# Servir arquivos
@app.route("/uploads/<path:filename>", methods=["GET"])
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Deletar arquivo por ID
@app.route("/delete/<int:id>", methods=["DELETE"])
def deletar_arquivo(id):
    conn, cursor = get_conn_cursor()
    cursor.execute("SELECT nome FROM arquivos WHERE id=%s", (id,))
    arquivo = cursor.fetchone()
    if not arquivo:
        cursor.close()
        conn.close()
        return jsonify({"error": "Arquivo não encontrado"}), 404

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], arquivo[0])
    if os.path.exists(filepath):
        os.remove(filepath)

    cursor.execute("DELETE FROM arquivos WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Arquivo removido com sucesso!"})

# Deletar todos os arquivos
@app.route("/delete_all", methods=["DELETE"])
def deletar_todos():
    conn, cursor = get_conn_cursor()
    cursor.execute("SELECT nome FROM arquivos")
    arquivos = cursor.fetchall()
    for arquivo in arquivos:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], arquivo[0])
        if os.path.exists(filepath):
            os.remove(filepath)

    cursor.execute("DELETE FROM arquivos")
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Todos os arquivos foram removidos!"})

# -------------------- RUN --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
