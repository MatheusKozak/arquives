import re
from enum import Enum
#from IPython.display import HTML, display

types = {}
ReferenceCheck = []
dict_id_content = {}
ids = []
''' Metodo para gerar uma pilha de erros para detalhes de erros e manipular o status de cada um dos parametros '''
StackTrace = []  # Pilha de Erros para Detalhes de erros

''' Classe Base para Status de cada um dos parametros utilizados no FlagConsoleGuide '''
class Status(Enum):
    OK = "OK"
    ERRO = "ERRO"

''' Classe utilizada para gerar um relatório de erros e OKs
Colore o Status atual de cada um dos parametros '''
class FlagConsoleGuide:
    def __init__(self, estrutura=Status.OK, sintaxe=Status.OK, referencias=Status.OK, tabela_xref=Status.OK):
        self.estrutura = estrutura
        self.sintaxe = sintaxe
        self.referencias = referencias
        self.tabela_xref = tabela_xref

    def gerar_relatorio(self):
        def format_status(status):
            space1 = " \033[32m" if status == Status.OK else "\033[31m"
            space2 = " \033[0m" if status == Status.OK else "\033[0m"
            return f'[{space1}{status.value}{space2}]'

        print(f"{format_status(self.estrutura)} Estrutura geral")
        print(f"{format_status(self.sintaxe)} Sintaxe de objetos")
        print(f"{format_status(self.referencias)} Referências")
        print(f"{format_status(self.tabela_xref)} Tabela xref")

'''Flag para manter controle e gerar o relatorio de erros e OK's'''
console_flag = FlagConsoleGuide()

''' Classe para criar uma arvore de objetos '''
class Object:
    def __init__(self, obj_id, obj_type=None, parent=None,content=None):
        self.obj_id = obj_id
        self.obj_type = obj_type
        self.parent = parent
        self.children = []
        self.content = content

    def add_child(self, child):
        self.children.append(child)
        child.parent = self

    def __str__(self, level=0):
        indent = '  ' * level
        result = f"{indent}+ {self.obj_type}\n"
        for child in self.children:
            result += child.__str__(level + 1)
        return result

def showStackTrace():
    print("Pilha de Erros: ")
    return StackTrace

def stackError(type, error):
    StackTrace.append(error)
    if type == "Estrutura Geral":
        console_flag.estrutura = Status.ERRO
    elif type == "Sintaxe de Objetos":
        console_flag.sintaxe = Status.ERRO
    elif type == "Referências":
        console_flag.referencias = Status.ERRO
    elif type == "Tabela xref":
        console_flag.tabela_xref = Status.ERRO

''' Conjunto de metodos para criar uma string sem perder o formato original e separar os objetos do pdf para analise '''
def create_no_newline_string(file_name):
    with open(file_name, 'r') as file:
        content = file.read()
    no_newlines = content.replace("\n", "")
    file.close()
    return no_newlines

def extract_pdf_objects(nospaces):
    objects = nospaces.split("endobj")  # Divide pelo "endobj"
    objects = [obj.strip() + "endobj" for obj in objects if obj.strip()]  # Adiciona "endobj" de volta
    return objects

def verificar_xref(arquivo_pdf, tabela_xref):
    with open(arquivo_pdf, 'rb') as f:
        for entrada in tabela_xref:
            offset, geracao, status = entrada
            if status == 'n':  # Apenas verificar objetos em uso
                f.seek(offset)
                inicio_objeto = f.read(20)
                if not inicio_objeto.startswith(b'obj'):
                    stackError("Tabela xref", f"Objeto não encontrado no offset {offset}")
                else:
                    print(f"Objeto encontrado no offset {offset}")

def parse_xref_string(xref_string):
    xref_string = xref_string.replace("xref", "")
    xref_string = xref_string.replace(" ", "")
    xref_string = xref_string[3:]  # Remove o cabeçalho 'xref' e divide a string em partes
    tamanho_entrada = 10 + 5 + 1  # 10 para offset, 5 para geração, 1 para status
    tabela_xref = []
    for i in range(0, len(xref_string), tamanho_entrada):
        offset = int(xref_string[i:i+10])
        geracao = int(xref_string[i+10:i+15])
        status = xref_string[i+15]
        tabela_xref.append((offset, geracao, status))
    return tabela_xref

def extract_all_types_from_the_object(obj):
    global types
    i = 0
    while i < len(obj):
        if obj[i] == '/':
            typeObj = ""
            i += 1
            while i < len(obj) and obj[i] != ' ' and obj[i] != '/':
                typeObj += obj[i]
                i += 1
            if typeObj:
                if typeObj in types:
                    types[typeObj] += 1
                else:
                    types[typeObj] = 1
        else:
            i += 1
    return types

def is_stream_object(obj):
    pattern = r"\d+ \d+ obj<<.*?>>stream.*?endstreamendobj*?"
    return re.search(pattern, obj, re.DOTALL)

def is_regular_object(obj):
    pattern = r"\d+ \d+ obj<<.*?>>endobj"
    return re.search(pattern, obj, re.DOTALL)

def is_xref_and_trailer(obj):
    return obj.startswith("xref")

