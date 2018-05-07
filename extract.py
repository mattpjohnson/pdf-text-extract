import os
import sys

NEWLINE = os.linesep

''' Class to represent PDF text stream object '''
class Glyph(object):
    def __init__(self):
        self.id   = None
        self.font = None
        self.text = ''
    def __str__(self):
        val = 'Font: %s\n' % self.get_font()
        val += 'Text: %s\n' % self.get_text()
        return val
    def add_text(self, text):
        self.text += Glyph.un_escape(text)
    def get_text(self):
        return self.text
    def set_font(self, font):
        self.font = font
    def get_font(self):
        return self.font
    def set_id(self, id):
        self.id = id
    def get_id(self):
        return self.id
    @staticmethod
    def un_escape(string):
        fixed = ''
        i = 0
        while i < len(string):
            if string[i] == '\\':
                val = string[i:i+2]
                unescaped = eval('"%s"' % val)
                fixed += unescaped
                # Increment to skip next/escaped char
                i += 2
            else:
                fixed += string[i]
            i += 1
        return fixed
    def load(self, obj):
        start = obj.index('BT\n')
        end = obj.index('\nET')
        text = obj[start:end]
        for line in text.split('\n'):
            if line.strip().endswith('Tj'):
                text = line[2:-3]
                self.add_text(text)
            elif line.strip().endswith('Tf'):
                font = line.split()[1]
                self.set_font(font)


class Font(object):
    def __init__(self):
        self.id = None
        self.char_map = []
    def set_id(self, id):
        self.id = id
    def get_id(self):
        return self.id
    def add_char(self, char):
        # Convert hex to string
        char = chr(int(char, 16))
        self.char_map.append(char)
    def load(self, obj):
        start = obj.index('beginbfrange')
        end = obj.index('endbfrange')
        bfrange = obj[start:end]

        start = obj.index('[')+1
        end = obj.index(']')-1
        cmap = obj[start:end]

        # Skip first element. What's it for? To enable natural-number indexing?
        for m in cmap.lstrip().split('\n')[1:]:
            if m.strip() == '':
                continue
            self.add_char(m.strip(' <>'))
    def translate(self, string):
        text = ''
        for char in string:
            index = ord(char)-1
            if index >= 0:
                text += self.char_map[index]
        return text


class PDFParser(object):
    def __init__(self, pdf):
        self.filename = pdf
        self.pdf = open(pdf, 'rb')
        # Find the location of the PDf's cross-reference table to use to lookup opjects
        self.set_xref_loc()
        self.reset_buffer()
        # Skip to first object
        self.goto_next_obj()
    def __del__(self):
        self.pdf.close()
    def set_xref_loc(self):
        currpos = self.pdf.tell()
        # Seek end of document
        self.pdf.seek(-1, 2)
        # The data we've "unread" (read backwards)
        unread = ''
        while True:
            unread = self.pdf.read(1) + unread
            if unread.startswith('startxref'):
                break
            self.pdf.seek(-2, 1)
        self.reset_buffer()
        # Skip startxref line
        self.readline()
        self.xrefloc = int(self.readline())
        # Reset to where we were
        self.pdf.seek(currpos)
        self.reset_buffer()
    def reset_buffer(self):
        self.buffer = self.pdf.readline()
    def goto_next_obj(self):
        while not self.peekline().strip().endswith(' obj'):
            self.readline()
    def read(self, nbytes):
        while len(self.buffer) < nbytes:
            l = self.readline()
            if l is not None:
                self.buffer += l
            else:
                val = self.buffer
                self.buffer = ''
                return val
        val = self.buffer[:nbytes]
        self.buffer = self.buffer[nbytes:]
        if NEWLINE not in self.buffer:
            self.buffer += self.pdf.readline()
        return val
    def readline(self):
        if NEWLINE not in self.buffer:
            val = self.buffer
            self.buffer = ''
            return self.buffer
        idx = self.buffer.index(NEWLINE)+1
        line = self.buffer[:idx]
        self.buffer = self.buffer[idx:]
        if NEWLINE not in self.buffer:
            self.buffer += self.pdf.readline()
        return line
    def peek(self, nbytes):
        return self.buffer[:nbytes]
    def peekline(self):
        if not NEWLINE in self.buffer:
            return self.buffer
        idx = self.buffer.index(NEWLINE)+1
        return self.buffer[:idx]
    def readobj(self):
        dict = self.readdict()
        # Skip endobj declaration
        line = self.readline()
        while line.strip() != 'endobj':
            line = self.readline()
        return dict
    def getobj(self, id):
        currpos = self.pdf.tell()
        self.pdf.seek(self.xrefloc)
        self.reset_buffer()
        # Skip first 2 records, not used
        self.readline()
        self.readline()
        for i in range(int(id)):
            self.readline()
        line = self.readline()
        offset = int(line.split()[0])
        self.pdf.seek(offset)
        self.reset_buffer()

        obj = ''
        while line.strip() != 'endobj':
            obj += line
            line = self.readline()

        self.pdf.seek(currpos)
        self.reset_buffer()
        return obj
    def readdict(self):
        bytes = [None, None]
        key = ''
        pos = 0
        while bytes != ['<','<']:
            char = self.read(1)
            key += char
            bytes[pos] = char
            # Alternate between the 2 bytes being used
            pos = (pos+1) % 2
        # Remove "<<" from the key
        key = key[:-2].strip()
        value = ''
        pos = 0
        # Count of open dict (<<) items found
        # When this becomes 0, the dictionary is read
        n = 1
        while n > 0:
            char = self.read(1)
            value += char
            bytes[pos] = char
            pos = (pos+1) % 2
            if bytes == ['<', '<']:
                n += 1
            elif bytes == ['>', '>']:
                n -= 1
        value = value[:-2].strip()
        return key, value


if __name__ == '__main__':
    pdf = PDFParser(sys.argv[1])
    glyphs = []

    while True:
        line = pdf.readline()

        # EOF check
        if not line:
            break

        if line.strip() == 'BT':
            text = ''
            while line.strip() != 'ET':
                text += line

            text += line
            glyph = Glyph()
            glyph.load(text)
            glyphs.append(glyph)


            font = Font()
            font.load(pdf.getobj(glyph.font))
            print font.translate(glyph.text)
