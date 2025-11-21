import json
import os
import time
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename
from collections import defaultdict

app = Flask(__name__)
DB_FILE = 'caderno_ptm_db.json'
REFERENCIAS_FILE = 'referencias.json'

# --- CONFIGURAÇÃO DE UPLOAD ---
UPLOAD_FOLDER = 'uploads'
# Cria a pasta se ela não existir
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# NOTA: Removida a linha app.config['MAX_CONTENT_LENGTH'] para não impor limite.
# ------------------------------

# --- FUNÇÕES DE CARREGAMENTO E SALVAMENTO GERAL ---

def load_data():
    """Carrega os registros do caderno."""
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except json.JSONDecodeError:
        print("Aviso: Arquivo DB vazio ou inválido. Iniciando com lista vazia.")
        return []


def save_data(data):
    """Salva os registros no caderno."""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_referencias():
    """Carrega as referências de NM/Descrição."""
    try:
        if os.path.exists(REFERENCIAS_FILE):
            with open(REFERENCIAS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except json.JSONDecodeError:
        print("Aviso: Arquivo de Referências vazio ou inválido. Iniciando com lista vazia.")
        return []


def save_referencias(data):
    """Salva as referências de NM/Descrição."""
    with open(REFERENCIAS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# --- ROTAS DA APLICAÇÃO ---

@app.route('/')
def index():
    """Rota principal que serve o frontend."""
    return render_template('index.html')


# -------------------------------------------------------------
# ROTA DE UPLOAD DE ARQUIVOS
# -------------------------------------------------------------
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Recebe um arquivo, salva no disco e retorna o nome único."""
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nome de arquivo inválido.'}), 400

    if file:
        filename = secure_filename(file.filename)
        # Usa timestamp para garantir um nome de arquivo único
        unique_filename = f"{int(time.time())}_{filename}"

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        try:
            file.save(file_path)
            # Retorna o nome do arquivo salvo (string) e o nome original
            return jsonify({'filename': unique_filename, 'original_name': filename}), 200
        except Exception as e:
            return jsonify({'error': f'Falha ao salvar o arquivo no disco: {str(e)}'}), 500

    return jsonify({'error': 'Falha no processamento do arquivo.'}), 500


# -------------------------------------------------------------
# ROTA PARA SERVIR ARQUIVOS SALVOS
# -------------------------------------------------------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve os arquivos estáticos da pasta de uploads."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# -------------------------------------------------------------
# ROTA PRINCIPAL DE REGISTROS (CRUD)
# -------------------------------------------------------------
@app.route('/api/registros', methods=['GET', 'POST', 'DELETE'])
def handle_registros():
    registros = load_data()

    if request.method == 'GET':
        return jsonify(registros)

    if request.method == 'POST':
        data = request.get_json()

        if 'id' in data and data['id'] != '0':
            # --- UPDATE (Confirmação de Entrega) ---
            for i, reg in enumerate(registros):
                if str(reg['id']) == data['id']:
                    # Atualiza campos de confirmação
                    registros[i]['data_coleta'] = data.get('data_coleta', 'Pendente')
                    registros[i]['nome_motorista'] = data.get('nome_motorista', '')
                    registros[i]['nota_fiscal'] = data.get('nota_fiscal', '')

                    # Salva apenas a lista de NOMES DOS ARQUIVOS (strings)
                    if 'anexos' in data:
                        registros[i]['anexos'] = data['anexos']

                    save_data(registros)
                    return jsonify({'message': f"Registro {data['id']} atualizado com sucesso."}), 200

            return jsonify({'error': 'Registro não encontrado para atualização.'}), 404
        else:
            # --- CREATE (Cadastro de Saída) ---

            # 1. Validação de duplicidade (NM + N° Doc. + Item)
            key = (data['num_doc_saida'], data['item_saida'])
            if any((r['num_doc_saida'], r['item_saida']) == key for r in registros):
                return jsonify({
                                   'error': f"O par N° Doc ({data['num_doc_saida']}) e Item ({data['item_saida']}) já existe no cadastro."}), 409

            # 2. Cria novo registro
            novo_id = max([r['id'] for r in registros] or [0]) + 1
            novo_registro = {
                'id': novo_id,
                'nm_saida': data['nm_saida'],
                'descricao_saida': data['descricao_saida'],
                'quantidade_saida': data['quantidade_saida'],
                'destino_saida': data['destino_saida'],
                'responsavel_entrega': data['responsavel_entrega'],
                'data_doc_saida': data['data_doc_saida'],
                'deposito_saida': data['deposito_saida'],
                'num_doc_saida': data['num_doc_saida'],
                'item_saida': data['item_saida'],

                # Campos de Confirmação (Início)
                'data_coleta': 'Pendente',
                'nome_motorista': '',
                'nota_fiscal': '',
                'anexos': [],  # Lista de nomes de arquivos
            }
            registros.append(novo_registro)
            save_data(registros)
            return jsonify({'message': 'Registro cadastrado com sucesso!', 'id': novo_id}), 201

    if request.method == 'DELETE':
        # Não implementado para esta versão
        return jsonify({'message': 'Ainda não implementado'}), 501

    return jsonify({'error': 'Método não permitido'}), 405


# -------------------------------------------------------------
# ROTA DE REFERÊNCIAS (NM/DESC)
# -------------------------------------------------------------
@app.route('/api/referencias', methods=['GET', 'POST'])
def handle_referencias():
    referencias = load_referencias()

    if request.method == 'GET':
        return jsonify(referencias)

    if request.method == 'POST':
        data = request.get_json()

        if 'referencias' in data:
            # Lógica de Atualização/Criação em Massa
            nm_to_update = {ref['nm']: ref for ref in referencias}

            for new_ref in data['referencias']:
                nm_to_update[new_ref['nm']] = new_ref

            referencias = list(nm_to_update.values())
            save_referencias(referencias)
            return jsonify({'message': 'Referências atualizadas com sucesso!'}), 200

    return jsonify({'error': 'Método não permitido'}), 405


@app.route('/api/referencias/<nm>', methods=['DELETE'])
def delete_referencia(nm):
    referencias = load_referencias()

    referencias_antes = len(referencias)
    referencias = [ref for ref in referencias if ref['nm'] != nm]

    if len(referencias) < referencias_antes:
        save_referencias(referencias)
        return jsonify({'message': f"Referência {nm} removida."}), 200

    return jsonify({'error': f"Referência {nm} não encontrada."}), 404


# -------------------------------------------------------------
# ROTA DE RESET GERAL
# -------------------------------------------------------------
@app.route('/api/reset', methods=['DELETE'])
def reset_data():
    """Limpa todos os registros e referências."""
    try:
        save_data([])
        save_referencias([])

        # Opcional: Remover arquivos na pasta de uploads (recomendado)
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Erro ao deletar arquivo {file_path}: {e}")

        return jsonify({'message': 'Todos os registros, referências e arquivos de uploads foram limpos.'}), 200
    except Exception as e:
        return jsonify({'error': f'Falha ao resetar os dados: {str(e)}'}), 500


# -------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