def extract_stream_from_object(obj):
    match = re.search(r"stream(.*?)endstream", obj, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

''' Recupera o Objeto Trailer e verifica se o numero de objetos é igual ao numero de objetos no array'''
def expected_size(object):
    return len(object)-1 == int(object[-2].split(" ")[0])

def validate_general_structure(object):
    if not expected_size(object):
        stackError("Estrutura Geral", 'Quantidade de Objetos não corresponde ao numero de objetos esperado')
    return

def parse_pdf_objects(pdf_text):
    objects = {}
    object_regex = re.finditer(r"(\d+) 0 obj(.*?)endobj", pdf_text, re.DOTALL)
    
    for match in object_regex:
        obj_id = int(match.group(1))
        ids.append(obj_id)
        obj_content = match.group(2).strip()
        
        type_match = re.search(r"/Type /([A-Za-z]+)", obj_content)
        obj_type = type_match.group(1) if type_match else "Unknown"
        
        objects[obj_id] = Object(obj_id, obj_type)
    return objects

def validate_reference(id):
    if id not in ids:
        stackError("Referências" , f"Referencia {id} não encontrada")

def build_tree(objects, pdf_text):
    for obj_id, obj in objects.items():
        match = re.search(rf"{obj_id} 0 obj(.*?)endobj", pdf_text, re.DOTALL)
        if not match:
            continue
        
        obj_content = match.group(1)
        
        if obj.obj_type == "Catalog":
            root = obj
            pages_ref = re.search(r"/Pages (\d+) 0 R", obj_content)
            if pages_ref:
                pages_id = int(pages_ref.group(1))
                obj.add_child(objects[pages_id])
        
        if obj.obj_type == "Pages":
            kids_matches = re.findall(r"(\d+) 0 R", obj_content)
            for kid_id in kids_matches:
                validate_reference(int(kid_id))
                if int(kid_id) not in objects:
                    obj.add_child(objects[int(kid_id)])
        
        if obj.obj_type == "Page":
            parent_match = re.search(r"/Parent (\d+) 0 R", obj_content)
            if parent_match:
                parent_id = int(parent_match.group(1))
                
                validate_reference(parent_id)
                if parent_id in objects:
                    objects[parent_id].add_child(obj)
            
            # Validações adicionais para o tipo "Page"
            resources_match = re.search(r"/Resources <<(.*?)>>", obj_content, re.DOTALL)
            if resources_match:
                
                parent_match = re.search(r"/Font << (\d+) 0 R", obj_content)
                if parent_match:
                    validate_reference(parent_match.group(1))                
                resources_obj = Object(obj_id=f"{obj.obj_id}_resources", obj_type="Resources" , content=resources_match.group(1))
                obj.add_child(resources_obj)
            else:
                stackError("Sintaxe de Objetos", "Faltando /Resources no objeto Page")

            media_box_match = re.search(r"/MediaBox \[.*?\]", obj_content)
            if media_box_match:
                media_box_obj = Object(obj_id=f"{obj.obj_id}_media_box", obj_type="MediaBox" , content=media_box_match.group(0))
                obj.add_child(media_box_obj)
            else:
                stackError("Sintaxe de Objetos", "Faltando /MediaBox no objeto Page")

            crop_box_match = re.search(r"/CropBox \[.*?\]", obj_content)
            if crop_box_match:
                crop_box_obj = Object(obj_id=f"{obj.obj_id}_crop_box", obj_type="CropBox" , content=crop_box_match.group(0))
                obj.add_child(crop_box_obj)
            else:
                stackError("Sintaxe de Objetos", "Faltando /CropBox no objeto Page")

            rotate_match = re.search(r"/Rotate \d+", obj_content)
            if rotate_match:
                rotate_obj = Object(obj_id=f"{obj.obj_id}_rotate", obj_type="Rotate" , content=rotate_match.group(0))
                obj.add_child(rotate_obj)
            else:
                stackError("Sintaxe de Objetos", "Faltando /Rotate no objeto Page")

            contents_match = re.search(r"/Contents (\d+) 0 R", obj_content)
            if contents_match:
                contents_obj = Object(obj_id=f"{obj.obj_id}_contents", obj_type="Contents" , content=contents_match.group(0))
                obj.add_child(contents_obj)
            else:
                stackError("Sintaxe de Objetos", "Faltando /Contents no objeto Page")
        
        if obj.obj_type == "Metadata":
            root.add_child(obj)

    return root

def carregar_configuracoes(config_file):
    configuracoes = {}
    with open(config_file, 'r', encoding='utf-8') as f:
        for linha in f:
            chave, valor = linha.strip().split('=')
            configuracoes[chave] = valor.lower() == 'sim'
    return configuracoes



def main():
    # Carregar configurações
    configuracoes = carregar_configuracoes('config')

    extrair_texto = configuracoes.get('extrair_texto', False)
    gerar_sumario = configuracoes.get('gerar_sumario', False)
    detectar_ciclos = configuracoes.get('detectar_ciclos', False)
    nivel_detalhe = configuracoes.get('nivel_detalhe', 'simples')  # Exemplo de valor padrão
    validar_xref = configuracoes.get('validar_xref', False)
    with open("exemplo", "r", encoding="utf-8") as f:
        pdf_text = f.read()
    
    objects = parse_pdf_objects(pdf_text)
    validate_general_structure(objects)
    root = build_tree(objects, pdf_text)
    
    if gerar_sumario:
        print(root)
        print(StackTrace)

    if validar_xref:
        verificar_xref()
    
    
if __name__ == '__main__':
    main()
