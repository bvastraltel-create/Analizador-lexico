from ply.lex import lex
from ply.yacc import yacc
import os
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from collections import Counter
from contextlib import redirect_stdout
import io
import re


reservadas = {
    'eldeste': 'ELDESTE',      # SELECT
    'ladeste': 'LADESTE',      # INSERT
    'ladasta': 'LADASTA',      # DELETE
    'esedeste': 'ESEDESTE',    # Alternativo
    'cafe': 'CAFE',            # FROM / INTO
    'conazucar': 'CONAZUCAR',  # WHERE
    'mezcla': 'MEZCLA',        # SET (para Update)
    'marcacafe': 'MARCACAFE',  # INTO (para Insert)
    'values': 'VALUES',
    'from': 'FROM'
}

tokens = [
    'NUM', 'VAR', 'STR',
    'ASG', 'IGUAL', 'GT', 'LT', 'DISTINTO',
    'MAS', 'MENOS', 'DIV', 'MUL',
    'LPAREN', 'RPAREN', 'COMA', 'PUNTOCOMA'
] + list(reservadas.values())

t_IGUAL = r'=='
t_DISTINTO = r'!='
t_GT = r'>'
t_LT = r'<'
t_ASG = r'='

t_MAS = r'\+'
t_MENOS = r'-'
t_DIV = r'/'
t_MUL = r'\*'

t_LPAREN = r'\('
t_RPAREN = r'\)'
t_COMA = r','
t_PUNTOCOMA = r';'

t_ignore = ' \t\r'

def t_NUM(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_STR(t):
    r'\".*?\"'
    t.value = t.value[1:-1]
    return t

def t_VAR(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    valor = t.value.lower()
    t.type = reservadas.get(valor, 'VAR')
    t.value = valor
    return t

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

def t_error(t):
    print(f'Error lexico (Linea {t.lineno}): "{t.value[0]}"')
    t.lexer.skip(1)

lexer = lex()

tabla_simbolos = {}
errores_semanticos = []

def registrar_error_semantico(linea, mensaje):
    errores_semanticos.append(f"Error semantico (Linea {linea}): {mensaje}")

precedence = (
    ('left', 'MAS', 'MENOS'),
    ('left', 'MUL', 'DIV'),
)

def p_programa(p):
    '''programa : programa instruccion
                | instruccion'''
    pass

def p_instruccion(p):
    '''instruccion : sentencia_select PUNTOCOMA
                   | sentencia_insert PUNTOCOMA
                   | sentencia_delete PUNTOCOMA
                   | sentencia_update PUNTOCOMA'''
    
    tipo_instruccion = p[1]['tipo']
    
    if len(errores_semanticos) == 0:
        print(f"Sentencia valida -> {tipo_instruccion} (linea {p.lineno(2)})")
    else:
        for err in errores_semanticos:
            print(f"{err}")
        errores_semanticos.clear()

def p_instruccion_error(p):
    '''instruccion : error PUNTOCOMA'''
    print(f'Error: estructura invalida (Linea {p.lineno(1)})')

def p_sentencia_select(p):
    '''sentencia_select : ELDESTE lista_vars CAFE VAR condicion_opt
                        | ELDESTE lista_vars FROM VAR condicion_opt'''
    p[0] = {'tipo': 'SELECT', 'tabla': p[4], 'columnas': p[2]}

def p_sentencia_insert(p):
    '''sentencia_insert : LADESTE MARCACAFE VAR LPAREN lista_vars RPAREN VALUES LPAREN lista_expresiones RPAREN'''
    cols = p[5]
    val_types = p[9]
    
    if len(cols) != len(val_types):
        registrar_error_semantico(
            p.lineno(1),
            f"El numero de columnas ({len(cols)}) no coincide con el numero de valores ({len(val_types)})"
        )
        
    p[0] = {'tipo': 'INSERT', 'tabla': p[3], 'columnas': cols, 'tipos_valores': val_types}

def p_sentencia_delete(p):
    '''sentencia_delete : LADASTA CAFE VAR condicion_opt'''
    p[0] = {'tipo': 'DELETE', 'tabla': p[3]}

def p_sentencia_update(p):
    '''sentencia_update : MEZCLA VAR LADESTE lista_asignaciones condicion_opt'''
    p[0] = {'tipo': 'UPDATE', 'tabla': p[2]}

def p_lista_vars(p):
    '''lista_vars : VAR
                  | lista_vars COMA VAR'''
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]

def p_lista_expresiones(p):
    '''lista_expresiones : expresion
                         | lista_expresiones COMA expresion'''
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]

def p_lista_asignaciones(p):
    '''lista_asignaciones : VAR ASG expresion
                          | lista_asignaciones COMA VAR ASG expresion'''
    pass

