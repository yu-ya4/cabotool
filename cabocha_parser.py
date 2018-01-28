from functools import reduce
from operator import add
import CaboCha

class CaboChaParser():
    def __init__(self):
        self._cabocha = CaboCha.Parser('-f1')

    def parse(self, sentence):
        parse_res = self._cabocha.parseToString(sentence)
        return self.to_sen(parse_res)

    def to_sen(self, parse_res):
        return Sentence(parse_res)

class Sentence():
    def __init__(self, sen):
        '''
        Args:
            sen: str or list<Chunk>
        '''

        from_cnklist = isinstance(sen, list) and \
                       all(isinstance(s, Chunk) for s in sen)

        if from_cnklist:
            # Chunkのリストなら処理を省略
            cnks = sen
        else:
            lines = sen.split('\n')

            cnks = []
            cnkhdr, cnktoks, cnktids = None, None, None
            tid = 0

            while True:
                line = lines.pop(0).strip(' ')

                if line == 'EOS':
                    # 文末
                    if cnkhdr is not None:
                        cnks.append(Chunk(cnkhdr, cnktoks, cnktids))
                    break
                elif '\t' not in line:
                    # Chunkの始まり

                    if cnkhdr is not None:
                        cnks.append(Chunk(cnkhdr, cnktoks, cnktids))

                    cnkhdr = line
                    cnktoks = []
                    cnktids = []
                else:
                    # Token
                    cnktoks.append(line)
                    cnktids.append(tid)
                    tid += 1

        self.cnks = cnks
        self.toks = reduce(add,
                           map(lambda c: c.toks, self.cnks),
                           [])

    def get_cnk(self, cid):
        '''idでチャンクを検索する'''
        for cnk in self.cnks:
            if cnk.cid == cid:
                return cnk

    # 追加 tidを指定し，そのTokenの属するChunkのcidを返す
    def get_cnk_has_tok(self, tid):
        res = -1
        cnks = self.cnks
        for cnk in cnks:
            for tok in cnk.toks:
                if tok.tid == tid:
                    res = cnk.cid
                    break
        return res


    def breakup(self):
        '''センテンスを係り受け構造に従って分解する
        e.g. やはり俺の青春ラブコメはまちがっている ->
        [やはり - まちがっている,
         俺の - 青春ラブコメは - まちがっている]
        '''

        paths = []
        processed_cids = set()  # 処理済みのチャンクを記憶する

        for cnk in self.cnks:
            # チャンクが処理済みなら飛ばす
            if cnk.cid in processed_cids:
                continue

            # 始点のチャンクから係り受け関係を辿る
            path = self._follow_link(cnk)
            paths.append(Sentence(path))
            processed_cids |= set(map(lambda c: c.cid, path))

        return paths

    def _follow_link(self, cnk):
        '''始点のチャンクを受け取って係り受け関係を辿る'''
        res = []
        res.append(cnk)

        # 根に辿り着くまでリンクを辿って結果に放り込む
        processing_cnk = cnk
        while not processing_cnk.is_root():
            linked_cnk = self.get_cnk(processing_cnk.link)
            res.append(linked_cnk)
            processing_cnk = linked_cnk

        return res

    def __str__(self):
        return reduce(add,
                      map(str, self.cnks),
                      '')


class Chunk():
    def __init__(self, hdr, toks, tids):
        hdrdata = hdr.split(' ')
        if len(hdrdata) == 5:
            # CaboChaの指定フォーマット
            # ['*', '0', '2D', '0/2', '-0.465738']
            _, cid, link, headfunc, score = hdrdata
            self.cid = int(cid)
            self.link = int(link[:-1])  # 'nD'の'D'を取る
            head, func = headfunc.split('/')
            self.head = int(head)
            self.func = int(func)
            self.score = float(score)
        elif len(hdrdata) == 3:
            # オレオレ簡易フォーマット
            # ['*', '0', '2D']
            _, cid, link = hdrdata
            self.cid = int(cid)
            self.link = int(link[:-1])  # 'nD'の'D'を取る
            self.head = None
            self.func = None
            self.score = None

        self.toks = [Token(tok, tid) for tok, tid in zip(toks, tids)]

    def get_tok(self, tid):
        for tok in self.toks:
            if tok.tid == tid:
                return tok

    def is_root(self):
        return self.link == -1

    def __str__(self):
        return reduce(add,
                      map(str, self.toks),
                      '')

    def __eq__(self, other):
        # 前方一致
        return all(stok == otok for stok, otok in zip(self.toks, other.toks))


class Token():
    def __init__(self, tok, tid):
        def empty_to_None(x):
            return None if x == '*' else x

        self.tid = tid

        # '研究\t名詞,サ変接続,*,*,*,*,研究,ケンキュウ,ケンキュー'
        surface, feature = tok.split('\t')

        self.surface = surface

        feature = feature.split(',')

        # featureが少なければ数を合わせる
        while len(feature) < 9:
            feature.append('*')

        if len(feature) == 9:
            # * を None に変換
            self.feature = list(map(empty_to_None, feature))
        else:
            raise Exception('Invalid token feature')

        # ここからはマッチングに用いる属性

        # 表層が空ならワイルドカード
        self.is_wild = not bool(self.surface)
        if self.feature[0][-1] == '*':
            # 品詞の末尾に * が付いてたら抽出対象
            self.feature[0] = self.feature[0][:-1]
            self.is_slot = True
        else:
            self.is_slot = False

    @property
    def pos(self):
        '''品詞'''
        return self.feature[0]

    @property
    def detailed_pos(self):
        '''品詞細分類'''
        return self.feature[1:4]

    @property
    def katsuyou_kei(self):
        '''活用形'''
        return self.feature[4]

    @property
    def katsuyou_gata(self):
        '''活用型'''
        return self.feature[5]

    @property
    def dictform(self):
        '''辞書形'''
        return self.feature[6] if self.feature[6] else self.surface

    @property
    def read(self):
        '''読み'''
        return self.feature[7]

    @property
    def pron(self):
        '''発音'''
        return self.feature[8]

    def __eq__(self, other):
        '''
        一致判定．辞書形と品詞と品詞細分類で判定する．
        ワイルドカードの場合は，品詞と細分類で判定
        '''
        same_dictform = (self.dictform == other.dictform)
        same_pos = (self.pos == other.pos)

        # 共にワイルドカードでない場合，辞書形をみる
        if not self.is_wild and not other.is_wild:
            if not same_dictform:
                return False

        # 品詞をみる
        if not same_pos:
            return False

        # 品詞細分類をみる
        for sp, op in zip(self.detailed_pos, other.detailed_pos):
            if sp is None or op is None:
                continue
            # 共にNoneでなければ一致判定
            if sp != op:
                return False

        return True

    def __str__(self):
        return self.surface if self.surface is not '' else ('[' + self.pos + ']')
