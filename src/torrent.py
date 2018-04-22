from . import abstract


class TorrentParser(abstract.AbstractParser):
    mimetypes = {'application/x-bittorrent', }
    whitelist = {b'announce', b'announce-list', b'info'}

    def get_meta(self) -> dict:
        metadata = {}
        with open(self.filename, 'rb') as f:
            d = _BencodeHandler().bdecode(f.read())
        if d is None:
            return {'Unknown meta': 'Unable to parse torrent file "%s".' % self.filename}
        for k,v in d.items():
            if k not in self.whitelist:
                metadata[k.decode('utf-8')] = v
        return metadata


    def remove_all(self) -> bool:
        cleaned = dict()
        with open(self.filename, 'rb') as f:
            d = _BencodeHandler().bdecode(f.read())
        if d is None:
            return False
        for k,v in d.items():
            if k in self.whitelist:
                cleaned[k] = v
        with open(self.output_filename, 'wb') as f:
            f.write(_BencodeHandler().bencode(cleaned))
        return True


class _BencodeHandler(object):
    """
    Since bencode isn't that hard to parse,
    MAT2 comes with its own parser, based on the spec
    https://wiki.theory.org/index.php/BitTorrentSpecification#Bencoding
    """
    def __init__(self):
        self.__decode_func = {
                    ord('d'): self.__decode_dict,
                    ord('i'): self.__decode_int,
                    ord('l'): self.__decode_list,
            }
        for i in range(0, 10):
            self.__decode_func[ord(str(i))] = self.__decode_string

        self.__encode_func = {
                bytes: self.__encode_string,
                dict: self.__encode_dict,
                int: self.__encode_int,
                list: self.__encode_list,
        }

    def __decode_int(self, s:str) -> (int, str):
        s = s[1:]
        next_idx = s.index(b'e')
        if s.startswith(b'-0'):
            raise ValueError  # negative zero doesn't exist
        elif s.startswith(b'0') and next_idx != 1:
            raise ValueError  # no leading zero except for zero itself
        return int(s[:next_idx]), s[next_idx+1:]

    def __decode_string(self, s:str) -> (str, str):
        sep = s.index(b':')
        str_len = int(s[:sep])
        if str_len < 0:
            raise ValueError
        elif s[0] == b'0' and sep != 1:
            raise ValueError
        s = s[1:]
        return s[sep:sep+str_len], s[sep+str_len:]

    def __decode_list(self, s:str) -> (list, str):
        r = list()
        s = s[1:]  # skip leading `l`
        while s[0] != ord('e'):
            v, s = self.__decode_func[s[0]](s)
            r.append(v)
        return r, s[1:]

    def __decode_dict(self, s:str) -> (dict, str):
        r = dict()
        s = s[1:]  # skip leading `d`
        while s[0] != ord(b'e'):
            k, s = self.__decode_string(s)
            r[k], s = self.__decode_func[s[0]](s)
        return r, s[1:]

    @staticmethod
    def __encode_int(x:str) -> bytes:
        return b'i' + bytes(str(x), 'utf-8') + b'e'

    @staticmethod
    def __encode_string(x:str) -> bytes:
        return bytes((str(len(x))), 'utf-8') + b':' + x

    def __encode_list(self, x:str) -> bytes:
        ret = b''
        for i in x:
            ret += self.__encode_func[type(i)](i)
        return b'l' + ret + b'e'

    def __encode_dict(self, x:str) -> bytes:
        ret = b''
        for k, v in sorted(x.items()):
            ret += self.__encode_func[type(k)](k)
            ret += self.__encode_func[type(v)](v)
        return b'd' + ret + b'e'

    def bencode(self, s:str) -> bytes:
        return self.__encode_func[type(s)](s)

    def bdecode(self, s:str):
        try:
            r, l = self.__decode_func[s[0]](s)
        except (IndexError, KeyError, ValueError) as e:
            print("not a valid bencoded string: %s" % e)
            return None
        if l != b'':
            print("invalid bencoded value (data after valid prefix)")
            return None
        return r