def p_condicion_opt(p):
    '''condicion_opt : CONAZUCAR condicion
                     | empty'''
    pass

def p_condicion(p):
    '''condicion : expresion IGUAL expresion
                 | expresion GT expresion
                 | expresion LT expresion
                 | expresion DISTINTO expresion'''
    tipo_izq = p[1]
    tipo_der = p[3]
    
    if tipo_izq != 'UNKNOWN' and tipo_der != 'UNKNOWN' and tipo_izq != tipo_der:
        registrar_error_semantico(
            p.lineno(2),
            f"Incompatibilidad de tipos en comparacion: '{tipo_izq}' no se puede comparar con '{tipo_der}'"
        )

def p_expresion_num(p):
    'expresion : NUM'
    p[0] = 'INT'

def p_expresion_str(p):
    'expresion : STR'
    p[0] = 'STRING'

def p_expresion_var(p):
    'expresion : VAR'
    p[0] = tabla_simbolos.get(p[1], 'UNKNOWN')

def p_expresion_operacion(p):
    '''expresion : expresion MAS expresion
                 | expresion MENOS expresion
                 | expresion MUL expresion
                 | expresion DIV expresion'''
    tipo_izq = p[1]
    tipo_der = p[3]
    operador = p[2]
    
    if tipo_izq == 'STRING' or tipo_der == 'STRING':
        registrar_error_semantico(
            p.lineno(2),
            f"Operacion aritmetica '{operador}' no permitida entre tipos '{tipo_izq}' y '{tipo_der}'"
        )
        p[0] = 'ERROR'
    else:
        p[0] = 'INT'

def p_expresion_parens(p):
    'expresion : LPAREN expresion RPAREN'
    p[0] = p[2]

def p_empty(p):
    'empty :'
    pass

def p_error(p):
    if p:
        print(
            f'Error sintactico (Linea {p.lineno}): 'f'no se esperaba "{p.value}"'
        )
    else:
        print('Error sintactico: fin inesperado del archivo')

parser = yacc()

CARPETA = os.path.dirname(os.path.abspath(__file__))

ARCHIVOS_DICCIONARIO = [
    "LLMFINETUNING.txt",
    "LLMFINETUNNING.txt"
]

TRADUCCION_SQL = {
    "SELECT": "eldeste",
    "INSERT": "ladeste",
    "DELETE": "ladasta",
    "FROM": "cafe",
    "WHERE": "conazucar",
    "SET": "mezcla",
    "INTO": "marcacafe",
    "VALUES": "values"
}

PALABRAS_PROPIAS = [
    "eldeste",
    "ladeste",
    "ladasta",
    "esedeste",
    "cafe",
    "conazucar",
    "mezcla",
    "marcacafe",
    "values",
    "from"
]


def cargar_palabras_diccionario():
    ruta_diccionario = None

    for nombre in ARCHIVOS_DICCIONARIO:
        posible = os.path.join(CARPETA, nombre)
        if os.path.isfile(posible):
            ruta_diccionario = posible
            break

    palabras = Counter()

    if ruta_diccionario:
        with open(ruta_diccionario, "r", encoding="utf-8") as archivo:
            contenido = archivo.read()

        encontradas = re.findall(
            r"[A-Za-z_][A-Za-z0-9_]*",
            contenido
        )

        for palabra in encontradas:
            palabra = palabra.lower()
            palabra = TRADUCCION_SQL.get(palabra.upper(), palabra)
            palabras[palabra] += 1

    for palabra in PALABRAS_PROPIAS:
        palabras[palabra] += 1

    return palabras


PALABRAS_DICCIONARIO = cargar_palabras_diccionario()


def obtener_palabra_actual():
    cursor = editor.index(tk.INSERT)
    inicio = editor.index(f"{cursor} wordstart")
    texto = editor.get(inicio, cursor)

    if not texto or texto[-1].isspace():
        return "", cursor

    coincidencia = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", texto)
    if coincidencia:
        return coincidencia.group(0), cursor

    return "", cursor


def obtener_palabra_actual():
    cursor = editor.index(tk.INSERT)
    linea, columna = map(int, cursor.split("."))
    texto_antes_cursor = editor.get(f"{linea}.0", cursor)

    coincidencia = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", texto_antes_cursor)
    if coincidencia:
        inicio_col = columna - len(coincidencia.group(0))
        inicio = f"{linea}.{inicio_col}"
        return coincidencia.group(0), inicio, cursor

    return "", cursor, cursor


