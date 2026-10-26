class _Var:
    def __init__(self, master=None, value=None, **k): self.v = value if value is not None else ""
    def get(self): return self.v
    def set(self, v): self.v = v
    def trace_add(self, *a): pass
StringVar = BooleanVar = _Var
