"""
Lista de Oradores — MiniONU
============================
Dois modos:
  python oradores_onu.py            → Janela do Operador (Mesa Diretora)
  python oradores_onu.py --painel   → Painel Público (tela cheia para projetor/TV)

Comunicação via arquivo JSON (onu_estado.json) na mesma pasta.
Teclas do Painel: ESC sai · F11 alterna tela cheia
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import json, os, sys, time

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

# Quando empacotado pelo PyInstaller (frozen), usa a pasta do .exe.
# Em desenvolvimento normal, usa a pasta do script.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ESTADO_PATH = os.path.join(BASE_DIR, "onu_estado.json")

# ── Paleta (ONU: azul institutional + dourado) ────────────────────────────────
BG          = "#0B1120"
BG2         = "#111827"
BG3         = "#1C2A3A"
BORDA       = "#1E3050"
BRANCO      = "#E8EDF5"
CINZA       = "#5A7090"
CINZA2      = "#2A3A50"

AZUL        = "#1A8FE3"
AZUL_ESC    = "#0A2540"
DOURADO     = "#F5C542"
DOURADO_ESC = "#3A2A00"
VERDE       = "#34D399"
VERMELHO    = "#F87171"
LARANJA     = "#FB923C"

TEMPO_PADRAO = 90   # segundos


# ══════════════════════════════════════════════════════════════════════════════
#  ESTADO
# ══════════════════════════════════════════════════════════════════════════════

def estado_inicial():
    return {
        "comite":        "Comitê Geral",
        "topico":        "Tema em debate",
        "orador_atual":  None,
        "fila":          [],
        "historico":     [],
        "tempo_limite":  TEMPO_PADRAO,
        "timer_inicio":  None,
        "timer_ativo":   False,
        "logo_path":     None,
        "font_topico":   15,       # tamanho da fonte do tópico no painel
        "atualizado_em": 0.0,
    }

def salvar(e):
    with open(ESTADO_PATH, "w", encoding="utf-8") as f:
        json.dump(e, f, ensure_ascii=False, indent=2)

def carregar():
    if not os.path.exists(ESTADO_PATH):
        e = estado_inicial()
        salvar(e)
        return e
    try:
        with open(ESTADO_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        e = estado_inicial()
        salvar(e)
        return e

def tempo_decorrido(e) -> int:
    """Segundos decorridos desde que o timer foi iniciado."""
    if not e.get("timer_ativo") or e.get("timer_inicio") is None:
        return 0
    return int(time.time() - e["timer_inicio"])

def tempo_restante(e) -> int:
    return max(0, e.get("tempo_limite", TEMPO_PADRAO) - tempo_decorrido(e))

def fmt_tempo(seg: int) -> str:
    m, s = divmod(abs(seg), 60)
    return f"{m:02d}:{s:02d}"


# ══════════════════════════════════════════════════════════════════════════════
#  OPERADOR
# ══════════════════════════════════════════════════════════════════════════════

class Operador(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mesa Diretora — Lista de Oradores MiniONU")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("560x760")
        self.estado = carregar()
        self._logo_img = None   # referência PhotoImage (evita GC)
        self._build()
        self._refresh()
        self._poll()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        # Cabeçalho
        cab = tk.Frame(self, bg=BG2, padx=20, pady=10)
        cab.pack(fill="x")

        # Lado esquerdo: logo + título
        esq = tk.Frame(cab, bg=BG2)
        esq.pack(side="left", fill="y")

        self.lbl_logo = tk.Label(esq, bg=BG2, cursor="hand2")
        self.lbl_logo.pack(side="left", padx=(0, 10))
        self.lbl_logo.bind("<Button-1>", lambda e: self._carregar_logo())

        titulo_frame = tk.Frame(esq, bg=BG2)
        titulo_frame.pack(side="left")
        tk.Label(titulo_frame, text="🌐  MESA DIRETORA", bg=BG2, fg=AZUL,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.lbl_logo_hint = tk.Label(titulo_frame,
                                       text="[ clique na logo para carregar PNG ]",
                                       bg=BG2, fg=CINZA2,
                                       font=("Segoe UI", 8), cursor="hand2")
        self.lbl_logo_hint.pack(anchor="w")
        self.lbl_logo_hint.bind("<Button-1>", lambda e: self._carregar_logo())

        # Lado direito: hora + botão remover logo
        dir_frame = tk.Frame(cab, bg=BG2)
        dir_frame.pack(side="right", fill="y")
        self.lbl_hora = tk.Label(dir_frame, text="", bg=BG2, fg=CINZA,
                                  font=("Segoe UI", 13))
        self.lbl_hora.pack(anchor="e")
        self.btn_rm_logo = tk.Button(dir_frame, text="✕ remover logo",
                                      bg=BG2, fg=CINZA2, relief="flat",
                                      font=("Segoe UI", 8), cursor="hand2",
                                      command=self._remover_logo)
        self.btn_rm_logo.pack(anchor="e")

        # Atualiza logo se já existir no estado
        self._atualizar_logo_widget()

        # Comitê / Tópico
        info = tk.Frame(self, bg=BG3, padx=16, pady=10)
        info.pack(fill="x")
        row1 = tk.Frame(info, bg=BG3)
        row1.pack(fill="x")
        tk.Label(row1, text="COMITÊ", bg=BG3, fg=CINZA,
                 font=("Segoe UI", 8)).pack(side="left")
        self._btn(row1, "✎", BG3, CINZA,
                  self._editar_comite, height=1, font_size=9).pack(side="right")
        self.lbl_comite = tk.Label(info, text="", bg=BG3, fg=BRANCO,
                                    font=("Segoe UI", 11, "bold"))
        self.lbl_comite.pack(anchor="w")

        row2 = tk.Frame(info, bg=BG3)
        row2.pack(fill="x", pady=(6, 0))
        tk.Label(row2, text="TÓPICO", bg=BG3, fg=CINZA,
                 font=("Segoe UI", 8)).pack(side="left")
        self._btn(row2, "✎", BG3, CINZA,
                  self._editar_topico, height=1, font_size=9).pack(side="right")
        self.lbl_topico = tk.Label(info, text="", bg=BG3, fg=DOURADO,
                                    font=("Segoe UI", 10), wraplength=500,
                                    justify="left")
        self.lbl_topico.pack(anchor="w")

        # Orador atual
        sec_atual = tk.Frame(self, bg=BG, padx=16, pady=10)
        sec_atual.pack(fill="x")
        tk.Label(sec_atual, text="ORADOR ATUAL", bg=BG, fg=CINZA,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.lbl_orador = tk.Label(sec_atual, text="—", bg=BG, fg=AZUL,
                                    font=("Segoe UI", 32, "bold"))
        self.lbl_orador.pack(anchor="w")

        # Timer
        timer_frame = tk.Frame(self, bg=BG2, padx=16, pady=12)
        timer_frame.pack(fill="x")

        left_t = tk.Frame(timer_frame, bg=BG2)
        left_t.pack(side="left", expand=True, fill="both")
        tk.Label(left_t, text="TEMPO RESTANTE", bg=BG2, fg=CINZA,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.lbl_timer = tk.Label(left_t, text="01:30", bg=BG2, fg=VERDE,
                                   font=("Segoe UI", 44, "bold"))
        self.lbl_timer.pack(anchor="w")

        right_t = tk.Frame(timer_frame, bg=BG2)
        right_t.pack(side="right")
        self.btn_iniciar = self._btn(right_t, "▶  Iniciar", AZUL, BG,
                                      self._iniciar_timer, height=2)
        self.btn_iniciar.pack(fill="x", pady=(0, 4))
        self._btn(right_t, "⏹  Parar / Reset", BG3, BRANCO,
                  self._parar_timer, height=2).pack(fill="x")

        # Config tempo
        cfg = tk.Frame(self, bg=BG, padx=16, pady=4)
        cfg.pack(fill="x")
        tk.Label(cfg, text="Tempo de fala:", bg=BG, fg=CINZA,
                 font=("Segoe UI", 9)).pack(side="left")
        self.lbl_tempo_cfg = tk.Label(cfg, text="", bg=BG, fg=CINZA,
                                       font=("Segoe UI", 9))
        self.lbl_tempo_cfg.pack(side="left", padx=6)
        self._btn(cfg, "✎ Alterar", BG3, CINZA,
                  self._alterar_tempo, height=1, font_size=9).pack(side="left")

        # Botões de ação
        sep = tk.Frame(self, bg=BORDA, height=1)
        sep.pack(fill="x", padx=16, pady=8)

        bf = tk.Frame(self, bg=BG, padx=16)
        bf.pack(fill="x")
        self._btn(bf, "▶  Chamar próximo orador", AZUL, BG,
                  self._chamar_proximo, height=2).pack(fill="x", pady=(0, 6))

        linha = tk.Frame(bf, bg=BG)
        linha.pack(fill="x", pady=(0, 6))
        self._btn(linha, "➕  Adicionar à lista", BG3, BRANCO,
                  self._adicionar, height=2).pack(side="left", expand=True,
                                                   fill="x", padx=(0, 4))
        self._btn(linha, "✏  Chamar por nome", BG3, BRANCO,
                  self._chamar_nome, height=2).pack(side="left", expand=True,
                                                     fill="x", padx=(4, 0))

        linha2 = tk.Frame(bf, bg=BG)
        linha2.pack(fill="x")
        self._btn(linha2, "🗑  Remover da lista", BG3, VERMELHO,
                  self._remover, height=2).pack(side="left", expand=True,
                                                 fill="x", padx=(0, 4))
        self._btn(linha2, "🔄  Zerar lista", BG3, VERMELHO,
                  self._zerar, height=2).pack(side="left", expand=True,
                                               fill="x", padx=(4, 0))

        linha3 = tk.Frame(bf, bg=BG)
        linha3.pack(fill="x", pady=(6, 0))
        self._btn(linha3, "📝  Editar lista completa", BG3, BRANCO,
                  self._editar_lista, height=2).pack(side="left", expand=True,
                                                      fill="x", padx=(0, 4))
        self._btn(linha3, "🔡  Fonte do tópico", BG3, DOURADO,
                  self._alterar_fonte_topico, height=2).pack(side="left", expand=True,
                                                              fill="x", padx=(4, 0))

        # Lista de espera
        sep2 = tk.Frame(self, bg=BORDA, height=1)
        sep2.pack(fill="x", padx=16, pady=10)

        lf = tk.Frame(self, bg=BG, padx=16)
        lf.pack(fill="both", expand=True)
        tk.Label(lf, text="LISTA DE ORADORES", bg=BG, fg=CINZA,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.lbl_lista = tk.Label(lf, text="", bg=BG, fg=BRANCO,
                                   font=("Segoe UI", 11), justify="left",
                                   wraplength=520)
        self.lbl_lista.pack(anchor="nw", pady=4)

        # Rodapé
        rod = tk.Frame(self, bg=BG2, padx=16, pady=8)
        rod.pack(fill="x", side="bottom")
        self.lbl_status = tk.Label(rod, text="Sistema pronto.", bg=BG2, fg=CINZA,
                                    font=("Segoe UI", 9))
        self.lbl_status.pack(side="left")
        tk.Label(rod, text="Painel: python oradores_onu.py --painel",
                 bg=BG2, fg=CINZA2, font=("Segoe UI", 8)).pack(side="right")

    def _btn(self, parent, txt, bg, fg, cmd, height=1, font_size=10):
        return tk.Button(parent, text=txt, bg=bg, fg=fg,
                         activebackground=CINZA2, activeforeground=BRANCO,
                         font=("Segoe UI", font_size, "bold"), relief="flat",
                         cursor="hand2", height=height, command=cmd, padx=8)

    # ── Logo ──────────────────────────────────────────────────────────────────
    def _carregar_logo(self):
        if not PIL_OK:
            messagebox.showwarning(
                "Pillow não instalado",
                "Para usar logo PNG instale o Pillow:\n\n  pip install Pillow")
            return
        path = filedialog.askopenfilename(
            title="Selecionar logo PNG",
            filetypes=[("Imagens PNG", "*.png"),
                       ("Imagens", "*.png *.jpg *.jpeg *.gif"),
                       ("Todos", "*.*")])
        if not path:
            return
        e = carregar()
        e["logo_path"] = path
        salvar(e)
        self._atualizar_logo_widget()
        self._status(f"Logo carregada: {os.path.basename(path)}")

    def _remover_logo(self):
        e = carregar()
        e["logo_path"] = None
        salvar(e)
        self._logo_img = None
        self.lbl_logo.config(image="", width=0)
        self.lbl_logo_hint.config(text="[ clique na logo para carregar PNG ]")
        self._status("Logo removida.")

    def _atualizar_logo_widget(self):
        e = carregar()
        path = e.get("logo_path")
        if not path or not os.path.exists(path):
            self.lbl_logo.config(image="", width=0)
            self.lbl_logo_hint.config(text="[ clique na logo para carregar PNG ]")
            return
        if not PIL_OK:
            return
        try:
            img = Image.open(path)
            img.thumbnail((64, 64), Image.LANCZOS)
            self._logo_img = ImageTk.PhotoImage(img)
            self.lbl_logo.config(image=self._logo_img, width=64)
            self.lbl_logo_hint.config(text=f"[ {os.path.basename(path)} ]")
        except Exception:
            self.lbl_logo.config(image="", width=0)

    # ── Lógica ────────────────────────────────────────────────────────────────
    def _adicionar(self):
        nome = simpledialog.askstring("Adicionar orador",
                                      "País / Delegação / Nome:", parent=self)
        if not nome or not nome.strip():
            return
        nome = nome.strip()
        e = carregar()
        e["fila"].append(nome)
        e["atualizado_em"] = time.time()
        salvar(e)
        self._status(f"'{nome}' adicionado à lista.")
        self._refresh()

    def _chamar_proximo(self):
        e = carregar()
        if not e["fila"]:
            messagebox.showinfo("Lista vazia", "Nenhum orador na lista.")
            return
        proximo = e["fila"].pop(0)
        self._registrar(e, proximo)

    def _chamar_nome(self):
        nome = simpledialog.askstring("Chamar por nome",
                                      "País / Delegação / Nome:", parent=self)
        if not nome or not nome.strip():
            return
        nome = nome.strip()
        e = carregar()
        if nome in e["fila"]:
            e["fila"].remove(nome)
        self._registrar(e, nome)

    def _registrar(self, e, nome):
        anterior = e.get("orador_atual")
        if anterior:
            hist = e.get("historico", [])
            hist.append(anterior)
            e["historico"] = hist[-10:]
        e["orador_atual"] = nome
        # Reinicia timer automaticamente
        e["timer_ativo"]  = False
        e["timer_inicio"] = None
        e["atualizado_em"] = time.time()
        salvar(e)
        self._status(f"'{nome}' está com a palavra.")
        self._refresh()

    def _remover(self):
        e = carregar()
        if not e["fila"]:
            messagebox.showinfo("Lista vazia", "Nenhum orador para remover.")
            return
        nome = simpledialog.askstring(
            "Remover orador",
            "Nome a remover:\n\nLista atual:\n" +
            "\n".join(f"  {i+1}. {n}" for i, n in enumerate(e["fila"])),
            parent=self)
        if not nome or not nome.strip():
            return
        nome = nome.strip()
        if nome not in e["fila"]:
            messagebox.showwarning("Não encontrado", f"'{nome}' não está na lista.")
            return
        e["fila"].remove(nome)
        e["atualizado_em"] = time.time()
        salvar(e)
        self._status(f"'{nome}' removido da lista.")
        self._refresh()

    def _zerar(self):
        if messagebox.askyesno("Zerar lista",
                               "Limpar toda a lista e histórico?"):
            e = carregar()
            novo = estado_inicial()
            novo["comite"] = e.get("comite", "Comitê Geral")
            novo["topico"] = e.get("topico", "Tema em debate")
            novo["tempo_limite"] = e.get("tempo_limite", TEMPO_PADRAO)
            salvar(novo)
            self._status("Lista zerada.")
            self._refresh()

    # ── Timer ─────────────────────────────────────────────────────────────────
    def _iniciar_timer(self):
        e = carregar()
        if not e.get("orador_atual"):
            messagebox.showinfo("Sem orador", "Chame um orador primeiro.")
            return
        e["timer_inicio"] = time.time()
        e["timer_ativo"]  = True
        e["atualizado_em"] = time.time()
        salvar(e)
        self._status("Cronômetro iniciado.")
        self._refresh()

    def _parar_timer(self):
        e = carregar()
        e["timer_ativo"]  = False
        e["timer_inicio"] = None
        e["atualizado_em"] = time.time()
        salvar(e)
        self._status("Cronômetro parado.")
        self._refresh()

    def _alterar_tempo(self):
        e = carregar()
        atual = e.get("tempo_limite", TEMPO_PADRAO)
        novo = simpledialog.askinteger(
            "Tempo de fala",
            f"Duração em segundos (atual: {atual}s):",
            parent=self, minvalue=10, maxvalue=600,
            initialvalue=atual)
        if novo:
            e["tempo_limite"] = novo
            e["timer_ativo"]  = False
            e["timer_inicio"] = None
            salvar(e)
            self._status(f"Tempo alterado para {novo}s.")
            self._refresh()

    # ── Configurações ─────────────────────────────────────────────────────────
    def _editar_comite(self):
        e = carregar()
        novo = simpledialog.askstring("Comitê", "Nome do comitê:",
                                      parent=self,
                                      initialvalue=e.get("comite",""))
        if novo:
            e["comite"] = novo.strip()
            e["atualizado_em"] = time.time()
            salvar(e)
            self._refresh()

    def _editar_topico(self):
        e = carregar()
        novo = simpledialog.askstring("Tópico", "Tópico em debate:",
                                      parent=self,
                                      initialvalue=e.get("topico",""))
        if novo:
            e["topico"] = novo.strip()
            e["atualizado_em"] = time.time()
            salvar(e)
            self._refresh()

    def _editar_lista(self):
        """Abre janela para reordenar, remover e adicionar oradores livremente."""
        e = carregar()
        win = tk.Toplevel(self)
        win.title("Editar lista de oradores")
        win.configure(bg=BG)
        win.geometry("400x500")
        win.grab_set()

        tk.Label(win, text="LISTA DE ORADORES", bg=BG, fg=CINZA,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(12,2))
        tk.Label(win, text="Edite um nome por linha. A ordem define a fila.",
                 bg=BG, fg=CINZA, font=("Segoe UI", 8)).pack(anchor="w", padx=16)

        txt = tk.Text(win, bg=BG3, fg=BRANCO, insertbackground=BRANCO,
                      font=("Segoe UI", 12), relief="flat",
                      padx=10, pady=10, height=16)
        txt.pack(fill="both", expand=True, padx=16, pady=8)

        # Preenche com a lista atual
        for nome in e.get("fila", []):
            txt.insert("end", nome + "\n")

        def salvar_lista():
            conteudo = txt.get("1.0", "end").strip()
            nova_fila = [l.strip() for l in conteudo.splitlines() if l.strip()]
            e2 = carregar()
            e2["fila"] = nova_fila
            e2["atualizado_em"] = time.time()
            salvar(e2)
            self._status(f"Lista atualizada com {len(nova_fila)} orador(es).")
            self._refresh()
            win.destroy()

        bf = tk.Frame(win, bg=BG, padx=16, pady=8)
        bf.pack(fill="x")
        self._btn(bf, "✔  Salvar lista", AZUL, BG,
                  salvar_lista, height=2).pack(side="left", expand=True, fill="x", padx=(0,4))
        self._btn(bf, "✖  Cancelar", BG3, CINZA,
                  win.destroy, height=2).pack(side="left", expand=True, fill="x", padx=(4,0))

    def _alterar_fonte_topico(self):
        e = carregar()
        atual = e.get("font_topico", 15)
        novo = simpledialog.askinteger(
            "Tamanho da fonte — Tópico",
            f"Tamanho atual: {atual}pt\n\nSugestões:\n  Pequeno → 14\n  Médio   → 20\n  Grande  → 28\n  Enorme  → 36",
            parent=self, minvalue=8, maxvalue=72, initialvalue=atual)
        if novo:
            e["font_topico"] = novo
            e["atualizado_em"] = time.time()
            salvar(e)
            self._status(f"Fonte do tópico: {novo}pt")
            self._refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────
    def _refresh(self):
        e = carregar()
        self.lbl_hora.config(text=time.strftime("%H:%M"))
        self.lbl_comite.config(text=e.get("comite", ""))
        self.lbl_topico.config(text=e.get("topico", ""))

        orador = e.get("orador_atual")
        self.lbl_orador.config(
            text=orador if orador else "—",
            fg=AZUL if orador else CINZA)

        # Timer
        restante = tempo_restante(e)
        limite   = e.get("tempo_limite", TEMPO_PADRAO)
        txt_t    = fmt_tempo(restante)
        if not e.get("timer_ativo"):
            cor_t = CINZA
        elif restante > limite * 0.4:
            cor_t = VERDE
        elif restante > 10:
            cor_t = LARANJA
        else:
            cor_t = VERMELHO
        self.lbl_timer.config(text=txt_t, fg=cor_t)
        self.lbl_tempo_cfg.config(text=f"{limite}s ({fmt_tempo(limite)})")

        # Botão iniciar/pausar
        if e.get("timer_ativo"):
            self.btn_iniciar.config(text="▶  Reiniciar", bg=AZUL_ESC, fg=AZUL)
        else:
            self.btn_iniciar.config(text="▶  Iniciar", bg=AZUL, fg=BG)

        # Lista
        fila = e.get("fila", [])
        if fila:
            txt = "\n".join(f"  {i+1}.  {n}" for i, n in enumerate(fila))
        else:
            txt = "  Nenhum orador inscrito"
        self.lbl_lista.config(text=txt)

    def _status(self, msg):
        self.lbl_status.config(text=msg)

    def _poll(self):
        self._refresh()
        self.after(500, self._poll)


# ══════════════════════════════════════════════════════════════════════════════
#  PAINEL PÚBLICO
# ══════════════════════════════════════════════════════════════════════════════

class Painel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Painel — Lista de Oradores MiniONU")
        self.configure(bg=BG)
        self.attributes("-fullscreen", True)
        self._fullscreen  = True
        self._ultimo_ts   = 0.0
        self._blink_on    = True
        self._logo_img    = None   # referência PhotoImage (evita GC)
        self._logo_path   = None   # caminho carregado atualmente
        self._build()
        self._poll()
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<F11>",    self._toggle_fs)

    def _toggle_fs(self, _=None):
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        self.grid_rowconfigure(0, weight=0)  # cabeçalho
        self.grid_rowconfigure(1, weight=0)  # tópico
        self.grid_rowconfigure(2, weight=2)  # orador + timer
        self.grid_rowconfigure(3, weight=0)  # separador
        self.grid_rowconfigure(4, weight=1)  # fila
        self.grid_rowconfigure(5, weight=0)  # rodapé
        self.grid_columnconfigure(0, weight=1)

        # ── Cabeçalho ──────────────────────────────────────────────────────
        cab = tk.Frame(self, bg=AZUL_ESC, padx=30, pady=14)
        cab.grid(row=0, sticky="ew")

        # Logo (lado esquerdo, antes do nome do comitê)
        self.lbl_logo_p = tk.Label(cab, bg=AZUL_ESC)
        self.lbl_logo_p.pack(side="left", padx=(0, 14))

        self.lbl_comite_p = tk.Label(cab, text="", bg=AZUL_ESC, fg=AZUL,
                                      font=("Segoe UI", 18, "bold"))
        self.lbl_comite_p.pack(side="left")
        self.lbl_hora_p = tk.Label(cab, text="", bg=AZUL_ESC, fg=CINZA,
                                    font=("Segoe UI", 16))
        self.lbl_hora_p.pack(side="right")

        # ── Tópico ─────────────────────────────────────────────────────────
        top = tk.Frame(self, bg=DOURADO_ESC, padx=30, pady=10)
        top.grid(row=1, sticky="ew")
        tk.Label(top, text="TÓPICO EM DEBATE", bg=DOURADO_ESC, fg=DOURADO,
                 font=("Segoe UI", 10)).pack(anchor="w")
        self.lbl_topico_p = tk.Label(top, text="", bg=DOURADO_ESC, fg=BRANCO,
                                      font=("Segoe UI", 15, "bold"),
                                      wraplength=1200, justify="left")
        self.lbl_topico_p.pack(anchor="w")

        # ── Orador atual + timer ───────────────────────────────────────────
        centro = tk.Frame(self, bg=BG)
        centro.grid(row=2, sticky="nsew")
        centro.grid_columnconfigure(0, weight=3)
        centro.grid_columnconfigure(1, weight=1)
        centro.grid_rowconfigure(0, weight=1)

        # Orador
        orador_frame = tk.Frame(centro, bg=BG, padx=40)
        orador_frame.grid(row=0, column=0, sticky="nsew")
        orador_frame.grid_rowconfigure(0, weight=1)
        orador_frame.grid_rowconfigure(1, weight=2)
        orador_frame.grid_columnconfigure(0, weight=1)

        tk.Label(orador_frame, text="COM A PALAVRA", bg=BG, fg=CINZA,
                 font=("Segoe UI", 16)).grid(row=0, column=0, sticky="s", pady=(20,0))
        self.lbl_orador_p = tk.Label(orador_frame, text="—", bg=BG, fg=AZUL,
                                      font=("Segoe UI", 72, "bold"),
                                      wraplength=700)
        self.lbl_orador_p.grid(row=1, column=0, sticky="n", pady=(10,20))

        # Timer
        timer_frame = tk.Frame(centro, bg=BG2, padx=30)
        timer_frame.grid(row=0, column=1, sticky="nsew")
        timer_frame.grid_rowconfigure(0, weight=1)
        timer_frame.grid_rowconfigure(1, weight=2)
        timer_frame.grid_columnconfigure(0, weight=1)

        tk.Label(timer_frame, text="TEMPO", bg=BG2, fg=CINZA,
                 font=("Segoe UI", 14)).grid(row=0, column=0, sticky="s", pady=(20,0))
        self.lbl_timer_p = tk.Label(timer_frame, text="—:——", bg=BG2, fg=VERDE,
                                     font=("Segoe UI", 72, "bold"))
        self.lbl_timer_p.grid(row=1, column=0, sticky="n", pady=(10,0))

        self.barra_frame = tk.Frame(timer_frame, bg=CINZA2, height=10)
        self.barra_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0,20))
        self.barra_fill = tk.Frame(self.barra_frame, bg=VERDE, height=10)
        self.barra_fill.place(x=0, y=0, relheight=1, relwidth=1)

        # ── Separador ──────────────────────────────────────────────────────
        sep = tk.Frame(self, bg=BORDA, height=2)
        sep.grid(row=3, sticky="ew")

        # ── Fila ───────────────────────────────────────────────────────────
        fila_frame = tk.Frame(self, bg=BG2, padx=40, pady=16)
        fila_frame.grid(row=4, sticky="nsew")
        fila_frame.grid_columnconfigure(0, weight=1)

        tk.Label(fila_frame, text="PRÓXIMOS ORADORES", bg=BG2, fg=CINZA,
                 font=("Segoe UI", 13)).grid(row=0, column=0, sticky="w")

        self.fila_inner = tk.Frame(fila_frame, bg=BG2)
        self.fila_inner.grid(row=1, column=0, sticky="ew", pady=(8,0))
        self.fila_labels = []

        # ── Rodapé ─────────────────────────────────────────────────────────
        rod = tk.Frame(self, bg=BG, pady=8)
        rod.grid(row=5, sticky="ew")
        tk.Label(rod, text="ESC · sair    F11 · tela cheia",
                 bg=BG, fg=CINZA2, font=("Segoe UI", 10)).pack()

    # ── Poll ──────────────────────────────────────────────────────────────────
    def _poll(self):
        e = carregar()
        self.lbl_hora_p.config(text=time.strftime("%H:%M:%S"))
        self.lbl_comite_p.config(text=e.get("comite",""))
        font_t = e.get("font_topico", 15)
        self.lbl_topico_p.config(text=e.get("topico",""),
                                  font=("Segoe UI", font_t, "bold"))
        self._atualizar_logo_painel(e.get("logo_path"))

        # Orador
        orador = e.get("orador_atual")
        ts     = e.get("atualizado_em", 0.0)
        if ts != self._ultimo_ts:
            self._ultimo_ts = ts
            self._anim_orador(orador, 6)
        else:
            self.lbl_orador_p.config(
                text=orador if orador else "—",
                fg=AZUL if orador else CINZA)

        # Timer
        ativo    = e.get("timer_ativo", False)
        restante = tempo_restante(e)
        limite   = e.get("tempo_limite", TEMPO_PADRAO)

        if not ativo and e.get("timer_inicio") is None:
            self.lbl_timer_p.config(text=fmt_tempo(limite), fg=CINZA)
            self._set_barra(1.0, CINZA2)
        else:
            ratio = restante / limite if limite > 0 else 0
            if restante > limite * 0.4:
                cor = VERDE
            elif restante > 10:
                cor = LARANJA
            else:
                cor = VERMELHO
                # Pisca quando acabar
                if restante == 0:
                    self._blink_on = not self._blink_on
                    cor = VERMELHO if self._blink_on else BG2

            self.lbl_timer_p.config(text=fmt_tempo(restante), fg=cor)
            self._set_barra(max(0.0, ratio), cor)

        # Fila
        self._atualizar_fila(e.get("fila", []))

        self.after(500, self._poll)

    def _atualizar_logo_painel(self, path):
        """Carrega e exibe a logo no cabeçalho do painel. Recarrega só se o path mudou."""
        if path == self._logo_path:
            return
        self._logo_path = path
        if not path or not os.path.exists(path) or not PIL_OK:
            self._logo_img = None
            self.lbl_logo_p.config(image="", width=0)
            return
        try:
            img = Image.open(path)
            img.thumbnail((72, 72), Image.LANCZOS)
            self._logo_img = ImageTk.PhotoImage(img)
            self.lbl_logo_p.config(image=self._logo_img, width=72)
        except Exception:
            self._logo_img = None
            self.lbl_logo_p.config(image="", width=0)

    def _set_barra(self, ratio: float, cor: str):
        self.barra_fill.config(bg=cor)
        self.barra_fill.place(x=0, y=0, relheight=1, relwidth=ratio)

    def _atualizar_fila(self, fila: list):
        # Limpa labels antigos
        for lbl in self.fila_labels:
            lbl.destroy()
        self.fila_labels = []

        if not fila:
            lbl = tk.Label(self.fila_inner, text="Nenhum orador inscrito",
                            bg=BG2, fg=CINZA, font=("Segoe UI", 14))
            lbl.grid(row=0, column=0, sticky="w")
            self.fila_labels.append(lbl)
            return

        for col, (i, nome) in enumerate(zip(range(8), fila)):
            f = tk.Frame(self.fila_inner, bg=BG3, padx=14, pady=8)
            f.grid(row=0, column=col, padx=(0, 8), sticky="nsew")
            self.fila_inner.grid_columnconfigure(col, weight=1)
            num = tk.Label(f, text=str(i+1), bg=BG3, fg=CINZA,
                            font=("Segoe UI", 10, "bold"))
            num.pack(anchor="w")
            nm = tk.Label(f, text=nome, bg=BG3, fg=BRANCO,
                           font=("Segoe UI", 13, "bold"), wraplength=160)
            nm.pack(anchor="w")
            self.fila_labels += [f, num, nm]

    def _anim_orador(self, nome, n):
        if n <= 0:
            self.lbl_orador_p.config(
                text=nome if nome else "—",
                fg=AZUL if nome else CINZA)
            return
        self.lbl_orador_p.config(fg=DOURADO if n % 2 == 0 else BG)
        self.after(120, lambda: self._anim_orador(nome, n-1))


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--painel" in sys.argv:
        Painel().mainloop()
    else:
        Operador().mainloop()