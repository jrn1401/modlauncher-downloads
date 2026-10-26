"""Attrappe von customtkinter: führt Konstruktoren und Callbacks aus, zeichnet aber nichts."""
class _W:
    def __init__(self, *a, **k):
        self._kw, self._text, self._children = dict(k), "", []
        if len(a) and isinstance(a[0], _W): a[0]._children.append(self)
    def __getattr__(self, name):
        if name.startswith("__"): raise AttributeError(name)
        return lambda *a, **k: self
    def get(self, *a): return self._text
    def insert(self, i, text): self._text += str(text)
    def delete(self, *a): self._text = ""
    def winfo_exists(self): return True
    def winfo_children(self): return list(self._children)
    def after(self, ms, fn=None, *a): return "id"
    def cget(self, k): return self._kw.get(k, "")
    def configure(self, **k): self._kw.update(k); return None
    def destroy(self): pass
class _Var:
    def __init__(self, value=None, **k): self.v = value if value is not None else ""
    def get(self): return self.v
    def set(self, v): self.v = v
    def trace_add(self, *a): pass
StringVar = BooleanVar = _Var
class ThemeManager: theme = {"CTkButton": {"fg_color": ["a","b"], "hover_color": ["a","b"]}}
def set_appearance_mode(m): print("  [stub] appearance_mode =", m)
def __getattr__(name):
    if name.startswith("CTk"): return type(name, (_W,), {})
    raise AttributeError(name)