def actualizar_sugerencias(event=None):
    prefijo, _, _ = obtener_palabra_actual()

    lista_sugerencias.delete(0, tk.END)

    if not prefijo:
        etiqueta_sugerencias.config(text="Sugerencias")
        return

    prefijo = prefijo.lower()

    coincidencias = [
        palabra
        for palabra in PALABRAS_DICCIONARIO
        if palabra.startswith(prefijo) and palabra != prefijo
    ]

    coincidencias.sort(
        key=lambda palabra: (
            -PALABRAS_DICCIONARIO[palabra],
            palabra
        )
    )

    for palabra in coincidencias[:30]:
        lista_sugerencias.insert(tk.END, palabra)

    etiqueta_sugerencias.config(
        text=f"Sugerencias para: {prefijo}"
    )


def aceptar_sugerencia(event=None):
    if lista_sugerencias.size() == 0:
        return "break"

    seleccion = lista_sugerencias.curselection()

    if seleccion:
        sugerencia = lista_sugerencias.get(seleccion[0])
    else:
        sugerencia = lista_sugerencias.get(0)

    prefijo, inicio, cursor = obtener_palabra_actual()

    if prefijo:
        editor.delete(inicio, cursor)
        editor.insert(inicio, sugerencia)
    else:
        editor.insert(tk.INSERT, sugerencia)

    actualizar_sugerencias()
    return "break"

def usar_sugerencia_lista(event=None):
    if lista_sugerencias.size() == 0:
        return

    seleccion = lista_sugerencias.curselection()
    if not seleccion:
        return

    aceptar_sugerencia()


def analizar_codigo():
    codigo = editor.get("1.0", "end-1c")
    salida = io.StringIO()

    errores_semanticos.clear()
    lexer.lineno = 1

    try:
        with redirect_stdout(salida):
            parser.parse(codigo, lexer=lexer)
    except Exception as error:
        salida.write(f"\nError al ejecutar el análisis: {error}\n")

    resultado = salida.getvalue().strip()

    if errores_semanticos:
        if resultado:
            resultado += "\n"

        resultado += "\n".join(errores_semanticos)

    if not resultado:
        resultado = "Análisis terminado. No se generaron mensajes."

    panel_resultado.config(state=tk.NORMAL)
    panel_resultado.delete("1.0", tk.END)
    panel_resultado.insert(tk.END, resultado)
    panel_resultado.config(state=tk.DISABLED)


def limpiar_editor():
    editor.delete("1.0", tk.END)
    panel_resultado.config(state=tk.NORMAL)
    panel_resultado.delete("1.0", tk.END)
    panel_resultado.config(state=tk.DISABLED)
    lista_sugerencias.delete(0, tk.END)
    editor.focus_set()


# =========================
# VENTANA
# =========================

ventana = tk.Tk()
ventana.title("Editor de lenguaje SQL personalizado")
ventana.geometry("1100x700")
ventana.minsize(800, 500)

marco_principal = ttk.Frame(ventana, padding=10)
marco_principal.pack(fill=tk.BOTH, expand=True)

barra_botones = ttk.Frame(marco_principal)
barra_botones.pack(fill=tk.X, pady=(0, 8))

ttk.Button(
    barra_botones,
    text="Analizar",
    command=analizar_codigo
).pack(side=tk.LEFT, padx=(0, 5))

ttk.Button(
    barra_botones,
    text="Limpiar",
    command=limpiar_editor
).pack(side=tk.LEFT)

marco_editor = ttk.Frame(marco_principal)
marco_editor.pack(fill=tk.BOTH, expand=True)

marco_texto = ttk.Frame(marco_editor)
marco_texto.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

editor = ScrolledText(
    marco_texto,
    wrap=tk.NONE,
    font=("Consolas", 12),
    undo=True
)
editor.pack(fill=tk.BOTH, expand=True)

marco_sugerencias = ttk.Frame(marco_editor, width=230)
marco_sugerencias.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
marco_sugerencias.pack_propagate(False)

etiqueta_sugerencias = ttk.Label(
    marco_sugerencias,
    text="Sugerencias"
)
etiqueta_sugerencias.pack(anchor=tk.W, pady=(0, 5))

lista_sugerencias = tk.Listbox(
    marco_sugerencias,
    font=("Consolas", 11),
    activestyle="dotbox"
)
lista_sugerencias.pack(fill=tk.BOTH, expand=True)

ttk.Label(
    marco_principal,
    text="Resultado del análisis"
).pack(anchor=tk.W, pady=(10, 5))

panel_resultado = ScrolledText(
    marco_principal,
    height=8,
    wrap=tk.WORD,
    font=("Consolas", 10),
    state=tk.DISABLED
)
panel_resultado.pack(fill=tk.X)

editor.bind("<KeyRelease>", actualizar_sugerencias)
editor.bind("<Tab>", aceptar_sugerencia)
lista_sugerencias.bind("<Double-Button-1>", usar_sugerencia_lista)

editor.focus_set()
ventana.mainloop()