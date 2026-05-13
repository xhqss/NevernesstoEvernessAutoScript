"""Code generator utility - adapted from Alas module/config/code_generator.py"""


class TabWrapper:
    def __init__(self, generator, prefix='', suffix='', newline=True):
        self.generator = generator
        self.prefix = prefix
        self.suffix = suffix
        self.newline = newline
        self.nested = False
    
    def __enter__(self):
        if not self.nested and self.prefix:
            self.generator.add(self.prefix, newline=self.newline)
        self.generator.tab_count += 1
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.generator.tab_count -= 1
        if self.suffix:
            self.generator.add(self.suffix)
    
    def set_nested(self, suffix=''):
        self.nested = True
        self.suffix += suffix


class CodeGenerator:
    """Utility for generating Python code with proper indentation."""
    
    def __init__(self):
        self.tab_count = 0
        self.lines = []
    
    def add(self, line, comment=False, newline=True):
        self.lines.append(self._line_with_tabs(line, comment=comment, newline=newline))
    
    def write(self, file):
        lines = ''.join(self.lines)
        with open(file, 'w', encoding='utf-8', newline='') as f:
            f.write(lines)
    
    def _line_with_tabs(self, line, comment=False, newline=True):
        if comment:
            line = '# ' + line
        out = '    ' * self.tab_count + line
        if newline:
            out += '\n'
        return out
    
    def tab(self):
        return TabWrapper(self)
    
    def Empty(self):
        self.add('')
