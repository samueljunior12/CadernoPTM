import json
import os
import time
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas (Vital para o Render)

# --- CONFIGURAÇÃO DE ARQUIVOS ---
DB_FILE = 'caderno_ptm_db.json'
REFERENCIAS_FILE = 'referencias.json'

# Configuração da pasta de Uploads
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Opcional: Limite de 50MB

# --- FUNÇÕES AUXILIARES (CARREGAR/SALVAR) ---

def load_data():
    """Carrega registros do arquivo JSON. Cria se não existir."""
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_data(data):
    """Salva registros no arquivo JSON."""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_referencias():
    """Carrega referências do arquivo JSON. Cria se não existir."""
    if not os.path.exists(REFERENCIAS_FILE):
        return []
    try:
        with open(REFERENCIAS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_referencias(data):
    """Salva referências no arquivo JSON."""
    with open(REFERENCIAS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- ROTAS ---

@app.route('/')
def index():
    """Serve o arquivo HTML principal."""
    return render_template('index.html')

# --- UPLOAD DE ARQUIVOS ---
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nome de arquivo inválido.'}), 400

    if file:
        try:
            filename = secure_filename(file.filename)
            # Adiciona timestamp para garantir unicidade
            unique_filename = f"{int(time.time())}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            file.save(file_path)
            
            # Retorna o nome salvo e o nome original
            return jsonify({'filename': unique_filename, 'original_name': filename}), 200
        except Exception as e:
            return jsonify({'error': f'Erro no servidor ao salvar arquivo: {str(e)}'}), 500

    return jsonify({'error': 'Erro desconhecido.'}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Rota para visualizar a imagem/pdf clicando no link."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- CRUD DE REGISTROS ---
@app.route('/api/registros', methods=['GET', 'POST', 'DELETE'])
def handle_registros():
    registros = load_data()

    if request.method == 'GET':
        return jsonify(registros)

    if request.method == 'POST':
        data = request.get_json()

        # Cenário 1: ATUALIZAÇÃO (Confirmação de Entrega)
        # Verifica se tem ID e se não é '0' (que seria novo)
        if 'id' in data and str(data['id']) != '0':
            registro_encontrado = False
            for i, reg in enumerate(registros):
                if str(reg['id']) == str(data['id']):
                    # Atualiza apenas os campos de entrega
                    registros[i]['data_coleta'] = data.get('data_coleta', 'Pendente')
                    registros[i]['nome_motorista'] = data.get('nome_motorista', '')
                    registros[i]['nota_fiscal'] = data.get('nota_fiscal', '')
                    
                    # Se houver novos anexos, atualiza a lista
                    if 'anexos' in data:
                        registros[i]['anexos'] = data['anexos']
                    
                    registro_encontrado = True
                    break
            
            if registro_encontrado:
                save_data(registros)
                return jsonify({'message': 'Registro atualizado com sucesso.'}), 200
            else:
                return jsonify({'error': 'Registro não encontrado para atualização.'}), 404

        # Cenário 2: NOVO CADASTRO (Saída)
        else:
            # Validação de Duplicidade (Mesmo Doc + Mesmo Item)
            for r in registros:
                if str(r['num_doc_saida']) == str(data['num_doc_saida']) and \
                   str(r['item_saida']) == str(data['item_saida']):
                    return jsonify({'error': f"Já existe um registro com Doc {data['num_doc_saida']} e Item {data['item_saida']}."}), 409

            # Gera novo ID
            novo_id = 1
            if registros:
                # Pega o maior ID existente e soma 1
                novo_id = max(int(r['id']) for r in registros) + 1

            novo_registro = {
                'id': str(novo_id),
                'nm_saida': data['nm_saida'],
                'descricao_saida': data['descricao_saida'],
                'quantidade_saida': data['quantidade_saida'],
                'destino_saida': data['destino_saida'],
                'responsavel_entrega': data['responsavel_entrega'],
                'data_doc_saida': data['data_doc_saida'],
                'deposito_saida': data['deposito_saida'],
                'num_doc_saida': data['num_doc_saida'],
                'item_saida': data['item_saida'],
                
                # Campos vazios iniciais
                'data_coleta': 'Pendente',
                'nome_motorista': '',
                'nota_fiscal': '',
                'anexos': []
            }
            registros.append(novo_registro)
            save_data(registros)
            return jsonify({'message': 'Cadastro realizado com sucesso!', 'id': novo_id}), 201

    return jsonify({'error': 'Método não permitido'}), 405

# --- CRUD DE REFERÊNCIAS (NM/DESCRIÇÃO) ---
@app.route('/api/referencias', methods=['GET', 'POST'])
def handle_referencias():
    referencias = load_referencias()

    if request.method == 'GET':
        return jsonify(referencias)

    if request.method == 'POST':
        data = request.get_json()

        if 'referencias' in data:
            # Cria um dicionário para facilitar a atualização (NM -> Objeto)
            nm_map = {ref['nm']: ref for ref in referencias}
            
            # Atualiza existentes ou adiciona novos
            for new_ref in data['referencias']:
                nm_map[new_ref['nm']] = new_ref
            
            # Converte de volta para lista
            nova_lista_referencias = list(nm_map.values())
            
            save_referencias(nova_lista_referencias)
            return jsonify({'message': 'Referências processadas com sucesso!'}), 200
        
        return jsonify({'error': 'Formato inválido. Esperado { "referencias": [] }'}), 400

    return jsonify({'error': 'Método não permitido'}), 405

@app.route('/api/referencias/<nm>', methods=['DELETE'])
def delete_referencia(nm):
    referencias = load_referencias()
    
    # Filtra removendo o NM especificado
    nova_lista = [ref for ref in referencias if ref['nm'] != nm]

    if len(nova_lista) < len(referencias):
        save_referencias(nova_lista)
        return jsonify({'message': f'Referência {nm} removida.'}), 200
    
    return jsonify({'error': 'Referência não encontrada.'}), 404

# --- RESET GERAL ---
@app.route('/api/reset', methods=['DELETE'])
def reset_data():
    """Apaga tudo: DB, Referências e Arquivos de Upload."""
    try:
        # Limpa JSONs
        save_data([])
        save_referencias([])
        
        # Limpa pasta de uploads
        if os.path.exists(UPLOAD_FOLDER):
            for filename in os.listdir(UPLOAD_FOLDER):
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(f"Erro ao deletar {file_path}: {e}")
                    
        return jsonify({'message': 'Sistema resetado com sucesso.'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    # Configuração para rodar tanto local quanto no Render
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
